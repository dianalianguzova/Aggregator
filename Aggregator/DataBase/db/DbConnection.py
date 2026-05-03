from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from Aggregator.Settings import settings
from Aggregator.Logger.Logger import get_logger

class DBConnection:
    def __init__(self, logger=None):
        self._host = settings.db.host
        self._port = settings.db.port
        self._password = settings.db.password
        self._database_name = settings.db.database
        self._username = settings.db.username
        self._engine = None
        self._logger = logger or get_logger(self.__class__.__name__)
        self._create_engine()

    def _create_engine(self):
        try:
            db_url = f"postgresql://{self._username}:{self._password}@{self._host}:{self._port}/{self._database_name}"
            self._engine = create_engine(db_url)

            self._logger.info("Движок SQLAlchemy успешно создан")
        except Exception as e:
            self._logger.error(f"Ошибка создания движка SQLAlchemy: {e}")
            raise

    def get_session(self) -> Session: #создание сессии для работы с бд
        try:
            session = Session(bind=self._engine)
            self._logger.debug("Создана новая сессия БД")
            return session
        except Exception as e:
            self._logger.error(f"Ошибка при создании сессии БД: {e}")
            raise

    def close_connection(self):
        if self._engine:
            self._engine.dispose()
            self._logger.info("Соединение с БД закрыто")