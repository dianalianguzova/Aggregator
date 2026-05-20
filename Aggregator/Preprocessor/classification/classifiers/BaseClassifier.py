from abc import ABC, abstractmethod
import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix

from Aggregator.Logger.Logger import get_logger

class BaseClassifier(ABC):
    def __init__(self, name: str, logger=None):
        self.name = name
        self._logger = logger or get_logger(self.__class__.__name__)
        self._text_col = 'text_processed'  # колонка с текстом для классификации
        self._target_col = 'is_news'  # целевая колонка (0 - шум, 1 - новость)
        self._is_trained = False

    @abstractmethod
    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
       pass

    def evaluate(self, df: pd.DataFrame, threshold: float) -> dict[str, any]: #оценка классификации при пороге
        y_true = df[self._target_col].values
        y_prob = df[f'prob_{self.name}'].values
        y_pred = (y_prob >= threshold).astype(int)

        tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()

        metrics = {
            'method': self.name,
            'threshold': threshold,
            'precision': precision_score(y_true, y_pred, zero_division=0),
            'recall': recall_score(y_true, y_pred, zero_division=0),
            'f1': f1_score(y_true, y_pred, zero_division=0),
            'tp': int(tp),
            'fp': int(fp),
            'tn': int(tn),
            'fn': int(fn)
        }
        return metrics
