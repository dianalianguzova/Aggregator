import os
from dataclasses import asdict
import pandas as pd

from Aggregator.Logger.Logger import get_logger
from Aggregator.Model.Post import Post
from Aggregator.Settings import settings
from Aggregator.Model.Structure import ExtractedStructure

class CsvManager:
    def __init__(self, logger=None):
        self._logger = logger or get_logger(self.__class__.__name__)
        self._raw_path = settings.common.NEWS_RAW_FILE

    def _serialize_list(self, val): # вспомогательный метод для сохранения списков через ;
        return ';'.join(val) if isinstance(val, list) and val else ''

    def save(self, data: list['Post'], filename: str = None) -> None:
        try:
            filename = filename or self._raw_path
            if not data:
                if self._logger: self._logger.warning("Нет данных для сохранения в csv")
                return

            df = pd.DataFrame([asdict(p) for p in data])
            for field in ['institute', 'faculty', 'department']:
                if field in df.columns:
                    df[field] = df[field].apply(self._serialize_list)

            if 'links' in df.columns:
                df['links'] = df['links'].apply(
                    lambda d: "; ".join(f"{k}: {v}" for k, v in d.items()) if isinstance(d, dict) and d else ''
                )

            df.to_csv(filename, index=False, encoding='utf-8-sig')
        except Exception as e:
            if self._logger: self._logger.error(f"Ошибка сохранения в Csv: {e}")
            raise

    def load(self, filename: str = None) -> list['Post']:
        try:
            filename = filename or self._raw_path
            if not os.path.exists(filename):
                return []

            df = pd.read_csv(filename, encoding='utf-8-sig')
            if df.empty:
                return []

            def parse_links(links_str): #обработка списка гиперссылок
                links_dict = {}
                if isinstance(links_str, str) and links_str:
                    items = links_str.split('; ')
                    for item in items:
                        if ':' in item:
                            parts = item.split(': ', 1) if ': ' in item else item.split(':', 1)
                            if len(parts) == 2:
                                links_dict[parts[0].strip()] = parts[1].strip()
                return links_dict

            def parse_list_field(val):#обработка подразделений
                if pd.isna(val) or val == '': return []
                return [item.strip() for item in str(val).split(';') if item.strip()]

            if 'links' in df.columns:
                df['links'] = df['links'].apply(parse_links)

            for field in ['institute', 'faculty', 'department']:
                if field in df.columns:
                    df[field] = df[field].fillna('').apply(parse_list_field)

            posts = [Post(**row) for row in df.to_dict('records')]
            if self._logger: self._logger.info(f"Загружено {len(posts)} записей из {filename}")
            return posts
        except Exception as e:
            if self._logger: self._logger.error(f"Ошибка загрузки из Csv: {e}")
            raise

    def add_structures_to_dataset(self, extracted_structures: list['ExtractedStructure'], filename: str = None) -> None:
        try:
            filename = filename or self._raw_path
            if not os.path.exists(filename): return

            df = pd.read_csv(filename, encoding='utf-8-sig', index_col='url')
            struct_map = {s.url: s for s in extracted_structures}
            common_urls = df.index.intersection(struct_map.keys()) # пересечение URL-адресов в файле и в новых данных

            for url in common_urls:
                extracted = struct_map[url]
                df.at[url, 'institute'] = self._serialize_list(extracted.institute)
                df.at[url, 'faculty'] = self._serialize_list(extracted.faculty)
                df.at[url, 'department'] = self._serialize_list(extracted.department)

            df.reset_index().to_csv(filename, index=False, encoding='utf-8-sig')
            if self._logger: self._logger.info(f"Структуры обновлены для {len(common_urls)} новостей")
        except Exception as e:
            if self._logger: self._logger.error(f"Ошибка обновления датасета: {e}")
            raise
