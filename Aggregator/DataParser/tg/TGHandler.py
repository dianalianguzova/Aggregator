import regex
import re
from Aggregator.Settings import settings
from Aggregator.Logger.Logger import get_logger

class TGHandler:
    def __init__(self, logger=None):
        self._logger = logger or get_logger(self.__class__.__name__)

    def extract_text_links(self, text) -> (str, dict):
        try:
            if (not text or len(text.split()) < settings.common.SHORT_TEXT_COUNT
                    or self._emoji_is_word(text)):  # если слов меньше опр количества - это не новостной текст
                return None, None

            links = {}

            text = self._normalize_keycap_digits(text)
            text = self._remove_emoji(text)

            text = re.sub(r'\*\*', '', text).strip() #жирный текст
            text = re.sub(r'__', '', text).strip() #курсив
            text = re.sub(r'\n{2,}', '\n', text)  #большой разрыв между строками

            link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'  # ищет [текст](URL)
            matches = list(re.finditer(link_pattern, text))
            for match in matches:
                link_text = match.group(1)  # текст ссылки
                url = match.group(2)  # URL

                start_pos = match.start()
                end_pos = match.end()

                sym_count = settings.common.CONTEXT_COUNT
                chars_before = text[max(0, start_pos - sym_count):start_pos]
                chars_after = text[end_pos:min(len(text), end_pos + sym_count)]
                links[url] = [link_text, chars_before.strip(), chars_after.strip()]
                text = text.replace(match.group(0), link_text, 1)#[текст](URL) на просто текст

            text = re.sub(r'\n\s+', '\n', text).strip()

            return text, links

        except Exception as e:
            self._logger.error(f"Ошибка парсинга текста и гиперссылок TG: {e}")
            return None, None

    def _remove_emoji(self, text: str) -> str: #удаление эмоджи
        text = regex.sub(
            r'\X',
            lambda m: '' if regex.match(r'\p{Extended_Pictographic}', m.group()) else m.group(),
            text
        )
        text = regex.sub(r'[\U0001F1E6-\U0001F1FF]', '', text) #доп удаление региональных индикаторов
        return text

    def _normalize_keycap_digits(self, text: str) -> str: #конвертация эмоджи-цифр в цифры
        return regex.sub(
            r'([0-9])\uFE0F?\u20E3',
            r'\1',
            text
        )

    def _emoji_is_word(self, text: str, max_run: int = 4) -> bool: #проверка на кастомные буквы
        count = 0
        for g in regex.findall(r'\X', text):
            if regex.match(r'\p{Extended_Pictographic}', g):
                count += 1
                if count > max_run:
                    return True
            else:
                count = 0
        return False