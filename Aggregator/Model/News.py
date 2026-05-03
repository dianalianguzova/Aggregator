from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, DateTime, String, BigInteger, Integer, ForeignKey, JSON, ARRAY
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import relationship

from Aggregator.DataBase.db.Base import Base
from Aggregator.Settings import settings
from Aggregator.Model.Post import Post

class NewsDB(Base):  #модель для работы с БД
    __tablename__ = 'news'

    id = Column(BigInteger, primary_key=True)
    title = Column(String, nullable=False)
    text = Column(String, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=False)
    source_id = Column(Integer, ForeignKey('source.id'), nullable=False)
    url = Column(String, unique=True, nullable=False)
    image = Column(String)
    image_path = Column(String)
    links = Column(JSON, default={})
    search_vector = Column(TSVECTOR)

    #связи
    source = relationship("SourceDB", back_populates="news")
    structures = relationship("NewsStructureDB", back_populates="news", cascade="all, delete-orphan")


    @classmethod
    def from_post(cls, post: Post, source_id: int): # преобразование из Post в ORM модель
        date_format = settings.common.DATE_FORMAT
        return cls(
            title=post.title,
            text=post.text,
            published_at=datetime.strptime(post.date, date_format),
            source_id=source_id,
            url=post.url,
            image=post.image,
            image_path=post.image_path,
            links=post.links
        )

class NewsSchema(BaseModel): #pydantic-схема модели новости
    id: int
    title: str
    text: str
    published_at: datetime
    source_id: int
    url: str
    image: Optional[str] = None
    image_path: Optional[str] = None
    links: dict = {}
    model_config = ConfigDict(from_attributes=True)

class PaginatedNewsResponse(BaseModel):
    items: list[NewsSchema] #список новостей на странице
    total: int #общее кол-во новостей в БД
    page: int #номер страницы
    page_size: int #количество новостей на одной странице
    total_pages: int #сколько всего страниц