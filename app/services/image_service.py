import uuid
import logging
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from app.config.s3_config import get_s3_client, S3_BUCKET_NAME
from app.models import Image, User
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Допустимые типы MIME для загрузки изображений
ALLOWED_IMAGE_TYPES = [
    "image/jpeg", 
    "image/png", 
    "image/gif", 
    "image/webp", 
    "image/svg+xml"
]

# Максимальный размер файла (10 МБ)
MAX_FILE_SIZE = 10 * 1024 * 1024

async def upload_image(db: Session, file: UploadFile, user_id: uuid.UUID):
    """Загрузка изображения в S3 и сохранение метаданных в БД"""
    
    # Проверка типа файла
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400, 
            detail=f"Недопустимый тип файла. Разрешены только: {', '.join(ALLOWED_IMAGE_TYPES)}"
        )
    
    # Чтение содержимого файла
    contents = await file.read()
    file_size = len(contents)
    
    # Проверка размера файла
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400, 
            detail=f"Размер файла превышает максимально допустимый ({MAX_FILE_SIZE // 1024 // 1024} МБ)"
        )
    
    # Генерация уникального имени файла в S3
    s3_key = f"{uuid.uuid4()}-{file.filename}"
    
    try:
        # Получение S3 клиента
        s3_client = get_s3_client()
        
        # Загрузка файла в S3
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=contents,
            ContentType=file.content_type
        )
        
        # Сохранение метаданных в БД через SQL-функцию
        db_cursor = db.connection().cursor()
        db_cursor.execute(
            "SELECT topotik.create_image(%s, %s, %s, %s, %s)",
            (
                str(user_id),
                file.filename,
                s3_key,
                file.content_type,
                file_size
            )
        )
        image_id = db_cursor.fetchone()[0]
        db.commit()
        
        return {
            "image_id": image_id,
            "file_name": file.filename,
            "s3_key": s3_key,
            "mime_type": file.content_type,
            "file_size": file_size,
            "url": get_image_url(s3_key)
        }
        
    except ClientError as e:
        logger.error(f"Ошибка при загрузке в S3: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при загрузке файла")
    except Exception as e:
        logger.error(f"Ошибка при сохранении метаданных: {str(e)}")
        # В случае ошибки пытаемся удалить загруженный файл из S3
        try:
            s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        except:
            pass
        raise HTTPException(status_code=500, detail="Ошибка при сохранении метаданных файла")

def get_user_images(db: Session, user_id: uuid.UUID):
    """Получение всех изображений пользователя"""
    
    try:
        db_cursor = db.connection().cursor()
        db_cursor.execute(
            "SELECT * FROM topotik.get_user_images(%s)",
            (str(user_id),)
        )
        
        images = []
        for row in db_cursor.fetchall():
            image = {
                "image_id": row[0],
                "file_name": row[1],
                "s3_key": row[2],
                "mime_type": row[3],
                "file_size": row[4],
                "created_at": row[5],
                "url": get_image_url(row[2])
            }
            images.append(image)
            
        return images
    
    except Exception as e:
        logger.error(f"Ошибка при получении изображений пользователя: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при получении изображений")

def get_image(db: Session, image_id: uuid.UUID):
    """Получение информации об изображении по ID"""
    
    try:
        db_cursor = db.connection().cursor()
        db_cursor.execute(
            "SELECT image_id, file_name, s3_key, mime_type, file_size, created_at, user_id FROM topotik.images WHERE image_id = %s",
            (str(image_id),)
        )
        
        row = db_cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Изображение не найдено")
            
        image = {
            "image_id": row[0],
            "file_name": row[1],
            "s3_key": row[2],
            "mime_type": row[3],
            "file_size": row[4],
            "created_at": row[5],
            "user_id": row[6],
            "url": get_image_url(row[2])
        }
            
        return image
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении информации об изображении: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при получении информации об изображении")

def delete_image(db: Session, image_id: uuid.UUID, user_id: uuid.UUID):
    """Удаление изображения из S3 и БД"""
    
    try:
        # Получаем информацию об изображении
        image = get_image(db, image_id)
        
        # Проверяем, что изображение принадлежит пользователю
        if str(image["user_id"]) != str(user_id):
            raise HTTPException(status_code=403, detail="Нет доступа к изображению")
        
        # Удаляем из S3
        s3_client = get_s3_client()
        s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=image["s3_key"])
        
        # Удаляем из БД через функцию
        db_cursor = db.connection().cursor()
        db_cursor.execute(
            "SELECT topotik.delete_image(%s, %s)",
            (str(user_id), str(image_id))
        )
        
        db.commit()
        return {"success": True}
    
    except HTTPException:
        raise
    except ClientError as e:
        logger.error(f"Ошибка при удалении из S3: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при удалении файла из хранилища")
    except Exception as e:
        logger.error(f"Ошибка при удалении изображения: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при удалении изображения")

def get_image_url(s3_key: str) -> str:
    """Генерация публичного URL для доступа к изображению"""
    try:
        # Генерируем pre-signed URL с доступом на 24 часа
        s3_client = get_s3_client()
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': S3_BUCKET_NAME,
                'Key': s3_key
            },
            ExpiresIn=86400  # 24 часа в секундах
        )
        return url
    except Exception as e:
        logger.error(f"Ошибка при создании URL: {str(e)}")
        return None 