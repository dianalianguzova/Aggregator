import re
import nltk
import pymorphy3
from nltk.corpus import stopwords
from Aggregator.Logger.Logger import get_logger
from Aggregator.Model.Post import Post

class TextCleaner:
    def __init__(self, logger = None):
        self._morph = pymorphy3.MorphAnalyzer()
        nltk.download('stopwords', quiet=True)
        self._stop_words = set(stopwords.words('russian'))
        self._lemma_cache = {}
        self._logger = logger or get_logger(self.__class__.__name__)

    def clean_text_posts(self, posts: list['Post']):
        for i, post in enumerate(posts):
            try:
                title = post.title if isinstance(post.title, str) else ''
                body = post.text if isinstance(post.text, str) else ''
                text = f"{title} {body}".strip()

                text = self._clean_text(text)
                lemm_text = self.lemmatizate(text)
                text_without_stop_words = self._remove_stopwords(lemm_text)

                post.text_processed = text_without_stop_words

            except Exception as e:
                self._logger.error(f"Ошибка обработки текста новости {post.url}: {e}")
                post.text_processed = ''

    def clean_structure_name(self, name: str) -> str:
        if not name: return ''
        lemm_name = self.lemmatizate(name)
        clean_name = self._remove_stopwords(lemm_name)
        return clean_name

    def lemmatizate(self, text: str) -> str:
        if not isinstance(text, str) or not text:
            return ''
        text = text.lower()
        tokens = re.findall(r'[а-яёa-z]+(?:-[а-яёa-z]+)*|\d+', text)
        lemmas = []
        for token in tokens:
            if token in self._lemma_cache:
                lemma = self._lemma_cache[token]
            else:
                try:
                    lemma = self._morph.parse(token)[0].normal_form
                except Exception:
                    lemma = token
                self._lemma_cache[token] = lemma
            lemmas.append(lemma)
        return ' '.join(lemmas)

    def _remove_stopwords(self, text: str) -> str:
        words = text.split()
        filtered_words = [word for word in words if word not in self._stop_words]
        return ' '.join(filtered_words)

    def _clean_text(self, text: str) -> str:
        if not isinstance(text, str) or not text:
            return ''
        text = re.sub(r'\S+\.\S+/\S+', '', text) #удаление ссылок
        text = re.sub(r'\s+', ' ', text).strip() #лишние пробелы
        return text


