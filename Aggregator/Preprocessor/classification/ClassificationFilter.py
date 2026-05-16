import pandas as pd

from Aggregator.DataManager.CsvManager import CsvManager
from Aggregator.Logger.Logger import get_logger
from Aggregator.Model.Post import Post
from Aggregator.Settings import settings
from Aggregator.Preprocessor.classification.classifiers.TfIdfLgClassifier import TfIdfLgClassifier

class ClassificationFilter:
    def __init__(self, logger=None):
        self._logger = logger or get_logger(self.__class__.__name__)
        self.threshold = settings.classification.TFIDF_THRESHOLD  # оптимальный порог вероятности
        self.classifier = TfIdfLgClassifier(logger)
        self.csv_manager = CsvManager(logger)
        self._is_ready = False

    def prepare(self):
        if self.classifier.load_model():
            self._is_ready = True
            self._logger.info(f"Классификатор загружен, порог вероятности={self.threshold}")
        else:
            raise ValueError("Модель классификатора не найдена и не переданы данные для обучения")

    def classify_posts_dataset(self, posts: list['Post'], output_file: str = None) -> list['Post']:
        if not self._is_ready:
            self.prepare()

        df = pd.DataFrame([{'text_processed': post.text_processed} for post in posts]) # DataFrame для батч предсказания
        self._logger.info(f"Бинарная классификация {len(posts)} постов")

        df_result = self.classifier.predict(df) # предсказания
        prob_col = f'prob_{self.classifier.name}'
        df_result['predicted_class'] = (df_result[prob_col] >= self.threshold).astype(int) # метка класса на основе предсказания

        classified_posts = [] # обновление постов
        for i, post in enumerate(posts):
            post.is_news = int(df_result.iloc[i]['predicted_class'])
            classified_posts.append(post)

        if output_file: # сохранение результатов
            self.csv_manager.save(classified_posts, output_file)
        self._logger.info(f"Классификация текстов завершена")
        return classified_posts

    def classify_posts_service(self, posts: list['Post']) -> list['Post']:
        if not posts:
            return []

        if not self._is_ready:
            self.prepare()

        texts = [post.text_processed for post in posts]
        df = pd.DataFrame({'text_processed': texts})

        df_result = self.classifier.predict(df)
        prob_col = f'prob_{self.classifier.name}'

        for i, post in enumerate(posts):
            probability = df_result.iloc[i][prob_col] #вероятность классов
            post.is_news = 1 if probability >= self.threshold else 0
        return posts
