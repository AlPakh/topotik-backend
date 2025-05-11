# app/routers/collections.py
from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional
from pydantic import UUID4
import uuid

from app import schemas, crud
from app.database import get_db
from app.routers.auth import get_user_id_from_token  

router = APIRouter(tags=["collections"])

@router.get("/", response_model=List[schemas.Collection], summary="Получить список коллекций", description="Возвращает список всех доступных коллекций с пагинацией.")
def list_collections(
    skip: int = 0, 
    limit: int = 100, 
    map_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_user_id_from_token)
):
    """Получить список коллекций с возможностью фильтрации по карте"""
    if map_id:
        # Проверяем, что пользователь имеет доступ к карте
        if not crud.check_map_ownership(db, map_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для доступа к этой карте"
            )
        return crud.get_collections_by_map(db, map_id)
    else:
        return crud.get_collections(db, skip=skip, limit=limit)

@router.get("/{collection_id}", response_model=schemas.Collection, summary="Получить коллекцию по ID", description="Возвращает детальную информацию о коллекции по её идентификатору.")
def get_collection(
    collection_id: UUID, 
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_user_id_from_token)
):
    """Получить информацию о коллекции по ID"""
    c = crud.get_collection(db, collection_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Коллекция не найдена")
    
    # Проверяем, имеет ли пользователь доступ к коллекции
    if not crud.check_collection_access(db, collection_id, user_id, "view"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для доступа к этой коллекции"
        )
    
    return c

@router.post("/", response_model=schemas.Collection, status_code=status.HTTP_201_CREATED, summary="Создать новую коллекцию", description="Создает новую коллекцию маркеров для указанной карты. Коллекция принадлежит текущему пользователю.")
def create_collection(
    collection_in: schemas.CollectionCreate, 
    db: Session = Depends(get_db), 
    user_id: UUID = Depends(get_user_id_from_token)
):
    """Создать новую коллекцию для карты"""
    try:
        return crud.create_collection(db, collection_in, user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании коллекции: {str(e)}"
        )

@router.put("/{collection_id}", response_model=schemas.Collection, summary="Обновить коллекцию", description="Обновляет свойства коллекции, такие как название и настройки доступа.")
def update_collection(
    collection_id: UUID, 
    collection_in: schemas.CollectionBase, 
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_user_id_from_token)
):
    """Обновить существующую коллекцию"""
    try:
        collection = crud.update_collection(db, collection_id, collection_in.dict(exclude_unset=True), user_id)
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Коллекция не найдена"
            )
        return collection
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении коллекции: {str(e)}"
        )

@router.delete("/{collection_id}", response_model=schemas.GenericResponse, summary="Удалить коллекцию", description="Удаляет коллекцию и связи с маркерами. Сами маркеры при этом не удаляются.")
def delete_collection(
    collection_id: UUID, 
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_user_id_from_token)
):
    """Удалить коллекцию"""
    try:
        collection = crud.delete_collection(db, collection_id, user_id)
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Коллекция не найдена"
            )
        return {"success": True, "message": "Коллекция успешно удалена"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при удалении коллекции: {str(e)}"
        )
