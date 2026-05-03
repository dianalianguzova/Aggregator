import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup, Tag
from Aggregator.Settings import settings

class WebHandler:
    def __init__(self, soup: BeautifulSoup, logger):
        self._soup = soup
        self._logger = logger

    def parse_title(self) -> str:
        try:
            title = self._soup.find("h1")
            return title.text.strip() if title else ""
        except Exception as e:
            self._logger.error(f"Ошибка парсинга заголовка новости: {e}")
            raise

    def parse_content(self) -> tuple[str, dict, str]:
        try:
            preview = self._soup.find("div", class_="preview")
            preview_text = preview.text.strip() if preview else ""

            img_url = self._extract_main_img()

            content_elem = self._soup.find("div", class_="content")
            text, links = self._extract_all_content(content_elem) if content_elem else ("", {})

            all_text = f"{preview_text}\n{text}".strip()
            return all_text, links, img_url

        except Exception as e:
            self._logger.error(f"Ошибка парсинга контенте: {e}")
            raise

    def _extract_main_img(self) -> str: #извлечение ссылки на основное фото новости
        try:
            main_img_wrapper = self._soup.find("div", class_="image-wrapper")
            if main_img_wrapper:
                main_img = main_img_wrapper.find("img")
                link = main_img.get("src", "") if main_img else ""
                return settings.web.BASE_URL + link
            return ""
        except Exception as e:
            self._logger.warning(f"Основное фото новости не найдено: {e}")
            return ""

    def _extract_all_content(self, element: Tag) -> tuple[str, dict]:
        try:
            text_parts = []
            links = {}
            for i, child in enumerate(element.children): #поиск дочерних элементов
                if not isinstance(child, Tag):
                    continue

                tag_name = child.name.lower()
                block_text = child.get_text(strip=False).strip()
                block_text = ' '.join(block_text.split())  # нормализация пробелов

                if block_text:
                    if tag_name == 'blockquote': #цитата
                        text_parts.append(f'«{block_text}»')
                    elif tag_name in ['ul', 'ol']: #список
                        text_parts.append(self._extract_list_text(child, tag_name))
                    elif tag_name == "table": #таблица
                        text_parts.append(settings.web.TABLE_PLUG)
                    else:
                        text_parts.append(block_text)
                    self._extract_links(child, links, block_text)
            text = '\n'.join(text_parts)
            return text, links
        except Exception as e:
            self._logger.error(f"Ошибка извлечения контента: {e}")
            raise

    def _extract_links(self, block: Tag, links_dict: dict[str, list[list[str]]], context_text: str) -> None:
        try: #извлечение гиперссылок
            link_elements = block.find_all("a", href=True)
            sym_count = settings.common.CONTEXT_COUNT  # количество символов контекста

            for link in link_elements:
                url = link.get('href')
                link_text = link.get_text(strip=True)

                if url and link_text:
                    start_pos = context_text.find(link_text) #позиция гиперссылки
                    if start_pos != -1:
                        end_pos = start_pos + len(link_text) #добавление текста перед гиперссылкой и после
                        chars_before = context_text[max(0, start_pos - sym_count):start_pos]
                        chars_after = context_text[end_pos:min(len(context_text), end_pos + sym_count)]

                        if url not in links_dict:
                            links_dict[url] = []
                        links_dict[url].append([link_text, chars_before.strip(), chars_after.strip()])

        except Exception as e:
            self._logger.error(f"Ошибка извлечения гиперссылки: {e}")

    def _extract_list_text(self, list_element: Tag, tag_name: str) -> str:
        try:
            items = list_element.find_all("li", recursive=False)
            if not items:
                return ""

            list_text = []
            for i, item in enumerate(items, 1):
                item_text = ' '.join(item.stripped_strings)#текст элемента
                nested_list = item.find(['ul', 'ol'])# проверка, есть ли вложенный список
                if nested_list:
                    nested_text = ' '.join(nested_list.stripped_strings)
                    main_text = item_text.replace(nested_text, '').strip()
                    if main_text:
                        if tag_name == 'ol':
                            list_text.append(f"{i}. {main_text}")
                        else:
                            list_text.append(f"- {main_text}")
                    nested_items = nested_list.find_all("li")# добавляем вложенный список с отступом
                    for nested_item in nested_items:
                        nested_item_text = ' '.join(nested_item.stripped_strings)
                        list_text.append(f"  - {nested_item_text}")
                else:# обычный элемент списка
                    if tag_name == 'ol':
                        list_text.append(f"{i}. {item_text}")
                    else:
                        list_text.append(f"- {item_text}")
            return '\n'.join(list_text)
        except Exception as e:
            self._logger.error(f"Ошибка парсинга списка: {e}")
            return ""

    def parse_date(self) -> str:
        try: #парсинг даты
            date_element = self._soup.select_one(".info ul.statistic li:first-child")
            date_str = date_element.get_text(strip=True) if date_element else ""
            return self._parse_date_string(date_str)
        except Exception as e:
            self._logger.error(f"Ошибка парсинга даты: {e}")
            raise

    def _parse_date_string(self, date_str: str) -> str:
        try:
            now = datetime.now()
            current_year = now.year
            date_str = re.sub(r'\s+', ' ', date_str.strip())

            time_match = re.search(r'(\d{2}):(\d{2})', date_str) # ищет время в строке в формате HH:MM
            if not time_match:
                self._logger.warning(f"Не найдено время в строке: {date_str}")
                return date_str
            hours, minutes = time_match.groups()

            if date_str.startswith('Вчера'): # 1. "Вчера, 11:47"
                yesterday = now - timedelta(days=1)  # сегодня - 1 день = вчерашняя дата
                result_date = yesterday.replace(hour=int(hours), minute=int(minutes), second=0, microsecond=0)
                return result_date.strftime(settings.common.DATE_FORMAT)

            elif date_str.startswith('Сегодня'): # 2. "Сегодня, 11:47"
                result_date = now.replace(hour=int(hours), minute=int(minutes), second=0, microsecond=0)
                return result_date.strftime(settings.common.DATE_FORMAT)

            # 3. "15 октября, 15:22" (год текущий)
            month_day_match = re.match(r'(\d{1,2})\s+([а-яё]+)\s*,\s*(\d{1,2}):(\d{2})', date_str, re.IGNORECASE)
            if month_day_match:
                day, month_ru, found_hours, found_minutes = month_day_match.groups()
                month_en = self._month_to_number(month_ru)
                if month_en:
                    result_date = datetime(
                        current_year, month_en, int(day),
                        int(found_hours), int(found_minutes), 0, 0
                    )
                    return result_date.strftime(settings.common.DATE_FORMAT)

            # 4. "15 февраля 2024, 12:21" (год указан)
            month_day_year_match = re.match(r'(\d{1,2})\s+([а-яё]+)\s+(\d{4})\s*,\s*(\d{1,2}):(\d{2})', date_str,
                                            re.IGNORECASE)
            if month_day_year_match:
                day, month_ru, year, found_hours, found_minutes = month_day_year_match.groups()
                month_en = self._month_to_number(month_ru)
                if month_en:
                    result_date = datetime(
                        int(year), month_en, int(day),
                        int(found_hours), int(found_minutes), 0, 0
                    )
                    return result_date.strftime(settings.common.DATE_FORMAT)
            self._logger.warning(f"Неизвестный формат даты: {date_str}")
            return date_str
        except Exception as e:
            self._logger.error(f"Ошибка преобразования даты '{date_str}': {e}")
            return date_str

    def _month_to_number(self, month_ru: str) -> int:
        months = {
            'января': 1, 'февраля': 2, 'марта': 3,
            'апреля': 4, 'мая': 5, 'июня': 6, 'июля': 7,
            'августа': 8, 'сентября': 9, 'октября': 10,
            'ноября': 11, 'декабря': 12,
        }
        return months.get(month_ru.lower())