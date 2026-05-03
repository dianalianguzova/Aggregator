from Aggregator.Logger.Logger import get_logger
from Aggregator.Preprocessor.deduplication.detectors.BaseDuplicateDetector import BaseDuplicateDetector

class InclusionDetector(BaseDuplicateDetector):
    def __init__(self, logger = None):
        super().__init__('inclusion')
        self._logger = logger or get_logger(self.__class__.__name__)

    def similarity(self, text1: str, text2: str) -> float:
        if not text1 or not text2:
            return 0.0
        try:
            words1 = set(str(text1).split())
            words2 = set(str(text2).split())
            if not words1 or not words2:
                return 0.0
            intersection = len(words1 & words2)
            min_len = min(len(words1), len(words2))
            return intersection / min_len
        except Exception as e:
            self._logger.error(f"Ошибка вычисления меры включения: {e}")
            return 0.0