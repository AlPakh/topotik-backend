# app/routers/markers.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional
from sqlalchemy.sql import text
import logging
import traceback
import json

from app import schemas, crud
from app.database import get_db
from app.routers.auth import get_user_id_from_token

router = APIRouter(tags=["markers"])

# Настройка логирования
logger = logging.getLogger(__name__)

@router.get("/", response_model=List[schemas.Marker], summary="Получить список маркеров", description="Возвращает список маркеров для указанной карты с пагинацией.")
def list_markers(map_id: UUID, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user_id: UUID = Depends(get_user_id_from_token)):
    """Получить список маркеров для указанной карты"""
    logger.info(f"Запрос списка маркеров для карты {map_id} от пользователя {user_id}")
    
    # Проверяем, что пользователь имеет доступ к карте
    has_access = crud.check_map_ownership(db, map_id, user_id)
    logger.debug(f"Результат проверки доступа к карте: {has_access}")
    
    if not has_access:
        logger.warning(f"Пользователь {user_id} не имеет прав для доступа к карте {map_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для доступа к этой карте"
        )
        
    markers = crud.get_markers_by_map(db, map_id, skip=skip, limit=limit)
    logger.info(f"Получено {len(markers)} маркеров для карты {map_id}")
    return markers

@router.get("/{marker_id}", response_model=schemas.Marker, summary="Получить маркер по ID", description="Возвращает детальную информацию о маркере по его идентификатору.")
def get_marker(marker_id: UUID, db: Session = Depends(get_db)):
    """Получить информацию о маркере по ID"""
    logger.info(f"Запрос маркера по ID {marker_id}")
    
    m = crud.get_marker(db, marker_id)
    logger.debug(f"Результат запроса маркера: {m}")
    
    if not m:
        logger.warning(f"Маркер {marker_id} не найден")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Маркер не найден")
    
    return m

@router.post("/", response_model=schemas.Marker, status_code=status.HTTP_201_CREATED, summary="Создать новый маркер", description="Создает новый маркер на указанной карте с заданными координатами и свойствами.")
def create_marker(marker_in: schemas.MarkerCreate, db: Session = Depends(get_db), user_id: UUID = Depends(get_user_id_from_token)):
    """Создать новый маркер"""
    logger.info(f"Запрос на создание маркера от пользователя {user_id}")
    
    # Преобразуем входные данные в словарь для логирования
    marker_data = {
        "latitude": marker_in.latitude if hasattr(marker_in, 'latitude') else None,
        "longitude": marker_in.longitude if hasattr(marker_in, 'longitude') else None,
        "title": marker_in.title if hasattr(marker_in, 'title') else None,
        "description": marker_in.description if hasattr(marker_in, 'description') else None,
        "map_id": str(marker_in.map_id) if hasattr(marker_in, 'map_id') and marker_in.map_id else None
    }
    
    logger.debug(f"Данные маркера: {json.dumps(marker_data)}")
    
    try:
        # Проверяем, что пользователь имеет доступ к карте
        if not marker_in.map_id:
            logger.warning("map_id не указан в запросе на создание маркера")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="map_id обязателен для создания маркера"
            )
            
        has_access = crud.check_map_ownership(db, marker_in.map_id, user_id)
        logger.debug(f"Результат проверки доступа к карте {marker_in.map_id}: {has_access}")
        
        if not has_access:
            logger.warning(f"Пользователь {user_id} не имеет прав для доступа к карте {marker_in.map_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для доступа к этой карте"
            )
        
        # Создаем маркер
        logger.debug(f"Вызываем crud.create_marker с параметрами: {json.dumps(marker_data)}")
        new_marker = crud.create_marker(db, marker_in)
        
        if not new_marker:
            logger.error("crud.create_marker вернул None")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось создать маркер"
            )
            
        logger.debug(f"Созданный маркер: {new_marker.__dict__ if new_marker else None}")
        
        # После создания маркера, нам нужно убедиться, что виртуальное поле map_id установлено
        # Обновляем маркер, чтобы включить map_id из входных данных
        try:
            new_marker_dict = {
                "marker_id": new_marker.marker_id,
                "latitude": float(new_marker.latitude),
                "longitude": float(new_marker.longitude),
                "title": new_marker.title,
                "description": new_marker.description,
                "map_id": marker_in.map_id  # Устанавливаем map_id из входных данных
            }
            logger.debug(f"Итоговый маркер с map_id: {json.dumps({k: str(v) for k, v in new_marker_dict.items()})}")
            
            # Закомментировано автоматическое добавление маркера в коллекцию по умолчанию
            # Теперь клиент должен явно указать, в какую коллекцию добавить маркер
            # через отдельный запрос к эндпоинту /collections/{collection_id}/markers
            # ---
            # Блок, который добавлял маркер в первую коллекцию карты, был здесь
            # ---
            
            # Возвращаем маркер с явно установленным map_id
            # С учетом разных версий Pydantic
            if hasattr(schemas.Marker, 'model_validate'):
                result = schemas.Marker.model_validate(new_marker_dict)
            else:
                result = schemas.Marker.parse_obj(new_marker_dict)
                
            logger.info(f"Маркер успешно создан с ID {result.marker_id}")
            return result
        except Exception as parsing_error:
            logger.error(f"Ошибка при формировании маркера для ответа: {str(parsing_error)}")
            logger.error(traceback.format_exc())
            # Всё равно пробуем вернуть маркер, даже если были проблемы с форматированием
            return new_marker
        
    except ValueError as e:
        logger.error(f"Ошибка валидации при создании маркера: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Логируем полное исключение для отладки
        logger.error(f"Ошибка при создании маркера: {str(e)}")
        logger.error(traceback.format_exc())
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

# Маршруты для работы со статьями маркеров
@router.get("/{marker_id}/article", response_model=schemas.Article, summary="Получить статью маркера", description="Возвращает статью, связанную с указанным маркером.")
def get_marker_article(
    marker_id: UUID, 
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_user_id_from_token)
):
    """Получить статью по ID маркера"""
    try:
        # Проверяем существование маркера
        marker = crud.get_marker(db, marker_id)
        if not marker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Маркер не найден"
            )
        
        # Проверка доступа к маркеру (через коллекции)
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
                detail="Недостаточно прав для доступа к этому маркеру"
            )
        
        # Получаем статью для маркера
        article = db.execute(
            text("SELECT * FROM topotik.get_article_by_marker(:marker_id)"),
            {"marker_id": str(marker_id)}
        ).fetchone()
        
        if not article:
            # Если статьи нет, но есть описание в маркере - создаем статью на основе описания
            if marker.description:
                article_id = db.execute(
                    text("SELECT topotik.create_article_for_marker(:marker_id, :markdown_content)"),
                    {"marker_id": str(marker_id), "markdown_content": marker.description}
                ).scalar()
                
                # Явно коммитим транзакцию после создания статьи из описания
                db.commit()
                
                # Получаем только что созданную статью
                article = db.execute(
                    text("SELECT * FROM topotik.get_article_by_marker(:marker_id)"),
                    {"marker_id": str(marker_id)}
                ).fetchone()
            else:
                # Если нет ни статьи, ни описания
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Статья для этого маркера не найдена"
                )
            
        # Преобразуем результат в нужный формат
        return {
            "article_id": article.article_id,
            "marker_id": marker_id,
            "markdown_content": article.markdown_content,
            "created_at": article.created_at
        }
        
    except Exception as e:
        db.rollback()  # Откатываем транзакцию в случае ошибки
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении статьи: {str(e)}"
        )

@router.post("/{marker_id}/article", status_code=status.HTTP_201_CREATED, response_model=schemas.Article, summary="Создать статью маркера", description="Создает или обновляет статью для указанного маркера.")
def create_marker_article(
    marker_id: UUID,
    article_data: dict,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_user_id_from_token)
):
    """Создать статью для маркера"""
    try:
        # Проверяем существование маркера
        marker = crud.get_marker(db, marker_id)
        if not marker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Маркер не найден"
            )
        
        # Проверка доступа к маркеру (через коллекции)
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
                detail="Недостаточно прав для редактирования этого маркера"
            )
        
        # Извлекаем markdown_content из данных запроса
        markdown_content = article_data.get("markdown_content", "")
        
        # Создаем или обновляем статью для маркера
        article_id = db.execute(
            text("SELECT topotik.create_article_for_marker(:marker_id, :markdown_content)"),
            {"marker_id": str(marker_id), "markdown_content": markdown_content}
        ).scalar()
        
        # Явно коммитим транзакцию после успешного создания/обновления статьи
        db.commit()
        
        if not article_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось создать статью для маркера"
            )
            
        # Получаем созданную статью
        article = db.execute(
            text("SELECT * FROM topotik.get_article_by_marker(:marker_id)"),
            {"marker_id": str(marker_id)}
        ).fetchone()
        
        return {
            "article_id": article.article_id,
            "marker_id": marker_id,
            "markdown_content": article.markdown_content,
            "created_at": article.created_at
        }
        
    except Exception as e:
        db.rollback()  # Откатываем транзакцию в случае ошибки
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании/обновлении статьи: {str(e)}"
        )

@router.put("/{marker_id}/article", response_model=schemas.Article, summary="Обновить статью маркера", description="Обновляет статью для указанного маркера.")
def update_marker_article(
    marker_id: UUID,
    article_data: dict,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_user_id_from_token)
):
    """Обновить статью для маркера"""
    # Реализация идентична созданию статьи, так как функция create_article_for_marker
    # сама определяет, нужно создать новую статью или обновить существующую
    return create_marker_article(marker_id, article_data, db, user_id)
