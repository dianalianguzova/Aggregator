from functools import lru_cache

import numpy as np
import pandas as pd

from Aggregator.Logger.Logger import get_logger
from Aggregator.Preprocessor.deduplication.detectors.BaseDuplicateDetector import BaseDuplicateDetector
from sentence_transformers import SentenceTransformer

class SBERTDetector(BaseDuplicateDetector):

    def __init__(self, logger=None):
        super().__init__("sbert", logger)

        self.model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

        self._text1 = "text1" #оригинальные тексты
        self._text2 = "text2"
        self._logger = logger or get_logger(self.__class__.__name__)

        self._max_seq_length = self.model.max_seq_length # количество токенов для кодирования (128)
        self._embedding_dim = self.model.get_sentence_embedding_dimension() #384-мерное пространство

    @lru_cache(maxsize=500) #кэширование векторизации для тексов
    def _encode_chunks(self, text: str) -> np.ndarray:
        if not text or not text.strip():
            return np.zeros(self._embedding_dim, dtype=np.float32)

        tokens = self.model.tokenizer(text,add_special_tokens=False)["input_ids"] #разбивка на токены
        chunk_size = self._max_seq_length - 2 # запас под служебные CLS/SEP

        if len(tokens) <= chunk_size: #если текст новости меньше 128 токенов кодируем сразу весь
            return self.model.encode(text, normalize_embeddings=True, show_progress_bar=False)

        overlap = 20
        step = max(1, chunk_size - overlap) #шаг сдвига для чанков
        chunks = []
        chunk_lengths = []

        for start in range(0, len(tokens), step): #деление на чанки и кодирование каждого
            chunk_ids = tokens[start:start + chunk_size]
            if not chunk_ids:
                continue
            chunk_text = self.model.tokenizer.decode(chunk_ids,skip_special_tokens=True)
            if chunk_text.strip():
                chunks.append(chunk_text)
                chunk_lengths.append(len(chunk_ids))

        if not chunks:
            return np.zeros(self._embedding_dim, dtype=np.float32)

        chunk_embeddings = self.model.encode( #эмбеддинги для всех чанков текста
            chunks,
            normalize_embeddings=False,show_progress_bar=False, batch_size=16)

        mean_embedding = np.average( #взвешенное усреднение эмбеддингов
            chunk_embeddings,
            axis=0,
            weights=chunk_lengths #вес - количество токенов в чанке
        )

        norm = np.linalg.norm(mean_embedding) #нормализация (для косинусного сходства)
        if norm > 0:
            mean_embedding = mean_embedding / norm
        return mean_embedding.astype(np.float32)

    def similarity(self, text1: str, text2: str) -> float: #для одной пары
        try:
            vec1 = self._encode_chunks(text1)
            vec2 = self._encode_chunks(text2)
            return float(np.dot(vec1, vec2)) #скалярное произведение

        except Exception as e:
            self._logger.error(f"Ошибка вычисления похожести текстов (SBERT): {e}")
            return 0.0

    def predict(self, df: pd.DataFrame) -> pd.DataFrame: #для всех пар из выборки
        df_result = df.copy()
        texts1 = (df_result[self._text1].fillna("").astype(str).tolist())
        texts2 = (df_result[self._text2].fillna("").astype(str).tolist())
        try:
            embeddings1 = np.vstack([self._encode_chunks(text) for text in texts1]) #все векторы текстов в один массив
            embeddings2 = np.vstack([self._encode_chunks(text) for text in texts2])
            similarities = np.einsum( "ij,ij->i",embeddings1,embeddings2) #попарное скалярное произведение между массивами эмбеддингов
            df_result[f"sim_{self.name}"] = similarities
            return df_result
        except Exception as e:
            self._logger.error(f"Ошибка в SBERT predict: {e}")
            df_result[f"sim_{self.name}"] = 0.0
            return df_result