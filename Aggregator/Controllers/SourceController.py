from datetime import datetime, timezone, timedelta
from http.client import HTTPException
from typing import Optional

from fastapi import APIRouter

from Aggregator.DataBase.db.DbConnection import DBConnection
from Aggregator.Logger.Logger import get_logger
from Aggregator.Model.Source import SourceDB, SourceSchema


class SourceController:
    def __init__(self, db_connection: DBConnection, logger=None):
        self.db = db_connection
        self._logger = logger or get_logger(self.__class__.__name__)
        self.router = APIRouter(prefix="/vyatsu.news/sources", tags=["Sources"])
        self._setup_routes()

    def _setup_routes(self):
        @self.router.get("/", response_model=list[SourceSchema]) #получение всех источников
        async def api_get_sources(active_only: bool = False):
            return self.get_all_sources(only_active=active_only)

    def get_all_sources(self, only_active: bool = False) -> list[SourceDB]:
        session = self.db.get_session()
        try:
            query = session.query(SourceDB)
            if only_active:
                query = query.filter(SourceDB.is_active == True)
            return query.all()
        finally:
            session.close()

    def update_last_parse(self, source_code: str, new_date=None): #метод для парсера: обновляет время последнего парсинга источника
        session = self.db.get_session()
        try:
            source = session.query(SourceDB).filter(SourceDB.code == source_code).first()
            if source:
                if new_date.tzinfo is None: #таймзона МСК
                    msk_tz = timezone(timedelta(hours=3))
                    new_date = new_date.replace(tzinfo=msk_tz)
                source.last_parse = new_date
                session.commit()
        finally:
            session.close()


    def get_source_by_code(self, code: str) -> Optional[SourceDB]:
        session = self.db.get_session()
        try:
            source = session.query(SourceDB).filter(SourceDB.code == code).first()
            if not source:
                self._logger.warning(f"Источник с кодом {code} не найден")
            return source
        except Exception as e:
            self._logger.error(f"Ошибка при поиске источника {code}: {e}")
            return None
        finally:
            session.close()

