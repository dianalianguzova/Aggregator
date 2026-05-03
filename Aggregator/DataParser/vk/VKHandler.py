import re
import regex
from Aggregator.Settings import settings
from Aggregator.Logger.Logger import get_logger

class VKHandler:
    def __init__(self, logger = None):
        self._logger = logger or get_logger(self.__class__.__name__)

    def extract_text_links(self, text):
        try:
            if not text or len(text.split()) < settings.common.SHORT_TEXT_COUNT:
                return None, None

            links = {}

            text = self._normalize_keycap_digits(text)
            text = self._remove_emoji(text)
            text = re.sub(r'\n\n+', '\n', text).strip()

            # паттерн для поиска гиперссылок вк [что-то | что-то]
            vk_link_pattern = r'\[\s*(.*?)\s*\|\s*(.*?)\s*\]'
            matches = list(re.finditer(vk_link_pattern, text)) #все совпадения вместе с позициями

            for match in reversed(matches): #обработка текста от конца к началу
                link_id = match.group(1).strip()
                link_text = match.group(2).strip()

                if link_id.startswith(('club', 'id', 'public', 'album')): #формируем url
                    url = f"https://vk.com/{link_id}"
                elif link_id.startswith('http'):
                    url = link_id
                else:
                    url = link_id

                start_pos = match.start() #поиск контекста вокруг гиперссылки
                end_pos = match.end()
                sym_count = settings.common.CONTEXT_COUNT
                chars_before = text[max(0, start_pos - sym_count):start_pos]
                chars_after = text[end_pos:min(len(text), end_pos + sym_count)]
                links[url] = [link_text, chars_before.strip(), chars_after.strip()]

                text = text[:start_pos] + link_text + text[end_pos:]

            text = re.sub(r'\n\s+', '\n', text).strip()
            return text.strip(), links
        except Exception as e:
            self._logger.error(f"ОШИБКА ПАРСИНГА ГИПЕРССЫЛОК: {e}")
            return None, None


    def extract_media(self, attachments: list[dict[str, any]]) -> str | None:
        try:
            for attachment in attachments:
                if attachment.get('type') == 'photo':
                    photo = attachment['photo']
                    sizes = photo.get('sizes', [])

                    quality_types = ['w', 'z', 'y', 'x','m']  #разрешения фото в вк от лучшего к худшему
                    for s in sizes:
                        if s['type'] in quality_types[:3]:
                            return s['url'] #первое качественное фото c разрешением выше 1080
                    return sizes[0]['url'] #если не нашлось качественного, то берем первое
                elif attachment.get('type') == 'video':
                    continue
            return None
        except Exception as e:
            self._logger.error(f"Ошибка извлечения медиа из ВК: {e}")
            return None

    def _remove_emoji(self, text: str) -> str:  # удаление эмоджи
        text = regex.sub(
            r'\X',
            lambda m: '' if regex.match(r'\p{Extended_Pictographic}', m.group()) else m.group(),
            text
        )
        text = regex.sub(r'[\U0001F1E6-\U0001F1FF]', '', text)  # доп удаление региональных индикаторов
        return text

    def _normalize_keycap_digits(self, text: str) -> str: #конвертация эмоджи-цифр в цифры
        return regex.sub(
            r'([0-9])\uFE0F?\u20E3',
            r'\1',
            text
        )