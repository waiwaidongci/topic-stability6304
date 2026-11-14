from sqlalchemy import select
from fastapi import HTTPException
from src.models import TopicRun,TopicProfile,EditorialNote
from src.constants.enums import RunStatus,NoteStatus,RunValidity
from src.utils.serialize import row
from .audit import record

def _view(note,run):
 data=row(note);quarantined=bool(note.quarantine_reason) or run is None or run.validity!=RunValidity.VALID
 data['exportable']=note.status==NoteStatus.APPROVED and not quarantined and run.status==RunStatus.SUCCEEDED
 data['quarantine_reason']=note.quarantine_reason or ('所依据的研究已隔离' if quarantined else '')
 data['superseded_by_note_id']=note.superseded_by_note_id
 if quarantined:
  # 旧词权随受污染说明停止对外提供；只保留可追溯的主题编号与结构。
  data['profile_snapshot']=[{'topic_index':p.get('topic_index'),'label':p.get('label'),'editor_note':'','weights':[],'mean_similarity':None} for p in (note.profile_snapshot or [])]
 return data

def list_notes(db):
 notes=list(db.scalars(select(EditorialNote).order_by(EditorialNote.id.desc())))
 runs={r.id:r for r in db.scalars(select(TopicRun))}
 return [_view(n,runs.get(n.run_id)) for n in notes]

def create_note(db,data,user):
 run=db.get(TopicRun,data.run_id)
 if not run or run.status!=RunStatus.SUCCEEDED or run.validity!=RunValidity.VALID:raise HTTPException(422,'请选择成功且未被撤回隔离的主题运行')
 valid=set(db.scalars(select(TopicProfile.id).where(TopicProfile.run_id==run.id)))
 if len(set(data.profile_ids))!=len(data.profile_ids) or not set(data.profile_ids)<=valid:raise HTTPException(422,'主题须来自本运行且不重复')
 snapshot=[row(p) for p in db.scalars(select(TopicProfile).where(TopicProfile.id.in_(data.profile_ids)).order_by(TopicProfile.topic_index))]
 obj=EditorialNote(**data.model_dump(),profile_snapshot=snapshot,creator_id=user.id);db.add(obj);db.commit();record(db,user.email,'editorial.created',{'note_id':obj.id});return _view(obj,run)

def approve_note(db,id,data,user):
 obj=db.get(EditorialNote,id)
 if not obj:raise HTTPException(404,'编辑说明不存在')
 if obj.quarantine_reason:raise HTTPException(409,'所依据的展签已撤回，该说明保持隔离，不能审阅')
 if obj.status!=NoteStatus.DRAFT:raise HTTPException(409,'仅草案可审阅')
 run=db.get(TopicRun,obj.run_id)
 if not run or run.validity!=RunValidity.VALID:raise HTTPException(409,'该说明所依据的研究已隔离，不能审阅')
 obj.status=data.status;obj.review_note=data.review_note;db.commit();record(db,user.email,'editorial.reviewed',{'note_id':id,'status':obj.status});return _view(obj,run)
