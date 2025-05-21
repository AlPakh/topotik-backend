# app/routers/collections.py
from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional
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
        # Получаем маркеры коллекции через прямой SQL запрос вместо функции
        logger.debug(f"Выполняем SQL запрос для получения маркеров коллекции {collection_id}")
        
        # Прямой запрос к таблицам вместо вызова функции PostgreSQL
        query = text("""
            SELECT m.marker_id, m.latitude, m.longitude, m.title, m.description, c.map_id
            FROM topotik.markers m
            JOIN topotik.markers_collections mc ON m.marker_id = mc.marker_id
            JOIN topotik.collections c ON mc.collection_id = c.collection_id
            WHERE mc.collection_id = :collection_id
        """)
        
        markers = db.execute(query, {"collection_id": str(collection_id)}).fetchall()
        
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
            
            # Создаем маркер из словаря
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
        
        # Удаляем маркер из всех других коллекций, принадлежащих к той же карте
        try:
            # Получаем map_id текущей коллекции
            map_id_query = text("""
                SELECT map_id FROM topotik.collections
                WHERE collection_id = :collection_id
            """)
            map_id_result = db.execute(map_id_query, {"collection_id": str(collection_id)}).fetchone()
            
            if map_id_result:
                map_id = map_id_result.map_id
                
                # Получаем все коллекции этой карты
                collections_query = text("""
                    SELECT collection_id FROM topotik.collections
                    WHERE map_id = :map_id AND collection_id != :collection_id
                """)
                collections = db.execute(
                    collections_query, 
                    {"map_id": str(map_id), "collection_id": str(collection_id)}
                ).fetchall()
                
                # Удаляем маркер из всех других коллекций этой карты
                if collections:
                    collection_ids = [str(row.collection_id) for row in collections]
                    collection_ids_str = ",".join([f"'{cid}'" for cid in collection_ids])
                    
                    delete_query = text(f"""
                        DELETE FROM topotik.markers_collections
                        WHERE marker_id = :marker_id 
                        AND collection_id IN ({collection_ids_str})
                    """)
                    
                    db.execute(delete_query, {"marker_id": str(marker_id)})
                    db.commit()
                    
                    logger.info(f"Маркер {marker_id} удален из других коллекций карты {map_id}")
        except Exception as e:
            logger.error(f"Ошибка при удалении маркера из других коллекций: {str(e)}")
            logger.error(traceback.format_exc())
            # Продолжаем выполнение, даже если не удалось удалить из других коллекций
        
        # Добавляем маркер в коллекцию
        try:
            # Прямой SQL-запрос вместо вызова функции
            insert_query = text("""
                INSERT INTO topotik.markers_collections (marker_id, collection_id)
                VALUES (:marker_id, :collection_id)
                ON CONFLICT (marker_id, collection_id) DO NOTHING
                RETURNING true
            """)
            
            result = db.execute(
                insert_query,
                {"marker_id": str(marker_id), "collection_id": str(collection_id)}
            ).scalar()
            
            db.commit()
            
            return {"success": True, "message": "Маркер успешно добавлен в коллекцию"}
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка при добавлении маркера в коллекцию: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка при добавлении маркера в коллекцию: {str(e)}"
            )
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при добавлении маркера в коллекцию: {str(e)}")
        logger.error(traceback.format_exc())
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
        try:
            # Прямой SQL-запрос вместо вызова функции
            delete_query = text("""
                DELETE FROM topotik.markers_collections
                WHERE marker_id = :marker_id AND collection_id = :collection_id
                RETURNING true
            """)
            
            result = db.execute(
                delete_query,
                {"marker_id": str(marker_id), "collection_id": str(collection_id)}
            ).scalar()
            
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Маркер не найден в указанной коллекции"
                )
                
            return {"success": True, "message": "Маркер успешно удален из коллекции"}
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            logger.error(f"Ошибка при удалении маркера из коллекции: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка при удалении маркера из коллекции: {str(e)}"
            )
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
    try:
        # Проверка существования исходной коллекции
        source_collection = crud.get_collection(db, source_collection_id)
        if not source_collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Исходная коллекция не найдена"
            )
        
        # Проверка существования целевой коллекции
        target_collection = crud.get_collection(db, target_collection_id)
        if not target_collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Целевая коллекция не найдена"
            )
        
        # Проверка доступа к исходной коллекции
        if not crud.check_collection_access(db, source_collection_id, user_id, "edit"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для редактирования исходной коллекции"
            )
        
        # Проверка доступа к целевой коллекции
        if not crud.check_collection_access(db, target_collection_id, user_id, "edit"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для редактирования целевой коллекции"
            )
        
        # Проверка существования маркера в исходной коллекции
        if not db.execute(
            text("""
                SELECT 1 FROM topotik.markers_collections
                WHERE marker_id = :marker_id AND collection_id = :collection_id
            """),
            {"marker_id": str(marker_id), "collection_id": str(source_collection_id)}
        ).fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Маркер не найден в исходной коллекции"
            )
        
        # Убедимся, что коллекции принадлежат одной карте
        if source_collection.map_id != target_collection.map_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Исходная и целевая коллекции должны принадлежать одной карте"
            )
        
        # Удаляем маркер из всех коллекций той же карты
        map_id = source_collection.map_id
        
        # Получаем все коллекции этой карты
        collections_query = text("""
            SELECT collection_id FROM topotik.collections
            WHERE map_id = :map_id AND collection_id != :target_collection_id
        """)
        collections = db.execute(
            collections_query, 
            {"map_id": str(map_id), "target_collection_id": str(target_collection_id)}
        ).fetchall()
        
        # Удаляем маркер из всех коллекций, кроме целевой
        if collections:
            collection_ids = [str(row.collection_id) for row in collections]
            collection_ids_str = ",".join([f"'{cid}'" for cid in collection_ids])
            
            delete_query = text(f"""
                DELETE FROM topotik.markers_collections
                WHERE marker_id = :marker_id 
                AND collection_id IN ({collection_ids_str})
            """)
            
            db.execute(delete_query, {"marker_id": str(marker_id)})
            
            logger.info(f"Маркер {marker_id} удален из всех коллекций карты {map_id}, кроме целевой")
        
        # Добавляем маркер в целевую коллекцию
        try:
            # Прямой SQL-запрос вместо вызова функции
            insert_query = text("""
                INSERT INTO topotik.markers_collections (marker_id, collection_id)
                VALUES (:marker_id, :collection_id)
                ON CONFLICT (marker_id, collection_id) DO NOTHING
                RETURNING true
            """)
            
            result = db.execute(
                insert_query,
                {"marker_id": str(marker_id), "collection_id": str(target_collection_id)}
            ).scalar()
            
            db.commit()
            
            return {"success": True, "message": "Маркер успешно перемещен между коллекциями"}
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка при добавлении маркера в целевую коллекцию: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка при перемещении маркера между коллекциями: {str(e)}"
            )
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при перемещении маркера между коллекциями: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при перемещении маркера между коллекциями: {str(e)}"
        )
