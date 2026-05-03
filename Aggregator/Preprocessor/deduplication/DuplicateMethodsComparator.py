import pandas as pd
from Aggregator.Logger.Logger import get_logger
from Aggregator.Model.Post import Post
from Aggregator.Settings import settings
from Aggregator.Preprocessor.deduplication.detectors.InclusionDetector import InclusionDetector
from Aggregator.Preprocessor.deduplication.detectors.TFIDFDetector import TFIDFDetector
from Aggregator.Preprocessor.deduplication.detectors.SBERTDetector import SBERTDetector

class DuplicateMethodComparator:
    def __init__(self, logger=None):
        self.tfidf_logreg = None
        self._logger = logger or get_logger(self.__class__.__name__)
        self._dataset_path = settings.ml_common.DATASET_PATH
        self._data_path = settings.dedup.DATA_FILE_PATH #размеченный файл с парами
        self._output_dir = settings.dedup.SIM_OUTPUT_FILE_PATH #выходной файл с результатами
        self._target_col = 'is_duplicate'
        self._vocab_sizes = settings.tfidf.VOCAB_SIZES
        self._thresholds = settings.ml_common.THRESHOLDS #разные пороги схожести для тестирования

        self.df = pd.read_csv(self._data_path)
        self.results_df = self.df.copy()

        self.methods = {
            'inclusion': InclusionDetector(),
            'tfidf': TFIDFDetector(logger),
            'sbert': SBERTDetector(logger)
        }

    def compare(self, posts: list['Post']): #сравнение методов всех
        try:
            for method_name, detector in self.methods.items():
                if method_name in ['tfidf']: #если tf-idf не обучена
                    detector.train(posts)

            for method_name, detector in self.methods.items():
                self._logger.info(f"Работа метода: {method_name}")
                try:
                    self._process_single_method(method_name, detector)
                except Exception as e:
                    self._logger.error(f"Ошибка работы метода {method_name}: {e}")
            self._logger.info(f"Сравнение методов оценки схожести пар текстов завершено. Результаты в {self.output_dir}")
        except Exception as e:
            self._logger.error(f"Ошибка сравнения методов: {e}")
            return None

    def _process_single_method(self, method_name: str, detector): #обработка одного метода дедупликации
        self.results_df = detector.predict(self.results_df)#similarity

        metrics = []
        for th in self._thresholds:
            metrics.append(detector.evaluate(self.results_df, th))

        metrics_df = pd.DataFrame(metrics)
        metrics_df.to_csv(f"{self._output_dir}/{method_name}_metrics.csv", index=False, encoding='utf-8-sig') #сохранение метрик метода

        best = max(metrics, key=lambda x: x['f1']) #вычисление лучшего порога для метода
        #best_df = pd.DataFrame([best])
        #best_df.to_csv(f"{self.output_dir}/{method_name}_best.csv", index=False, encoding='utf-8-sig')

        df_pred = self.results_df.copy() #сохранение предсказаний с лучшим порогом
        df_pred[f'pred_{method_name}'] = (df_pred[f'sim_{method_name}'] >= best['threshold']).astype(int)
        df_pred.to_csv(f"{self._output_dir}/{method_name}_predictions.csv", index=False, encoding='utf-8-sig')

    def optimize_tfidf_vocabulary(self, posts: list['Post'], threshold=0.55):
        results = []

        try:
            for size in self._vocab_sizes:
                original_path = settings.tfidf.DEDUPLICATION_MODEL_PATH
                settings.tfidf.DEDUPLICATION_MODEL_PATH = f"Preprocessor/deduplication/models/tfidf_{size}.model" #смена пути для модели, чтобы не перезаписывать файл
                detector = TFIDFDetector(self._logger, max_features=size)

                detector._is_trained = False
                detector.train(posts)  # обучение с новым размером
                settings.tfidf.DEDUPLICATION_MODEL_PATH = original_path

                df_result = self.df.copy() #результаты предсказаний
                df_result = detector.predict(df_result)

                metrics = detector.evaluate(df_result, threshold)
                metrics['vocab_size'] = size
                results.append(metrics)

            results_df = pd.DataFrame(results)
            results_df.to_csv(f"{self._output_dir}/vocabulary_optimization.csv",index=False, encoding='utf-8-sig')
            return results_df
        except Exception as e:
            self._logger.error(f"Ошибка тестирования TF-IDF: {e}")
            return None
