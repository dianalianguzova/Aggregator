from datetime import timedelta, datetime, timezone

from sqlalchemy.orm import joinedload

from Aggregator.DataBase.db.DbConnection import DBConnection
from Aggregator.Logger.Logger import get_logger
from Aggregator.Model.News import NewsDB
from Aggregator.Model.NewsStructure import NewsStructureDB
from Aggregator.Model.Post import Post
from Aggregator.Model.Source import SourceDB
from Aggregator.Settings import Settings

class NewsIngestionService: #для работы с сохранением и извлечением данных из БД
    def __init__(self, db_connection: DBConnection, structure_controller, logger=None):
        self.db = db_connection
        self.structure_controller = structure_controller  # контроллер структур
        self._logger = logger or get_logger(self.__class__.__name__)

    def add_news_from_posts(self, posts: list[Post]) -> bool:  # сохранение постов в базу
        session = self.db.get_session()
        try:
            structures_cache = {s.name.lower(): s for s in self.structure_controller.get_all_structures()}  # кэш структур
            sources = {s.code: s.id for s in session.query(SourceDB).all()}  # получение справочника источников

            urls = [p.url for p in posts]  # сбор всех ссылок из пачки
            existing_urls = {u[0] for u in session.query(NewsDB.url).filter(NewsDB.url.in_(urls)).all()}  # поиск дубликатов в бд

            added_count = 0  # счетчик добавленных новостей
            for post in posts:
                if post.is_news != 1 or post.url in existing_urls:  # фильтрация не-новостей и дублей
                    continue

                source_id = sources.get(post.source)  # поиск id источника
                if not source_id:  # пропуск если источник не найден
                    self._logger.warning(f"Источник {post.source} не найден в бд")
                    continue

                news = NewsDB.from_post(post, source_id)  # конвертация во внутреннюю модель
                session.add(news)  # добавление в сессию
                session.flush()  # получение id новости без коммита
                added_count += 1  # инкремент счетчика

                found_names = set()  # сет для уникальных имен структур
                if post.institute: found_names.update(n.lower() for n in post.institute)  # сбор институтов
                if post.faculty: found_names.update(n.lower() for n in post.faculty)  # сбор факультетов
                if post.department: found_names.update(n.lower() for n in post.department)  # сбор кафедр

                for name in found_names:
                    struct = structures_cache.get(name)  # поиск структуры в кеше
                    if struct:
                        news_struct = NewsStructureDB(news_id=news.id, structure_id=struct.id)  # связь новости со структурой
                        session.add(news_struct)  # сохранение связи

            session.commit()
            self._logger.info(f"Успешно сохранено новых новостей: {added_count}")  # лог успеха
            return True
        except Exception as e:
            session.rollback()
            self._logger.error(f"Ошибка сохранения новостей в БД: {e}", exc_info=True)
            return False
        finally:
            session.close()

    def get_week_posts_for_dedup(self, days: int = 7) -> list[Post]:  # получение данных для проверки дублей
        session = self.db.get_session()
        try:
            threshold = datetime.now(timezone.utc) - timedelta(days=days)  # расчет временной границы
            db_news = session.query(NewsDB).options(joinedload(NewsDB.source)) \
                .filter(NewsDB.published_at >= threshold).all()  # загрузка новостей с источниками

            results = []
            for news in db_news:
                p = Post(
                    id=news.id,
                    title=news.title,
                    text=news.text,
                    date=news.published_at.strftime(Settings.common.DATE_FORMAT),
                    source=news.source.code if news.source else str(news.source_id),
                    url=news.url,
                    image=news.image or '',
                    image_path=news.image_path or '',
                    links=news.links or {}
                )
                results.append(p)

            self._logger.debug(f"Из БД извлечено {len(results)} постов для дедупликации")
            return results
        except Exception as e:
            self._logger.error(f"Ошибка получения постов для дедупликации: {e}")
            return []
        finally:
            session.close()
