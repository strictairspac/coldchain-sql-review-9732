from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy import String,JSON,DateTime,func
from datetime import datetime
from ..config.database import Base
class RenumberBatch(Base):
    __tablename__='renumber_batches'
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(120),unique=True)
    idempotency_key:Mapped[str]=mapped_column(String(64),unique=True)
    status:Mapped[str]=mapped_column(String(20))
    moves:Mapped[list]=mapped_column(JSON)
    created_at:Mapped[datetime]=mapped_column(DateTime,server_default=func.now())
