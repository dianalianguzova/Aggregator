from datetime import datetime, timezone, timedelta
from typing import Optional
from Aggregator.Logger.Logger import get_logger
from Aggregator.Settings import settings


class Parser:
    def __init__(self, source: str):
        self._source = source #источник - сайт, вк или телеграм
        self._data = []
        self._logger = get_logger(self.__class__.__name__)
        self.target_date: Optional[datetime] = None

    @property
    def data(self) -> list:
        return self._data.copy()

    def _is_target_date_reached(self, date_str: str) -> bool:
        if not self.target_date:
            return False
        try:
            naive_date = datetime.strptime(date_str, settings.common.DATE_FORMAT)
            msk_tz = timezone(timedelta(hours=3)) #  часовой пояс (МСК = UTC+3)
            news_date = naive_date.replace(tzinfo=msk_tz)
            return news_date <= self.target_date
        except Exception as e:
            self._logger.warning(f"Ошибка сравнения даты {date_str} с целевой датой {self.target_date}: {e}")
            return False
