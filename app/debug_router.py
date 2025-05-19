import os
import logging
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import Optional

router = APIRouter(prefix="/debug", tags=["debug"])

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@router.post("/upload-test")
async def test_upload(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None)
):
    """
    Тестовый эндпоинт для проверки загрузки файлов
    """
    try:
        logger.debug(f"Получен запрос на тестовую загрузку файла: {file.filename}")
        logger.debug(f"Content-Type: {file.content_type}")
        
        content = await file.read()
        size = len(content)
        logger.debug(f"Размер файла: {size} байт")
        
        # Получаем переменные окружения для диагностики
        s3_vars = {
            "S3_ACCESS_KEY_ID": os.getenv("S3_ACCESS_KEY_ID", "Не задано"),
            "S3_SECRET_ACCESS_KEY": os.getenv("S3_SECRET_ACCESS_KEY", "Не задано") != "Не задано",
            "S3_ENDPOINT": os.getenv("S3_ENDPOINT", "Не задано"),
            "S3_BUCKET_NAME": os.getenv("S3_BUCKET_NAME", "Не задано")
        }
        
        logger.debug(f"Переменные окружения S3: {s3_vars}")
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "Файл успешно получен (тестовый режим)",
                "filename": file.filename,
                "content_type": file.content_type,
                "size": size,
                "description": description,
                "s3_config": s3_vars
            }
        )
    except Exception as e:
        logger.error(f"Ошибка при тестовой загрузке: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Произошла ошибка: {str(e)}"}
        ) 