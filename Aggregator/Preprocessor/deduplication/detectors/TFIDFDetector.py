import os
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from Aggregator.Logger.Logger import get_logger
from Aggregator.Model.Post import Post
from Aggregator.Settings import settings
from Aggregator.Preprocessor.deduplication.detectors.BaseDuplicateDetector import BaseDuplicateDetector

class TFIDFDetector(BaseDuplicateDetector):
    def __init__(self, logger=None, max_features=None):
        super().__init__("tfidf", logger)
        self.vectorizer = None
        self.vectors = None
        self.model_path = settings.tfidf.DEDUPLICATION_MODEL_PATH
        self._is_trained = False
        self.max_features = max_features if max_features else settings.tfidf.MAX_FEATURES_DEDUPLICATION
        self._logger = logger or get_logger(self.__class__.__name__)

    def similarity(self, text1: str, text2: str) -> float:
        if not self._is_trained:
            self._logger.error("Модель не обучена")
            return 0.0
        if not text1 or not text2:
            return 0.0
        try:
            vectors = self.vectorize([text1, text2])
            if vectors is None or vectors.shape[0] < 2:
                return 0.0
            sim = cosine_similarity(vectors[0], vectors[1])[0][0]
            return float(sim)
        except Exception as e:
            self._logger.error(f"Ошибка вычисления значения похожести текстов (TF-IDF): {e}")
            return 0.0

    def train(self, posts: list['Post']) -> None:
        try:
            if self.load_model():
                self._logger.info(f"Модель TF-IDF загружена из файла {self.model_path}")
                self._is_trained = True
                return

            texts = []
            for post in posts:
                text = post.text_processed
                texts.append(text)

            self.vectorizer = TfidfVectorizer(
                max_features=self.max_features,
                min_df=settings.tfidf.MIN_DF,
                max_df=settings.tfidf.MAX_DF,
                ngram_range=settings.tfidf.NGRAM_RANGE
            )
            self.vectors = self.vectorizer.fit_transform(texts)
            self._is_trained = True
            self.save_model()
            self._logger.info(f"TF-IDF модель обучена на {len(posts)} документах")
        except Exception as e:
            self._logger.error(f"Ошибка обучения TF-IDF: {e}")
            raise

    def vectorize(self, texts: list[str]):
        if not self._is_trained or self.vectorizer is None:
            if not self.load_model():
                self._logger.error("Модель TF-IDF не обучена и не загружена")
                return None
        try:
            return self.vectorizer.transform(texts)
        except Exception as e:
            self._logger.error(f"Ошибка векторизации текстов: {e}")
            return None

    def load_model(self) -> bool:
        try:
            if os.path.exists(self.model_path):
                self.vectorizer = joblib.load(self.model_path)
                self._is_trained = True
                return True
            else:
                self._logger.warning(f"Файл модели TF-IDF не найден: {self.model_path}")
                return False
        except Exception as e:
            self._logger.error(f"Ошибка загрузки модели TF-IDF: {e}")
            return False

    def save_model(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            joblib.dump(self.vectorizer, self.model_path)
            self._logger.info(f"TF-IDF модель сохранена в {self.model_path}")
        except Exception as e:
            self._logger.error(f"Ошибка сохранения TF-IDF модели: {e}")


