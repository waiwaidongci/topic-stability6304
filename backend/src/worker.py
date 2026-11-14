import json
from pathlib import Path
from sqlalchemy import select
from celery import Celery
from src.config.database import SessionLocal
from src.config.settings import REDIS_URL,ARTIFACT_DIR
from src.models import TopicRun,Corpus,TopicProfile
from src.constants.enums import RunStatus,RunValidity
from src.services.corpora import list_documents
from src.services.analysis import analyze
from src.services.audit import record
from src.utils.serialize import row
app=Celery('topic_stability',broker=REDIS_URL,backend=REDIS_URL)
app.conf.update(task_track_started=True,worker_prefetch_multiplier=1,task_acks_late=True)

def _current(db,id,lock=False):
 q=select(TopicRun).where(TopicRun.id==id)
 if lock:q=q.with_for_update()
 return db.scalar(q)

def _finish_invalidated(db,run,stage):
 record(db,'worker','topic.discarded',{'run_id':run.id,'stage':stage,'status':run.status,'validity':run.validity,'reason':'展签撤回后隔离；晚到结果不得恢复有效状态'})

@app.task(name='topic.analyze',soft_time_limit=240,time_limit=270)
def analyze_run(id):
 with SessionLocal() as db:
  run=_current(db,id,lock=True)
  if not run or run.status in (RunStatus.SUCCEEDED,RunStatus.INVALIDATED):return
  if run.validity!=RunValidity.VALID:
   _finish_invalidated(db,run,'start');return
  run.status=RunStatus.RUNNING;db.commit()
  try:
   result=analyze(row(db.get(Corpus,run.corpus_id)),list_documents(db,run.corpus_id),run.config)
   # Fence: hold the run row while committing. A withdrawal may have arrived
   # during the fit; its transaction must win, and this late result is discarded.
   db.rollback()
   run=_current(db,id,lock=True)
   if not run or run.status!=RunStatus.RUNNING or run.validity!=RunValidity.VALID:
    if run:_finish_invalidated(db,run,'finish');db.commit()
    return
   corpus=db.get(Corpus,run.corpus_id)
   if corpus and int(run.corpus_revision or 0)!=int(corpus.revision or 0):
    run.status=RunStatus.INVALIDATED;run.validity=RunValidity.CONTAMINATED;run.invalidation_reason=run.invalidation_reason or '语料在计算期间发生撤回修订；晚到结果不采用'
    _finish_invalidated(db,run,'revision');db.commit();return
   for p in result['profiles']:
    if not db.scalar(select(TopicProfile).where(TopicProfile.run_id==id,TopicProfile.topic_index==p['topic_index'])):db.add(TopicProfile(run_id=id,topic_index=p['topic_index'],label=p['label'],weights=p['weights'],mean_similarity=p['mean_similarity']))
   Path(ARTIFACT_DIR).mkdir(parents=True,exist_ok=True);Path(ARTIFACT_DIR,f'topic-{id}.json').write_text(json.dumps(result,ensure_ascii=False,allow_nan=False));run.result=result;run.status=RunStatus.SUCCEEDED;run.error=None;db.commit();record(db,'worker','topic.succeeded',{'run_id':id,'repeats':run.config['repeats'],'corpus_revision':run.corpus_revision})
  except Exception as e:
   db.rollback();run=_current(db,id,lock=True)
   if not run:return
   if run.validity!=RunValidity.VALID or run.status==RunStatus.INVALIDATED:
    _finish_invalidated(db,run,'error');db.commit();return
   run.status=RunStatus.FAILED;run.error=str(e)[:1000];db.commit();record(db,'worker','topic.failed',{'run_id':id,'error':run.error})
