# app/routers/collections.py
from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional
from pydantic import UUID4
import uuid
from sqlalchemy.sql import text
import logging
import traceback

from app import schemas, crud
from app.database import get_db
from app.routers.auth import get_user_id_from_token  

router = APIRouter(tags=["collections"])

# Настройка логирования
logger = logging.getLogger(__name__)

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

# Маршруты для работы с маркерами в коллекциях
@router.get("/{collection_id}/markers", response_model=List[schemas.Marker], summary="Получить маркеры коллекции", description="Возвращает список всех маркеров в указанной коллекции.")
def get_collection_markers(
    collection_id: UUID, 
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_user_id_from_token)
):
    """Получить маркеры из коллекции"""
    logger.info(f"Запрос маркеров для коллекции {collection_id} от пользователя {user_id}")
    
    # Проверяем существование коллекции
    collection = crud.get_collection(db, collection_id)
    logger.debug(f"Результат get_collection: {collection}")
    
    if not collection:
        logger.warning(f"Коллекция {collection_id} не найдена")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Коллекция не найдена"
        )
    
    # Проверяем, имеет ли пользователь доступ к коллекции
    has_access = crud.check_collection_access(db, collection_id, user_id, "view")
    logger.debug(f"Результат проверки доступа: {has_access}")
    
    if not has_access:
        logger.warning(f"Пользователь {user_id} не имеет прав для доступа к коллекции {collection_id}")
        # Это исключение должно пробрасываться напрямую, без преобразования в 500
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для доступа к этой коллекции"
        )
    
    try:
        # Получаем маркеры коллекции через SQL-функцию
        logger.debug(f"Выполняем SQL запрос для получения маркеров коллекции {collection_id}")
        markers = db.execute(
            text("SELECT * FROM topotik.get_markers_by_collection(:collection_id)"),
            {"collection_id": str(collection_id)}
        ).fetchall()
        
        logger.debug(f"Получено {len(markers) if markers else 0} маркеров")
        
        # Преобразуем результат в список маркеров, используя явное создание словарей
        # вместо автоматического преобразования ORM-объектов
        result = []
        for marker in markers:
            # Создаем явный словарь с полями маркера, включая map_id
            marker_dict = {
                "marker_id": marker.marker_id,
                "latitude": float(marker.latitude),
                "longitude": float(marker.longitude),
                "title": marker.title,
                "description": marker.description,
                "map_id": marker.map_id
            }
            logger.debug(f"Обрабатываем маркер: {marker_dict}")
            
            # Создаем маркер из словаря, используя direct=True для обхода проверки атрибутов модели
            result.append(schemas.Marker.parse_obj(marker_dict))
            
        logger.info(f"Успешно получены и преобразованы {len(result)} маркеров для коллекции {collection_id}")
        return result
        
    except Exception as e:
        # Логируем полное исключение для отладки
        logger.error(f"Ошибка при получении маркеров коллекции {collection_id}: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении маркеров коллекции: {str(e)}"
        )

@router.post("/{collection_id}/markers", response_model=schemas.GenericResponse, summary="Добавить маркер в коллекцию", description="Добавляет существующий маркер в указанную коллекцию.")
def add_marker_to_collection(
    collection_id: UUID,
    marker_data: dict,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_user_id_from_token)
):
    """Добавить маркер в коллекцию"""
    try:
        # Проверяем существование коллекции
        collection = crud.get_collection(db, collection_id)
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Коллекция не найдена"
            )
        
        # Проверяем, имеет ли пользователь права на редактирование коллекции
        if not crud.check_collection_access(db, collection_id, user_id, "edit"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для редактирования этой коллекции"
            )
        
        # Получаем ID маркера из данных запроса
        marker_id = marker_data.get("marker_id")
        if not marker_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Необходимо указать marker_id"
            )
        
        # Проверяем существование маркера
        marker = crud.get_marker(db, UUID(marker_id))
        if not marker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Маркер не найден"
            )
        
        # Добавляем маркер в коллекцию
        success = db.execute(
            text("SELECT topotik.add_marker_to_collection(:marker_id, :collection_id)"),
            {"marker_id": str(marker_id), "collection_id": str(collection_id)}
        ).scalar()
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось добавить маркер в коллекцию"
            )
            
        return {"success": True, "message": "Маркер успешно добавлен в коллекцию"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при добавлении маркера в коллекцию: {str(e)}"
        )

@router.delete("/{collection_id}/markers/{marker_id}", response_model=schemas.GenericResponse, summary="Удалить маркер из коллекции", description="Удаляет маркер из указанной коллекции, но не удаляет сам маркер.")
def remove_marker_from_collection(
    collection_id: UUID,
    marker_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_user_id_from_token)
):
    """Удалить маркер из коллекции"""
    try:
        # Проверяем существование коллекции
        collection = crud.get_collection(db, collection_id)
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Коллекция не найдена"
            )
        
        # Проверяем, имеет ли пользователь права на редактирование коллекции
        if not crud.check_collection_access(db, collection_id, user_id, "edit"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для редактирования этой коллекции"
            )
        
        # Проверяем существование маркера
        marker = crud.get_marker(db, marker_id)
        if not marker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Маркер не найден"
            )
        
        # Удаляем маркер из коллекции
        success = db.execute(
            text("SELECT topotik.remove_marker_from_collection(:marker_id, :collection_id)"),
            {"marker_id": str(marker_id), "collection_id": str(collection_id)}
        ).scalar()
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось удалить маркер из коллекции"
            )
            
        return {"success": True, "message": "Маркер успешно удален из коллекции"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при удалении маркера из коллекции: {str(e)}"
        )

@router.post("/{source_collection_id}/move_marker/{marker_id}/to/{target_collection_id}", 
             response_model=schemas.GenericResponse,
             summary="Переместить маркер между коллекциями",
             description="Перемещает маркер из одной коллекции в другую в рамках одной транзакции.")
def move_marker_between_collections(
    source_collection_id: UUID,
    marker_id: UUID,
    target_collection_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_user_id_from_token)
):
    """Переместить маркер из одной коллекции в другую"""
    logger.info(f"Запрос на перемещение маркера {marker_id} из коллекции {source_collection_id} в коллекцию {target_collection_id}")
    
    try:
        # Проверяем доступ к исходной коллекции
        if not crud.check_collection_access(db, source_collection_id, user_id, "edit"):
            logger.warning(f"У пользователя {user_id} нет прав на редактирование исходной коллекции {source_collection_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для редактирования исходной коллекции"
            )
        
        # Проверяем доступ к целевой коллекции
        if not crud.check_collection_access(db, target_collection_id, user_id, "edit"):
            logger.warning(f"У пользователя {user_id} нет прав на редактирование целевой коллекции {target_collection_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для редактирования целевой коллекции"
            )
        
        # Вызываем SQL-функцию для перемещения маркера
        result = db.execute(
            text("""
                SELECT topotik.move_marker_between_collections(
                    :marker_id, 
                    :source_collection_id, 
                    :target_collection_id
                )
            """),
            {
                "marker_id": str(marker_id),
                "source_collection_id": str(source_collection_id),
                "target_collection_id": str(target_collection_id)
            }
        ).scalar()
        
        # Явный коммит транзакции
        db.commit()
        
        if result:
            logger.info(f"Маркер {marker_id} успешно перемещен из коллекции {source_collection_id} в коллекцию {target_collection_id}")
            return {"success": True, "message": "Маркер успешно перемещен"}
        else:
            logger.error(f"Не удалось переместить маркер {marker_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось переместить маркер"
            )
    except Exception as e:
        logger.error(f"Ошибка при перемещении маркера: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при перемещении маркера: {str(e)}"
        )
