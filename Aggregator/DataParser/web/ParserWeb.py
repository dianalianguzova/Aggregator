from datetime import datetime
from Aggregator.DataManager.MediaManager import MediaManager
from Aggregator.Logger.Logger import get_logger
from Aggregator.Model.Post import Post
from Aggregator.Settings import settings
from Aggregator.DataParser.parser.Parser import Parser
from Aggregator.DataParser.web.WebSession import WebSession
from Aggregator.DataParser.web.WebHandler import WebHandler
from bs4 import BeautifulSoup

class ParserWeb(Parser):
    def __init__(self):
        super().__init__(settings.web.SOURCE)
        self._news_url = settings.web.NEWS_URL  # url страницы с новостями
        self._logger = get_logger(self.__class__.__name__)
        self._session_manager = WebSession(self._logger)
        self._media_manager = MediaManager()
        self._period_reached = False # флаг достижения целевой даты
        self._session = None  # сессия для http-запросов

    def parse_service(self, last_parse: datetime):
        self.target_date = last_parse
        self._run_parsing()

    def parse_dataset(self):
        self.target_date = settings.common.LAST_DATE
        self._run_parsing()

    def _run_parsing(self):
        self._data = []
        try:
            self._session = self._session_manager.setup_session()
            page = 1
            while not self._period_reached:
                curr_url = f"{self._news_url}{settings.web.PAGINATION}{page}"  # url текущей страницы
                self._logger.info(f"Загрузка новостной страницы {page}: {curr_url}")

                response = self._session.get(curr_url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')  # парсинг html

                news_links = soup.select("a.item[href]")  # селектор для ссылок на новости
                news_urls = [settings.web.BASE_URL + link['href'] for link in news_links if link['href']]

                for i, news_url in enumerate(news_urls):
                    if self._period_reached:  # если достигнута целевая дата, то заканчиваем парсинг
                        break
                    post = self._parse_news_item(self._session, news_url, page)
                    if post:
                        self._data.append(post)
                    else:
                        break
                if self._period_reached:
                    self._logger.info(f"Прерывание после обработки страницы {page} - достигнута целевая дата")
                    break
                page += 1
        except Exception as e:
            self._logger.error(f"Ошибка последовательного парсинга: {e}")
        finally:
            if self._session:
                self._session.close()
        self._logger.info(f"Успешно получено новостей: {len(self._data)}")

    def _parse_news_item(self, session, news_url: str, page_num: int) -> Post | None:
        try:
            response = session.get(news_url)
            response.raise_for_status() # проверка успешности запроса
            soup = BeautifulSoup(response.text, 'html.parser')
            web_handler = WebHandler(soup, self._logger) # обработчик для извлечения данных

            date = web_handler.parse_date()
            if self._is_target_date_reached(date):
                self._period_reached = True #если целевая дата достигнута, то прекращаем парсинг
                return None

            title = web_handler.parse_title()
            text, links, image_url = web_handler.parse_content() # извлечение текста, ссылок и изображения
           # image_path = self._media_manager.generate_image_filename(date, ParserConfig.WebConfig.SOURCE) if image_url else ''
           # self._media_manager.save_media(news_url, image_url, image_path)

            post = Post(title=title, text=text, date=date,
                        source=settings.web.SOURCE, url=news_url,
                        image=image_url, image_path='', links=links, text_processed='',
                        institute=None, faculty=None, department=None)

            self._logger.info(f"Обработана новость {news_url} со страницы {page_num}")
            return post
        except Exception as e:
            self._logger.error(f"Ошибка парсинга новости {news_url} со страницы {page_num}: {e}")
            return None