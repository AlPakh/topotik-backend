# app/routers/markers.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional
from sqlalchemy.sql import text

from app import schemas, crud
from app.database import get_db
from app.routers.auth import get_user_id_from_token

router = APIRouter(tags=["markers"])

@router.get("/", response_model=List[schemas.Marker], summary="Получить список маркеров", description="Возвращает список маркеров для указанной карты с пагинацией.")
def list_markers(map_id: UUID, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user_id: UUID = Depends(get_user_id_from_token)):
    """Получить список маркеров для указанной карты"""
    # Проверяем, что пользователь имеет доступ к карте
    if not crud.check_map_ownership(db, map_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для доступа к этой карте"
        )
        
    return crud.get_markers_by_map(db, map_id, skip=skip, limit=limit)

@router.get("/{marker_id}", response_model=schemas.Marker, summary="Получить маркер по ID", description="Возвращает детальную информацию о маркере по его идентификатору.")
def get_marker(marker_id: UUID, db: Session = Depends(get_db)):
    """Получить информацию о маркере по ID"""
    m = crud.get_marker(db, marker_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Маркер не найден")
    return m

@router.post("/", response_model=schemas.Marker, status_code=status.HTTP_201_CREATED, summary="Создать новый маркер", description="Создает новый маркер на указанной карте с заданными координатами и свойствами.")
def create_marker(marker_in: schemas.MarkerCreate, db: Session = Depends(get_db), user_id: UUID = Depends(get_user_id_from_token)):
    """Создать новый маркер"""
    try:
        # Проверяем, что пользователь имеет доступ к карте
        if not marker_in.map_id or not crud.check_map_ownership(db, marker_in.map_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для доступа к этой карте"
            )
            
        return crud.create_marker(db, marker_in)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании маркера: {str(e)}"
        )

@router.put("/{marker_id}", response_model=schemas.Marker, summary="Обновить маркер", description="Обновляет данные маркера - координаты, название, описание.")
def update_marker(
    marker_id: UUID, 
    marker_in: schemas.MarkerBase, 
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_user_id_from_token)
):
    """Обновить существующий маркер"""
    try:
        # Получаем маркер
        marker = crud.get_marker(db, marker_id)
        if not marker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Маркер не найден"
            )
        
        # Проверка доступа (через коллекции)
        collections_with_marker = db.execute(
            text("""
                SELECT c.map_id
                FROM topotik.collections c
                JOIN topotik.markers_collections mc ON c.collection_id = mc.collection_id
                WHERE mc.marker_id = :marker_id
            """),
            {"marker_id": str(marker_id)}
        ).fetchall()
        
        has_access = False
        for row in collections_with_marker:
            if crud.check_map_ownership(db, row.map_id, user_id):
                has_access = True
                break
                
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для обновления этого маркера"
            )
        
        # Обновляем маркер
        return crud.update_marker(db, marker_id, marker_in.dict(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении маркера: {str(e)}"
        )

@router.delete("/{marker_id}", response_model=schemas.GenericResponse, summary="Удалить маркер", description="Удаляет маркер и все связанные с ним данные (статьи). Операция необратима.")
def delete_marker(
    marker_id: UUID, 
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_user_id_from_token)
):
    """Удалить маркер и связанные с ним данные"""
    try:
        # Получаем маркер
        marker = crud.get_marker(db, marker_id)
        if not marker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Маркер не найден"
            )
        
        # Проверка доступа (через коллекции)
        collections_with_marker = db.execute(
            text("""
                SELECT c.map_id
                FROM topotik.collections c
                JOIN topotik.markers_collections mc ON c.collection_id = mc.collection_id
                WHERE mc.marker_id = :marker_id
            """),
            {"marker_id": str(marker_id)}
        ).fetchall()
        
        has_access = False
        for row in collections_with_marker:
            if crud.check_map_ownership(db, row.map_id, user_id):
                has_access = True
                break
                
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для удаления этого маркера"
            )
        
        # Удаляем маркер
        crud.delete_marker(db, marker_id)
        return {"success": True, "message": "Маркер успешно удален"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Ошибка при удалении маркера: {str(e)}"
        )
