import os
from collections import Counter
import joblib
import pandas as pd
from Aggregator.Logger.Logger import get_logger
from Aggregator.Settings import settings
from Aggregator.Preprocessor.classification.classifiers.BaseClassifier import BaseClassifier

class KeywordClassifier(BaseClassifier):
    def __init__(self, logger=None, top_n=None):
        super().__init__('keyword', logger)
        self.top_n = top_n if top_n else settings.classification.KEYWORDS_TOPN
        self.class_0_words = []  # топ-N слов для класса 0 (шум)
        self.class_1_words = []  # топ-N слов для класса 1 (новость)
        self.dicts_path = settings.classification.KEYWORDS_DICTS_PATH
        self._logger = logger or get_logger(self.__class__.__name__)

    def _is_ready(self) -> bool: #загружены ли словари
        return bool(self.class_0_words or self.class_1_words)

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.load_dicts():
            raise RuntimeError("Не найдены словари уникальных слов")

        df_result = df.copy()
        pred_col = f'pred_{self.name}'  # метка класса (0,1,-1)
        predictions = []

        for text in df_result[self._text_col]:
            words = set(str(text).split())  # слова из запроса (одной новости)
            intersect_0 = len(words & set(self.class_0_words))
            intersect_1 = len(words & set(self.class_1_words))

            if intersect_0 > intersect_1:
                predictions.append(0)
            elif intersect_1 > intersect_0:
                predictions.append(1)
            else:
                predictions.append(-1)  # неопределенный класс -1
        df_result[pred_col] = predictions
        return df_result

    def train(self, texts, labels, optimization = False):
        try:
            if not optimization and self.load_dicts():
                self._logger.info(f"Словари загружены из {self.dicts_path}")
                return

            texts_series = pd.Series(texts)
            labels_series = pd.Series(labels)

            texts_class_0 = texts_series[labels_series == 0] # все тексты для каждого класса
            texts_class_1 = texts_series[labels_series == 1]

            self._logger.info(f"Класс 0 (шум): {len(texts_class_0)} текстов")
            self._logger.info(f"Класс 1 (новость): {len(texts_class_1)} текстов")

            words_0 = ' '.join(texts_class_0).split()# частоты слов для каждого класса
            words_1 = ' '.join(texts_class_1).split()

            counter_0 = Counter(words_0)
            counter_1 = Counter(words_1)

            set_0 = set(counter_0.keys())# множества слов из обоих классов
            set_1 = set(counter_1.keys())

            # слова, которых нет в классе 1
            unique_0 = [(w, c) for w, c in counter_0.items() if w not in set_1]
            unique_0.sort(key=lambda x: x[1], reverse=True)
            self.class_0_words = [w for w, _ in unique_0[:self.top_n]]

            # слова, которых нет в классе 0
            unique_1 = [(w, c) for w, c in counter_1.items() if w not in set_0]
            unique_1.sort(key=lambda x: x[1], reverse=True)
            self.class_1_words = [w for w, _ in unique_1[:self.top_n]]

            #self._logger.info(f"Примеры слов класса 0: {self.class_0_words[:20]}")
            #self._logger.info(f"Примеры слов класса 1: {self.class_1_words[:20]}")
            self._logger.info(f"Размер полученных словарей: {len(self.class_0_words)} слов класса 0 и {len(self.class_1_words)} класса 1")
            if not optimization:
                self.save_dicts()
        except Exception as e:
            self._logger.error(f"Ошибка получения словарей ключевых слов: {e}")
            raise

    def evaluate(self, df: pd.DataFrame, threshold=None) -> dict[str, any]: #переопределение подсчета метрик
        y_true = df[self._target_col].values
        y_pred = df[f'pred_{self.name}'].values

        tp = ((y_true == 1) & (y_pred == 1)).sum()
        tn = ((y_true == 0) & (y_pred == 0)).sum()
        fp = ((y_true == 0) & (y_pred == 1)).sum()
        fn = ((y_true == 1) & (y_pred == 0)).sum()

        undefined = (y_pred == -1).sum() # неопределенные -1 - ошибочные
        fp += ((y_true == 0) & (y_pred == -1)).sum()
        fn += ((y_true == 1) & (y_pred == -1)).sum()

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0 #подсчет вручную, так как есть еще третий класс -1 (ошибочный)
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) > 0 else 0.0

        metrics = {
            'method': self.name,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'tp': int(tp),
            'fp': int(fp),
            'tn': int(tn),
            'fn': int(fn),
            'undefined': int(undefined)
        }
        return metrics

    def load_dicts(self) -> bool:
        try:
            if os.path.exists(self.dicts_path):
                data = joblib.load(self.dicts_path)
                self.class_0_words = data['class_0_words']
                self.class_1_words = data['class_1_words']
                self.top_n = data['top_n']
                self._logger.info(f"Словари {self.name} загружены из {self.dicts_path}")
                return True
            return False
        except Exception as e:
            self._logger.error(f"Ошибка загрузки словарей из файла: {e}")
            return False

    def save_dicts(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.dicts_path), exist_ok=True)
            joblib.dump({
                'class_0_words': self.class_0_words,
                'class_1_words': self.class_1_words,
                'top_n': self.top_n
            }, self.dicts_path)
            self._logger.info(f"Словари {self.name} сохранены в {self.dicts_path}")
        except Exception as e:
            self._logger.error(f"Ошибка сохранения словарей: {e}")
