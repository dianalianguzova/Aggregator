from abc import ABC, abstractmethod
import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score

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
        y_true = df[self._target_col].values # целевые значения
        y_prob = df[f'prob_{self.name}'].values #вероятность класса 1 (для логистической регрессии)
        y_pred = (y_prob >= threshold).astype(int) #предсказанная метка

        metrics = {
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

        if len(set(y_true)) > 1: #roc-auc
            try:
                metrics['roc_auc'] = roc_auc_score(y_true, y_prob)
            except:
                metrics['roc_auc'] = 0.0
        else:
            metrics['roc_auc'] = 0.0
        return metrics
