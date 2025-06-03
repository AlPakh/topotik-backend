import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud, schemas, models
from app.routers.auth import get_current_user
from sqlalchemy import text

# Настройка логирования
logger = logging.getLogger(__name__)

router = APIRouter()

# Получить URL основного сайта для формирования ссылок на виджеты
def get_base_url(request: Request) -> str:
    host = request.headers.get("host", "localhost:8000")
    scheme = request.headers.get("x-forwarded-proto", "http")
    return f"{scheme}://{host}"

# ————————————————————————————————————————————————
# Маршруты для работы с шерингом
@router.post("/create", response_model=schemas.Sharing)
async def create_sharing_record(
    sharing: schemas.SharingCreate,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    Создать новую запись о шеринге ресурса (карты или коллекции)
    """
    logger.info(f"Запрос на создание записи шеринга от пользователя {current_user.user_id}")
    logger.info(f"Данные запроса: {sharing.model_dump()}")
    
    # Проверяем доступность ресурса для шеринга
    try:
        # Проверяем, имеет ли пользователь право делиться этим ресурсом
        if sharing.resource_type.lower() == "map":
            # Получаем информацию о карте для диагностики
            map_obj = crud.get_map(db, sharing.resource_id)
            if not map_obj:
                logger.error(f"Карта {sharing.resource_id} не найдена")
                raise HTTPException(status_code=404, detail="Карта не найдена")
                
            # Получаем записи доступа к карте для отладки
            access_records = db.query(models.MapAccess).filter(
                models.MapAccess.map_id == sharing.resource_id
            ).all()
            
            # Выводим подробную информацию о доступе
            logger.info(f"Записи доступа к карте {sharing.resource_id}:")
            for record in access_records:
                logger.info(f"  Пользователь: {record.user_id}, права: {record.permission}")
                
            # Для диагностики находим пользователей, у которых есть карта в папках
            folder_maps = db.execute(
                text("""
                    SELECT f.user_id 
                    FROM topotik.folder_maps fm
                    JOIN topotik.folders f ON fm.folder_id = f.folder_id
                    WHERE fm.map_id = :map_id
                """),
                {"map_id": str(sharing.resource_id)}
            ).fetchall()
            
            logger.info(f"Пользователи с картой в папках: {[str(row[0]) for row in folder_maps]}")
            
            # Проверяем права доступа
            ownership_result = crud.check_map_ownership(db, sharing.resource_id, current_user.user_id)
            logger.info(f"Результат проверки владения картой: {ownership_result}")
            
            if not ownership_result:
                raise HTTPException(
                    status_code=403,
                    detail=f"У пользователя {current_user.user_id} нет прав для предоставления доступа к карте {sharing.resource_id}"
                )
        elif sharing.resource_type.lower() == "collection":
            collection = crud.get_collection(db, sharing.resource_id)
            if not collection:
                raise HTTPException(status_code=404, detail="Коллекция не найдена")
                
            # Получаем информацию о карте коллекции
            map_obj = crud.get_map(db, collection.map_id)
            logger.info(f"Коллекция {sharing.resource_id} принадлежит карте {collection.map_id}")
            
            if not crud.check_map_ownership(db, collection.map_id, current_user.user_id):
                raise HTTPException(
                    status_code=403,
                    detail="У вас нет прав для предоставления доступа к этой коллекции"
                )
        else:
            raise HTTPException(status_code=400, detail="Неподдерживаемый тип ресурса")
        
        # Если все проверки пройдены, создаем запись шеринга
        sharing_record = crud.create_sharing(db, sharing_in=sharing, current_user_id=current_user.user_id)
        return sharing_record
    except HTTPException:
        # Пробрасываем HTTP исключения дальше
        raise
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при создании записи шеринга: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Ошибка при создании записи шеринга: {str(e)}")

@router.get("/resource/{resource_type}/{resource_id}", response_model=List[schemas.Sharing])
async def get_resource_sharing_records(
    resource_type: str,
    resource_id: UUID,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    Получить все записи шеринга для конкретного ресурса
    """
    logger.info(f"Запрос на получение записей шеринга для {resource_type} {resource_id} от пользователя {current_user.user_id}")
    
    try:
        # Проверяем доступность ресурса
        if resource_type.lower() == "map":
            # Получаем информацию о карте для диагностики
            map_obj = crud.get_map(db, resource_id)
            if not map_obj:
                logger.error(f"Карта {resource_id} не найдена")
                raise HTTPException(status_code=404, detail="Карта не найдена")
                
            # Получаем записи доступа к карте для отладки
            access_records = db.query(models.MapAccess).filter(
                models.MapAccess.map_id == resource_id
            ).all()
            
            # Выводим подробную информацию о доступе
            logger.info(f"Записи доступа к карте {resource_id}:")
            for record in access_records:
                logger.info(f"  Пользователь: {record.user_id}, права: {record.permission}")
                
            # Для диагностики находим пользователей, у которых есть карта в папках
            folder_maps = db.execute(
                text("""
                    SELECT f.user_id 
                    FROM topotik.folder_maps fm
                    JOIN topotik.folders f ON fm.folder_id = f.folder_id
                    WHERE fm.map_id = :map_id
                """),
                {"map_id": str(resource_id)}
            ).fetchall()
            
            logger.info(f"Пользователи с картой в папках: {[str(row[0]) for row in folder_maps]}")
            
            # Проверяем права доступа
            ownership_result = crud.check_map_ownership(db, resource_id, current_user.user_id)
            logger.info(f"Результат проверки владения картой: {ownership_result}")
            
            if not ownership_result:
                raise HTTPException(
                    status_code=403,
                    detail=f"У пользователя {current_user.user_id} нет прав для просмотра информации о доступе к карте {resource_id}"
                )
        elif resource_type.lower() == "collection":
            collection = crud.get_collection(db, resource_id)
            if not collection:
                raise HTTPException(status_code=404, detail="Коллекция не найдена")
                
            # Получаем информацию о карте коллекции
            map_obj = crud.get_map(db, collection.map_id)
            logger.info(f"Коллекция {resource_id} принадлежит карте {collection.map_id}")
            
            if not crud.check_map_ownership(db, collection.map_id, current_user.user_id):
                raise HTTPException(
                    status_code=403,
                    detail="У вас нет прав для просмотра информации о доступе к этой коллекции"
                )
        else:
            raise HTTPException(status_code=400, detail="Неподдерживаемый тип ресурса")
        
        # Получаем записи шеринга
        sharing_records = crud.get_sharings_by_resource(db, resource_id, resource_type.lower())
        return sharing_records
    except HTTPException:
        # Пробрасываем HTTP исключения дальше
        raise
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при получении записей шеринга: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Ошибка при получении записей шеринга: {str(e)}")

@router.get("/my-shared", response_model=List[schemas.SharingResponse])
async def get_my_shared_resources(
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    Получить все ресурсы, к которым у текущего пользователя есть доступ
    """
    logger.info(f"Запрос на получение ресурсов с доступом для пользователя {current_user.user_id}")
    
    # Получаем записи шеринга
    sharing_records = crud.get_user_shared_resources(db, current_user.user_id)
    
    # Формируем ответ с информацией о ресурсах
    response = []
    for sharing in sharing_records:
        # Получаем информацию о ресурсе
        resource_title = crud.get_resource_title(db, sharing.resource_id, sharing.resource_type)
        
        # Получаем информацию о владельце
        owner = crud.get_resource_owner(db, sharing.resource_id, sharing.resource_type)
        owner_name = owner.username if owner else "Неизвестный пользователь"
        
        response.append(schemas.SharingResponse(
            sharing=sharing,
            resource_title=resource_title,
            resource_owner=owner_name
        ))
    
    return response

@router.put("/{sharing_id}", response_model=schemas.Sharing)
async def update_sharing_record(
    sharing_id: UUID,
    sharing_update: schemas.SharingUpdate,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    Обновить запись о шеринге
    """
    logger.info(f"Запрос на обновление записи шеринга {sharing_id}")
    
    # Получаем запись шеринга
    sharing = crud.get_sharing_by_id(db, sharing_id)
    if not sharing:
        raise HTTPException(status_code=404, detail="Запись о шеринге не найдена")
    
    # Проверяем, имеет ли пользователь право обновлять эту запись
    if sharing.resource_type == "map":
        if not crud.check_map_ownership(db, sharing.resource_id, current_user.user_id):
            raise HTTPException(
                status_code=403,
                detail="У вас нет прав для изменения доступа к этой карте"
            )
    elif sharing.resource_type == "collection":
        collection = crud.get_collection(db, sharing.resource_id)
        if not collection:
            raise HTTPException(status_code=404, detail="Коллекция не найдена")
            
        if not crud.check_map_ownership(db, collection.map_id, current_user.user_id):
            raise HTTPException(
                status_code=403,
                detail="У вас нет прав для изменения доступа к этой коллекции"
            )
    
    # Обновляем запись
    updated_sharing = crud.update_sharing(db, sharing_id, sharing_update)
    if not updated_sharing:
        raise HTTPException(status_code=500, detail="Ошибка при обновлении записи шеринга")
        
    return updated_sharing

@router.delete("/{sharing_id}")
async def delete_sharing_record(
    sharing_id: UUID,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    Удалить запись о шеринге
    """
    logger.info(f"Запрос на удаление записи шеринга {sharing_id}")
    
    # Получаем запись шеринга
    sharing = crud.get_sharing_by_id(db, sharing_id)
    if not sharing:
        raise HTTPException(status_code=404, detail="Запись о шеринге не найдена")
    
    # Проверяем, имеет ли пользователь право удалять эту запись
    if sharing.resource_type == "map":
        if not crud.check_map_ownership(db, sharing.resource_id, current_user.user_id):
            raise HTTPException(
                status_code=403,
                detail="У вас нет прав для отзыва доступа к этой карте"
            )
    elif sharing.resource_type == "collection":
        collection = crud.get_collection(db, sharing.resource_id)
        if not collection:
            raise HTTPException(status_code=404, detail="Коллекция не найдена")
            
        if not crud.check_map_ownership(db, collection.map_id, current_user.user_id):
            raise HTTPException(
                status_code=403,
                detail="У вас нет прав для отзыва доступа к этой коллекции"
            )
    
    # Удаляем запись
    result = crud.delete_sharing(db, sharing_id)
    if not result:
        raise HTTPException(status_code=500, detail="Ошибка при удалении записи шеринга")
        
    return {"success": True, "message": "Запись о шеринге удалена"}

@router.post("/{sharing_id}/revoke")
async def revoke_sharing(
    sharing_id: UUID,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    Отозвать доступ (деактивировать запись о шеринге)
    """
    logger.info(f"Запрос на отзыв доступа для записи шеринга {sharing_id}")
    
    # Получаем запись шеринга
    sharing = crud.get_sharing_by_id(db, sharing_id)
    if not sharing:
        raise HTTPException(status_code=404, detail="Запись о шеринге не найдена")
    
    # Проверяем, имеет ли пользователь право отзывать доступ
    if sharing.resource_type == "map":
        if not crud.check_map_ownership(db, sharing.resource_id, current_user.user_id):
            raise HTTPException(
                status_code=403,
                detail="У вас нет прав для отзыва доступа к этой карте"
            )
    elif sharing.resource_type == "collection":
        collection = crud.get_collection(db, sharing.resource_id)
        if not collection:
            raise HTTPException(status_code=404, detail="Коллекция не найдена")
            
        if not crud.check_map_ownership(db, collection.map_id, current_user.user_id):
            raise HTTPException(
                status_code=403,
                detail="У вас нет прав для отзыва доступа к этой коллекции"
            )
    
    # Деактивируем запись
    result = crud.deactivate_sharing(db, sharing_id)
    if not result:
        raise HTTPException(status_code=500, detail="Ошибка при отзыве доступа")
        
    return {"success": True, "message": "Доступ отозван"}

# ————————————————————————————————————————————————
# Маршруты для работы с виджетами
@router.post("/embed/{resource_type}/{resource_id}", response_model=schemas.EmbedCodeResponse)
async def create_embed_widget(
    resource_type: str,
    resource_id: UUID,
    embed_config: Optional[Dict[str, Any]] = None,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    Создать виджет для встраивания на сторонние сайты
    """
    logger.info(f"Запрос на создание виджета для {resource_type} {resource_id}")
    
    # Проверяем, имеет ли пользователь право создавать виджет
    if resource_type.lower() == "map":
        if not crud.check_map_ownership(db, resource_id, current_user.user_id):
            raise HTTPException(
                status_code=403,
                detail="У вас нет прав для создания виджета для этой карты"
            )
    elif resource_type.lower() == "collection":
        collection = crud.get_collection(db, resource_id)
        if not collection:
            raise HTTPException(status_code=404, detail="Коллекция не найдена")
            
        if not crud.check_map_ownership(db, collection.map_id, current_user.user_id):
            raise HTTPException(
                status_code=403,
                detail="У вас нет прав для создания виджета для этой коллекции"
            )
    else:
        raise HTTPException(status_code=400, detail="Неподдерживаемый тип ресурса")
    
    # Создаем запись шеринга для виджета
    sharing_data = schemas.SharingCreate(
        resource_id=resource_id,
        resource_type=resource_type.lower(),
        is_embed=True,
        is_active=True,
        is_public=True,  # Виджеты всегда публичные
        access_level="view"  # У виджета всегда доступ только для просмотра
    )
    
    try:
        # Создаем запись шеринга
        sharing_record = crud.create_sharing(db, sharing_in=sharing_data, current_user_id=current_user.user_id)
        
        # Формируем URL для встраивания
        base_url = get_base_url(request)
        iframe_url = f"{base_url}/embed/{sharing_record.sharing_id}"
        
        # Используем дефолтные значения для ширины и высоты
        width = "100%"
        height = "500px"
        
        # Формируем HTML код для встраивания
        embed_code = f'<iframe src="{iframe_url}" width="{width}" height="{height}" frameborder="0" allowfullscreen></iframe>'
        
        return schemas.EmbedCodeResponse(
            embed_code=embed_code,
            iframe_url=iframe_url,
            sharing_id=sharing_record.sharing_id
        )
    except Exception as e:
        logger.error(f"Ошибка при создании виджета: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при создании виджета: {str(e)}")

@router.get("/embed/{sharing_id}/code", response_model=schemas.EmbedCodeResponse)
async def get_embed_code(
    sharing_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    Получить HTML код для встраивания виджета
    """
    logger.info(f"Запрос на получение кода виджета для {sharing_id}")
    
    # Получаем запись шеринга
    sharing = crud.get_sharing_by_id(db, sharing_id)
    if not sharing or not sharing.is_embed:
        raise HTTPException(status_code=404, detail="Виджет не найден")
    
    # Проверяем, имеет ли пользователь право получать код виджета
    if sharing.resource_type == "map":
        if not crud.check_map_ownership(db, sharing.resource_id, current_user.user_id):
            raise HTTPException(
                status_code=403,
                detail="У вас нет прав для получения кода виджета этой карты"
            )
    elif sharing.resource_type == "collection":
        collection = crud.get_collection(db, sharing.resource_id)
        if not collection:
            raise HTTPException(
                status_code=404,
                detail="Коллекция не найдена"
            )
            
        if not crud.check_map_ownership(db, collection.map_id, current_user.user_id):
            raise HTTPException(
                status_code=403,
                detail="У вас нет прав для получения кода виджета этой коллекции"
            )
    
    # Формируем URL для встраивания
    base_url = get_base_url(request)
    iframe_url = f"{base_url}/embed/{sharing_id}"
    
    # Используем дефолтные значения для ширины и высоты
    width = "100%"
    height = "500px"
    
    embed_code = f'<iframe src="{iframe_url}" width="{width}" height="{height}" frameborder="0" allowfullscreen></iframe>'
    
    return schemas.EmbedCodeResponse(
        embed_code=embed_code,
        iframe_url=iframe_url,
        sharing_id=sharing.sharing_id
    )

@router.get("/embed/{sharing_id}")
async def render_embed_widget(
    sharing_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Отрендерить виджет для встраивания (без аутентификации)
    """
    logger.info(f"Запрос на рендеринг виджета для {sharing_id}")
    
    # Получаем активную запись шеринга
    sharing = crud.get_active_sharing_by_id(db, sharing_id)
    
    # Подробное логирование для отладки
    if sharing:
        logger.info(f"Запись шеринга найдена: ID={sharing.sharing_id}, is_active={sharing.is_active}, is_embed={getattr(sharing, 'is_embed', False)}")
    else:
        logger.error(f"Запись шеринга с ID={sharing_id} не найдена")
        raise HTTPException(status_code=404, detail="Виджет не найден")
    
    if not sharing.is_active:
        logger.error(f"Виджет {sharing_id} неактивен")
        raise HTTPException(status_code=404, detail="Виджет неактивен")
    
    # Проверяем признак is_embed, но если его нет (старые записи), 
    # считаем публичную запись эмбедом
    is_embed = getattr(sharing, 'is_embed', None)
    if is_embed is None:
        is_embed = sharing.is_public
        logger.warning(f"У записи шеринга {sharing_id} отсутствует поле is_embed, используем is_public={sharing.is_public}")
    
    if not is_embed and not sharing.is_public:
        logger.error(f"Запись шеринга {sharing_id} не является виджетом (is_embed={is_embed}, is_public={sharing.is_public})")
        raise HTTPException(status_code=404, detail="Виджет не найден")
    
    # Используем дефолтные настройки виджета
    width = "100%"
    height = "500px"
    theme = "light"
    show_controls = True
    
    # Формируем базовый HTML-шаблон для виджета
    html_template = """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Карта Topotik</title>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
        <style>
            body, html { 
                margin: 0; 
                padding: 0; 
                height: 100%; 
                width: 100%;
                font-family: Arial, sans-serif;
                background-color: """ + ("#ffffff" if theme == "light" else "#333333") + """;
                color: """ + ("#333333" if theme == "light" else "#ffffff") + """;
            }
            #map-container {
                height: 100%;
                width: 100%;
                position: relative;
            }
            #map {
                height: 100%;
                width: 100%;
            }
            /* Стили для типов карт */
            .custom-image-map {
                background-color: #d1d1d1;
            }
            .osm-map {
                background-color: #f2f2f2;
            }
            .map-title {
                position: absolute;
                top: 10px;
                left: 10px;
                z-index: 1000;
                background-color: """ + ("rgba(255, 255, 255, 0.8)" if theme == "light" else "rgba(51, 51, 51, 0.8)") + """;
                padding: 5px 10px;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
                display: """ + ("block" if True else "none") + """;
            }
            .topotik-attribution {
                position: absolute;
                bottom: 5px;
                right: 5px;
                z-index: 1000;
                font-size: 10px;
                background-color: """ + ("rgba(255, 255, 255, 0.7)" if theme == "light" else "rgba(51, 51, 51, 0.7)") + """;
                padding: 2px 5px;
                border-radius: 3px;
            }
            .topotik-attribution a {
                color: """ + ("#0078A8" if theme == "light" else "#6BAED6") + """;
                text-decoration: none;
            }
            .controls {
                display: """ + ("block" if show_controls else "none") + """;
            }
            /* Стили для маркеров и попапов из CustomMapView.vue */
            .custom-map-marker {
                background-color: transparent;
                border: none;
            }
            .marker-tooltip {
                padding: 5px 10px;
                background-color: rgba(255, 255, 255, 0.9);
                border-radius: 4px;
                box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
                font-weight: bold;
                font-size: 14px;
                text-align: center;
                border: 1px solid #ccc;
            }
            .marker-popup {
                font-size: 14px;
            }
            .marker-popup h3 {
                margin: 0 0 5px 0;
                font-size: 16px;
                font-weight: bold;
            }
            .marker-popup p {
                margin: 5px 0 0 0;
            }
            .loading-indicator {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background-color: """ + ("rgba(255, 255, 255, 0.8)" if theme == "light" else "rgba(51, 51, 51, 0.8)") + """;
                padding: 15px 20px;
                border-radius: 6px;
                z-index: 1001;
                font-weight: bold;
                text-align: center;
            }
            /* Добавление стилей для классов popop и leaflet-popup */
            .leaflet-popup-content-wrapper {
                border-radius: 4px;
                box-shadow: 0 3px 14px rgba(0,0,0,0.4);
            }
            .leaflet-popup-content {
                margin: 8px 10px;
                line-height: 1.4;
            }
            /* Стили для масштабирования карты */
            .leaflet-control-zoom {
                border-radius: 4px;
                box-shadow: 0 1px 5px rgba(0,0,0,0.4);
            }
            .leaflet-control-zoom a {
                background-color: white;
                color: #333;
            }
        </style>
    </head>
    <body>
        <div id="map-container">
            <div class="map-title"></div>
            <div id="map"></div>
            <div id="loading" class="loading-indicator">Загрузка карты...</div>
            <div class="topotik-attribution">
                Создано с помощью <a href="https://topotik-frontend.onrender.com" target="_blank">Topotik</a>
            </div>
        </div>
    
        <script>
            // Инициализация карты
            var map;
            var markers = [];
            var customImageOverlay = null;
            
            // Функция для создания маркеров на карте
            function createMarker(lat, lng, title, content, color) {
                // Создаем SVG-маркер с указанным цветом
                var markerSvg = `
                    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="48" viewBox="0 0 32 48">
                      <path fill="${color || '#4a90e2'}" d="M16 0C7.2 0 0 7.2 0 16c0 8.8 16 32 16 32s16-23.2 16-32C32 7.2 24.8 0 16 0z"/>
                      <circle fill="white" cx="16" cy="16" r="8"/>
                    </svg>
                `;
                
                // Создаем собственную иконку
                var customIcon = L.divIcon({
                    className: "custom-map-marker",
                    html: markerSvg,
                    iconSize: [32, 48],
                    iconAnchor: [16, 48],
                    popupAnchor: [0, -48],
                    // Отключаем нежелательные свойства
                    riseOnHover: false,
                    riseOffset: 0
                });
                
                // Создаем маркер и добавляем его на карту
                var marker = L.marker([lat, lng], { 
                    icon: customIcon,
                    interactive: true,
                    zIndexOffset: lat * 10,
                    riseOnHover: false,
                    riseOffset: 0,
                    // Отключаем анимации для стабильности
                    animate: false
                }).addTo(map);
                
                // Добавляем всплывающее окно
                if (title || content) {
                    var popupContent = '<div class="marker-popup">';
                    if (title) popupContent += '<h3>' + title + '</h3>';
                    if (content) popupContent += '<p>' + content + '</p>';
                    popupContent += '</div>';
                    
                    // Используем опции для попапа из CustomMapView.vue
                    var popup = L.popup({
                        className: "marker-tooltip",
                        offset: [0, -48],
                        closeButton: false,
                        autoClose: true,
                        closeOnEscapeKey: false,
                        closeOnClick: false
                    });
                    
                    popup.setContent(popupContent);
                    
                    // Открываем попап при наведении
                    marker.on('mouseover', function() {
                        marker.bindPopup(popup).openPopup();
                    });
                    
                    // Закрываем попап при уходе мыши
                    marker.on('mouseout', function() {
                        marker.closePopup();
                    });
                }
                
                return marker;
            }
            
            // Функция для настройки карты с пользовательским изображением
            function setupCustomImageMap(imageUrl) {
                console.log('Настройка карты с пользовательским изображением:', imageUrl);
                
                // Преобразуем относительный URL в абсолютный
                if (imageUrl && imageUrl.startsWith('/')) {
                    imageUrl = window.location.origin + imageUrl;
                }

                if (!imageUrl) {
                    console.error('URL изображения не предоставлен');
                    document.getElementById('loading').innerText = 'Ошибка загрузки изображения';
                    return;
                }

                // Применяем класс к контейнеру карты
                document.getElementById('map').classList.add('custom-image-map');
                
                // Загружаем изображение для определения его размеров
                var img = new Image();
                img.onload = function() {
                    console.log('Изображение загружено, размеры:', img.width, 'x', img.height);
                    
                    // Скрываем индикатор загрузки
                    document.getElementById('loading').style.display = 'none';
                    
                    try {
                        // Используем тот же метод настройки карты, что и в CustomMapView.vue
                        
                        // Используем нестандартную систему координат CRS.Simple
                        map.options.crs = L.CRS.Simple;
                        
                        // Устанавливаем ограничения масштаба как в CustomMapView.vue
                        map.options.minZoom = -2;
                        map.options.maxZoom = 2;
                        
                        console.log('Настройки масштаба карты:', {
                            minZoom: map.options.minZoom,
                            maxZoom: map.options.maxZoom
                        });
                        
                        // Устанавливаем границы карты на основе размеров изображения,
                        // точно как это делается в CustomMapView.vue
                        const southWest = map.unproject([0, img.height], 0);
                        const northEast = map.unproject([img.width, 0], 0);
                        const bounds = new L.LatLngBounds(southWest, northEast);
                        
                        console.log('Границы изображения:', {
                            southWest: southWest,
                            northEast: northEast,
                            boundsString: bounds.toBBoxString()
                        });

                        // Устанавливаем максимальные границы карты
                        map.setMaxBounds(bounds);

                        // Добавляем изображение на карту
                        customImageOverlay = L.imageOverlay(imageUrl, bounds).addTo(map);
                        
                        // Центрируем карту и устанавливаем зум
                        map.fitBounds(bounds, {
                            animate: false, // Отключаем анимацию для стабильности
                            padding: [10, 10] // Добавляем небольшие отступы
                        });
                        
                        // Установка начального масштаба
                        map.setZoom(0, {animate: false});
                        
                        console.log('Текущий масштаб карты:', map.getZoom());
                        
                        // Добавляем маркеры на карту после инициализации изображения
                        if (window.markersData && window.markersData.length > 0) {
                            console.log('Добавление маркеров на пользовательскую карту:', window.markersData.length);
                            
                            window.markersData.forEach(marker => {
                                // Получаем координаты маркера (они уже должны быть в системе координат изображения)
                                let lat = parseFloat(marker.latitude);
                                let lng = parseFloat(marker.longitude);
                                
                                console.log(`Исходные координаты маркера "${marker.title}": lat=${lat}, lng=${lng}`);
                                
                                // Проверка на корректные координаты
                                if (isNaN(lat) || isNaN(lng)) {
                                    console.warn(`Пропуск маркера "${marker.title}" с некорректными координатами`);
                                    return;
                                }
                                
                                // Создаем маркер с преобразованными координатами
                                createMarker(lat, lng, marker.title, marker.description, marker.color);
                                
                                console.log(`Маркер "${marker.title}" добавлен на карту в позиции [${lat}, ${lng}]`);
                            });
                        }
                    } catch (error) {
                        console.error('Ошибка при настройке пользовательской карты:', error);
                        document.getElementById('loading').innerText = 'Ошибка настройки карты';
                        document.getElementById('loading').style.display = 'block';
                    }
                };
                
                img.onerror = function() {
                    console.error('Ошибка загрузки изображения:', imageUrl);
                    document.getElementById('loading').innerText = 'Ошибка загрузки изображения';
                };
                    
                // Начинаем загрузку изображения
                img.src = imageUrl;
            }

            // Функция для настройки карты OSM (OpenStreetMap)
            function setupOSMMap() {
                console.log('Настройка карты OSM');
                
                try {
                    // Применяем класс к контейнеру карты
                    document.getElementById('map').classList.add('osm-map');
                    
                    // Добавляем базовый слой карты
                    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                        maxZoom: 19,
                        minZoom: 3,
                    }).addTo(map);
                    
                    // Скрываем индикатор загрузки
                    document.getElementById('loading').style.display = 'none';
                    
                    // Используем значения по умолчанию
                    let center = {"lat": 55.7558, "lng": 37.6173}; 
                    let zoom = 10;
                    
                    // Если есть маркеры, устанавливаем вид на их граничные рамки
                    if (window.markersData && window.markersData.length > 0) {
                        console.log('Добавление маркеров на OSM карту:', window.markersData.length);
                        
                        // Создаем массив для хранения действительных точек
                        const validPoints = [];
                        
                        // Создаем маркеры
                        window.markersData.forEach(marker => {
                            // Преобразуем строковые координаты в числовые
                            const lat = parseFloat(marker.latitude);
                            const lng = parseFloat(marker.longitude);
                            
                            console.log(`Координаты маркера "${marker.title}": lat=${lat}, lng=${lng}`);
                            
                            // Проверяем, что координаты валидны для географической карты
                            if (isNaN(lat) || isNaN(lng) || lat < -90 || lat > 90 || lng < -180 || lng > 180) {
                                console.warn(`Маркер "${marker.title}" имеет невалидные географические координаты: [${lat}, ${lng}]`);
                                return; // Пропускаем этот маркер
                            }
                            
                            // Добавляем точку для расчета границ
                            validPoints.push([lat, lng]);
                            
                            createMarker(
                                lat,
                                lng,
                                marker.title,
                                marker.description,
                                marker.color
                            );
                            
                            console.log(`Маркер "${marker.title}" добавлен на OSM карту в позиции [${lat}, ${lng}]`);
                        });
                        
                        // Если есть действительные точки
                        if (validPoints.length > 0) {
                            // Если более одного маркера, вычисляем граничные рамки
                            if (validPoints.length > 1) {
                                const bounds = L.latLngBounds(validPoints);
                                map.fitBounds(bounds, { 
                                    padding: [50, 50],
                                    animate: false // Отключаем анимацию для стабильности
                                });
                                console.log('Карта центрирована по всем маркерам');
                            } else {
                                // Если только один маркер, центрируем на нем
                                map.setView(
                                    validPoints[0],
                                    13,
                                    { animate: false }
                                );
                                console.log('Карта центрирована по единственному маркеру');
                            }
                        } else {
                            // Если нет валидных маркеров, используем центр по умолчанию
                            map.setView([center.lat, center.lng], zoom, { animate: false });
                            console.log('Нет валидных маркеров, используется центр по умолчанию');
                        }
                    } else {
                        // Если нет маркеров, используем центр и масштаб по умолчанию или из настроек
                        map.setView([center.lat, center.lng], zoom, { animate: false });
                        console.log('Нет маркеров, используется центр по умолчанию');
                    }
                } catch (error) {
                    console.error('Ошибка при настройке OSM карты:', error);
                    document.getElementById('loading').innerText = 'Ошибка настройки карты';
                    document.getElementById('loading').style.display = 'block';
                }
            }
            
            // Функция для загрузки данных карты или коллекции
            async function loadResource() {
                try {
                    // Инициализация карты Leaflet
                    map = L.map('map', {
                        zoomControl: """ + str(show_controls).lower() + """,
                        attributionControl: false
                    });
                    
                    // URL для получения данных ресурса
                    const apiUrl = `/sharing/api/embed-data/""" + str(sharing.resource_type) + """/""" + str(sharing.resource_id) + """`;
                    
                    // Запрос к API
                    const response = await fetch(apiUrl);
                    
                    if (!response.ok) {
                        throw new Error('Не удалось загрузить данные');
                    }
                    
                    const data = await response.json();
                    console.log('Получены данные ресурса:', data);
                    
                    // Устанавливаем название
                    document.querySelector('.map-title').textContent = data.title || 'Карта без названия';
                    
                    // Сохраняем данные о маркерах глобально
                    window.markersData = data.markers || [];
                    
                    // Определяем тип карты и настраиваем соответствующий вид
                    if (data.map_type === 'custom_image' && data.background_image_url) {
                        // Для карт с пользовательским изображением
                        document.getElementById('map').classList.add('custom-image-map');
                        setupCustomImageMap(data.background_image_url);
                    } else {
                        // Для карт OSM
                        setupOSMMap();
                    }
                    
                } catch (error) {
                    console.error('Ошибка при загрузке данных:', error);
                    document.querySelector('.map-title').textContent = 'Ошибка загрузки карты';
                    document.getElementById('loading').innerText = 'Ошибка загрузки данных';
                }
            }
            
            // Загружаем ресурс после загрузки страницы
            document.addEventListener('DOMContentLoaded', loadResource);
        </script>
    </body>
    </html>
    """
    
    # Возвращаем HTML как текстовый ответ
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html_template, status_code=200)

# Добавляем новый маршрут для получения данных для встраиваемого виджета
@router.get("/api/embed-data/{resource_type}/{resource_id}")
async def get_embed_data(
    resource_type: str,
    resource_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Получить данные для встраиваемого виджета (публичный API без аутентификации)
    """
    logger.info(f"Запрос данных для виджета: {resource_type}/{resource_id}")

    # Проверяем доступность ресурса через публичные записи шеринга
    sharing_records = crud.get_active_sharings_by_resource(db, resource_id, resource_type)
    
    # Проверяем, есть ли записи шеринга с is_embed=True и is_active=True
    is_public = any(record.is_public and getattr(record, 'is_embed', False) for record in sharing_records)
    
    if not is_public:
        raise HTTPException(status_code=403, detail="Ресурс не доступен для публичного просмотра")

    # Получаем данные в зависимости от типа ресурса
    if resource_type.lower() == "map":
        map_data = crud.get_map(db, resource_id)
        if not map_data:
            raise HTTPException(status_code=404, detail="Карта не найдена")
        
        # Добавляем URL изображения, если это карта с пользовательским изображением
        background_image_url = None
        if map_data.map_type == "custom_image" and map_data.background_image_id:
            # Преобразуем background_image_id в URL
            if hasattr(map_data, 'background_image_url') and map_data.background_image_url:
                background_image_url = map_data.background_image_url
            else:
                # Формируем URL для изображения, если он не предоставлен напрямую
                background_image_url = f"/images/proxy/{map_data.background_image_id}"
        
        logger.info(f"Тип карты: {map_data.map_type}, URL фона: {background_image_url}")
        
        # Получаем коллекции для этой карты
        collections = crud.get_collections_by_map(db, resource_id)
        logger.info(f"Получено коллекций: {len(collections)}")
        
        # Получаем все маркеры для карты
        all_markers = []
        for collection in collections:
            # Логирование названия коллекции для отладки
            logger.info(f"Обработка коллекции '{collection.title}' с ID: {collection.collection_id}")
            
            # Получаем маркеры для каждой коллекции
            collection_markers = []
            
            if not hasattr(collection, 'markers') or not collection.markers:
                logger.warning(f"У коллекции {collection.collection_id} нет маркеров или они недоступны")
                continue
                
            logger.info(f"Маркеров в коллекции: {len(collection.markers)}")
            
            for marker in collection.markers:
                try:
                    # Преобразуем координаты в float для точности
                    latitude = float(marker.latitude)
                    longitude = float(marker.longitude)
                    
                    logger.info(f"Маркер {marker.marker_id}: координаты в БД: lat={latitude}, lng={longitude}")
                    
                    # Здесь мы не преобразуем координаты, так как система координат
                    # соответствует CustomMapView.vue, где longitude=x, latitude=y
                    # и x,y - это пиксельные координаты на изображении
                    
                    # Получаем статью маркера, если есть
                    article = None
                    try:
                        articles = crud.get_articles_by_marker(db, marker.marker_id)
                        if articles:
                            article = articles[0]
                    except Exception as e:
                        logger.warning(f"Ошибка при получении статьи для маркера {marker.marker_id}: {str(e)}")
                    
                    marker_data = {
                        "id": str(marker.marker_id),
                        "latitude": latitude,
                        "longitude": longitude,
                        "title": marker.title or "Метка без названия",
                        "description": marker.description or "",
                        "color": collection.collection_color or "#4a90e2",
                    }
                    
                    if article:
                        if hasattr(article, 'markdown_content'):
                            # Если это объект с атрибутами
                            if article.markdown_content:
                                marker_data["content"] = article.markdown_content
                        elif isinstance(article, dict) and "markdown_content" in article:
                            # Если это словарь
                            if article["markdown_content"]:
                                marker_data["content"] = article["markdown_content"]
                    
                    collection_markers.append(marker_data)
                except Exception as e:
                    logger.error(f"Ошибка при обработке маркера {getattr(marker, 'marker_id', 'unknown')}: {str(e)}")
                    continue
            
            all_markers.extend(collection_markers)
        
        logger.info(f"Всего маркеров для отображения: {len(all_markers)}")
        
        # Формируем ответ
        response = {
            "title": map_data.title,
            "map_type": map_data.map_type,
            "background_image_url": background_image_url,
            "markers": all_markers,
            "collections": [
                {
                    "id": str(c.collection_id),
                    "title": c.title,
                    "color": c.collection_color or "#4a90e2"
                }
                for c in collections
            ]
        }
        
        return response
    
    elif resource_type.lower() == "collection":
        collection = crud.get_collection(db, resource_id)
        if not collection:
            raise HTTPException(status_code=404, detail="Коллекция не найдена")
        
        # Получаем маркеры коллекции
        markers = []
        logger.info(f"Обработка коллекции {collection.title} с ID: {collection.collection_id}")
        
        # Проверка наличия маркеров
        if not hasattr(collection, 'markers') or not collection.markers:
            logger.warning(f"У коллекции {collection.collection_id} нет маркеров или они недоступны")
        else:
            logger.info(f"Маркеров в коллекции: {len(collection.markers)}")
            
            for marker in collection.markers:
                try:
                    # Преобразуем координаты в float для точности
                    latitude = float(marker.latitude)
                    longitude = float(marker.longitude)
                    
                    # Определяем тип координат
                    is_geographic = (-90 <= latitude <= 90 and -180 <= longitude <= 180)
                    coordinate_type = "географические" if is_geographic else "пиксельные"
                    
                    logger.info(f"Маркер {marker.marker_id}: координаты [{latitude}, {longitude}] - {coordinate_type}")
                    
                    # Получаем статью маркера, если есть
                    article = None
                    try:
                        articles = crud.get_articles_by_marker(db, marker.marker_id)
                        if articles:
                            article = articles[0]
                    except Exception as e:
                        logger.warning(f"Ошибка при получении статьи для маркера {marker.marker_id}: {str(e)}")
                    
                    marker_data = {
                        "id": str(marker.marker_id),
                        "latitude": latitude,
                        "longitude": longitude,
                        "title": marker.title or "Метка без названия",
                        "description": marker.description or "",
                        "color": collection.collection_color or "#4a90e2",
                    }
                    
                    if article:
                        if hasattr(article, 'markdown_content'):
                            # Если это объект с атрибутами
                            if article.markdown_content:
                                marker_data["content"] = article.markdown_content
                        elif isinstance(article, dict) and "markdown_content" in article:
                            # Если это словарь
                            if article["markdown_content"]:
                                marker_data["content"] = article["markdown_content"]
                    
                    markers.append(marker_data)
                except Exception as e:
                    logger.error(f"Ошибка при обработке маркера {getattr(marker, 'marker_id', 'unknown')}: {str(e)}")
                    continue
        
        logger.info(f"Всего маркеров для отображения коллекции: {len(markers)}")
        
        # Формируем ответ
        response = {
            "title": collection.title,
            "map_id": str(collection.map_id),
            "color": collection.collection_color or "#4a90e2",
            "markers": markers
        }
        
        return response
    
    raise HTTPException(status_code=400, detail="Неподдерживаемый тип ресурса") 