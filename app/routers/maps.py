# app/routers/maps.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional, Any

from app import schemas, crud
from app.database import get_db
from app.routers.auth import get_user_id_from_token

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
def create_map(map_in: schemas.MapCreate, db: Session = Depends(get_db), user_id: UUID = Depends(get_user_id_from_token)):
    try:
        return crud.create_map(db, map_in, user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании карты: {str(e)}"
        )

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
