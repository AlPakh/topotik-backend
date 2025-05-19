# app/routers/maps.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional, Any
import uuid

from app import schemas, crud, models
from app.database import get_db
from app.routers.auth import get_user_id_from_token, get_current_user
from app.services import image_service

router = APIRouter(tags=["maps"])

@router.get("/", response_model=List[schemas.Map], summary="Получить список всех карт", description="Возвращает список всех карт с пагинацией. Доступно для всех пользователей.")
def list_maps(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_maps(db, skip=skip, limit=limit)

@router.get("/user", response_model=List[schemas.Map], summary="Получить карты пользователя", description="Возвращает список всех карт, принадлежащих текущему пользователю.")
def get_user_maps(db: Session = Depends(get_db), user_id: UUID = Depends(get_user_id_from_token)):
    return crud.get_user_maps(db, user_id)

@router.get("/{map_id}", response_model=schemas.Map, summary="Получить карту по ID", description="Возвращает детальную информацию о карте по её идентификатору.")
def get_map(map_id: UUID, db: Session = Depends(get_db)):
    m = crud.get_map(db, map_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Карта не найдена")
    return m

@router.post("/", response_model=schemas.Map, status_code=status.HTTP_201_CREATED, summary="Создать новую карту", description="Создает новую карту для текущего пользователя. Может быть карта OSM (реальная) или пользовательская карта.")
def create_map(
    map_data: schemas.MapCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Создание новой карты.
    
    Можно указать background_image_id для создания пользовательской карты.
    Если указан background_image_id, то is_custom автоматически устанавливается в True.
    """
    # Проверяем наличие изображения, если указан его ID
    if map_data.background_image_id:
        try:
            # Сначала проверяем формат ID
            try:
                image_uuid = uuid.UUID(str(map_data.background_image_id))
            except ValueError:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Неверный формат ID изображения: {map_data.background_image_id}. Должен быть UUID."
                )
                
            db_cursor = db.connection().cursor()
            db_cursor.execute(
                "SELECT 1 FROM topotik.images WHERE image_id = %s",
                (str(image_uuid),)
            )
            if db_cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail=f"Указанное изображение {image_uuid} не найдено")
            
            # Устанавливаем флаг пользовательской карты
            map_data.is_custom = True
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Ошибка при проверке изображения: {str(e)}"
            )
    
    return crud.create_map(db, map_data, current_user.user_id)

@router.put("/{map_id}", response_model=schemas.Map, summary="Обновить карту", description="Обновляет данные существующей карты")
def update_map(
    map_id: UUID, 
    map_data: schemas.MapUpdate, 
    db: Session = Depends(get_db), 
    user_id: UUID = Depends(get_user_id_from_token)
):
    # Проверяем, что пользователь имеет доступ к карте
    if not crud.check_map_ownership(db, map_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для редактирования этой карты"
        )
    
    # Запрашиваем объект карты для проверки существования
    map_obj = crud.get_map(db, map_id)
    if not map_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Карта не найдена"
        )
    
    # Обновляем карту
    updated_map = crud.update_map(db, map_id, map_data)
    if not updated_map:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Карта не найдена или возникла ошибка при обновлении"
        )
    return updated_map

@router.put("/{map_id}/move", response_model=schemas.GenericResponse, summary="Переместить карту в папку", description="Перемещает карту в указанную папку. Карта может находиться только в одной папке или быть вне папок.")
def move_map_to_folder(
    map_id: UUID, 
    move_data: schemas.MapMove, 
    db: Session = Depends(get_db), 
    user_id: UUID = Depends(get_user_id_from_token)
):
    # Проверка доступа пользователя к карте
    if not crud.check_map_ownership(db, map_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для перемещения этой карты"
        )
        
    try:
        result = crud.move_map_to_folder(db, user_id, map_id, move_data.folder_id)
        if result:
            return {"success": True, "message": "Карта успешно перемещена"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось переместить карту. Проверьте права доступа к папке назначения."
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete("/{map_id}", response_model=schemas.GenericResponse, summary="Удалить карту", description="Удаляет карту и все связанные с ней данные")
def delete_map(
    map_id: UUID, 
    db: Session = Depends(get_db), 
    user_id: UUID = Depends(get_user_id_from_token)
):
    # Проверяем, что пользователь имеет доступ к карте
    if not crud.check_map_ownership(db, map_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для удаления этой карты"
        )
    
    if crud.delete_map(db, map_id):
        return {"success": True, "message": "Карта успешно удалена"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Карта не найдена или возникла ошибка при удалении"
        )

@router.put("/{map_id}/background-image", response_model=schemas.Map, summary="Обновить фоновое изображение карты", description="Обновляет фоновое изображение для карты. Если изображение установлено, карта автоматически помечается как пользовательская (is_custom = True).")
def update_map_background(
    map_id: uuid.UUID,
    background_data: schemas.MapBackgroundUpdate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Обновление фонового изображения карты.
    
    Устанавливает фоновое изображение для карты. Если изображение установлено,
    карта автоматически помечается как пользовательская (is_custom = True).
    """
    print(f"[DEBUG] Обновление фонового изображения для карты {map_id}")
    print(f"[DEBUG] Полученные данные: {background_data}")
    
    # Получаем карту через ORM
    map_entity = crud.get_map(db, map_id)
    
    if not map_entity:
        print(f"[DEBUG] Карта {map_id} не найдена")
        raise HTTPException(status_code=404, detail="Карта не найдена")
    
    # Проверяем владение картой
    if not crud.check_map_ownership(db, map_id, current_user.user_id):
        print(f"[DEBUG] Пользователь {current_user.user_id} не имеет прав на карту {map_id}")
        raise HTTPException(
            status_code=403, 
            detail="У вас нет прав на редактирование этой карты"
        )
    
    # Обработка ID изображения
    image_uuid = None
    if background_data.background_image_id:
        try:
            # Проверяем формат ID
            image_uuid = uuid.UUID(str(background_data.background_image_id))
            print(f"[DEBUG] Установлен ID изображения: {image_uuid}")
            
            # Проверяем существование изображения через ORM
            image_exists = db.query(models.Image).filter(
                models.Image.image_id == image_uuid
            ).first()
            
            if not image_exists:
                print(f"[DEBUG] Изображение {image_uuid} не найдено в БД")
                raise HTTPException(
                    status_code=404, 
                    detail=f"Изображение с ID {image_uuid} не найдено"
                )
            print(f"[DEBUG] Изображение {image_uuid} найдено в БД")
        except ValueError:
            print(f"[DEBUG] Неверный формат UUID: {background_data.background_image_id}")
            raise HTTPException(
                status_code=400, 
                detail=f"Неверный формат ID изображения: {background_data.background_image_id}"
            )
    
    try:
        # Обновляем карту через ORM
        map_entity.background_image_id = image_uuid
        if image_uuid:
            map_entity.is_custom = True
        
        db.add(map_entity)
        db.commit()
        db.refresh(map_entity)
        print(f"[DEBUG] Карта {map_id} обновлена, background_image_id: {map_entity.background_image_id}")
        
        # Получаем информацию о изображении, если оно установлено
        background_image_url = None
        if map_entity.background_image_id:
            try:
                # Получаем информацию о изображении из БД
                image = db.query(models.Image).filter(
                    models.Image.image_id == map_entity.background_image_id
                ).first()
                
                if image and image.s3_key:
                    # Формируем URL изображения
                    background_image_url = f"https://s3.eu-central-003.backblazeb2.com/bex-sber-bucket/{image.s3_key}"
                    print(f"[DEBUG] URL изображения на основе s3_key: {background_image_url}")
                else:
                    # Если не можем получить s3_key, формируем URL на основе UUID
                    background_image_url = f"https://s3.eu-central-003.backblazeb2.com/bex-sber-bucket/map_images/{str(map_entity.background_image_id)}.png"
                    print(f"[DEBUG] URL изображения на основе UUID: {background_image_url}")
            except Exception as e:
                # Логируем ошибку, но не прерываем выполнение
                print(f"[DEBUG] Ошибка при получении URL изображения: {str(e)}")
                # Формируем запасной URL на основе UUID
                background_image_url = f"https://s3.eu-central-003.backblazeb2.com/bex-sber-bucket/map_images/{str(map_entity.background_image_id)}.png"
                print(f"[DEBUG] Запасной URL изображения: {background_image_url}")
        
        # Формируем ответ
        response = {
            "map_id": str(map_entity.map_id),
            "title": map_entity.title,
            "map_type": map_entity.map_type,
            "is_public": map_entity.is_public,
            "created_at": map_entity.created_at,
            "background_image_id": str(map_entity.background_image_id) if map_entity.background_image_id else None,
            "is_custom": map_entity.is_custom,
            "description": None,  # Добавляем поле description, требуемое схемой
            "background_image_url": background_image_url  # Добавляем URL изображения
        }
        
        print(f"[DEBUG] Возвращаемый ответ: {response}")
        return response
    except Exception as e:
        db.rollback()
        print(f"[DEBUG] Ошибка при обновлении карты: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Ошибка при обновлении фонового изображения карты: {str(e)}"
        )

@router.delete("/{map_id}/background", response_model=schemas.MapResponse)
def clear_map_background_image(
    map_id: uuid.UUID,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Удаление фонового изображения карты"""
    
    # Вызываем хранимую функцию для удаления фонового изображения
    db_cursor = db.connection().cursor()
    try:
        db_cursor.execute(
            "SELECT topotik.clear_map_background_image(%s, %s)",
            (str(current_user.user_id), str(map_id))
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    
    # Возвращаем обновленную карту
    map_data = crud.get_map(db, map_id)
    if not map_data:
        raise HTTPException(status_code=404, detail="Карта не найдена")
    
    return map_data
