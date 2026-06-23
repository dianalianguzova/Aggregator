from sqlalchemy import Column, BigInteger, ForeignKey
from sqlalchemy.orm import relationship
from Aggregator.DataBase.db.Base import Base

class NewsStructureDB(Base):
    __tablename__ = 'news_structure'
    news_structure_id = Column(BigInteger, primary_key=True, autoincrement=True)
    news_id = Column(BigInteger, ForeignKey('news.id', ondelete='CASCADE'), nullable=False)
    structure_id = Column(BigInteger, ForeignKey('structure.id', ondelete='CASCADE'), nullable=False)

    news = relationship("NewsDB", back_populates="structures")# связи
    structure = relationship("StructureDB", back_populates="news")
