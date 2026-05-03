import requests
from Aggregator.Settings import settings
from Aggregator.Logger.Logger import get_logger

class WebSession:
    def __init__(self, logger = None):
        self._logger = logger or get_logger(self.__class__.__name__)
        self._session = None

    def setup_session(self) -> requests.Session:
        try:
            self._logger.info("Начата инициализация сессии requests")
            self._session = requests.Session()
            self._session.headers.update({
                'User-Agent': settings.web.USER_AGENT
            })
            return self._session
        except Exception as e:
            self._logger.error(f"Ошибка настройки сессии: {e}")
            raise