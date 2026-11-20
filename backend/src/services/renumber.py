from sqlalchemy import select,text
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from ..models.renumber import RenumberBatch
def serialize(x,deduplicated=False):
    return {'id':x.id,'name':x.name,'idempotency_key':x.idempotency_key,'status':x.status,'moves':x.moves,'created_at':str(x.created_at),'deduplicated':deduplicated}
def list_renumbers(db):return [serialize(x) for x in db.scalars(select(RenumberBatch).order_by(RenumberBatch.id.desc()))]
def get_renumber(db,ident):
    x=db.get(RenumberBatch,ident)
    if not x:raise HTTPException(404,'调号批次不存在')
    return serialize(x)
def create_renumber(db,data):
    existing=db.scalar(select(RenumberBatch).where(RenumberBatch.idempotency_key==data.idempotency_key))
    if existing:return serialize(existing,deduplicated=True)
    if db.scalar(select(RenumberBatch).where(RenumberBatch.name==data.name)):raise HTTPException(409,'批次名称已存在')
    moves=[(m.from_,m.to) for m in data.moves]
    numbers=sorted({n for pair in moves for n in pair})
    for n in numbers:db.execute(text('SELECT pg_advisory_xact_lock(:k)'),{'k':n})
    present=set(db.scalars(text('SELECT invoice_id FROM invoices WHERE invoice_id = ANY(:ids)'),{'ids':numbers}))
    sources={f for f,_ in moves}
    detail=[];blocked=False
    for f,t in moves:
        if f not in present:detail.append({'from':f,'to':t,'state':'missing','note':'源号码不存在，可能已被其他批次调走'});blocked=True
        elif t in present and t not in sources:detail.append({'from':f,'to':t,'state':'conflict','note':'目标号被批外账单占用'});blocked=True
        else:detail.append({'from':f,'to':t,'state':'pending','note':''})
    if blocked:
        for d in detail:
            if d['state']=='pending':d['state']='skipped';d['note']='整批退回，未生效'
        status='rejected'
    else:
        db.execute(text('UPDATE invoices SET invoice_id=-invoice_id WHERE invoice_id = ANY(:ids)'),{'ids':list(sources)})
        for f,t in moves:db.execute(text('UPDATE invoices SET invoice_id=:t WHERE invoice_id=:tmp'),{'t':t,'tmp':-f})
        for d in detail:d['state']='applied';d['note']='已生效'
        status='applied'
    obj=RenumberBatch(name=data.name,idempotency_key=data.idempotency_key,status=status,moves=detail)
    db.add(obj)
    try:db.commit()
    except IntegrityError:
        db.rollback()
        again=db.scalar(select(RenumberBatch).where(RenumberBatch.idempotency_key==data.idempotency_key))
        if again:return serialize(again,deduplicated=True)
        raise
    return serialize(obj)
