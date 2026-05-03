import time
from datetime import datetime
from Aggregator.Logger.Logger import get_logger
from Aggregator.Model.Post import Post
from Aggregator.Settings import settings
from Aggregator.DataParser.parser.Parser import Parser
import requests
from Aggregator.DataManager.MediaManager import MediaManager
from Aggregator.DataParser.vk.VKHandler import VKHandler

class ParserVK(Parser):
    def __init__(self):
        super().__init__(settings.vk.SOURCE)
        self._url = settings.vk.WALL_GET_URL
        self._period_reached = False
        self._groups = settings.vk.GROUPS
        self._logger = get_logger(self.__class__.__name__)
        self._vk_handler = VKHandler(self._logger)
        self._media_manager = MediaManager()
        self._offset = 1 #смещение, начинает парсинг с 1 записи (пропуск закрепленной)
        self._count = 100 #количество постов за один запрос

    def parse_service(self, domain: str, last_parse: datetime, source_code: str): #парсинг определенной группы для веба
        self._data = []
        self._offset = 1
        self.target_date = last_parse
        self._period_reached = False
        self._data = self._parse_group(domain, source=source_code)

    def parse_dataset(self): #парсинг списка групп для датасета
        self._data = []
        self.target_date = settings.common.LAST_DATE
        for domain, source_name in self._groups.items():
            self._period_reached = False
            self._offset = 1
            group_posts = self._parse_group(domain, source=source_name)
            self._data.extend(group_posts)

    def _parse_group(self, group: str, source: str) -> list[Post]:
        posts = []
        try:
            while not self._period_reached:
                response = requests.get(self._url,
                    params={
                        'access_token': settings.vk.token,
                        'v': settings.vk.API_VERSION,
                        'domain': group,
                        'count': self._count,
                        'offset': self._offset
                    }
                )

                if response.status_code != 200:
                    self._logger.error(f"Код HTTP {response.status_code} при парсинге {group}: {response.text}")
                    break

                data = response.json()
                if 'response' not in data:
                    self._logger.warning(f"Нет данных в ответе ВК для {group}: {data}")
                    break

                items = data['response']['items']
                if not items:
                    break

                for post in items:
                    if self._period_reached:
                        break #достигнута целевая
                    parsed_post = self._parse_news_item(post, source)
                    if parsed_post:
                        posts.append(parsed_post)

                self._offset += self._count
                self._logger.info(f"Обработано {self._offset} постов из {group}")
                time.sleep(settings.vk.REQUEST_DELAY)
        except Exception as e:
            self._logger.error(f"Ошибка парсинга ВК группы {group}: {e}")
        return posts


    def _parse_news_item(self, post: dict[str, any], source: str) -> Post | None:
        try:
            if post.get('marked_as_ads') == 1: #пропуск рекламных постов
                return None

            self._vk_handler = VKHandler(self._logger)

            post_date = datetime.fromtimestamp(post['date'])
            date = post_date.strftime(settings.common.DATE_FORMAT)

            if self._is_target_date_reached(date):
                self._period_reached = True
                self._logger.info(f"Достигнута целевая дата: {date}")
                return None

            full_text = post['text']
            text, links = self._vk_handler.extract_text_links(full_text)
            if text is None and links is None: #не новостной текст
                return None

            first_break_index = text.find('\n')
            if first_break_index == -1:
                title = text  # если нет переноса
                text = ""  # основного текста нет
            else:
                title = text[:first_break_index].strip()
                text = text[first_break_index + 1:].strip()

            post_url = f"https://vk.com/wall{post['owner_id']}_{post['id']}"

            attachments = post['attachments'] #для поиска первого качественного фото для сохранения
            image_url = self._vk_handler.extract_media(attachments)

            #image_path = self._media_manager.generate_image_filename(date, source) if image_url else ''
            #self._media_manager.save_media(post_url, image_url, image_path)

            post = Post(title=title, text=text, date=date,
                        source=source,
                        url=post_url, image=image_url, image_path = '', links=links,
                        text_processed='',
                        institute=None, faculty=None, department=None)
            return post
        except Exception as e:
            self._logger.warning(f"Ошибка парсинга поста: {e}")
            return None

