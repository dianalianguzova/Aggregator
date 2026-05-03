from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship

from Aggregator.DataBase.db.Base import Base
class SourceDB(Base):
    __tablename__ = 'source'

    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    type = Column(String(20), nullable=False)
    group_name = Column(String(100))
    is_active = Column(Boolean, default=True)
    last_parse = Column(DateTime(timezone=True))
    #связи
    news = relationship("NewsDB", back_populates="source")


class SourceSchema(BaseModel):
    id: int
    name: str
    type: str #для группировки по источнику, в котором может быть несколько групп

    model_config = ConfigDict(from_attributes=True)