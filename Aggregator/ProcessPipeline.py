import time
from datetime import datetime, timezone, timedelta

from sqlalchemy import text

from Aggregator.Controllers.NewsIngestionService import NewsIngestionService
from Aggregator.Controllers.SourceController import SourceController
from Aggregator.Controllers.StructureController import StructureController
from Aggregator.DataBase.db.DbConnection import DBConnection
from Aggregator.Settings import settings
from Aggregator.DataParser.tg.ParserTG import ParserTG
from Aggregator.DataParser.vk.ParserVK import ParserVK
from Aggregator.DataParser.web.ParserWeb import ParserWeb
from Aggregator.Model.Post import Post
from Aggregator.Preprocessor.classification.ClassificationFilter import ClassificationFilter
from Aggregator.Preprocessor.deduplication.DuplicateFilter import DuplicateFilter
from Aggregator.Preprocessor.processor.TextCleaner import TextCleaner
from Aggregator.Preprocessor.structure.StructureExtractor import StructureExtractor

class ProcessPipeline:
    def __init__(self, logger):
        self._logger = logger
        self._web_parser = ParserWeb()
        self._vk_parser = ParserVK()
        self._tg_parser = ParserTG()
        self._db = DBConnection()
        self._structure_controller = StructureController(self._db)
        self._news_controller = NewsIngestionService(self._db, self._structure_controller, logger)
        self._source_controller = SourceController(self._db, logger)
        self._cleaner = TextCleaner(logger)
        self._classifier = ClassificationFilter(logger)
        self._deduplicator = DuplicateFilter(logger)
        self._structure_extractor = StructureExtractor(logger)

    def run(self, interval_minutes=60):
        while True:
            try:
                new_posts = self._parse_sources()
                if not new_posts:
                    self._logger.info("Новых постов в источниках не найдено")
                else:
                    self._cleaner.clean_text_posts(new_posts) #предобработка текстов
                    new_posts = self._classifier.classify_posts_service(new_posts) #бинарная классификация
                    new_posts = [p for p in new_posts if p.is_news == 1]

                    self._logger.info(f"После классификации: {len(new_posts)} новостей")
                    if not new_posts:
                        self._logger.info("Ни один из новых постов не прошел фильтр новостей")
                    else:
                        db_posts = self._news_controller.get_week_posts_for_dedup()  #новости из БД за посл неделю
                        self._cleaner.clean_text_posts(db_posts) #предобработка текстов из БД

                        unique_posts = self._deduplicator.deduplicate_service(new_posts=new_posts,db_posts=db_posts) #дедупликация
                        self._logger.info(f"После дедупликации осталось: {len(unique_posts)}")
                        if not unique_posts:
                            self._logger.info("Все новые новости являются дубликатами")
                        else:
                            posts = self._structure_extractor.extract_structures_service(unique_posts) #извлечение подразделений
                            success = self._news_controller.add_news_from_posts(posts) #добавление в БД
                            if success:
                                self._refresh_search_dictionary()  # обновление словаря
                                self._logger.info("Пайплайн завершен: новости сохранены")
            except Exception as e:
                self._logger.error(f"Ошибка в цикле пайплайна: {e}", exc_info=True)
            self._logger.info(f"Ожидание {interval_minutes} минут до следующего запуска")
            time.sleep(interval_minutes * 60)

    def _refresh_search_dictionary(self):
        session = self._db.get_session()
        try:
            session.execute(text("REFRESH MATERIALIZED VIEW news_dictionary"))
            session.commit()
            self._logger.info("Словарь терминов обновлен")
        except Exception as e:
            session.rollback()
            self._logger.error(f"Ошибка обновления словаря поиска: {e}")
        finally:
            session.close()

    def _parse_sources(self) -> list['Post']:
        self._logger.info("Начат парсинг новостей по источникам")
        active_sources = self._source_controller.get_all_sources(only_active=True)
        posts = []

        for source in active_sources:
            target_dt = source.last_parse
            if not target_dt:
                target_dt = datetime.strptime(settings.common.LAST_DATE, settings.common.DATE_FORMAT) #дата, до которой нужно парсить
                target_dt = target_dt.replace(tzinfo=timezone(timedelta(hours=3)))
            self._logger.info(f"Парсинг {source.code} ({source.type}) с даты: {target_dt}")
            try:
                if source.type == 'tg':
                    self._tg_parser.parse_service(source.group_name, target_dt)
                    source_posts = self._tg_parser.data

                elif source.type == 'vk':
                    self._vk_parser.parse_service(source.group_name, target_dt, source_code=source.code)
                    source_posts = self._vk_parser.data

                elif source.type == 'web':
                    self._web_parser.parse_service(target_dt)
                    source_posts = self._web_parser.data
                else:
                    self._logger.warning(f"Неизвестный источник: {source.type}")
                    continue

                if source_posts: #обновление даты последнего парсинга
                    latest_post_date_str = source_posts[0].date
                    new_last_parse = datetime.strptime(latest_post_date_str, settings.common.DATE_FORMAT)
                    posts.extend(source_posts)
                else: #если постов за период нет, тогда в бд последняя дата - настоящее время
                    new_last_parse = datetime.now(timezone(timedelta(hours=3)))

                self._source_controller.update_last_parse(source.code, new_last_parse) #обновляем дату
                self._logger.info(f"Источник {source.code} обработан. Найдено: {len(source_posts)}")

            except Exception as e:
                self._logger.error(f"Ошибка при парсинге {source.code}: {e}")

        self._logger.info(f"Парсинг завершен. Всего новых постов собрано: {len(posts)}")
        return posts