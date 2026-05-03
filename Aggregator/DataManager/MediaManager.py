import os
import requests
from telethon.tl.types import MessageMediaPhoto
from Aggregator.Settings import settings
from Aggregator.Logger.Logger import get_logger

class MediaManager:
    def __init__(self, logger = None):
        self._logger = logger or get_logger(self.__class__.__name__)

    def save_media(self, news_url: str, image_url: str, filename: str):
        try:
            if image_url:
                response = requests.get(image_url, timeout=10)
                response.raise_for_status()
                filepath = os.path.join(settings.common.MEDIA_BASE_PATH, filename)
                with open(filepath, 'wb') as f:
                    f.write(response.content)
        except Exception as e:
            self._logger.error(f"Ошибка скачивания изображения новости {news_url}: {e}")

    async def save_telegram_media(self, tg_client, message, filename: str):
        try:
            if message.media:
                filepath = os.path.join(settings.common.MEDIA_BASE_PATH, filename)
                os.makedirs(settings.common.MEDIA_BASE_PATH, exist_ok=True)
                if type(message.media) == MessageMediaPhoto:  # является ли тип вложения сообщения фотографией
                    await tg_client.download_media(message.media, file=filepath)
        except Exception as e:
            self._logger.error(f"Ошибка скачивания изображения из TG: {e}")

    def generate_image_filename(self, date: str, source: str) -> str:
        file_date = date.replace(' ','_').replace('/','').replace(':','')
        return f"{source}_{file_date}.jpg"