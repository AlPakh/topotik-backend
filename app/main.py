import logging
import sys
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware as StaletteCORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.responses import PlainTextResponse
from starlette.requests import Request as StarletteRequest
from app.database import init_db
from app.routers import auth, maps, markers, collections, folders, users, location, images

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log', mode='a')
    ]
)

logger = logging.getLogger(__name__)

# Создаем экземпляр FastAPI
app = FastAPI(title="Topotik API")

# Список разрешенных источников для CORS
origins = [
    "http://localhost:8080",  # Vue.js dev server
    "http://localhost:8000",
    "https://topotik-frontend.onrender.com",
    "https://topotik-backend.onrender.com",
    "*"  # Временно разрешаем все источники для отладки
]

# CORS middleware (добавляем до включения маршрутов)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Type", "Authorization"],
    max_age=600,  # 10 минут кэширования preflight-запросов
)

@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    """
    Собственный middleware для CORS, который явно обрабатывает все OPTIONS запросы
    и добавляет нужные заголовки ответа
    """
    if request.method == "OPTIONS":
        # Для preflight запросов возвращаем пустой ответ с нужными заголовками
        response = JSONResponse(content={})
        response.headers["Access-Control-Allow-Origin"] = "*"  # Или конкретные домены
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Max-Age"] = "600"  # 10 минут кэширования
        return response
    
    # Для обычных запросов вызываем следующий обработчик
    response = await call_next(request)
    return response

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/")
def read_root():
    return {"message": "Hello, world!"}

# Добавляем общий обработчик OPTIONS для всех маршрутов
@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    return {"detail": "Разрешено"}

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(maps.router, prefix="/maps", tags=["maps"])
app.include_router(markers.router, prefix="/markers", tags=["markers"])
app.include_router(collections.router, prefix="/collections", tags=["collections"])
app.include_router(folders.router, prefix="/folders", tags=["folders"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(location.router, prefix="/location", tags=["location"])
app.include_router(images.router, prefix="/images", tags=["images"])

# Обработчик необработанных исключений
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(f"Необработанное исключение при обработке {request.method} {request.url}: {str(exc)}")
    import traceback
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": "Внутренняя ошибка сервера"},
    )
