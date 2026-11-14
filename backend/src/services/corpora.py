from sqlalchemy import select,func
from fastapi import HTTPException
from src.models import Corpus,DocumentWithdrawal,TokenDocument
from src.utils.serialize import row
from .audit import record

def _active_document_ids():return select(DocumentWithdrawal.document_id)

def list_corpora(db):
 return [dict(row(c),document_count=db.scalar(select(func.count()).select_from(TokenDocument).where(TokenDocument.corpus_id==c.id,~TokenDocument.id.in_(_active_document_ids())))) for c in db.scalars(select(Corpus).order_by(Corpus.id))]

def list_documents(db,corpus_id=None,include_withdrawn=False):
 q=select(TokenDocument).order_by(TokenDocument.reference)
 if corpus_id is not None:q=q.where(TokenDocument.corpus_id==corpus_id)
 if not include_withdrawn:q=q.where(~TokenDocument.id.in_(_active_document_ids()))
 docs=list(db.scalars(q));withdrawn={w.document_id:w for w in db.scalars(select(DocumentWithdrawal))}
 result=[]
 for doc in docs:
  item=row(doc);w=withdrawn.get(doc.id)
  item['withdrawn']=bool(w)
  item['withdrawal_id']=w.id if w else None
  if w:
   # Withdrawn 展签原文不再对外提供；仅保留引用与追溯编号。
   item['tokens_text']=''
   item['title']=w.title
  result.append(item)
 return result

def create_corpus(db,data,user):
 if db.scalar(select(Corpus).where(Corpus.name==data.name)):raise HTTPException(409,'语料名称已存在')
 obj=Corpus(**data.model_dump(exclude={'documents'}));db.add(obj);db.flush();db.add_all([TokenDocument(corpus_id=obj.id,**d.model_dump()) for d in data.documents]);db.commit();record(db,user.email,'corpus.import',{'corpus_id':obj.id,'documents':len(data.documents)});return row(obj)

def patch_document(db,id,data,user):
 obj=db.get(TokenDocument,id)
 if not obj:raise HTTPException(404,'文档不存在')
 if db.scalar(select(DocumentWithdrawal).where(DocumentWithdrawal.document_id==id)):raise HTTPException(409,'该展签已撤回，原文不再接受修订或对外提供')
 obj.title=data.title;obj.tokens_text=data.tokens_text;db.commit();record(db,user.email,'document.edit',{'document_id':id});return row(obj)
