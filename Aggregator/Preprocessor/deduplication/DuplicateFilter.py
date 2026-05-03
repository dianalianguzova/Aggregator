import pandas as pd

from Aggregator.Logger.Logger import get_logger
from Aggregator.Settings import settings

from Aggregator.DataManager.CsvManager import CsvManager
from Aggregator.Model.Post import Post
from Aggregator.Preprocessor.deduplication.detectors.TFIDFDetector import TFIDFDetector
from datetime import datetime
from sklearn.metrics.pairwise import cosine_similarity

class DuplicateFilter:
    def __init__(self, logger=None, max_search_window=500):
        self._logger = logger or get_logger(self.__class__.__name__)
        self.threshold = settings.dedup.THRESHOLD
        self.tfidf_detector = TFIDFDetector(logger)
        self.csv_manager = CsvManager(logger)
        self.max_date_diff_days = 7
        self.date_format = settings.common.DATE_FORMAT
        self.vectors = None
        self.posts = None
        self._is_ready = False
        self.priority = settings.dedup.PRIORITY
        self.max_search_window = max_search_window  # макс. количество для сравнения

    def _parse_date(self, date_str):
        try:
            return datetime.strptime(date_str, self.date_format)
        except Exception as e:
            self._logger.error(f"Ошибка парсинга даты {date_str}: {e}")
            return datetime.min

    def prepare(self):
        if self.tfidf_detector.load_model():
            self._is_ready = True
            self._logger.info(f"Модель TF-IDF загружена, порог схожести текстов={self.threshold}")
        else:
            raise ValueError("Модель TF-IDF не найдена и не переданы данные для обучения")

    def deduplicate_dataset(self, output_file: str, pairs_file: str = None) -> list['Post']:
        if self.vectors is None or self.posts is None:
            return []

        clean_indices = []
        duplicate_pairs = []
        skipped = 0
        batch_size = 100

        for i in range(0, len(self.posts), batch_size):
            batch_end = min(i + batch_size, len(self.posts))

            for idx in range(i, batch_end):
                is_duplicate = False
                date_idx = self._parse_date(self.posts[idx].date)

                if clean_indices:
                    search_indices = clean_indices[-self.max_search_window:] #последние n новостей для сравнения (они отсортированы по дате)

                    sims = cosine_similarity(self.vectors[idx:idx + 1],self.vectors[search_indices])[0]

                    # проходим по индексам в порядке убывания приоритета
                    for sim, j in sorted(zip(sims, search_indices), key=lambda x: -self.priority.get(self.posts[x[1]].source, 999)):
                        if sim < self.threshold:
                            continue

                        date_j = self._parse_date(self.posts[j].date)
                        if abs((date_idx - date_j).days) > self.max_date_diff_days: #проверка дат
                            continue
                        if self.posts[idx].source == self.posts[j].source: #проверка источников
                            continue

                        is_duplicate = True
                        if self.priority.get(self.posts[idx].source, 999) < self.priority.get(self.posts[j].source, 999):
                            clean_indices.remove(j)
                            clean_indices.append(idx)
                            kept, removed = idx, j
                        else:
                            skipped += 1
                            kept, removed = j, idx

                        duplicate_pairs.append({
                            'kept_url': self.posts[kept].url,
                            'kept_source': self.posts[kept].source,
                            'kept_date': self.posts[kept].date,
                            'kept_text': f"{self.posts[kept].title or ''}\n{self.posts[kept].text or ''}".strip(),
                            'removed_url': self.posts[removed].url,
                            'removed_source': self.posts[removed].source,
                            'removed_date': self.posts[removed].date,
                            'removed_text': f"{self.posts[removed].title or ''}\n{self.posts[removed].text or ''}".strip(),
                            'similarity': float(sim)
                        })
                        break

                if not is_duplicate:
                    clean_indices.append(idx)

            self._logger.info(f"Обработано {batch_end}/{len(self.posts)}")

        clean_posts = [self.posts[i] for i in clean_indices]
        self.csv_manager.save(clean_posts, output_file) #сохранение уникальных новостей

        if pairs_file and duplicate_pairs:
            pd.DataFrame(duplicate_pairs).to_csv(pairs_file, index=False, encoding='utf-8-sig')  #сохранение дубликатов
        self._logger.info(f"Уникальных новостей: {len(clean_posts)}, дубликатов: {skipped}")
        return clean_posts

    def deduplicate_service(self, new_posts: list['Post'], db_posts: list['Post']) -> list['Post']:
        if not new_posts:
            return []
        if not self._is_ready:
            self.prepare()

        comb = new_posts + db_posts #новые посты + старые из БД за последние 7 дней
        texts = [p.text_processed for p in comb]
        vectors = self.tfidf_detector.vectorize(texts)

        new_indices = list(range(len(new_posts)))
        db_indices = list(range(len(new_posts), len(comb)))
        clean_new_indices = []

        for i in new_indices:
            cur_post =comb[i]
            cur_date = self._parse_date(cur_post.date)
            is_duplicate = False

            compare_with = clean_new_indices + db_indices #сравнение с уже отобранными постами + постами из бд
            if compare_with:
                sims = cosine_similarity(vectors[i:i + 1], vectors[compare_with])[0] #косинусное сходство текущего со всеми

                for sim, j in zip(sims, compare_with):
                    if sim < self.threshold:
                        continue
                    target_post = comb[j]
                    target_date = self._parse_date(target_post.date)

                    if abs((cur_date - target_date).days) > self.max_date_diff_days: #проверка окна 7 дней
                        continue

                    curr_pri = self.priority.get(cur_post.source, 999)  #проверяем приоритет
                    target_pri = self.priority.get(target_post.source, 999)

                    if j in db_indices: #если новость уже в базе, то не заменяем
                        is_duplicate = True
                        break
                    else:
                        is_duplicate = True
                        if curr_pri < target_pri:
                            clean_new_indices.remove(j) # текущий приоритетнее,заменяем новость
                            clean_new_indices.append(i)
                        break
            if not is_duplicate:
                clean_new_indices.append(i)

        result = [comb[idx] for idx in clean_new_indices]
        self._logger.info(f"Дедупликация: из {len(new_posts)} новых осталось {len(result)}")
        return result