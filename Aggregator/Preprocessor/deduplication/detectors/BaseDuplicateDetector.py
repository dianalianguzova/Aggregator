from abc import abstractmethod
from sklearn.metrics import precision_score, recall_score, f1_score
import pandas as pd
from Aggregator.Logger.Logger import get_logger

class BaseDuplicateDetector:
    def __init__(self, name: str, logger=None):
        self.name = name
        self._logger = logger or get_logger(self.__class__.__name__)
        self._text1 = 'clean_text1' # лемматизированный + без стоп-слов текст
        self._text2 = 'clean_text2'

    @abstractmethod
    def similarity(self, text1: str, text2: str) -> float: #возвращает меру похожести двух текстов
        pass

    def predict(self, df: pd.DataFrame) -> pd.DataFrame: #добавление колонки с мерой похожести для пары
        df_result = df.copy()
        df_result[f'sim_{self.name}'] = df_result.apply(
            lambda row: self.similarity(str(row[self._text1]), str(row[self._text2])),
            axis=1
        )
        return df_result

    def evaluate(self, df: pd.DataFrame, threshold: float) -> dict[str, any]: #оценка качества при заданном пороге
        y_true = df['is_duplicate'].values
        y_pred = (df[f'sim_{self.name}'] >= threshold).astype(int)

        return {
            'method': self.name,
            'threshold': threshold,
            'precision': precision_score(y_true, y_pred, zero_division=0),
            'recall': recall_score(y_true, y_pred, zero_division=0),
            'f1': f1_score(y_true, y_pred, zero_division=0),
            'tp': ((y_true == 1) & (y_pred == 1)).sum(),
            'fp': ((y_true == 0) & (y_pred == 1)).sum(),
            'tn': ((y_true == 0) & (y_pred == 0)).sum(),
            'fn': ((y_true == 1) & (y_pred == 0)).sum()
        }

