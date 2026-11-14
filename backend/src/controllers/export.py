from fastapi import HTTPException
from src.models import EditorialNote,TopicProfile,TopicRun
from src.constants.enums import NoteStatus,RunStatus,RunValidity
from src.utils.csv_export import csv_response
def export_note(db,id):
 note=db.get(EditorialNote,id)
 if not note:raise HTTPException(404,'编辑说明不存在')
 if note.quarantine_reason:raise HTTPException(410,'所依据的展签已撤回，该说明停止对外提供')
 run=db.get(TopicRun,note.run_id)
 if not run:raise HTTPException(404,'主题运行不存在')
 if run.validity!=RunValidity.VALID or run.status==RunStatus.INVALIDATED:raise HTTPException(410,'该说明所依据的研究受撤回展签污染，已隔离，不能导出')
 if run.status!=RunStatus.SUCCEEDED:raise HTTPException(409,'研究尚未完成，暂不能导出')
 if note.status!=NoteStatus.APPROVED:raise HTTPException(403,'仅获批说明可导出')
 rows=[]
 if any(not p.get('weights') for p in note.profile_snapshot):raise HTTPException(410,'说明词权已停止对外提供，不能导出')
 for p in note.profile_snapshot:
  for word in p['weights'][:12]:rows.append([note.name,p['topic_index']+1,p['label'],p['editor_note'],word['term'],word['weight'],p['mean_similarity'],run.config['k'],run.config['repeats'],note.interpretation,note.next_step,note.review_note,'相对激活非后验概率；稳定性非语义真值'])
 return csv_response(f'editorial-{id}.csv',rows,['编辑说明','主题编号','人工主题名','命名备注','词','L1词权','平均对齐余弦','预选K','初始化重复','人工解释','下一步','审阅说明','边界'])
