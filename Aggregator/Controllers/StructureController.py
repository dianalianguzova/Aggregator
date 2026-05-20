from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import aliased

from Aggregator.DataBase.db.DbConnection import DBConnection
from Aggregator.Logger.Logger import get_logger
from Aggregator.Model.Structure import Structure, StructureDB, StructureSchema, StructureTreeSchema

class StructureController:
    def __init__(self, db_connection: DBConnection, logger = None):
        self.db = db_connection
        self._logger = logger or get_logger(self.__class__.__name__)

    def get_structure_tree(self) -> list[Structure]: #получение иерархии подразделений для фильтра
        session = self.db.get_session()
        try:
            db_structures = session.query(StructureDB).all()
            nodes = {s.id: Structure.from_db(s) for s in db_structures}
            tree = []

            for s_id, node in nodes.items():
                if node.parent_id is None:
                    tree.append(node)
                else:
                    parent = nodes.get(node.parent_id)
                    if parent:
                        if parent.children is None:
                            parent.children = []
                        parent.children.append(node)
            return tree
        finally:
            session.close()

    def get_all_structures(self) -> list[Structure]:
        session = self.db.get_session()
        try:
            db_structures = session.query(StructureDB).all()
            return [Structure.from_db(db_struct) for db_struct in db_structures] #преобразование ORM в модель
        except Exception as e:
            self.logger.error(f"Ошибка при получении структур из БД: {e}")
            return []
        finally:
            session.close()

    def get_all_child_ids(self, session, parent_id: int) -> list[int]: #рекурсивно находит детей родительской структуры
        # начальная точка (институт/факультет)
        hierarchy = session.query(StructureDB.id).filter(StructureDB.id == parent_id).cte(name="hierarchy", recursive=True)

        parent_alias = aliased(StructureDB)# находим детей рекурсивно
        hierarchy = hierarchy.union_all(session.query(parent_alias.id).join(hierarchy, parent_alias.parent_id == hierarchy.c.id))

        results = session.query(hierarchy).all() # возвращаем список всех id (корень + дети все)
        return [r[0] for r in results]



