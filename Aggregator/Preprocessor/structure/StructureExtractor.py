from typing import Set, Dict, Optional
import re

from Aggregator.Controllers.StructureController import StructureController
from Aggregator.DataBase.db.DbConnection import DBConnection
from Aggregator.Logger.Logger import get_logger
from Aggregator.Model.Post import Post
from Aggregator.Model.Structure import ExtractedStructure
from Aggregator.Settings import settings
from Aggregator.Preprocessor.processor.TextCleaner import TextCleaner

class StructureExtractor:
    def __init__(self, logger=None):
        self._logger = logger or get_logger(self.__class__.__name__)
        self._db = DBConnection()
        self._structure_controller = StructureController(self._db, logger)
        self._loaded_names: Optional[Set[str]] = None
        self._structure_mapping: dict[str, list[Dict]] = {}
        self._hierarchy_cache: dict[int, dict] = {}
        self._cleaner = TextCleaner(logger)
        self._combined_pattern: Optional[re.Pattern] = None
        self._structure_levels = {
            'first_level': settings.structure.FIRST_LEVEL,
            'second_level': settings.structure.SECOND_LEVEL,
            'third_level': settings.structure.THIRD_LEVEL
        }

    def extract_structures(self, data: list[Post]) -> list[ExtractedStructure]:
        self._load_structure_names()
        results = []
        for i, post in enumerate(data, start=1):
            try:
                result = self._extract_from_post(post)
                if result.has_structures():
                    results.append(result)
            except Exception as e:
                self._logger.error(f"Ошибка обработки поста {post.url}: {e}")
        extracted_structures = results
        return extracted_structures

    def extract_structures_service(self, data: list[Post]) -> list[Post]:
        self._load_structure_names()
        for post in data:
            try:
                found_structures = self._find_structures_in_text(post.text_processed)
                if found_structures:
                    result = self._rebuild_hierarchy(found_structures)
                    if result.has_structures():
                        post.institute = result.institute
                        post.faculty = result.faculty
                        post.department = result.department
            except Exception as e:
                self._logger.error(f"Ошибка извлечения структур для поста {post.url}: {e}")
        return data

    def _load_structure_names(self) -> None: #загрузка всех структурных подразделений из БД
        if self._loaded_names is not None:
            return
        try:
            structures = self._structure_controller.get_all_structures()
            if not structures:
                self._logger.warning("Не найдено структурных подразделений в БД")
                self._loaded_names = set()
                return

            self._structure_mapping.clear()
            self._hierarchy_cache.clear()
            for struct in structures:
                self._hierarchy_cache[struct.id] = {
                    'id': struct.id,
                    'name': struct.name,
                    'type': struct.type,
                    'abbreviation': struct.abbreviation,
                    'parent_id': struct.parent_id
                }
                search_terms = self._build_search_terms(struct)
                for term in search_terms:
                    self._add_structure_term(term, struct)
            if self._structure_mapping:
                self._prepare_search_pattern()
                self._loaded_names = set(self._structure_mapping.keys())
                self._logger.info(f"Загружено {len(self._loaded_names)} терминов для {len(structures)} структур")
            else:
                self._loaded_names = set()
        except Exception as e:
            self._logger.error(f"Ошибка загрузки структурных подразделений: {e}")
            self._loaded_names = set()


    def _extract_from_post(self, post: Post) -> ExtractedStructure:
        text = post.text_processed
        if not text or not text.strip():
            self._logger.warning(f"Нет текста в посте с URL: {post.url}")
            return ExtractedStructure(url=post.url)
        try:
            found_structures = self._find_structures_in_text(text)
            if found_structures:
                result = self._rebuild_hierarchy(found_structures)
                result.url = post.url
                return result
            return ExtractedStructure(url=post.url)
        except Exception as e:
            self._logger.error(f"Ошибка извлечения подразделения из поста {post.url}: {e}")
            return ExtractedStructure(url=post.url)


    def _find_structures_in_text(self, text: str) -> list[dict]:
        if not text or not self._combined_pattern:
            return []
        found_structures = []
        seen_ids = set()
        found_terms = self._combined_pattern.findall(text)

        for term in found_terms:
            term_lower = term.lower()
            if term_lower in self._structure_mapping:
                for struct_info in self._structure_mapping[term_lower]:
                    struct_id = struct_info['id']
                    if struct_id not in seen_ids:
                        seen_ids.add(struct_id)
                        found_structures.append(struct_info)
        return found_structures


    def _build_search_terms(self, structure) -> list[str]:
        terms = []
        lemmas = self._cleaner.clean_structure_name(structure.name)
        terms.append(lemmas.lower())
        if structure.abbreviation:
            terms.append(structure.abbreviation.lower())
        return terms

    def _add_structure_term(self, term: str, structure) -> None:
        if term not in self._structure_mapping:
            self._structure_mapping[term] = []
        self._structure_mapping[term].append({
            'id': structure.id,
            'name': structure.name,
            'type': structure.type,
            'abbreviation': structure.abbreviation,
            'parent_id': structure.parent_id
        })

    def _prepare_search_pattern(self): #подготовка паттерна из структур для поиска в тексте
        sorted_terms = sorted(self._structure_mapping.keys(), key=len, reverse=True)
        pattern_string = r'\b(?:' + '|'.join(map(re.escape, sorted_terms)) + r')\b'
        self._combined_pattern = re.compile(pattern_string, re.IGNORECASE)


    def _rebuild_hierarchy(self, found_structures: list[dict]) -> ExtractedStructure:
        levels = self._structure_levels
        institutes = set()
        faculties = set()
        departments = set()

        for struct in found_structures:
            self._add_to_level(struct, levels, institutes, faculties, departments)
        for struct in found_structures:
            self._traverse_parents(struct['parent_id'], levels, institutes, faculties, departments)
        return ExtractedStructure(
            institute=list(institutes),
            faculty=list(faculties),
            department=list(departments)
        )

    def _add_to_level(self, struct: dict, levels: dict, institutes: set, faculties: set, departments: set) -> None:
        type_key = struct['type']
        name = struct['name']
        if type_key in levels['first_level']:
            institutes.add(name)
        elif type_key in levels['second_level']:
            faculties.add(name)
        elif type_key in levels['third_level']:
            departments.add(name)

    #поднятие вверх по иерархии
    def _traverse_parents(self, parent_id: int, levels: dict, institutes: set, faculties: set,departments: set) -> None:
        current_id = parent_id
        while current_id:
            parent = self._hierarchy_cache.get(current_id)
            if not parent:
                break
            self._add_to_level(parent, levels, institutes, faculties, departments)
            current_id = parent['parent_id']
