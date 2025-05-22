import os
import uuid
import datetime
import logging
from typing import List, Optional, BinaryIO, Dict, Any, Union
import boto3
import aiohttp
from botocore.exceptions import NoCredentialsError, ClientError
from fastapi import UploadFile, HTTPException
import aiofiles
import aioboto3
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import tempfile
import requests
from botocore.auth import S3SigV4Auth
from botocore.awsrequest import AWSRequest
import json
from urllib.parse import urlparse

from ..config.s3_config import settings
from ..database import get_async_session
from ..models import Image, Map
from ..schemas import ImageResponse, ImageUploadResponse

logger = logging.getLogger(__name__)

class ImageService:
    """Сервис для работы с изображениями"""
    
    def __init__(self):
        """Инициализация сервиса с настройками S3"""
        self.s3_key_id = settings.s3_access_key_id
        self.s3_secret = settings.s3_secret_access_key
        self.s3_endpoint = settings.s3_endpoint
        self.s3_region = settings.s3_region
        self.s3_bucket = settings.s3_bucket_name
        
        logger.debug(f"ImageService инициализирован с настройками:")
        logger.debug(f"S3 endpoint: {self.s3_endpoint}")
        logger.debug(f"S3 bucket: {self.s3_bucket}")
        logger.debug(f"S3 region: {self.s3_region}")
        logger.debug(f"S3 key ID: {'Задано' if self.s3_key_id else 'Не задано'}")
        logger.debug(f"S3 secret key: {'Задано' if self.s3_secret else 'Не задано'}")
        
    async def _get_db_session(self) -> AsyncSession:
        """Получаем сессию для работы с базой данных"""
        db = get_async_session()
        async for session in db:
            return session

    async def upload_image(
        self, 
        file: UploadFile, 
        user_id: uuid.UUID, 
        description: Optional[str] = None
    ) -> ImageResponse:
        """
        Загрузка файла изображения в S3 хранилище.
        
        Аргументы:
            file: Загружаемый файл
            user_id: ID пользователя, загрузившего файл
            description: Описание изображения (опционально, не используется, т.к. отсутствует в БД)
            
        Возвращает:
            Объект ImageResponse с данными о загруженном изображении
        """
        # Генерируем уникальное имя файла
        original_filename = file.filename
        extension = original_filename.split(".")[-1] if "." in original_filename else ""
        new_filename = f"{uuid.uuid4()}.{extension}"
        
        logger.debug(f"Загрузка изображения: {original_filename}, новое имя: {new_filename}")
        logger.debug(f"Пользователь: {user_id}, описание: {description}")
    
        try:
            # Загружаем файл из памяти
            file_content = await file.read()
            content_type = file.content_type or "application/octet-stream"
            
            logger.debug(f"Загружаем в S3 файл размером {len(file_content)} байт, тип: {content_type}")
            
            # Генерируем ключ S3
            s3_key = f"map_images/{new_filename}"
            
            # Используем напрямую requests для загрузки файла в S3 без boto3
            # 1. Создаем полный URL для доступа к объекту в S3
            endpoint_url = f"https://{self.s3_endpoint}"
            url = f"{endpoint_url}/{self.s3_bucket}/{s3_key}"
            
            # 2. Используем boto3 только для генерации полномочий, но не для загрузки
            s3_client = boto3.client(
                's3',
                aws_access_key_id=self.s3_key_id,
                aws_secret_access_key=self.s3_secret,
                endpoint_url=endpoint_url,
                region_name=self.s3_region
            )
            
            # 3. Генерируем пресигнированный URL (он не будет иметь проблемного заголовка)
            presigned_url = s3_client.generate_presigned_url(
                ClientMethod='put_object',
                Params={
                    'Bucket': self.s3_bucket,
                    'Key': s3_key,
                    'ContentType': content_type
                },
                ExpiresIn=3600
            )
            
            # 4. Используем requests с пресигнированным URL для загрузки
            response = requests.put(
                presigned_url,
                data=file_content,
                headers={'Content-Type': content_type}
            )
            
            if response.status_code != 200:
                raise Exception(f"Ошибка при загрузке в S3: статус {response.status_code}, ответ: {response.text}")
                
            # Формируем URL к изображению (но не сохраняем его в БД)
            file_url = f"https://{self.s3_endpoint}/{self.s3_bucket}/{s3_key}"
            logger.debug(f"URL изображения: {file_url}")
            
            # Сохраняем информацию в базе данных
            db = await self._get_db_session()
            
            # Создаем запись
            image_id = uuid.uuid4()
            current_time = datetime.datetime.now()
            
            logger.debug(f"Сохраняем запись в БД с ID: {image_id}")
            
            # Создаем объект Image только с полями, существующими в БД
            new_image = Image(
                image_id=image_id,
                file_name=original_filename,
                s3_key=s3_key,
                mime_type=content_type,
                file_size=len(file_content),
                user_id=user_id,
                created_at=current_time
            )
            
            db.add(new_image)
            await db.commit()
            await db.refresh(new_image)
            
            logger.debug(f"Запись в БД успешно создана")
            
            # Возвращаем данные о загруженном изображении
            # Примечание: url не сохраняется в базе данных, но нужен для ответа
            return ImageResponse(
                id=str(new_image.image_id),
                filename=new_image.file_name,
                url=file_url,  # Используем локальную переменную, а не поле из БД
                uploaded_by=str(new_image.user_id),
                created_at=new_image.created_at
            )
            
        except NoCredentialsError as e:
            logger.error(f"Ошибка доступа к S3: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail="Не удалось получить доступ к S3. Проверьте ключи доступа."
            )
        except ClientError as e:
            logger.error(f"Ошибка S3 клиента: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Ошибка при загрузке в S3: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Необработанная ошибка: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Ошибка при загрузке изображения: {str(e)}"
            )
            
    async def get_image_by_id(self, image_id: str) -> Optional[Image]:
        """
        Получение информации об изображении по его ID.
        
        Аргументы:
            image_id: ID изображения
            
        Возвращает:
            Объект Image из БД или None, если изображение не найдено
        """
        try:
            db = await self._get_db_session()
            
            # Запрос к БД
            query = select(Image).where(Image.image_id == image_id)
            result = await db.execute(query)
            image = result.scalar_one_or_none()
            
            return image
        except Exception as e:
            logger.error(f"Ошибка при получении изображения {image_id}: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Ошибка при получении изображения: {str(e)}"
            )

    async def get_user_images(
        self, 
        user_id: uuid.UUID, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[ImageResponse]:
        """
        Получение списка изображений пользователя.
        
        Аргументы:
            user_id: ID пользователя
            limit: Максимальное количество изображений
            offset: Смещение для пагинации
            
        Возвращает:
            Список объектов ImageResponse
        """
        try:
            db = await self._get_db_session()
            
            # Запрос к БД
            query = (select(Image)
                    .where(Image.user_id == user_id)
                    .order_by(Image.created_at.desc())
                    .limit(limit)
                    .offset(offset))
            
            result = await db.execute(query)
            images = result.scalars().all()
            
            # Преобразуем в схему ответа
            return [
                ImageResponse(
                    id=str(image.image_id),
                    filename=image.file_name,
                    url=f"https://{self.s3_endpoint}/{self.s3_bucket}/{image.s3_key}",
                    uploaded_by=str(image.user_id),
                    created_at=image.created_at
                )
                for image in images
            ]
        except Exception as e:
            logger.error(f"Ошибка при получении списка изображений для {user_id}: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Ошибка при получении списка изображений: {str(e)}"
            )

    async def delete_image(self, image_id: str) -> bool:
        """
        Удаление изображения из S3 и из базы данных.
        
        Аргументы:
            image_id: ID изображения
            
        Возвращает:
            True в случае успешного удаления, False в противном случае
        """
        try:
            db = await self._get_db_session()
            
            # Получаем информацию об изображении
            query = select(Image).where(Image.image_id == image_id)
            result = await db.execute(query)
            image = result.scalar_one_or_none()
            
            if not image:
                return False
            
            # Удаляем из S3 с пресигнированным URL
            s3_client = boto3.client(
                's3',
                aws_access_key_id=self.s3_key_id,
                aws_secret_access_key=self.s3_secret,
                endpoint_url=f"https://{self.s3_endpoint}",
                region_name=self.s3_region
            )
            
            # Создаем пресигнированный URL для удаления
            url = s3_client.generate_presigned_url(
                ClientMethod='delete_object',
                Params={
                    'Bucket': self.s3_bucket,
                    'Key': image.s3_key
                },
                ExpiresIn=3600
            )
            
            # Выполняем удаление через requests
            response = requests.delete(url)
            
            if response.status_code >= 300:
                raise Exception(f"Ошибка удаления из S3: {response.status_code} {response.text}")
        
            # Удаляем из БД
            await db.delete(image)
            await db.commit()
            
            return True
        except NoCredentialsError as e:
            logger.error(f"Ошибка доступа к S3 при удалении {image_id}: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail="Не удалось получить доступ к S3. Проверьте ключи доступа."
            )
        except ClientError as e:
            logger.error(f"Ошибка S3 клиента при удалении {image_id}: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Ошибка при удалении из S3: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Необработанная ошибка при удалении {image_id}: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Ошибка при удалении изображения: {str(e)}"
            )

    async def is_image_used_in_maps(self, image_id: str) -> bool:
        """
        Проверка, используется ли изображение в каких-либо картах.
        
        Аргументы:
            image_id: ID изображения
            
        Возвращает:
            True если изображение используется в картах, False в противном случае
        """
        try:
            db = await self._get_db_session()
            
            # Проверяем использование в картах
            query = select(Map).where(Map.background_image_id == image_id)
            result = await db.execute(query)
            maps = result.scalars().all()
            
            return len(maps) > 0
        except Exception as e:
            logger.error(f"Ошибка при проверке использования изображения {image_id}: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Ошибка при проверке использования изображения: {str(e)}"
            )

    def get_image_url(self, image_id=None, s3_key=None):
        """
        Получает полный URL изображения на основе его ID или s3_key
        
        Args:
            image_id: UUID изображения 
            s3_key: Ключ S3 для прямого доступа
            
        Returns:
            str: Полный URL для доступа к изображению
        """
        if s3_key:
            return f"https://{self.s3_endpoint}/{self.s3_bucket}/{s3_key}"
        elif image_id:
            # Для случаев, когда у нас есть только ID, но нет s3_key
            # Предполагаем что изображение хранится в стандартной папке с названием image_id
            return f"https://{self.s3_endpoint}/{self.s3_bucket}/map_images/{str(image_id)}.png"
        else:
            logger.error("Невозможно сформировать URL: не предоставлен ни image_id, ни s3_key")
            return None
            
    def get_s3_client(self):
        """
        Создает и возвращает клиент boto3 S3 для работы с хранилищем
        
        Returns:
            boto3.client: Настроенный клиент S3
        """
        import boto3
        
        # Создаем клиент S3 с настройками
        s3_client = boto3.client(
            's3',
            aws_access_key_id=self.s3_key_id,
            aws_secret_access_key=self.s3_secret,
            endpoint_url=f"https://{self.s3_endpoint}",
            region_name=self.s3_region
        )
        
        return s3_client 