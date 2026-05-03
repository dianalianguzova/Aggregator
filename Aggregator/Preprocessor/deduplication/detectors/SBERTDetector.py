import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from Aggregator.Logger.Logger import get_logger
from Aggregator.Preprocessor.deduplication.detectors.BaseDuplicateDetector import BaseDuplicateDetector
from sentence_transformers import SentenceTransformer

class SBERTDetector(BaseDuplicateDetector):
    def __init__(self, logger=None):
        super().__init__("sbert", logger)
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        self.embeddings = None
        self._text1= 'text1'
        self._text2= 'text2'
        self._logger = logger or get_logger(self.__class__.__name__)

    def similarity(self, text1: str, text2: str) -> float:
        try:
            vec1 = self.model.encode([text1], normalize_embeddings=True)[0]
            vec2 = self.model.encode([text2], normalize_embeddings=True)[0]
            return float(cosine_similarity([vec1], [vec2])[0][0])
        except Exception as e:
            self._logger.error(f"Ошибка вычисления значения похожести текстов (SBert): {e}")
            return 0.0

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        df_result = df.copy()

        texts1 = df_result[self._text1].fillna('').astype(str).tolist() #  все тексты сразу
        texts2 = df_result[self._text2].fillna('').astype(str).tolist()

        try:
            embeddings1 = self.model.encode(
                texts1,
                batch_size=64,
                normalize_embeddings=True,
                show_progress_bar=True,
                convert_to_numpy=True
            )

            embeddings2 = self.model.encode(
                texts2,
                batch_size=64,
                normalize_embeddings=True,
                show_progress_bar=True,
                convert_to_numpy=True
            )

            similarities = np.sum(embeddings1 * embeddings2, axis=1) # косинусная схожесть для всех пар сразу
            df_result[f'sim_{self.name}'] = similarities
            return df_result
        except Exception as e:
            self._logger.error(f"Ошибка в SBert predict: {e}")
            df_result[f'sim_{self.name}'] = 0.0
            return df_result