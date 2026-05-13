import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from Aggregator.Controllers.NewsPageController import NewsPageController
from Aggregator.Controllers.SourceController import SourceController
from Aggregator.Controllers.StructureController import StructureController
from Aggregator.DataBase.db.DbConnection import DBConnection

db_connection = DBConnection()
templates = Jinja2Templates(directory="Web/templates")

app = FastAPI(
    title="News Aggregator API",
    description="API для агрегатора новостей вуза",
    version="1.0.0"
)

app.mount("/media", StaticFiles(directory="DataParser/media"), name="media")
app.mount("/static", StaticFiles(directory="Web/static"), name="static")

# настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

# инициализация контроллеров
news_page_controller = NewsPageController(db_connection, templates)

# подключение маршрутов
app.include_router(news_page_controller.router)

@app.get("/")
async def root():
    return {"message": "API Aggregator is running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
