import logging
import sys
import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.database import init_db
from app.routers import auth, maps, markers, collections, folders, users, location, images
from app.debug_router import router as debug_router  # Импорт отладочного роутера

# Загрузка переменных окружения из .env файла
load_dotenv()

# Вывод информации о загруженных переменных S3 для отладки
s3_vars = {
    "S3_ACCESS_KEY_ID": os.getenv("S3_ACCESS_KEY_ID", "Не задано"),
    "S3_SECRET_ACCESS_KEY": os.getenv("S3_SECRET_ACCESS_KEY", "Не задано") != "Не задано",
    "S3_ENDPOINT": os.getenv("S3_ENDPOINT", "Не задано"),
    "S3_BUCKET_NAME": os.getenv("S3_BUCKET_NAME", "Не задано")
}

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
logger.info(f"Загруженные переменные окружения S3: {s3_vars}")

# Создаем экземпляр FastAPI
app = FastAPI(title="Topotik API")

# Настройка списка разрешенных источников для CORS
allowed_origins = [
    "https://topotik-frontend.onrender.com",  # продакшен фронтенд
    "https://topotik.onrender.com",           # альтернативный домен
    "http://localhost:8080",                  # локальная разработка фронтенда
    "http://localhost:5173",                  # альтернативный порт локальной разработки
]

# CORS настройки
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"]    # Для скачивания файлов
)

logger.info(f"API запущен с настройками CORS для следующих источников: {allowed_origins}")

@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("База данных инициализирована")

@app.get("/")
def read_root():
    return {"message": "Hello, world!"}

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(maps.router, prefix="/maps", tags=["maps"])
app.include_router(markers.router, prefix="/markers", tags=["markers"])
app.include_router(collections.router, prefix="/collections", tags=["collections"])
app.include_router(folders.router, prefix="/folders", tags=["folders"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(location.router, prefix="/location", tags=["location"])

# Регистрируем роутер для изображений без дополнительных префиксов,
# так как они уже заданы в самом роутере
app.include_router(images.router)

app.include_router(debug_router)  # Добавление отладочного роутера

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
