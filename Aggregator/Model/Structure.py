from dataclasses import dataclass
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import  relationship

from Aggregator.DataBase.db.Base import Base

class StructureDB(Base): #модель для работы с БД
    __tablename__ = 'structure'
    id = Column(Integer, primary_key=True)
    name = Column(String(500), nullable=False)
    type = Column(String(50), nullable=False)
    abbreviation = Column(String(100))
    parent_id = Column(Integer, ForeignKey('structure.id'))

    #рекурсивная связь
    parent = relationship('StructureDB', remote_side=[id], backref='children')
    news = relationship("NewsStructureDB", back_populates="structure", cascade="all, delete-orphan")


@dataclass
class Structure:
    id: int
    name: str
    type: str
    abbreviation: Optional[str] = None
    parent_id: Optional[int] = None
    parent: Optional['Structure'] = None
    children: list['Structure'] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []

    @classmethod
    def from_db(cls, db_structure: StructureDB):
        return cls(
            id=db_structure.id,
            name=db_structure.name,
            type=db_structure.type,
            abbreviation=db_structure.abbreviation,
            parent_id=db_structure.parent_id
        )

@dataclass
class ExtractedStructure:
    url: str = ''  # URL новости
    institute: list[str] = None  # первый уровень иерархии
    faculty: list[str] = None  # второй уровень иерархии
    department: list[str] = None  # третий уровень иерархии

    def __post_init__(self):
        if self.institute is None:
            self.institute = []
        if self.faculty is None:
            self.faculty = []
        if self.department is None:
            self.department = []

    def has_structures(self) -> bool: #проверка на наличие структур
        return bool(self.institute or self.faculty or self.department)

class StructureSchema(BaseModel): #pydantic-схема модели структурного подразделения
    id: int
    name: str
    type: str
    abbreviation: Optional[str] = None
    parent_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

class StructureTreeSchema(BaseModel): #вложенный список структур
    id: int
    name: str
    type: str
    abbreviation: Optional[str] = None
    parent_id: Optional[int] = None
    children: List["StructureTreeSchema"] = []# рекурсивная связь

    model_config = ConfigDict(from_attributes=True)