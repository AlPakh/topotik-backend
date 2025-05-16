import logging
import sys
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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

# CORS настройки - упрощенная версия с разрешением всех источников
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешаем все источники для отладки
    allow_credentials=True,
    allow_methods=["*"],  # Разрешаем все методы
    allow_headers=["*"],  # Разрешаем все заголовки
)

@app.on_event("startup")
def on_startup():
    init_db()

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
