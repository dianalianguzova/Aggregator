import ast
import re
from datetime import datetime

from fastapi import APIRouter, Request, Query
from sqlalchemy import func, text
from sqlalchemy.orm import joinedload, selectinload

from Aggregator.Controllers.SourceController import SourceController
from Aggregator.Controllers.StructureController import StructureController
from Aggregator.DataBase.db.DbConnection import DBConnection
from Aggregator.Logger.Logger import get_logger
from Aggregator.Model.News import NewsDB
from Aggregator.Model.NewsStructure import NewsStructureDB


class NewsPageController:
    def __init__(self, db_connection: DBConnection, templates, logger=None):
        self.db = db_connection
        self.templates = templates
        self._logger = logger or get_logger(self.__class__.__name__)
        self.structure_controller = StructureController(db_connection, logger)
        self.source_controller = SourceController(db_connection, logger)
        self.router = APIRouter(prefix="/vyatsu.news", tags=["News Pages"])
        self._setup_routes()

    def _setup_routes(self):
        @self.router.get("/")
        async def news_page(
                request: Request,
                page: int = Query(1, ge=1),
                page_size: int = Query(20, ge=1, le=100),
                source_id: list[int] = Query(default=[]),
                structure_id: list[int] = Query(default=[]),
                date_from: str = Query(None),
                date_to: str = Query(None),
                date_mode: str = Query("range"),
                search: str = Query(None),
        ):
            session = self.db.get_session()
            try:
                query = self._build_news_query(session, search, source_id, structure_id, date_from, date_to, date_mode)

                total = query.with_entities(func.count(NewsDB.id)).scalar()

                query = self._apply_eager_loading(query) # загрузка и сортировка только для финальной выборки
                query = self._apply_ordering(query, search)

                db_news = query.offset((page - 1) * page_size).limit(page_size).all()

                context = self._build_context(
                    request, db_news, page, page_size, total,
                    source_id, structure_id, date_from, date_to, date_mode, search
                )

                if request.headers.get("HX-Request"):
                    return self.templates.TemplateResponse("components/news_list.html", context)

                context["structures"] = self.structure_controller.get_structure_tree()
                context["sources"] = self.source_controller.get_all_sources()
                return self.templates.TemplateResponse("index.html", context)
            finally:
                session.close()

        @self.router.get("/post/{news_id}")
        async def news_detail(request: Request, news_id: int, back: str = Query(default="")):
            session = self.db.get_session()
            try:
                news = session.get(NewsDB, news_id)
                if news and news.links:
                    news.text = self.inject_links_into_text(news.text, news.links)
                return self.templates.TemplateResponse(
                    "components/news_page.html",
                    {"request": request, "news": news, "back": back, "hide_search": True}
                )
            finally:
                session.close()

    def _apply_eager_loading(self, query):
        return query.options(
            joinedload(NewsDB.source),
            selectinload(NewsDB.structures).joinedload(NewsStructureDB.structure)
        )

    def _build_news_query(self, session, search, source_id, structure_id, date_from, date_to, date_mode):
        query = session.query(NewsDB)

        if search and search.strip():
            words = search.strip().split()[:5]
            corrected_words = []

            for w in words:
                result = session.execute(
                    text("SELECT word FROM news_dictionary ORDER BY word <-> :w LIMIT 1"),
                    {"w": w}
                )
                suggested = result.scalar()
                corrected_words.append(suggested if suggested else w)

            ts_query_str = " ".join(corrected_words)

            query = query.filter(#фильтр по вектору
                NewsDB.search_vector.op('@@')(func.plainto_tsquery('russian', ts_query_str))
            )

        if source_id: # фильтр по источникам
            query = query.filter(NewsDB.source_id.in_(source_id))

        if structure_id:
            all_ids = set()
            for sid in structure_id:
                all_ids.update(self.structure_controller.get_all_child_ids(session, sid))
            query = query.filter(
                NewsDB.structures.any(NewsStructureDB.structure_id.in_(all_ids))
            )

        query = self._filter_by_date(query, date_from, date_to, date_mode)
        return query

    def _filter_by_date(self, query, date_from, date_to, date_mode):
        if not date_from:
            return query
        try:
            df = datetime.fromisoformat(date_from)
            if date_mode == "single":
                return query.filter(NewsDB.published_at.between(df, df.replace(hour=23, minute=59, second=59)))

            query = query.filter(NewsDB.published_at >= df)
            if date_to:
                dt = datetime.fromisoformat(date_to).replace(hour=23, minute=59, second=59)
                query = query.filter(NewsDB.published_at <= dt)
        except (ValueError, TypeError):
            pass
        return query

    def _apply_ordering(self, query, search):
        if search and search.strip():
            return query.order_by(NewsDB.published_at.desc())
        return query.order_by(NewsDB.published_at.desc())

    def _build_context(self, request, db_news, page, page_size, total,
                        source_id, structure_id, date_from, date_to, date_mode, search):
        total_pages = (total + page_size - 1) // page_size
        return {
                "request": request,
                "news": db_news,
                "page": page,
                "total_pages": total_pages,
                "pages": self.get_pagination_pages(page, total_pages),
                "prev_page": page - 1 if page > 1 else None,
                "next_page": page + 1 if page < total_pages else None,
                "selected_sources": [str(i) for i in source_id],
                "selected_structures": [str(i) for i in structure_id],
                "date_from": date_from or "",
                "date_to": date_to or "",
                "date_mode": date_mode,
                "search_query": search or "",
        }

    def get_pagination_pages(self, current_page: int, total_pages: int, window: int = 7):
        start = max(1, current_page - window // 2)
        end = min(total_pages, start + window - 1)
        start = max(1, end - window + 1)
        return list(range(start, end + 1))

    def inject_links_into_text(self, text: str, links: dict) -> str:
        if not text or not links:
            return text  # возвращаем исходный текст, если данных нет

        for url, ctx in links.items():
            try:
                if isinstance(ctx, str):
                    try:
                        parts = ast.literal_eval(ctx)
                    except (ValueError, SyntaxError):
                        continue  # если строка не парсится, пропускаем
                else:
                    parts = ctx

                # распаковка вложенных списков
                while isinstance(parts, (list, tuple)) and len(parts) == 1 and isinstance(parts[0], (list, tuple)):
                    parts = parts[0]

                if not isinstance(parts, (list, tuple)) or len(parts) < 1:
                    continue  # список пуст или имеет неверный формат

                anchor = str(parts[0]).strip()
                before = str(parts[1]).strip() if len(parts) > 1 and parts[1] else ''
                after = str(parts[2]).strip() if len(parts) > 2 and parts[2] else ''

                if not anchor:
                    continue  # без текста ссылки замена невозможна

                re_before = re.escape(before)
                re_anchor = re.escape(anchor)
                re_after = re.escape(after)

                link_html = f'<a href="{url}" target="_blank" class="text-primary underline">{anchor}</a>'

                pattern = fr"({re_before})\s*({re_anchor})\s*({re_after})"

                if before or after:
                    if re.search(pattern, text):
                        text = re.sub(pattern, rf"\1 {link_html} \3", text, count=1)
                    elif anchor in text:
                        text = text.replace(anchor, link_html, 1)
                else:
                    text = text.replace(anchor, link_html, 1)

            except Exception as e:
                self._logger.error(f"Ошибка вставки ссылки {url}: {e}")
                continue
        return text