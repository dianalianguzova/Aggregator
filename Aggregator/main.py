import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from Aggregator.Controllers.NewsPageController import NewsPageController
from Aggregator.DataBase.db.DbConnection import DBConnection

db_connection = DBConnection()
templates = Jinja2Templates(directory="Web/templates")

app = FastAPI()

app.mount("/media", StaticFiles(directory="DataParser/media"), name="media")  # медиа для тг постов
app.mount("/static", StaticFiles(directory="Web/static"), name="static") # лого

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

news_page_controller = NewsPageController(db_connection, templates)
app.include_router(news_page_controller.router) # подключение маршрутов

@app.get("/")
async def root():
    return {"message": "API Aggregator is running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
