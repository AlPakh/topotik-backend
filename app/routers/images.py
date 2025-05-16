import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import image_service
from app.routers.auth import get_current_user
from app.schemas import ImageResponse, ImageListResponse, ImageDeleteResponse

router = APIRouter()

@router.post("", response_model=ImageResponse)
async def upload_image(
    file: UploadFile = File(...),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Загрузка изображения"""
    result = await image_service.upload_image(db, file, current_user.user_id)
    return result

@router.get("", response_model=List[ImageResponse])
def get_user_images(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение всех изображений пользователя"""
    return image_service.get_user_images(db, current_user.user_id)

@router.get("/{image_id}", response_model=ImageResponse)
def get_image(
    image_id: uuid.UUID,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение информации о конкретном изображении"""
    image = image_service.get_image(db, image_id)
    
    # Если изображение не принадлежит пользователю, проверяем доступность
    if str(image["user_id"]) != str(current_user.user_id):
        # Здесь можно добавить логику проверки общедоступности
        # Например, проверка является ли изображение частью публичной карты
        pass
    
    return image

@router.delete("/{image_id}", response_model=ImageDeleteResponse)
def delete_image(
    image_id: uuid.UUID,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Удаление изображения"""
    return image_service.delete_image(db, image_id, current_user.user_id) 