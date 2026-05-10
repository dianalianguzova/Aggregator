import os
import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
from Aggregator.Logger.Logger import get_logger
from Aggregator.Settings import settings
from Aggregator.Preprocessor.classification.classifiers.BaseClassifier import BaseClassifier

class NaiveBayesClassifier(BaseClassifier):
    def __init__(self, logger=None, max_features=None, alpha=1.0):
        super().__init__("naive_bayes", logger)
        self.max_features = max_features if max_features else settings.classification.NB_FEATURES
        self.threshold = settings.classification.NB_THRESHOLD
        self.alpha = alpha #сглаживание лапласа
        self.model_path = settings.nb.MODEL_PATH
        self._logger = logger or get_logger(self.__class__.__name__)

        self.vectorizer = CountVectorizer(
            max_features=self.max_features,
            min_df=settings.nb.MIN_DF,
            max_df=settings.nb.MAX_DF,
            ngram_range=settings.nb.NGRAM_RANGE
        )
        self.classifier = MultinomialNB(alpha=self.alpha)

    def train(self, texts, labels, optimization = False):
        try:
            if not optimization and self.load_model():
                self._logger.info(f"Классификатор загружен из файла {self.model_path}")
                return

            texts_clean = [str(t) if pd.notna(t) else "" for t in texts]
            x = self.vectorizer.fit_transform(texts_clean) #  матрица частот слов
            self.classifier.fit(x, labels) #обучение
            if not optimization:
                self.save_model()
                self._logger.info(f"Модель наивного байесовского классификатора обучена на {len(texts_clean)} текстах")
        except Exception as e:
            self._logger.error(f"Ошибка обучения NB: {e}")
            raise

    def predict(self, df: pd.DataFrame, optimization = False) -> pd.DataFrame:
        if not optimization:
            if not self.load_model():
                self._logger.error(f"Файл модели байесовского классификатора не найден: {self.model_path}")
                raise RuntimeError()

        df_result = df.copy()
        texts = df_result[self._text_col].fillna('').astype(str).tolist()
        x = self.vectorizer.transform(texts)
        df_result[f'prob_{self.name}'] = self.classifier.predict_proba(x)[:, 1]# вероятность класса 1
        return df_result

    def predict_class(self, df: pd.DataFrame, threshold=0.5) -> pd.DataFrame:
        df_result = self.predict(df)
        prob_col = f'prob_{self.name}'
        df_result[f'pred_{self.name}'] = (df_result[prob_col] >= threshold).astype(int)
        return df_result

    def get_top_features(self, class_id=1, n=20):
        feature_names = self.vectorizer.get_feature_names_out()
        # логарифм вероятности слова в классе
        log_probs = self.classifier.feature_log_prob_[class_id]
        top_indices = np.argsort(log_probs)[-n:][::-1]
        return [(feature_names[i], log_probs[i]) for i in top_indices]

    def load_model(self) -> bool:
        try:
            if os.path.exists(self.model_path):
                data = joblib.load(self.model_path)
                self.vectorizer = data['vectorizer']
                self.classifier = data['classifier']
                self._is_trained = True
                return True
            return False
        except Exception as e:
            self._logger.error(f"Ошибка загрузки модели NB из файла: {e}")
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