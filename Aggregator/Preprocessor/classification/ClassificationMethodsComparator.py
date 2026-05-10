import pandas as pd

from Aggregator.Logger.Logger import get_logger
from Aggregator.Settings import settings
from sklearn.model_selection import train_test_split

from Aggregator.Preprocessor.classification.classifiers.KeywordClassifier import KeywordClassifier
from Aggregator.Preprocessor.classification.classifiers.NaiveBayesClassifier import NaiveBayesClassifier
from Aggregator.Preprocessor.classification.classifiers.TfIdfLgClassifier import TfIdfLgClassifier

class ClassificationMethodsComparator:
    def __init__(self, logger=None):
        self._logger = logger or get_logger(self.__class__.__name__)
        self._data_path = settings.classification.DATA_FILE_PATH
        self._output_dir = settings.classification.RESULTS_OUTPUT_PATH
        self._target_col = 'is_news'
        self._thresholds = settings.ml_common.THRESHOLDS
        self._vocab_sizes = settings.ml_common.VOCAB_SIZES

        self.df = pd.read_csv(self._data_path)
        self._logger.info(f"Загружено {len(self.df)} размеченных новостей")

        self.methods = {
            'keyword': KeywordClassifier(logger),
            'tfidf_lr': TfIdfLgClassifier(logger),
            'naive_bayes': NaiveBayesClassifier(logger)
        }

    def split_data(self):
        train_val_df, test_df = train_test_split(
            self.df, test_size=0.2, random_state=42,
            stratify=self.df[self._target_col]
        )
        train_df, val_df = train_test_split(
            train_val_df, test_size=0.25,  # 0.25 от 0.8 = 0.2 от всего
            random_state=42,
            stratify=train_val_df[self._target_col]
        )
        self._logger.info(f"Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")
        return train_df, val_df, test_df

    def compare(self): #сравнение на тестовой выборке
        train_df, val_df, test_df = self.split_data()

        for name, clf in self.methods.items():
            self._logger.info(f"Работа метода: {name}")
            self._logger.info(f"Обучающая выборка (размер): {len(train_df)} текстах")
            clf.train(train_df['text_processed'].tolist(), train_df[self._target_col].tolist())

            if name == 'keyword':
                self._logger.info(f"Оценка на тестовой выборке")
                self._evaluate_on_test_keyword(name, clf, test_df)
            else:
                self._logger.info(f"Оценка на тестовой выборке размера {len(test_df)} с порогом {clf.threshold:.2f}")
                self._evaluate_on_test(name, clf, test_df, clf.threshold)
        self._logger.info(f"Результаты классификации в {self._output_dir}")

    def _evaluate_on_test(self, name, clf, test_df, threshold): #тест на тестовой выборке
        df_result = clf.predict(test_df)

        prob_col = f'prob_{clf.name}'
        pred_col = f'pred_{name}'

        if prob_col not in df_result.columns:
            self._logger.error(f"Колонка {prob_col} не создана")
            df_result[prob_col] = 0.35 #заглушка

        metrics = clf.evaluate(df_result, threshold) #расчет метрик и их сохранение
        pd.DataFrame([metrics]).to_csv(f"{self._output_dir}/{name}_test_metrics.csv", index=False, encoding='utf-8-sig')

        df_result[pred_col] = (df_result[prob_col] >= threshold).astype(int)
        df_result.to_csv(f"{self._output_dir}/{name}_test_predictions.csv", index=False, encoding='utf-8-sig') #разметка методом и ее сохранение

    def _evaluate_on_test_keyword(self, name, clf, test_df): #оценка словарного метода на тесте при лучших параметрах
        df_result = clf.predict(test_df)
        metrics = clf.evaluate(df_result)
        pd.DataFrame([metrics]).to_csv(f"{self._output_dir}/{name}_test_metrics.csv", index=False, encoding='utf-8-sig')
        df_result.to_csv(f"{self._output_dir}/{name}_test_predictions.csv", index=False, encoding='utf-8-sig')

    def get_tfidf_lg_params(self):  # тест на подбор лучшего размера словаря tf-idf + поиск лучшего порога lg
        return self._optimize_vocabulary_base(
            clf_name=TfIdfLgClassifier,
            param_name='max_features',
            file_prefix='tfidf_vocab',
            thresholds_include=True
        )

    def get_keyword_params(self):  # тестирование размерности словарей уникальных слов каждого класса
        return self._optimize_vocabulary_base(
            clf_name=KeywordClassifier,
            param_name='top_n',
            file_prefix='keyword',
            thresholds_include=False #для словарного метода не важны пороги вероятности
        )

    def get_count_nb_params(self):  # тестирование размерности словарей count для nb + поиск лучшего порога
        return self._optimize_vocabulary_base(
            clf_name=NaiveBayesClassifier,
            param_name='max_features',
            file_prefix='count_vocab',
            thresholds_include=True
        )

    def _optimize_vocabulary_base(self, clf_name, param_name, file_prefix, thresholds_include):
        results = []
        train_df, val_df, _ = self.split_data()

        try:
            for size in self._vocab_sizes:
                self._logger.info(f"Тестирование словаря размера: {size}")
                clf = clf_name(logger=self._logger, **{param_name: size})
                clf.train(train_df['text_processed'].tolist(), train_df[self._target_col].tolist(), True)
                df_val = clf.predict(val_df, True)

                if thresholds_include:
                    for th in self._thresholds:  # оценка при разных порогах
                        metrics = clf.evaluate(df_val, th)
                        metrics[param_name] = size
                        metrics['threshold'] = th
                        results.append(metrics)
                    size_results = [m for m in results if m[param_name] == size]  # сохранение всех метрик на всех порогах для словаря текущего размера
                    pd.DataFrame(size_results).to_csv(
                        f"{self._output_dir}/{file_prefix}_{size}_metrics.csv",
                        index=False,
                        encoding='utf-8-sig'
                    )
                else:
                    metrics = clf.evaluate(df_val)
                    metrics[param_name] = size
                    results.append(metrics)

            pd.DataFrame(results).to_csv(  # сохранение всех результатов
                f"{self._output_dir}/{file_prefix}_optimization.csv",
                index=False,
                encoding='utf-8-sig'
            )
            return pd.DataFrame(results)
        except Exception as e:
            self._logger.error(f"Ошибка при оптимизации {file_prefix}: {e}")
            return None