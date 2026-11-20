from fastapi import APIRouter,Depends
from ..config.database import get_db
from ..schemas.renumber import RenumberInput
from ..services.auth import current_user,writer
from ..services.renumber import list_renumbers,get_renumber,create_renumber
router=APIRouter(prefix='/renumbers')
@router.get('')
def listing(db=Depends(get_db),user=Depends(current_user)):return list_renumbers(db)
@router.get('/{ident}')
def detail(ident:int,db=Depends(get_db),user=Depends(current_user)):return get_renumber(db,ident)
@router.post('')
def create(data:RenumberInput,db=Depends(get_db),user=Depends(writer)):return create_renumber(db,data)
