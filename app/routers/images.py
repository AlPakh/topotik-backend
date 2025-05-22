import uuid
import sys
import requests
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse, Response, StreamingResponse
from app.database import get_db
from app.services import image_service
from app.routers.auth import get_current_user
from app.schemas import ImageResponse, ImageListResponse, ImageDeleteResponse, ImageUploadResponse, User
from app.services.image_service import ImageService
import logging
from sqlalchemy.future import select
from app.models import Image

logger = logging.getLogger(__name__)

# Настраиваем дополнительное логирование для диагностики
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

# Выводим информацию о запуске модуля
logger.debug("Модуль images.py загружен, регистрируем маршруты...")

# Создаем роутер с указанием префикса и тега
router = APIRouter(prefix="/images", tags=["images"])

# Определяем маршрут для загрузки изображения
# Важно: этот маршрут должен быть определен ДО маршрутов с параметрами пути
@router.post("/upload", response_model=ImageUploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """
    Загрузка изображения на S3-сервер.
    
    Принимает файл изображения и опционально его описание.
    Загружает файл в S3-хранилище и возвращает ссылку на него.
    """
    logger.debug(f"Вызван маршрут POST /images/upload, параметры: файл={file.filename}, описание={description}")
    logger.debug(f"Начинаем загрузку изображения: {file.filename}")
    try:
        image_service = ImageService()
        
        # Проверяем тип файла
        logger.debug(f"Content-Type: {file.content_type}")
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Файл должен быть изображением")
        
        # Проверяем размер файла (максимум 100 МБ)
        MAX_SIZE = 100 * 1024 * 1024  # 100 МБ в байтах
        file_content = await file.read()
        
        file_size = len(file_content)
        logger.debug(f"Размер файла: {file_size} байт")
        
        if file_size > MAX_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"Размер файла превышает допустимый максимум в 100 МБ. Текущий размер: {file_size / (1024 * 1024):.2f} МБ"
            )
        
        # Перематываем файл в начало
        await file.seek(0)
        
        # Загружаем изображение в S3
        logger.debug(f"Передаем файл в сервис для загрузки в S3, user_id: {current_user.user_id}")
        image_data = await image_service.upload_image(
            file=file, 
            user_id=current_user.user_id,
            description=description
        )
        
        # Возвращаем информацию о загруженном изображении
        logger.debug(f"Изображение успешно загружено с ID: {image_data.id}")
        return ImageUploadResponse(
            success=True,
            message="Изображение успешно загружено",
            id=image_data.id,
            url=f"/images/proxy/{image_data.id}", # Изменяем URL на прокси-эндпоинт
            filename=image_data.filename,
            created_at=image_data.created_at,
            uploaded_by=str(current_user.user_id)
        )
    except Exception as e:
        # Логгируем ошибку
        logger.error(f"Ошибка при загрузке изображения: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при загрузке изображения: {str(e)}"
        )

# Новый прокси-эндпоинт для доступа к изображениям
@router.get("/proxy/{image_id}")
async def proxy_image(
    image_id: str
):
    """
    Прокси для получения изображения из S3.
    
    Этот эндпоинт загружает изображение из S3 и передает его клиенту,
    решая проблему с авторизацией при прямом доступе к S3.
    """
    try:
        image_service = ImageService()
        
        # Получаем сессию БД
        db = await image_service._get_db_session()
        
        # Прямой запрос к БД для получения модели Image с s3_key
        query = select(Image).where(Image.image_id == image_id)
        result = await db.execute(query)
        image_model = result.scalar_one_or_none()
        
        if not image_model:
            raise HTTPException(status_code=404, detail=f"Изображение с ID {image_id} не найдено")
        
        # Получаем s3_key напрямую из модели
        s3_key = image_model.s3_key
        
        # Получаем пресигнированный URL для изображения
        s3_client = image_service.get_s3_client()
        
        # Генерируем пресигнированный URL с помощью boto3
        presigned_url = s3_client.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': image_service.s3_bucket,
                'Key': s3_key
            },
            ExpiresIn=60  # URL действителен 60 секунд
        )
        
        # Получаем изображение по пресигнированному URL
        response = requests.get(presigned_url, stream=True)
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при загрузке изображения из S3: {response.status_code}"
            )
        
        # Определяем тип содержимого из ответа
        content_type = response.headers.get('Content-Type', 'image/png')
        
        # Возвращаем изображение клиенту с правильным типом содержимого
        return StreamingResponse(
            response.iter_content(chunk_size=8192),
            media_type=content_type
        )
    except Exception as e:
        logger.error(f"Ошибка при проксировании изображения: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при получении изображения: {str(e)}"
        )

# Маршрут для получения списка изображений
@router.get("/list", response_model=ImageListResponse)
async def get_user_images(
    current_user: User = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0
):
    """
    Получение списка изображений, загруженных текущим пользователем.
    """
    logger.debug(f"Вызван маршрут GET /images/list, параметры: limit={limit}, offset={offset}")
    try:
        image_service = ImageService()
        images = await image_service.get_user_images(
            user_id=current_user.user_id,
            limit=limit,
            offset=offset
        )
        
        # Возвращаем список изображений в формате ImageListResponse
        return ImageListResponse(
            images=images,
            total=len(images)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при получении списка изображений: {str(e)}"
        )

# Маршруты с параметрами пути должны быть определены ПОСЛЕ конкретных маршрутов
@router.get("/{image_id}", response_model=ImageResponse)
async def get_image(
    image_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Получение информации об изображении по его ID.
    """
    logger.debug(f"Вызван маршрут GET /images/{image_id}")
    try:
        image_service = ImageService()
        image = await image_service.get_image_by_id(image_id)
        
        if not image:
            raise HTTPException(status_code=404, detail=f"Изображение с ID {image_id} не найдено")
        
        # Преобразуем модель Image в схему ImageResponse
        file_url = f"https://{image_service.s3_endpoint}/{image_service.s3_bucket}/{image.s3_key}"
        
        return ImageResponse(
            id=str(image.image_id),
            filename=image.file_name,
            url=file_url,
            uploaded_by=str(image.user_id),
            created_at=image.created_at
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при получении изображения: {str(e)}"
        )

@router.delete("/{image_id}")
async def delete_image(
    image_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Удаление изображения с S3-сервера и из базы данных.
    
    Доступно только для владельца изображения или администратора.
    """
    logger.debug(f"Вызван маршрут DELETE /images/{image_id}")
    try:
        image_service = ImageService()
        
        # Получаем информацию об изображении
        image = await image_service.get_image_by_id(image_id)
        
        if not image:
            raise HTTPException(status_code=404, detail=f"Изображение с ID {image_id} не найдено")
        
        # Проверяем права доступа (только владелец или админ)
        if str(image.user_id) != str(current_user.user_id) and not current_user.is_admin:
            raise HTTPException(
                status_code=403,
                detail="Недостаточно прав для удаления этого изображения"
            )
        
        # Проверяем, используется ли изображение в картах
        if await image_service.is_image_used_in_maps(image_id):
            raise HTTPException(
                status_code=400,
                detail="Невозможно удалить изображение, так как оно используется в одной или нескольких картах"
            )
        
        # Удаляем изображение
        success = await image_service.delete_image(image_id)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Не удалось удалить изображение"
            )
        
        return JSONResponse(
            status_code=200,
            content={"message": "Изображение успешно удалено"}
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при удалении изображения: {str(e)}"
        )

# Добавляем тестовый маршрут для диагностики
@router.get("/test", response_model=dict)
async def test_route():
    """
    Тестовый маршрут для проверки работы роутера.
    """
    logger.debug("Вызван тестовый маршрут GET /images/test")
    return {"status": "ok", "message": "Тестовый эндпоинт работает"}

# Маршруты с параметрами пути должны быть определены ПОСЛЕ конкретных маршрутов 