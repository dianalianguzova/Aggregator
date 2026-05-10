import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(CURRENT_DIR, ".env")

class DBConfig(BaseSettings):
    host: str = Field(alias="db_host")
    port: int = Field(alias="db_port")
    password: str = Field(alias="db_password")
    username: str = Field(alias="db_username")
    database: str = Field(alias="db_basename")
    model_config = SettingsConfigDict(env_file=ENV_PATH,env_file_encoding="utf-8",extra="ignore")

class ParserCommonConfig:
    NEWS_RAW_FILE: str = "Datafiles/jan_test_raw.csv"
    DATE_FORMAT: str = "%d/%m/%Y %H:%M"
    LAST_DATE: str = "31/12/2022 23:59"
    MEDIA_BASE_PATH: str = "DataParser/media/"
    CONTEXT_COUNT: int = 50 # количество символов до и после ссылки
    SHORT_TEXT_COUNT: int = 10 # порог слов для определения новости

class WebConfig:
    BASE_URL: str = "https://www.vyatsu.ru"
    NEWS_URL: str = f"{BASE_URL}/internet-gazeta.html"
    PAGINATION: str = "/page:"
    IMPLICITY_TIMEOUT: int = 10 # задержка на элемент
    PAGE_TIMEOUT: int = 120 # задержка на страницу
    USER_AGENT: str = (
        '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
    SOURCE: str = "WEB"
    THREADS_NUMBER: int = 6
    TABLE_PLUG: str = 'Смотри таблицу в первоисточнике'
    VIDEO_PLUG: str = 'Смотри видео в первоисточнике'

class VKConfig(BaseSettings):
    token: str = Field(alias="vk_token")
    SOURCE: str = "VK"
    API_VERSION: str = "5.199"
    WALL_GET_URL: str = "https://api.vk.com/method/wall.get"
    REQUEST_DELAY: int = 2
    GROUPS: dict[str, str] = {
        "vyatsu": "VK_OFFICIAL",
        "prcom_vyatsu": "VK_APPLICANTS",
        "sno.vyatsu": "VK_SNO"
    }
    model_config = SettingsConfigDict(env_file=ENV_PATH, env_file_encoding="utf-8",extra="ignore")

class TGConfig(BaseSettings):
    api_id: int = Field(alias="tg_api_id")
    api_hash: str = Field(alias="tg_api_hash")
    token: str = Field(alias="tg_token")
    SOURCE: str = "TG"
    CHANNELS: list[str] = ['vyatsunews']
    SESSION_NAME: str = 'news_parser'
    REQUEST_DELAY: float = 0.3 # задержка запросов
    model_config = SettingsConfigDict(env_file=ENV_PATH,env_file_encoding="utf-8",extra="ignore")

class MLCommonConfig:
    DATASET_PATH: str = "Datafiles/dataset_raw.csv"
    THRESHOLDS: list[float] = [
        0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5,
        0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95
    ]
    VOCAB_SIZES: list[int] = [1000, 3000, 5000, 8000, 10000, 12000]

class DeduplicationConfig:
    DATA_FILE_PATH: str = "Datafiles/deduplication/test_pairs_400.csv"
    SIM_OUTPUT_FILE_PATH: str = "Datafiles/deduplication"
    MAX_DAY_DIFF: int = 7
    PRIORITY: dict[str, int] = {
        'WEB': 1, 'VK_OFFICIAL': 2, 'VK_SNO': 3, 'VK_APPLICANTS': 4, 'TG': 5
    }
    THRESHOLD: float = 0.55
    TFIDF_FEATURES: int = 10000

class ClassificationConfig:
    DATA_FILE_PATH: str = "Datafiles/dataset_cleaned_marked.csv"
    RESULTS_OUTPUT_PATH: str = "Datafiles/classification/"
    KEYWORDS_DICTS_PATH: str = "Preprocessor/models/keywords_sets.pkl"
    KEYWORDS_TOPN: int = 12000
    TFIDF_THRESHOLD: float = 0.35
    TFIDF_FEATURES: int = 8000
    NB_THRESHOLD: float = 0.1
    NB_FEATURES: int = 10000

class TFIDFConfig:
    MIN_DF: int = 1 # слово должно быть минимум в 1 документе
    MAX_DF: float = 0.8 # слово не более чем в 80% документов
    NGRAM_RANGE: tuple[int, int] = (1, 2)
    DEDUPLICATION_MODEL_PATH: str = "Preprocessor/models/tfidf.model"
    CLASSIFICATION_MODEL_PATH: str = "Preprocessor/models/tfidf_lg.model"

class CountNBConfig:
    MIN_DF: int = 1 # минимум документов
    MAX_DF: float = 0.8 # максимум документов
    NGRAM_RANGE: tuple[int, int] = (1, 2)
    MODEL_PATH: str = "Preprocessor/models/count_nb.model"
    ALPHA: float = 1.0

class StructureConfig:
    STRUCTURE_FILE_PATH: str = "Preprocessor/structure/results/news_with_structure.csv"
    FIRST_LEVEL: list[str] = ['Институт', 'Колледж', 'Совет', 'СНО']
    SECOND_LEVEL: list[str] = ['Факультет', 'Центр', 'Лаборатория', 'Прочее']
    THIRD_LEVEL: list[str] = ['Кафедра']

class Settings:
    common = ParserCommonConfig()
    web = WebConfig()
    vk = VKConfig()
    tg = TGConfig()
    db = DBConfig()
    ml_common = MLCommonConfig()
    dedup = DeduplicationConfig()
    classification = ClassificationConfig()
    tfidf = TFIDFConfig()
    nb = CountNBConfig()
    structure = StructureConfig()

settings = Settings()