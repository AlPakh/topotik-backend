# app/routers/folders.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Dict, Any
import json
from sqlalchemy.sql import text

from app import schemas, crud
from app.database import get_db
from app.routers.auth import get_user_id_from_token, get_current_user
import logging

# Настройка логирования
logger = logging.getLogger(__name__)

router = APIRouter(tags=["folders"])

@router.get("/user", response_model=List[schemas.Folder], summary="Получить все папки пользователя", description="Возвращает список всех папок, принадлежащих текущему пользователю")
def get_user_folders(
    db: Session = Depends(get_db), 
    user_id: UUID = Depends(get_user_id_from_token)
):
    """Получить список папок пользователя"""
    return crud.get_user_folders(db, user_id)

@router.get("/structure", response_model=List[Dict[str, Any]], summary="Получить структуру папок и карт пользователя", 
           description="Возвращает иерархическую структуру папок и карт пользователя")
def get_user_folder_structure(
    db: Session = Depends(get_db), 
    user_id: UUID = Depends(get_user_id_from_token)
):
    """
    Получить иерархическую структуру папок и карт пользователя
    """
    try:
        # Получаем структуру папок и карт из БД
        result = db.execute(
            text("""
                SELECT * FROM topotik.get_user_folder_structure(:user_id);
            """),
            {"user_id": str(user_id)}
        ).scalar()
        
        if not result:
            # Если функция вернула NULL, возвращаем пустой список
            return []
            
        # Преобразуем результат в нужный формат
        if isinstance(result, str):
            # Если строка JSON, преобразуем её в словарь
            result_dict = json.loads(result)
        else:
            # Если уже словарь, используем как есть
            result_dict = result
            
        # Проверяем структуру результата
        if isinstance(result_dict, dict) and 'items' in result_dict:
            result = result_dict['items']
        elif isinstance(result_dict, list):
            result = result_dict
        else:
            result = []
            
        # Затем получаем shared maps и добавляем их к результату
        shared_maps = get_shared_maps_for_user(db, user_id)
        
        if shared_maps:
            # Если есть shared maps, добавляем их к результату
            if isinstance(result, list):
                result.extend(shared_maps)
            else:
                return shared_maps
                
        return result
    except Exception as e:
        logger.error(f"Ошибка при получении структуры папок: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def get_shared_maps_for_user(db: Session, user_id: UUID):
    """
    Получить список карт, к которым у пользователя есть доступ по шарингу
    """
    try:
        # Получаем карты, к которым у пользователя есть доступ
        shared_maps = db.execute(
            text("""
                SELECT 
                    m.map_id as id, 
                    m.title as name, 
                    m.map_type, 
                    u.username as owner_username
                FROM topotik.maps m
                JOIN topotik.sharing s ON m.map_id = s.resource_id
                -- Получаем владельца карты из таблицы map_access
                JOIN topotik.map_access ma ON m.map_id = ma.map_id AND ma.permission = 'edit'
                JOIN topotik.users u ON ma.user_id = u.user_id
                WHERE s.user_id = :user_id 
                  AND s.resource_type = 'map' 
                  AND s.is_active = true
                  -- Исключаем самого пользователя как владельца
                  AND ma.user_id != :user_id
            """),
            {"user_id": str(user_id)}
        ).fetchall()
        
        # Преобразуем в список словарей для возврата в API
        result = []
        for map_data in shared_maps:
            map_dict = {
                'id': str(map_data.id),
                'name': map_data.name,
                'type': 'map',
                'mapType': 'real' if map_data.map_type == 'osm' else 'custom',
                'isShared': True,
                'ownerName': map_data.owner_username
            }
            result.append(map_dict)
            
        return result
    except Exception as e:
        logger.error(f"Ошибка при получении shared maps: {e}")
        return []

@router.get("/{folder_id}", response_model=schemas.Folder, summary="Получить папку по ID", description="Возвращает детальную информацию о папке по её идентификатору. Доступно только владельцу папки.")
def get_folder(
    folder_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_user_id_from_token)
):
    """Получить информацию о папке"""
    folder = crud.get_folder(db, folder_id)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Папка не найдена"
        )
    
    # Проверка доступа
    if folder.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для доступа к этой папке"
        )
        
    return folder

@router.get("/{folder_id}/content", response_model=schemas.FolderContent, summary="Получить содержимое папки", description="Возвращает списки подпапок и карт, находящихся непосредственно в указанной папке")
def get_folder_content(
    folder_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_user_id_from_token)
):
    """Получить содержимое папки (подпапки и карты)"""
    folder = crud.get_folder(db, folder_id)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Папка не найдена"
        )
    
    # Проверка доступа
    if folder.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для доступа к этой папке"
        )
    
    return crud.get_folder_content(db, folder_id)

@router.post("/", response_model=schemas.Folder, status_code=status.HTTP_201_CREATED, summary="Создать новую папку", description="Создает новую папку для текущего пользователя. Можно указать родительскую папку или создать корневую.")
def create_folder(
    folder_in: schemas.FolderCreate,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_user_id_from_token)
):
    """Создать новую папку"""
    try:
        return crud.create_folder(db, folder_in, user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании папки: {str(e)}"
        )

@router.put("/{folder_id}", response_model=schemas.Folder, summary="Обновить папку", description="Обновляет данные существующей папки")
def update_folder(
    folder_id: UUID, 
    folder_data: schemas.FolderUpdate, 
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_user_id_from_token)
):
    # Проверяем владение папкой
    if not crud.check_folder_ownership(db, folder_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для редактирования этой папки"
        )
    
    updated_folder = crud.update_folder(db, folder_id, folder_data)
    if not updated_folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Папка не найдена или возникла ошибка при обновлении"
        )
    return updated_folder

@router.put("/{folder_id}/move", response_model=schemas.GenericResponse, summary="Переместить папку", description="Перемещает папку в другую папку. Папки могут быть вложенными.")
def move_folder(
    folder_id: UUID, 
    move_data: schemas.FolderMove, 
    db: Session = Depends(get_db), 
    user_id: UUID = Depends(get_user_id_from_token)
):
    # Сначала проверяем владение исходной папкой
    if not crud.check_folder_ownership(db, folder_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для перемещения этой папки"
        )
    
    # Если указана новая родительская папка, проверяем доступ к ней
    if move_data.new_parent_id:
        if not crud.check_folder_ownership(db, move_data.new_parent_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для перемещения в указанную папку"
            )
    
    try:
        result = crud.move_folder(db, folder_id, move_data.new_parent_id)
        if result:
            return {"success": True, "message": "Папка успешно перемещена"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось переместить папку. Возможно обнаружено циклическое вложение."
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(e)
        )

@router.delete("/{folder_id}", response_model=schemas.GenericResponse, summary="Удалить папку", description="Удаляет папку. Вложенные папки и карты перемещаются на верхний уровень.")
def delete_folder(
    folder_id: UUID, 
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_user_id_from_token)
):
    """Удалить папку и переместить содержимое в родительскую папку"""
    # Проверяем владение папкой
    if not crud.check_folder_ownership(db, folder_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для удаления этой папки"
        )
    
    try:
        result = crud.delete_folder(db, folder_id)
        if result:
            return {"success": True, "message": "Папка успешно удалена"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Папка не найдена или возникла ошибка при удалении"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при удалении папки: {str(e)}"
        )

@router.post("/shared-map-to-folder", response_model=schemas.GenericResponse, summary="Переместить общую карту в папку", description="Перемещает ярлык на общую карту в указанную папку пользователя")
async def move_shared_map_to_folder(
    map_data: schemas.SharedMapMove,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """
    Перемещение ярлыка на общую карту в папку пользователя
    """
    logger.info(f"Запрос на перемещение ярлыка карты {map_data.map_id} в папку {map_data.target_folder_id}")
    
    try:
        # Проверяем, что у пользователя есть доступ к этой карте через sharing
        shared_resource = crud.get_shared_resource_for_user(
            db, map_data.map_id, "map", current_user.user_id
        )
        
        if not shared_resource:
            raise HTTPException(
                status_code=403, 
                detail="У вас нет доступа к этой карте"
            )
        
        # Если указана целевая папка - проверяем её принадлежность пользователю
        if map_data.target_folder_id:
            folder = crud.get_folder(db, map_data.target_folder_id)
            if not folder or folder.user_id != current_user.user_id:
                raise HTTPException(
                    status_code=403,
                    detail="Указанная папка вам не принадлежит"
                )
        
        # Удаляем старые привязки карты к папкам пользователя
        crud.remove_map_from_user_folders(db, map_data.map_id, current_user.user_id)
        
        # Если указана целевая папка - добавляем в неё
        if map_data.target_folder_id:
            crud.add_map_to_folder(db, map_data.map_id, map_data.target_folder_id)
        
        return {"success": True, "message": "Карта успешно перемещена"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при перемещении ярлыка: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при перемещении ярлыка: {str(e)}")

@router.put("/shared-maps/move", response_model=schemas.Folder, summary="Переместить ярлык общей карты в другую папку", 
           description="Перемещает ярлык общей карты в указанную папку или в корневой каталог")
def move_shared_map(
    data: schemas.SharedMapMove,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_user_id_from_token)
):
    """
    Переместить ярлык общей карты в другую папку
    
    - **map_id**: ID общей карты
    - **target_folder_id**: ID целевой папки (null для перемещения в корневой каталог)
    """
    try:
        logger.info(f"Перемещение ярлыка общей карты {data.map_id} в папку {data.target_folder_id}")
        
        # Проверяем, что пользователь имеет доступ к этой карте через шеринг
        sharing = crud.get_sharing_by_resource_id(db, data.map_id, user_id)
        if not sharing:
            logger.error(f"Доступ к карте {data.map_id} не найден для пользователя {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Общая карта не найдена или у вас нет к ней доступа"
            )
            
        # Если указана целевая папка, проверяем, что она принадлежит пользователю
        if data.target_folder_id:
            if not crud.check_folder_ownership(db, data.target_folder_id, user_id):
                logger.error(f"Папка {data.target_folder_id} не принадлежит пользователю {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Указанная папка не принадлежит текущему пользователю"
                )
        
        # Перемещаем ярлык карты
        result = crud.move_shared_map_to_folder(db, data.map_id, user_id, data.target_folder_id)
        
        return result
    except HTTPException as e:
        # Пробрасываем HTTP-исключения дальше
        raise e
    except Exception as e:
        logger.error(f"Ошибка при перемещении ярлыка общей карты: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось переместить ярлык карты: {str(e)}"
        ) 