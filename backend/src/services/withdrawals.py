import hashlib
from datetime import datetime,timezone
from sqlalchemy import select
from fastapi import HTTPException
from src.config.database import SessionLocal
from src.models import Corpus,DocumentWithdrawal,EditorialNote,TokenDocument,TopicRun
from src.constants.enums import RunStatus,RunValidity
from src.utils.serialize import row
from .audit import record
from .artifacts import quarantine

AFFECTED_STATUSES=(RunStatus.SUCCEEDED,RunStatus.QUEUED,RunStatus.RUNNING)

def _trace(w):
 return {'id':w.id,'corpus_id':w.corpus_id,'document_id':w.document_id,'reference':w.reference,'title':w.title,'reason':w.reason,'actor':w.actor,'content_sha256':w.content_sha256,'token_count':w.token_count,'corpus_revision':w.corpus_revision,'affected_run_ids':list(w.affected_run_ids or []),'replacement_run_ids':list(w.replacement_run_ids or []),'affected_note_ids':list(w.affected_note_ids or []),'created_at':row(w)['created_at']}

def list_withdrawals(db):
 return [_trace(w) for w in db.scalars(select(DocumentWithdrawal).order_by(DocumentWithdrawal.id.desc()))]

def get_withdrawal(db,id):
 w=db.get(DocumentWithdrawal,id)
 if not w:raise HTTPException(404,'撤回记录不存在')
 return _trace(w)

def _result(db,existing,created,message):
 return {'withdrawal':_trace(existing),'created':created,'affected_run_ids':list(existing.affected_run_ids or []),'replacement_run_ids':list(existing.replacement_run_ids or []),'affected_runs':_run_traces(db,existing.affected_run_ids or [],existing.replacement_run_ids or []),'message':message}

def _run_traces(db,old_ids,new_ids):
 traces=[]
 for old_id,new_id in zip(old_ids,new_ids):
  old=db.get(TopicRun,old_id);new=db.get(TopicRun,new_id)
  if not old:continue
  traces.append({'run_id':old.id,'name':old.name,'fingerprint':(old.result or {}).get('fingerprint'),'status':old.status,'validity':old.validity,'invalidated_at':row(old)['invalidated_at'],'replacement_run_id':new.id if new else None,'replacement_status':new.status if new else None})
 return traces

def withdraw_document(db,id,reason,user):
 doc=db.get(TokenDocument,id)
 if not doc:raise HTTPException(404,'分词文档不存在')
 existing=db.scalar(select(DocumentWithdrawal).where(DocumentWithdrawal.document_id==id))
 if existing:return _result(db,existing,False,'该展签已撤回；旧版研究保持隔离，未重复重算')
 corpus=db.scalar(select(Corpus).where(Corpus.id==doc.corpus_id).with_for_update())
 if not corpus:raise HTTPException(404,'语料不存在')
 # Corpus row lock serializes duplicate/concurrent withdrawals; re-check after lock.
 existing_id=db.scalar(select(DocumentWithdrawal.id).where(DocumentWithdrawal.document_id==id).with_for_update())
 if existing_id:
  db.rollback();return _result(db,db.get(DocumentWithdrawal,existing_id),False,'该展签已撤回；旧版研究保持隔离，未重复重算')
 new_revision=int(corpus.revision or 0)+1
 corpus.revision=new_revision
 runs=list(db.scalars(select(TopicRun).where(TopicRun.corpus_id==corpus.id).order_by(TopicRun.id).with_for_update()))
 affected=[r for r in runs if r.validity==RunValidity.VALID and r.status in AFFECTED_STATUSES and int(r.corpus_revision or 0)<new_revision]
 replacements={}
 notes=[]
 now=datetime.now(timezone.utc)
 for old in affected:
  old.status=RunStatus.INVALIDATED
  old.validity=RunValidity.CONTAMINATED
  old.invalidated_at=now
  old.invalidation_reason=f'展签 {doc.reference} 已撤回；该版不再对外提供'
  replacement=TopicRun(corpus_id=corpus.id,name=f'{old.name} · 重算替代',config=dict(old.config),status=RunStatus.QUEUED,result={},error=None,creator_id=old.creator_id,corpus_revision=new_revision,validity=RunValidity.VALID,supersedes_run_id=old.id)
  db.add(replacement);db.flush();replacements[old.id]=replacement.id
  notes.extend(db.scalars(select(EditorialNote).where(EditorialNote.run_id==old.id).with_for_update()))
 for note in notes:
  note.quarantine_reason=f'所依据的展签 {doc.reference} 已撤回，说明导出停止对外提供'
 texts=doc.tokens_text or ''
 withdrawal=DocumentWithdrawal(corpus_id=corpus.id,document_id=doc.id,reference=doc.reference,title=doc.title,reason=reason.strip(),actor=user.email,content_sha256=hashlib.sha256(texts.encode()).hexdigest(),token_count=len(texts.split()),corpus_revision=new_revision,affected_run_ids=[r.id for r in affected],replacement_run_ids=[replacements[r.id] for r in affected],affected_note_ids=[n.id for n in notes])
 db.add(withdrawal);db.commit()
 record(db,user.email,'corpus.withdrawal',{'withdrawal_id':withdrawal.id,'document_id':doc.id,'reference':doc.reference,'reason':withdrawal.reason,'affected_run_ids':withdrawal.affected_run_ids,'replacement_run_ids':withdrawal.replacement_run_ids})
 for old in affected:
  record(db,user.email,'topic.quarantined',{'run_id':old.id,'supersedes_run_id':None,'replacement_run_id':replacements[old.id],'reason':old.invalidation_reason})
  quarantine(old.id)
 for old_id,new_id in replacements.items():
  record(db,user.email,'topic.recompute.queued',{'run_id':new_id,'supersedes_run_id':old_id})
 _enqueue(replacements)
 return _result(db,withdrawal,True,'展签已撤回；受污染旧版已隔离，重算替代版待审阅')

def _enqueue(replacements):
 if not replacements:return
 from src.worker import analyze_run
 for old_id,new_id in replacements.items():
  try:analyze_run.delay(new_id)
  except Exception:
   with SessionLocal() as db:
    run=db.get(TopicRun,new_id)
    if run and run.status==RunStatus.QUEUED:
     run.status=RunStatus.FAILED;run.error='队列不可用，重算未提交';db.commit()
     record(db,'system','topic.recompute.queue_failed',{'run_id':new_id,'supersedes_run_id':old_id})
