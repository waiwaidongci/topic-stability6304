from sqlalchemy import select
from fastapi import HTTPException
from src.models import Corpus,TopicRun
from src.constants.enums import RunStatus,RunValidity
from src.utils.serialize import row
from .audit import record

def _replacement_map(db):
 mapping={}
 for r in db.scalars(select(TopicRun).where(TopicRun.supersedes_run_id.is_not(None)).order_by(TopicRun.id)):
  mapping[r.supersedes_run_id]=r.id
 return mapping

def _view(run,replacements):
 data=row(run);data['replacement_run_id']=replacements.get(run.id)
 data['exportable']=run.status==RunStatus.SUCCEEDED and run.validity==RunValidity.VALID
 if run.validity!=RunValidity.VALID:
  # 受污染旧版不提供词权、idf、文档激活等成果；仅保留指纹作为追溯。
  data['result']={'fingerprint':(run.result or {}).get('fingerprint'),'quarantined':True}
 return data

def list_runs(db):
 replacements=_replacement_map(db)
 return [_view(r,replacements) for r in db.scalars(select(TopicRun).order_by(TopicRun.id.desc()))]

def get_run(db,id):
 obj=db.get(TopicRun,id)
 if not obj:raise HTTPException(404,'主题运行不存在')
 return obj

def view_run(db,obj):return _view(obj,_replacement_map(db))

def create_run(db,data,user):
 corpus=db.scalar(select(Corpus).where(Corpus.id==data.corpus_id).with_for_update())
 if not corpus:raise HTTPException(404,'语料不存在')
 obj=TopicRun(corpus_id=data.corpus_id,name=data.name,config=data.model_dump(exclude={'name','corpus_id'}),creator_id=user.id,corpus_revision=int(corpus.revision or 0),validity=RunValidity.VALID);db.add(obj);db.commit()
 from src.worker import analyze_run
 try:analyze_run.delay(obj.id)
 except Exception:obj.status=RunStatus.FAILED;obj.error='队列不可用';db.commit();raise HTTPException(503,obj.error)
 record(db,user.email,'topic.queued',{'run_id':obj.id,'corpus_revision':obj.corpus_revision});return _view(obj,_replacement_map(db))
