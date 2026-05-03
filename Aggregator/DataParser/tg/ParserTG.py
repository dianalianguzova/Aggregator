import asyncio
from datetime import timedelta, datetime
from telethon import TelegramClient

from Aggregator.Logger.Logger import get_logger
from Aggregator.Model.Post import Post
from Aggregator.Settings import settings
from Aggregator.DataParser.parser.Parser import Parser
from Aggregator.DataManager.MediaManager import MediaManager
from Aggregator.DataParser.tg.TGHandler import TGHandler

class ParserTG(Parser):
    def __init__(self):
        super().__init__(settings.tg.SOURCE)
        self._channels = settings.tg.CHANNELS
        self._client = TelegramClient(settings.tg.SESSION_NAME, settings.tg.api_id, settings.tg.api_hash)
        self._period_reached = False
        self._logger = get_logger(self.__class__.__name__)
        self._tg_handler = TGHandler(self._logger)
        self._media_manager = MediaManager()

    def parse_service(self, channel: str, last_parse: datetime): #для сервиса парсится один канал из БД до даты последнего парсинга этого канала
        self._data = []
        self.target_date = last_parse
        self._period_reached = False
        self._run_parsing([channel])


    def parse_dataset(self): #для датасета парсится список каналов до фикс даты
        self._data = []
        self.target_date = settings.common.LAST_DATE
        self._period_reached = False
        self._run_parsing(self._channels)


    def _run_parsing(self, channels: list[str]):
        try:
            if not self._client.is_connected():
                self._client.start()
            for channel in channels:
                self._period_reached = False # сброс флага для каждого канала
                posts = self._client.loop.run_until_complete(self._parse_channel(channel))
                self._data.extend(posts)
        except Exception as e:
            self._logger.error(f"Ошибка TG: {e}")


    async def _parse_channel(self, channel: str): #парсинг одного канала
        self._logger.info(f"Начинаем парсинг канала: {channel}")
        posts = []
        try:
            entity = await self._client.get_entity(channel) #посты в виде сущностей
            async for message in self._client.iter_messages(entity):
                if self._period_reached:
                    break
                try:
                    post = await self._parse_news_item(message, channel)
                except Exception as e:
                    self._logger.warning(f"Ошибка: {e}")
                    await asyncio.sleep(1)
                    continue
                if post is None and self._period_reached:
                    break #достижение целевой даты
                elif post:
                    posts.append(post)
                await asyncio.sleep(settings.tg.REQUEST_DELAY)
        except Exception as e:
            self._logger.error(f"Ошибка парсинга TG канала {channel}: {e}")
            await self._client.disconnect()
            await asyncio.sleep(2)
            await self._client.connect()
        return posts


    async def _parse_news_item(self, message, channel: str) -> Post | None:
        try:
            if not message.text:
                return None

            utc_time = message.date
            msk_time = utc_time + timedelta(hours=3)  # UTC+3
            post_date = msk_time.strftime(settings.common.DATE_FORMAT)

            if self._is_target_date_reached(post_date):
                self._period_reached = True
                return None

            full_text = message.text
            text, links = self._tg_handler.extract_text_links(full_text)

            if text is None and links is None:  # не новостной пост
                return None

            first_break_index = text.find('\n')
            if first_break_index == -1:
                title = text  # если нет переноса
                text = ""  # основного текста нет
            else:
                title = text[:first_break_index].strip()
                text = text[first_break_index + 1:].strip()

            post_url = f"https://t.me/{channel}/{message.id}"

            image_path = self._media_manager.generate_image_filename(post_date, settings.tg.SOURCE)
            await self._save_image(message, image_path)

            post = Post(title=title, text=text, date=post_date,
                        source=settings.tg.SOURCE, url=post_url,
                        image='', image_path=image_path,
                        links=links, text_processed='',
                        institute=None, faculty=None, department=None)
            self._logger.info(f"Обработан пост: {post_url} Дата: {post_date}")
            return post
        except Exception as e:
            self._logger.warning(f"Ошибка парсинга TG поста: {e}")
            return None


    async def _save_image(self, message, image_filename: str) -> None:
        if hasattr(message, 'media') and message.media:
            await self._media_manager.save_telegram_media(self._client, message, image_filename)


