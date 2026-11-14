from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.controllers.dependencies import current_user,writers
from src.schemas.withdrawal import WithdrawalInput
from src.services import withdrawals
router=APIRouter()
@router.get('/withdrawals')
def index(db:Session=Depends(get_db),user=Depends(current_user)):return withdrawals.list_withdrawals(db)
@router.get('/withdrawals/{id}')
def detail(id:int,db:Session=Depends(get_db),user=Depends(current_user)):return withdrawals.get_withdrawal(db,id)
@router.post('/documents/{id}/withdraw',status_code=201)
def withdraw(id:int,data:WithdrawalInput,db:Session=Depends(get_db),user=Depends(writers)):return withdrawals.withdraw_document(db,id,data.reason,user)
