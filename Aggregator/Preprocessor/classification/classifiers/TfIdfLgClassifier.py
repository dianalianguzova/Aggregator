import os
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from Aggregator.Logger.Logger import get_logger
from Aggregator.Settings import settings
from Aggregator.Preprocessor.classification.classifiers.BaseClassifier import BaseClassifier

class TfIdfLgClassifier(BaseClassifier):
    def __init__(self, logger=None, max_features=None):
        super().__init__("tfidf_clf", logger)
        self.max_features = max_features if max_features else settings.classification.TFIDF_FEATURES
        self.threshold = settings.classification.TFIDF_THRESHOLD
        self.vectorizer = TfidfVectorizer(
            max_features=self.max_features,
            min_df=settings.tfidf.MIN_DF,
            max_df=settings.tfidf.MAX_DF,
            ngram_range=settings.tfidf.NGRAM_RANGE
        )
        self.classifier = LogisticRegression(max_iter=10000, class_weight='balanced')
        self.model_path = settings.tfidf.CLASSIFICATION_MODEL_PATH
        self._logger = logger or get_logger(self.__class__.__name__)

    def train(self, texts, labels, optimization = False):
        try:
            if not optimization and self.load_model():
                self._logger.info(f"Классификатор загружен из файла {self.model_path}")
                return

            texts_clean = [str(t) if pd.notna(t) else "" for t in texts]
            x = self.vectorizer.fit_transform(texts_clean)
            self.classifier.fit(x, labels)
            if not optimization:
                self.save_model()
                self._logger.info(f"TF-IDF классификатор обучен на {len(texts_clean)} текстах и сохранен")
        except Exception as e:
            self._logger.error(f"Ошибка в процессе обучения классификатора: {e}")
            raise

    def predict(self, df: pd.DataFrame, optimization = False) -> pd.DataFrame: #батч-предсказание
        if not optimization:
            if not self.load_model():
                self._logger.error(f"Файл модели TF-IDF не найден: {self.model_path}")
                raise RuntimeError()

        df_result = df.copy()
        prob_col = f'prob_{self.name}'
        texts = df_result[self._text_col].fillna('').astype(str).tolist()# векторизуем весь столбец сразу
        X = self.vectorizer.transform(texts)
        df_result[prob_col] = self.classifier.predict_proba(X)[:, 1] # вероятности для всех строк (второй столбец — вероятность класса 1)
        return df_result

    def load_model(self) -> bool:
        try:
            if os.path.exists(self.model_path):
                data = joblib.load(self.model_path)
                self.vectorizer = data['vectorizer']
                self.classifier = data['classifier']
                return True
            else:
                self._logger.warning(f"Файл модели не найден: {self.model_path}")
                return False
        except Exception as e:
            self._logger.error(f"Ошибка загрузки модели {self.name}: {e}")
            return False

    def save_model(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            joblib.dump({
                'vectorizer': self.vectorizer,
                'classifier': self.classifier
            }, self.model_path)
            self._logger.info(f"Модель {self.name} сохранена в {self.model_path}")
        except Exception as e:
            self._logger.error(f"Ошибка сохранения модели {self.name}: {e}")

