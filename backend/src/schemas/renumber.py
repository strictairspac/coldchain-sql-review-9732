from pydantic import BaseModel,Field,model_validator
class Move(BaseModel):
    from_:int=Field(alias='from',gt=0,le=2147483647)
    to:int=Field(gt=0,le=2147483647)
class RenumberInput(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    idempotency_key:str=Field(min_length=8,max_length=64)
    moves:list[Move]=Field(min_length=1,max_length=50)
    @model_validator(mode='after')
    def check_moves(self):
        if any(m.from_==m.to for m in self.moves):raise ValueError('同一账单的新旧号码不能相同')
        sources=[m.from_ for m in self.moves];targets=[m.to for m in self.moves]
        if len(set(sources))!=len(sources):raise ValueError('同一账单在批次中只能调整一次')
        if len(set(targets))!=len(targets):raise ValueError('两个账单不能调入同一号码')
        return self
