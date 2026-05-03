from datetime import datetime

from sqlalchemy import func, text
from sqlalchemy.orm import joinedload, selectinload

from Aggregator.DataBase.db.DbConnection import DBConnection
from Aggregator.Logger.Logger import get_logger
from Aggregator.Model.News import NewsDB
from Aggregator.Model.NewsStructure import NewsStructureDB

class NewsService:
    def __init__(self, db_connection: DBConnection, structure_controller, logger=None):
        self.db = db_connection
        self.structure_controller = structure_controller
        self._logger = logger or get_logger(self.__class__.__name__)

    def get_news(self, session, page, page_size, q, source_id, structure_id, date_from, date_to, date_mode): # получение списка новостей
        query = self._build_news_query(session, q, source_id, structure_id, date_from, date_to, date_mode)
        total = query.with_entities(func.count(NewsDB.id)).scalar() # подсчет общего количества
        query = self._apply_eager_loading(query) # подгрузка связанных данных
        query = self._apply_ordering(query, q) # применение сортировки
        db_news = query.offset((page - 1) * page_size).limit(page_size).all() # выполнение пагинации
        return db_news, total

    def _apply_eager_loading(self, query): # оптимизация загрузки связей
        return query.options(
            joinedload(NewsDB.source), # загрузка источника
            selectinload(NewsDB.structures).joinedload(NewsStructureDB.structure) # загрузка вложенных структур
        )

    def _build_news_query(self, session, q, source_id, structure_id, date_from, date_to, date_mode): # конструктор фильтров
        query = session.query(NewsDB)

        if q and q.strip():
            words = q.strip().split()[:5]
            corrected_words = [] # список исправленных слов

            for w in words:
                result = session.execute(
                    text("SELECT word FROM news_dictionary ORDER BY word <-> :w LIMIT 1"), # поиск по триграммам
                    {"w": w}
                )
                suggested = result.scalar() # получаем подсказку
                corrected_words.append(suggested if suggested else w) # заменяем на подсказку

            ts_query_str = " & ".join(corrected_words) # формирование строки для tsquery
            query = query.filter(
                NewsDB.search_vector.op('@@')(func.to_tsquery('russian', ts_query_str)) # фильтр по вектору
            )

        if source_id: # фильтр по источникам
            query = query.filter(NewsDB.source_id.in_(source_id)) # фильтрация списка id

        if structure_id: # фильтр по подразделениям
            all_ids = set() # сет для всех id включая детей
            for sid in structure_id:
                all_ids.update(self.structure_controller.get_all_child_ids(session, sid)) # рекурсивный сбор id
            query = query.filter(
                NewsDB.structures.any(NewsStructureDB.structure_id.in_(all_ids)) # фильтр через связь any
            )

        query = self._filter_by_date(query, date_from, date_to, date_mode) # фильтр дат
        return query


    def _apply_ordering(self, query, q): # настройка сортировки
        if q and q.strip(): # если есть поиск
            return query.order_by(NewsDB.published_at.desc()) # сортируем по дате все равно
        return query.order_by(NewsDB.published_at.desc()) # стандартная сортировка по свежести


    def _filter_by_date(self, query, date_from, date_to, date_mode): # фильтрация по периоду
        if not date_from:
            return query
        try:
            df = datetime.fromisoformat(date_from) # парсинг начальной даты
            if date_mode == "single": # режим одного дня
                return query.filter(NewsDB.published_at.between(df, df.replace(hour=23, minute=59, second=59))) # диапазон дня

            query = query.filter(NewsDB.published_at >= df) # фильтр "от"
            if date_to: # если есть конечная дата
                dt = datetime.fromisoformat(date_to).replace(hour=23, minute=59, second=59) # парсинг конца дня
                query = query.filter(NewsDB.published_at <= dt) # фильтр "до"
        except (ValueError, TypeError) as e: # ошибка формата даты
            self._logger.warning(f"Неверный формат даты: {date_from}/{date_to} - {e}")
            pass
        return query
