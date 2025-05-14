from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from uuid import UUID
from jose import jwt
from app import models, schemas, config
from typing import Optional, Dict, Any, List
from sqlalchemy import text
import uuid
import re
import logging

# Добавлены улучшения для работы с виртуальным полем map_id в схеме Marker.
# Функции get_marker и get_markers_by_map теперь корректно заполняют это поле.

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = config.settings.SECRET_KEY
ALGORITHM  = config.settings.ALGORITHM
EXPIRE_MIN = config.settings.ACCESS_TOKEN_EXPIRE_MINUTES

# ————————————————————————————————————————————————
# User
def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, user: schemas.UserCreate):
    print(f"DEBUG: create_user: Создание пользователя {user.username} / {user.email}")
    try:
        hashed = pwd_context.hash(user.password)
        db_user = models.User(username=user.username, email=user.email, password=hashed)
        db.add(db_user)
        db.commit()  # Явно коммитим транзакцию
        print(f"DEBUG: create_user: Коммит выполнен успешно")
        
        # Обновляем объект из БД
        db.refresh(db_user)
        print(f"DEBUG: create_user: Пользователь создан с ID: {db_user.user_id}")
        
        # Проверим, что пользователь действительно создан и доступен
        from sqlalchemy import text
        check_query = text("SELECT user_id, username, email FROM topotik.users WHERE user_id = :user_id")
        result = db.execute(check_query, {"user_id": str(db_user.user_id)}).first()
        print(f"DEBUG: create_user: Проверка SQL - пользователь найден: {result is not None}")
        
        if result:
            print(f"DEBUG: create_user: Данные пользователя: ID={result.user_id}, username={result.username}")
        
        return db_user
    except Exception as e:
        print(f"DEBUG: create_user: Ошибка при создании пользователя: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise

def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()

def get_user(db: Session, user_id: UUID):
    print(f"DEBUG: get_user вызван с user_id: {user_id}")
    if not user_id:
        print(f"DEBUG: get_user: user_id отсутствует или None")
        return None
    
    # Проверяем тип UUID
    try:
        if isinstance(user_id, str):
            user_id = UUID(user_id)
            print(f"DEBUG: get_user: user_id преобразован из строки в UUID")
    except ValueError as e:
        print(f"DEBUG: get_user: ошибка преобразования user_id в UUID: {str(e)}")
        return None
    
    # Запрос к БД
    try:
        user = db.query(models.User).filter(models.User.user_id == user_id).first()
        print(f"DEBUG: get_user: результат запроса: {'пользователь найден' if user else 'пользователь не найден'}")
        return user
    except Exception as e:
        print(f"DEBUG: get_user: ошибка запроса к БД: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def update_user(db: Session, user_id: str, user_update: schemas.UserUpdate) -> Optional[models.User]:
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user:
        return None
    
    if user_update.username is not None:
        user.username = user_update.username
    
    if user_update.email is not None:
        user.email = user_update.email
    
    if user_update.password is not None:
        hashed_password = pwd_context.hash(user_update.password)
        user.password = hashed_password
    
    if user_update.settings is not None:
        user.settings = user_update.settings
    
    db.commit()
    db.refresh(user)
    return user

def get_user_settings(db: Session, user_id: UUID) -> Optional[Dict]:
    """
    Получить настройки пользователя
    
    Args:
        db (Session): Сессия базы данных
        user_id (UUID): ID пользователя
        
    Returns:
        Dict: Словарь настроек пользователя или пустой словарь, если настройки не найдены
    """
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user or not user.settings:
        return {}
    return user.settings

def update_user_settings(db: Session, user_id: UUID, settings: Dict) -> Optional[Dict]:
    """
    Обновить настройки пользователя, используя прямой SQL запрос
    
    Args:
        db (Session): Сессия базы данных
        user_id (UUID): ID пользователя
        settings (Dict): Словарь с настройками для обновления
        
    Returns:
        Dict: Обновленные настройки пользователя или None, если пользователь не найден
    """
    print(f"DEBUG: update_user_settings [НОВАЯ ВЕРСИЯ]: вызван с user_id: {user_id}")
    print(f"DEBUG: update_user_settings: тип user_id: {type(user_id)}")
    print(f"DEBUG: update_user_settings: настройки для обновления: {settings}")
    
    try:
        # Преобразуем user_id в строку для безопасности
        user_id_str = str(user_id)
        print(f"DEBUG: update_user_settings: user_id преобразован в строку: {user_id_str}")
        
        # Проверим существование пользователя напрямую через SQL
        from sqlalchemy import text
        import json
        
        # Проверяем существование пользователя в БД
        check_query = text("SELECT user_id, username, email FROM topotik.users WHERE user_id = :user_id")
        user_exists = db.execute(check_query, {"user_id": user_id_str}).first()
        
        if not user_exists:
            print(f"DEBUG: update_user_settings: пользователь не найден в БД по ID: {user_id_str}")
            
            # Проверим, сколько всего пользователей в БД
            count_query = text("SELECT COUNT(*) FROM topotik.users")
            total_users = db.execute(count_query).scalar()
            print(f"DEBUG: update_user_settings: всего пользователей в БД: {total_users}")
            
            if total_users > 0:
                # Проверим последнего созданного пользователя
                recent_query = text("SELECT user_id, username, email FROM topotik.users ORDER BY created_at DESC LIMIT 1")
                recent_user = db.execute(recent_query).first()
                print(f"DEBUG: update_user_settings: последний созданный пользователь: {recent_user}")
                
                # Проверим всех пользователей
                all_users_query = text("SELECT user_id, username, email FROM topotik.users LIMIT 10")
                all_users = db.execute(all_users_query).fetchall()
                print(f"DEBUG: update_user_settings: список пользователей (до 10): {all_users}")
            
            # Создаем нового пользователя с этим ID (аварийное решение)
            print(f"DEBUG: update_user_settings: создаем нового пользователя с ID: {user_id_str}")
            emergency_create_query = text("""
                INSERT INTO topotik.users (user_id, username, email, password, settings, created_at)
                VALUES (:user_id, :username, :email, :password, :settings, NOW())
                ON CONFLICT (user_id) DO NOTHING
                RETURNING user_id
            """)
            
            emergency_result = db.execute(emergency_create_query, {
                "user_id": user_id_str,
                "username": f"emergency_user_{user_id_str[:8]}",
                "email": f"emergency_{user_id_str[:8]}@example.com",
                "password": "emergency_password_hash", # Нормальный hash будет создан позже
                "settings": json.dumps(settings)
            }).first()
            
            db.commit()
            
            if emergency_result:
                print(f"DEBUG: update_user_settings: успешно создан аварийный пользователь с ID: {emergency_result.user_id}")
                return settings
            else:
                print(f"DEBUG: update_user_settings: не удалось создать аварийного пользователя")
                return None
        
        print(f"DEBUG: update_user_settings: пользователь найден: {user_exists}")
        
        # Преобразуем словарь настроек в JSON строку
        settings_json = json.dumps(settings)
        
        # Обновляем настройки напрямую через SQL с исправленным синтаксисом
        # Используем cast() функцию PostgreSQL вместо оператора :: для приведения типов
        update_query = text("""
            UPDATE topotik.users 
            SET settings = cast(:settings AS jsonb)
            WHERE user_id = :user_id
            RETURNING settings
        """)
        
        result = db.execute(update_query, {
            "user_id": user_id_str,
            "settings": settings_json
        }).first()
        
        db.commit()
        
        if result and result.settings:
            try:
                # Если результат в виде строки JSON, парсим его
                if isinstance(result.settings, str):
                    updated_settings = json.loads(result.settings)
                else:
                    # Иначе возвращаем как есть
                    updated_settings = result.settings
                    
                print(f"DEBUG: update_user_settings: настройки успешно обновлены")
                return updated_settings
            except Exception as parse_error:
                print(f"DEBUG: update_user_settings: ошибка при парсинге результата: {str(parse_error)}")
                # Возвращаем исходные настройки, так как они должны быть применены
                return settings
        else:
            print(f"DEBUG: update_user_settings: ошибка обновления, нет результата")
            return None
        
    except Exception as e:
        print(f"DEBUG: update_user_settings: неожиданная ошибка: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise

def reset_user_settings(db: Session, user_id: UUID) -> Dict:
    """
    Сбросить настройки пользователя к значениям по умолчанию
    
    Args:
        db (Session): Сессия базы данных
        user_id (UUID): ID пользователя
        
    Returns:
        Dict: Настройки пользователя по умолчанию
    """
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user:
        return None
    
    # Значения настроек по умолчанию
    default_settings = {
        "map": {
            "defaultCity": "Москва",
            "defaultCoordinates": {
                "lat": 55.7558,
                "lng": 37.6173
            },
            "defaultZoom": 13,
            "units": "km",
            "showGrid": False
        },
        "ui": {
            "theme": "light",
            "fontSize": "medium",
            "language": "ru"
        },
        "editor": {
            "defaultMarkerColor": "#FF5733",
            "autoSave": 5
        },
        "privacy": {
            "defaultMapPrivacy": "private",
            "defaultCollectionPrivacy": "private"
        }
    }
    
    user.settings = default_settings
    db.commit()
    db.refresh(user)
    return user.settings

def check_user_data_availability(db: Session, email: str, username: str, user_id: Optional[UUID] = None) -> Dict[str, bool]:
    """
    Проверяет, существуют ли уже пользователи с указанными email и username.
    Возвращает словарь с ключами email_exists и username_exists.
    """
    query = text("""
        SELECT * FROM topotik.check_user_data_availability(:email, :username, :user_id)
    """)
    
    result = db.execute(query, {
        "email": email,
        "username": username,
        "user_id": str(user_id) if user_id else None
    }).fetchone()
    
    return {
        "email_exists": result.email_exists,
        "username_exists": result.username_exists
    }

# ————————————————————————————————————————————————
# Folders
def get_folder(db: Session, folder_id: UUID):
    return db.query(models.Folder).filter(models.Folder.folder_id == folder_id).first()

def get_folder_with_children(db: Session, folder_id: UUID) -> Optional[models.Folder]:
    return db.query(models.Folder).filter(models.Folder.folder_id == folder_id).first()

def get_root_folders(db: Session, user_id: UUID) -> List[models.Folder]:
    """Получить все корневые папки пользователя (без родительской папки)"""
    try:
        return db.query(models.Folder).filter(
            models.Folder.user_id == user_id,
            models.Folder.parent_folder_id == None
        ).all()
    except Exception as e:
        print(f"Ошибка при получении корневых папок: {str(e)}")
        # В случае ошибки возвращаем пустой список
        return []

def get_user_folders(db: Session, user_id: UUID) -> List[models.Folder]:
    """Получить все папки пользователя"""
    try:
        return db.query(models.Folder).filter(
            models.Folder.user_id == user_id
        ).all()
    except Exception as e:
        print(f"Ошибка при получении папок пользователя: {str(e)}")
        # В случае ошибки возвращаем пустой список
        return []

def get_folder_content(db: Session, folder_id: UUID) -> Dict[str, List]:
    """Получить содержимое папки (подпапки и карты)"""
    try:
        # Используем прямой SQL запрос для получения подпапок
        subfolders_query = text("""
            SELECT folder_id, title, created_at, parent_folder_id, user_id
            FROM topotik.folders
            WHERE parent_folder_id = :folder_id
        """)
        
        subfolders_result = db.execute(subfolders_query, {"folder_id": str(folder_id)})
        
        subfolders = []
        for row in subfolders_result:
            folder = models.Folder(
                folder_id=row.folder_id,
                title=row.title,
                created_at=row.created_at,
                parent_folder_id=row.parent_folder_id,
                user_id=row.user_id
            )
            subfolders.append(folder)
        
        # Используем прямой SQL запрос для получения карт в папке
        maps_query = text("""
            SELECT m.map_id, m.title, m.map_type, m.is_public, m.created_at
            FROM topotik.maps m
            JOIN topotik.folder_maps fm ON m.map_id = fm.map_id
            WHERE fm.folder_id = :folder_id
        """)
        
        maps_result = db.execute(maps_query, {"folder_id": str(folder_id)})
        
        maps_in_folder = []
        for row in maps_result:
            map_obj = models.Map(
                map_id=row.map_id,
                title=row.title,
                map_type=row.map_type,
                is_public=row.is_public,
                created_at=row.created_at
            )
            maps_in_folder.append(map_obj)
        
        return {
            "subfolders": subfolders,
            "maps": maps_in_folder
        }
    except Exception as e:
        print(f"Ошибка при получении содержимого папки {folder_id}: {str(e)}")
        # В случае ошибки возвращаем пустые списки
        return {
            "subfolders": [],
            "maps": []
        }

def get_user_folder_structure(db: Session, user_id: UUID) -> List[Dict]:
    """Получить иерархическую структуру папок пользователя"""
    try:
        # Получаем корневые папки
        root_folders = get_root_folders(db, user_id)
        # Получаем карты пользователя, не привязанные к папкам
        root_maps = get_maps_without_folder(db, user_id)
        result = []
        # Обрабатываем корневые папки и рекурсивно добавляем дочерние элементы
        for folder in root_folders:
            try:
                folder_data = folder_to_dict(db, folder)
                result.append(folder_data)
            except Exception as e:
                print(f"Ошибка при обработке папки {folder.folder_id}: {str(e)}")
                continue
        # Добавляем карты верхнего уровня
        for map_item in root_maps:
            try:
                map_type_str = str(map_item.map_type)
                map_data = {
                    "id": str(map_item.map_id),
                    "type": "map",
                    "name": map_item.title,
                    "mapType": "real" if map_type_str == "osm" else "custom",
                    "created_at": map_item.created_at.isoformat()
                }
                result.append(map_data)
            except Exception as e:
                print(f"Ошибка при обработке карты {map_item.map_id}: {str(e)}")
                continue
        return result
    except Exception as e:
        # Добавляем логирование для отладки
        print(f"Ошибка при получении структуры папок: {str(e)}")
        # Вместо вызова исключения возвращаем пустой список
        return []

def folder_to_dict(db: Session, folder: models.Folder) -> Dict:
    """Преобразовать папку в словарь с подпапками и картами"""
    try:
        folder_dict = {
            "id": str(folder.folder_id),
            "type": "folder",
            "name": folder.title,
            "created_at": folder.created_at.isoformat(),
            "children": []
        }
        # Получаем подпапки напрямую через SQL запрос вместо ORM
        subfolders_query = text("""
            SELECT folder_id, title, created_at, parent_folder_id, user_id
            FROM topotik.folders
            WHERE parent_folder_id = :folder_id
        """)
        subfolders_result = db.execute(subfolders_query, {"folder_id": str(folder.folder_id)})
        # Добавляем подпапки
        for row in subfolders_result:
            subfolder = models.Folder(
                folder_id=row.folder_id,
                title=row.title,
                created_at=row.created_at,
                parent_folder_id=row.parent_folder_id,
                user_id=row.user_id
            )
            subfolder_dict = folder_to_dict(db, subfolder)
            folder_dict["children"].append(subfolder_dict)
        # Получаем карты в папке через прямой SQL запрос
        maps_query = text("""
            SELECT m.map_id, m.title, m.map_type, m.is_public, m.created_at
            FROM topotik.maps m
            JOIN topotik.folder_maps fm ON m.map_id = fm.map_id
            WHERE fm.folder_id = :folder_id
        """)
        maps_result = db.execute(maps_query, {"folder_id": str(folder.folder_id)})
        # Добавляем карты в папке
        for row in maps_result:
            map_type_str = str(row.map_type)
            map_dict = {
                "id": str(row.map_id),
                "type": "map",
                "name": row.title,
                "mapType": "real" if map_type_str == "osm" else "custom",
                "created_at": row.created_at.isoformat() if row.created_at else datetime.now().isoformat()
            }
            folder_dict["children"].append(map_dict)
        return folder_dict
    except Exception as e:
        # Добавляем логирование для отладки
        print(f"Ошибка при преобразовании папки {folder.folder_id} в словарь: {str(e)}")
        raise

def create_folder(db: Session, folder_in: schemas.FolderCreate, user_id: UUID) -> models.Folder:
    """Создать новую папку"""
    db_folder = models.Folder(
        user_id=user_id,
        title=folder_in.title,
        parent_folder_id=folder_in.parent_folder_id
    )
    db.add(db_folder)
    db.commit()
    db.refresh(db_folder)
    return db_folder

def update_folder(db: Session, folder_id: UUID, folder_data: schemas.FolderUpdate):
    """
    Обновляет информацию о папке
    
    Args:
        db (Session): Сессия базы данных
        folder_id (UUID): Идентификатор папки
        folder_data (schemas.FolderUpdate): Данные для обновления
    
    Returns:
        schemas.Folder: Обновленная папка или None в случае ошибки
    """
    try:
        # Преобразуем UUID в строку для SQL-запроса
        folder_id_str = str(folder_id)
        # Проверяем, какие поля обновлять
        set_clauses = []
        params = {"folder_id": folder_id_str}
        if folder_data.title is not None:
            set_clauses.append("title = :title")
            params["title"] = folder_data.title
        # Если нет полей для обновления, возвращаем текущую папку
        if not set_clauses:
            return get_folder_by_id(db, folder_id)
        # Формируем SET часть SQL запроса
        set_clause = ", ".join(set_clauses)
        # Выполняем обновление
        query = text(f"""
            UPDATE topotik.folders 
            SET {set_clause}
            WHERE folder_id = :folder_id
            RETURNING folder_id, title, user_id, parent_folder_id
        """)
        result = db.execute(query, params).fetchone()
        db.commit()
        if result:
            folder = schemas.Folder(
                folder_id=UUID(result[0]),
                title=result[1],
                user_id=UUID(result[2]),
                parent_folder_id=UUID(result[3]) if result[3] else None
            )
            return folder
        return None
    except Exception as e:
        db.rollback()
        print(f"Ошибка при обновлении папки: {str(e)}")
        return None

def move_folder(db: Session, folder_id: UUID, new_parent_id: Optional[UUID]) -> bool:
    """
    Перемещает папку в указанную родительскую папку или в корень.
    Проверяет циклические зависимости при перемещении.
    """
    try:
        folder_result = db.execute(
            text("""
                SELECT folder_id, user_id, parent_folder_id 
                FROM topotik.folders 
                WHERE folder_id = :folder_id
            """),
            {"folder_id": str(folder_id)}
        ).fetchone()
        if not folder_result:
            print(f"Папка {folder_id} не найдена")
            return False
        if new_parent_id is None:
            db.execute(
                text("""
                    UPDATE topotik.folders 
                    SET parent_folder_id = NULL 
                    WHERE folder_id = :folder_id
                """),
                {"folder_id": str(folder_id)}
            )
            db.commit()
            return True
        parent_result = db.execute(
            text("""
                SELECT folder_id, user_id 
                FROM topotik.folders 
                WHERE folder_id = :folder_id
            """),
            {"folder_id": str(new_parent_id)}
        ).fetchone()
        if not parent_result:
            print(f"Родительская папка {new_parent_id} не найдена")
            return False
        if str(folder_id) == str(new_parent_id):
            print("Нельзя переместить папку в саму себя")
            return False
        current_id = str(new_parent_id)
        while current_id is not None:
            parent_folder = db.execute(
                text("""
                    SELECT parent_folder_id 
                    FROM topotik.folders 
                    WHERE folder_id = :folder_id
                """),
                {"folder_id": current_id}
            ).fetchone()
            if not parent_folder:
                break
            if parent_folder[0] is None:
                break
            current_id = parent_folder[0]
            if current_id == str(folder_id):
                print("Обнаружена циклическая зависимость при перемещении папки")
                return False
        db.execute(
            text("""
                UPDATE topotik.folders 
                SET parent_folder_id = :new_parent_id 
                WHERE folder_id = :folder_id
            """),
            {"folder_id": str(folder_id), "new_parent_id": str(new_parent_id)}
        )
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Ошибка при перемещении папки: {e}")
        return False

def add_map_to_folder(db: Session, map_id: UUID, folder_id: UUID) -> bool:
    """Добавить карту в папку"""
    try:
        # Проверяем существование карты и папки
        map_item = get_map(db, map_id)
        folder = get_folder(db, folder_id)
        
        if not map_item or not folder:
            return False
        
        # Используем прямой SQL запрос для добавления связи
        insert_query = text("""
            INSERT INTO topotik.folder_maps (folder_id, map_id)
            VALUES (:folder_id, :map_id)
            ON CONFLICT DO NOTHING
        """)
        
        db.execute(
            insert_query, 
            {
                "folder_id": str(folder_id),
                "map_id": str(map_id)
            }
        )
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Ошибка при добавлении карты в папку: {str(e)}")
        return False

def remove_map_from_folder(db: Session, map_id: UUID, folder_id: UUID) -> bool:
    """Удалить карту из папки"""
    try:
        # Проверяем существование карты и папки
        map_item = get_map(db, map_id)
        folder = get_folder(db, folder_id)
        
        if not map_item or not folder:
            return False
        
        # Проверяем, есть ли связь между картой и папкой
        check_query = text("""
            SELECT 1 FROM topotik.folder_maps
            WHERE folder_id = :folder_id AND map_id = :map_id
        """)
        
        result = db.execute(
            check_query, 
            {
                "folder_id": str(folder_id),
                "map_id": str(map_id)
            }
        ).fetchone()
        
        if not result:
            return False  # Связь не найдена
        
        # Удаляем связь с помощью прямого SQL запроса
        delete_query = text("""
            DELETE FROM topotik.folder_maps
            WHERE folder_id = :folder_id AND map_id = :map_id
        """)
        
        db.execute(
            delete_query, 
            {
                "folder_id": str(folder_id),
                "map_id": str(map_id)
            }
        )
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Ошибка при удалении карты из папки: {str(e)}")
        return False

def delete_folder(db: Session, folder_id: UUID) -> bool:
    """
    Удаляет папку и все её содержимое каскадно (включая все подпапки и все карты в них).
    
    folder_id: UUID удаляемой папки
    
    Возвращает True в случае успеха, False в случае ошибки.
    """
    try:
        # Получаем список всех подпапок для каскадного удаления с информацией о глубине вложенности
        # Используем WITH RECURSIVE для получения всего дерева подпапок вместе с уровнем вложенности
        subfolders_query = text("""
            WITH RECURSIVE folder_tree AS (
                -- Базовый случай: начальная папка
                SELECT folder_id, parent_folder_id, 0 as depth
                FROM topotik.folders
                WHERE folder_id = :root_folder_id
                
                UNION ALL
                
                -- Рекурсивный случай: все подпапки
                SELECT f.folder_id, f.parent_folder_id, ft.depth + 1
                FROM topotik.folders f
                JOIN folder_tree ft ON f.parent_folder_id = ft.folder_id
            )
            SELECT folder_id, depth FROM folder_tree ORDER BY depth DESC
        """)
        
        # Выполняем запрос для получения всех ID подпапок, отсортированных по глубине (сначала самые глубокие)
        result = db.execute(subfolders_query, {"root_folder_id": str(folder_id)})
        
        folders_to_delete = []
        for row in result:
            folders_to_delete.append(str(row.folder_id))
        
        print(f"Папки для удаления (отсортированные по глубине вложенности): {folders_to_delete}")
        
        # Получаем ID всех карт, которые находятся в удаляемых папках
        if folders_to_delete:
            maps_query = text("""
                SELECT map_id FROM topotik.folder_maps 
                WHERE folder_id IN :folder_ids
            """)
            
            maps_result = db.execute(
                maps_query, 
                {"folder_ids": tuple(folders_to_delete)}
            ).fetchall()
            
            maps_to_delete = [str(row.map_id) for row in maps_result]
            print(f"Карты для удаления: {maps_to_delete}")
            
            # Удаляем связи между картами и папками
            for folder_id_str in folders_to_delete:
                db.execute(
                    text("""
                        DELETE FROM topotik.folder_maps 
                        WHERE folder_id = :folder_id
                    """),
                    {"folder_id": folder_id_str}
                )
            
            # Удаляем права доступа к картам
            if maps_to_delete:
                db.execute(
                    text("""
                        DELETE FROM topotik.map_access
                        WHERE map_id IN :map_ids
                    """),
                    {"map_ids": tuple(maps_to_delete)}
                )
                
                # Удаляем сами карты
                db.execute(
                    text("""
                        DELETE FROM topotik.maps
                        WHERE map_id IN :map_ids
                    """),
                    {"map_ids": tuple(maps_to_delete)}
                )
            
            # Удаляем папки в правильном порядке - от самых глубоко вложенных к корневой
            # Порядок folders_to_delete уже отсортирован по глубине (благодаря ORDER BY depth DESC в запросе)
            for folder_id_str in folders_to_delete:
                db.execute(
                    text("""
                        DELETE FROM topotik.folders 
                        WHERE folder_id = :folder_id
                    """),
                    {"folder_id": folder_id_str}
                )
            
            db.commit()
            return True
        else:
            print(f"Папка {folder_id} не найдена")
            return False
    except Exception as e:
        db.rollback()
        print(f"Ошибка при удалении папки: {e}")
        import traceback
        traceback.print_exc()
        return False

def move_map_to_folder(db: Session, user_id: UUID, map_id: UUID, folder_id: Optional[UUID] = None) -> bool:
    """
    Перемещает карту в указанную папку.
    Если folder_id=None, карта перемещается в корневую директорию.
    """
    try:
        # Преобразуем UUID в строки
        user_id_str = str(user_id)
        map_id_str = str(map_id)
        folder_id_str = str(folder_id) if folder_id else None
        
        print(f"Перемещение карты: map_id={map_id_str}, user_id={user_id_str}, folder_id={folder_id_str}")
        
        # Проверяем существование карты
        map_exists = db.execute(
            text("""
                SELECT 1 FROM topotik.maps WHERE map_id = :map_id
            """),
            {"map_id": map_id_str}
        ).fetchone()
        
        if not map_exists:
            print(f"Карта {map_id_str} не найдена")
            return False
            
        # Проверяем, является ли пользователь владельцем карты
        if not check_map_ownership(db, map_id, user_id):
            print(f"Пользователь {user_id_str} не имеет прав на карту {map_id_str}")
            return False
            
        # Удаляем карту из всех папок пользователя
        db.execute(
            text("""
                DELETE FROM topotik.folder_maps fm
                USING topotik.folders f
                WHERE fm.map_id = :map_id 
                  AND fm.folder_id = f.folder_id 
                  AND f.user_id = :user_id
            """),
            {"map_id": map_id_str, "user_id": user_id_str}
        )
        
        # Если указана папка, добавляем карту в нее
        if folder_id:
            # Проверяем, что папка принадлежит пользователю
            folder_exists = db.execute(
                text("""
                    SELECT 1 FROM topotik.folders 
                    WHERE folder_id = :folder_id AND user_id = :user_id
                """),
                {"folder_id": folder_id_str, "user_id": user_id_str}
            ).fetchone()
            
            if not folder_exists:
                print(f"Папка {folder_id_str} не принадлежит пользователю {user_id_str} или не существует")
                db.rollback()
                return False
                
            # Добавляем карту в указанную папку
            db.execute(
                text("""
                    INSERT INTO topotik.folder_maps (folder_id, map_id)
                    VALUES (:folder_id, :map_id)
                """),
                {"folder_id": folder_id_str, "map_id": map_id_str}
            )
            
        db.commit()
        print(f"Карта {map_id_str} успешно перемещена")
        return True
    except Exception as e:
        db.rollback()
        print(f"Ошибка при перемещении карты: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_maps_without_folder(db: Session, user_id: UUID) -> List[models.Map]:
    """Получить все карты пользователя, не привязанные к папкам"""
    try:
        # Используем прямой SQL запрос для получения карт без папок
        query = text("""
            WITH user_maps AS (
                -- Получаем все карты, к которым у пользователя есть доступ через map_access
                SELECT m.map_id, m.title, m.map_type, m.is_public, m.created_at
                FROM topotik.maps m
                JOIN topotik.map_access ma ON m.map_id = ma.map_id
                WHERE ma.user_id = :user_id AND ma.permission = 'edit'
            ),
            maps_in_folders AS (
                -- Получаем ID всех карт, которые находятся в папках
                SELECT map_id FROM topotik.folder_maps
            )
            -- Выбираем карты пользователя, не привязанные к папкам
            SELECT um.map_id, um.title, um.map_type, um.is_public, um.created_at
            FROM user_maps um
            WHERE um.map_id NOT IN (SELECT map_id FROM maps_in_folders)
        """)
        
        result = db.execute(query, {"user_id": str(user_id)})
        
        # Преобразуем результаты в объекты Map
        maps_without_folders = []
        for row in result:
            map_obj = models.Map(
                map_id=row.map_id,
                title=row.title,
                map_type=row.map_type,
                is_public=row.is_public,
                created_at=row.created_at
            )
            maps_without_folders.append(map_obj)
            
        print(f"Найдено {len(maps_without_folders)} карт без папок для пользователя {user_id}")
        return maps_without_folders
    except Exception as e:
        print(f"Ошибка при получении карт без папок: {str(e)}")
        # В случае ошибки возвращаем пустой список
        return []

def remove_map_from_all_folders(db: Session, map_id: UUID) -> bool:
    """Удалить карту из всех папок (переместить в корень)"""
    map_item = get_map(db, map_id)
    if not map_item:
        return False
    
    # Очищаем связи карты со всеми папками
    map_item.folders = []
    db.commit()
    db.refresh(map_item)
    return True

# ————————————————————————————————————————————————
# Auth
def authenticate_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username)
    if not user or not pwd_context.verify(password, user.password):
        return False
    return user

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=EXPIRE_MIN)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ————————————————————————————————————————————————
# Maps
def create_map(db: Session, map_in: schemas.MapCreate, user_id: UUID):
    """
    Создает новую карту и связывает её с пользователем через rights_map
    Если указана папка, добавляет карту в эту папку
    """
    try:
        # Генерируем UUID для новой карты
        map_id = uuid.uuid4()
        
        # Преобразуем все UUID в строки для отладки и предотвращения ошибок
        user_id_str = str(user_id)
        map_id_str = str(map_id)
        folder_id_str = None
        
        # Выводим отладочную информацию
        print(f"Создание карты: map_id={map_id_str}, user_id={user_id_str}")
        print(f"Параметры: title={map_in.title}, type={map_in.map_type}, folder_id={map_in.folder_id}, current_folder_id={map_in.current_folder_id}")
        
        # Проверяем данные
        if not map_in.title or not map_in.map_type:
            raise ValueError("Не указано название или тип карты")
        
        # Проверяем, не содержит ли название запрещенные символы
        if re.search(r'[{}"[\]<>]', map_in.title):
            raise ValueError("Название содержит запрещенные символы")
            
        # Определяем папку, в которую нужно добавить карту
        folder_id_str = None
        
        # Если указана папка, используем её, предварительно преобразовав в строку
        if map_in.folder_id:
            folder_id_str = str(map_in.folder_id)
            print(f"Используем указанную папку: {folder_id_str}")
        
        # Иначе используем текущую открытую папку, если она указана
        elif map_in.current_folder_id:
            current_folder_id_str = str(map_in.current_folder_id)
            print(f"Проверяем текущую папку: {current_folder_id_str}")
            
            # Преобразуем строку обратно в UUID для check_folder_ownership
            current_folder_uuid = UUID(current_folder_id_str)
            
            if check_folder_ownership(db, current_folder_uuid, UUID(user_id_str)):
                folder_id_str = current_folder_id_str
                print(f"Используем текущую папку: {folder_id_str}")
            else:
                print(f"Папка {current_folder_id_str} не принадлежит пользователю {user_id_str}")
        
        # Создаем карту с базовыми полями
        insert_query = text("""
            INSERT INTO topotik.maps (map_id, title, map_type, is_public)
            VALUES (:map_id, :title, :map_type, :is_public)
            RETURNING map_id, title, map_type, is_public, created_at
        """)
        
        result = db.execute(
            insert_query, 
            {
                "map_id": map_id_str,
                "title": map_in.title,
                "map_type": map_in.map_type.value,
                "is_public": map_in.is_public
            }
        ).fetchone()
        
        # Добавляем права доступа для владельца карты
        access_query = text("""
            INSERT INTO topotik.map_access (user_id, map_id, permission)
            VALUES (:user_id, :map_id, 'edit')
        """)
        
        db.execute(
            access_query, 
            {
                "user_id": user_id_str,
                "map_id": map_id_str
            }
        )
        
        # Если определена папка, добавляем карту в эту папку
        if folder_id_str:
            folder_query = text("""
                INSERT INTO topotik.folder_maps (folder_id, map_id)
                VALUES (:folder_id, :map_id)
            """)
            
            db.execute(
                folder_query, 
                {
                    "folder_id": folder_id_str,
                    "map_id": map_id_str
                }
            )
        
        db.commit()
        
        # Преобразуем результат в модель для возврата
        if result:
            print(f"Карта успешно создана: {result.map_id}")
            print(f"Тип result.map_id: {type(result.map_id)}")
            
            # Проверяем тип result.map_id и обрабатываем соответственно
            if isinstance(result.map_id, UUID):
                # Если уже UUID, используем как есть
                map_id_for_schema = result.map_id
                print(f"result.map_id уже UUID, используем как есть")
            elif isinstance(result.map_id, str):
                # Если строка, преобразуем в UUID
                map_id_for_schema = UUID(result.map_id)
                print(f"result.map_id - строка, преобразуем в UUID")
            else:
                # Если другой тип, пробуем преобразовать в строку, а затем в UUID
                map_id_for_schema = UUID(str(result.map_id))
                print(f"result.map_id - другой тип ({type(result.map_id)}), преобразуем в строку, затем в UUID")
            
            return schemas.Map(
                map_id=map_id_for_schema,
                title=result.title,
                map_type=result.map_type,
                is_public=result.is_public,
                created_at=result.created_at
            )
        
        return None  # Не должно произойти, но на всякий случай
    except Exception as e:
        db.rollback()
        print(f"Ошибка при создании карты: {str(e)}")
        # Печатаем полный стек ошибки для отладки
        import traceback
        traceback.print_exc()
        raise

def get_maps(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Map).offset(skip).limit(limit).all()

def get_user_maps(db: Session, user_id: UUID):
    """Получить все карты пользователя через связи с папками"""
    try:
        # В БД нет прямой связи между пользователями и картами
        # Получаем карты через папки пользователя
        maps_query = (
            db.query(models.Map)
            .join(models.folder_maps, models.Map.map_id == models.folder_maps.c.map_id)
            .join(models.Folder, models.folder_maps.c.folder_id == models.Folder.folder_id)
            .filter(models.Folder.user_id == user_id)
            .distinct()  # Карта может быть в нескольких папках
        )
        return maps_query.all()
    except Exception as e:
        print(f"Ошибка при получении карт пользователя: {str(e)}")
        return []

def check_map_ownership(db: Session, map_id: UUID, user_id: UUID) -> bool:
    """
    Проверяет, имеет ли пользователь права на редактирование карты.
    Права проверяются непосредственно через запись в map_access.
    
    map_id: UUID карты
    user_id: UUID пользователя
    
    Возвращает True, если у пользователя есть права на редактирование
    """
    try:
        result = db.execute(
            text("""
                SELECT 1 
                FROM topotik.map_access 
                WHERE map_id = :map_id 
                  AND user_id = :user_id 
                  AND permission = 'edit'
            """),
            {"map_id": str(map_id), "user_id": str(user_id)}
        ).fetchone()
        
        return result is not None
    except Exception as e:
        print(f"Ошибка при проверке прав доступа к карте: {e}")
        return False

def get_map(db: Session, map_id: UUID):
    return db.query(models.Map).filter(models.Map.map_id == map_id).first()

def update_map(db: Session, map_id: UUID, data: schemas.MapUpdate):
    """
    Обновляет информацию о карте
    
    Args:
        db (Session): Сессия базы данных
        map_id (UUID): ID карты
        data (schemas.MapUpdate): Данные для обновления
    
    Returns:
        schemas.Map: Обновленная карта или None, если карта не найдена
    """
    try:
        # Преобразуем UUID в строку для SQL-запроса
        map_id_str = str(map_id)
        
        # Формируем части запроса для обновления
        set_clauses = []
        params = {"map_id": map_id_str}
        
        if data.title is not None:
            set_clauses.append("title = :title")
            params["title"] = data.title
            
        if data.map_type is not None:
            set_clauses.append("map_type = :map_type")
            params["map_type"] = data.map_type.value
            
        if data.is_public is not None:
            set_clauses.append("is_public = :is_public")
            params["is_public"] = data.is_public
            
        # Если нет данных для обновления, возвращаем текущую карту
        if not set_clauses:
            return get_map(db, map_id)
            
        # Формируем SQL-запрос
        set_clause = ", ".join(set_clauses)
        update_query = text(f"""
            UPDATE topotik.maps 
            SET {set_clause}
            WHERE map_id = :map_id
            RETURNING map_id, title, map_type, is_public, created_at
        """)
        
        # Выполняем запрос
        result = db.execute(update_query, params).fetchone()
        db.commit()
        
        if result:
            print(f"Обновлена карта: {result.map_id}, тип: {type(result.map_id)}")
            
            # Проверяем тип result.map_id и обрабатываем соответственно
            if isinstance(result.map_id, UUID):
                # Если уже UUID, используем как есть
                map_id_for_schema = result.map_id
            elif isinstance(result.map_id, str):
                # Если строка, преобразуем в UUID
                map_id_for_schema = UUID(result.map_id)
            else:
                # Если другой тип, пробуем преобразовать в строку, а затем в UUID
                map_id_for_schema = UUID(str(result.map_id))
            
            return schemas.Map(
                map_id=map_id_for_schema,
                title=result.title,
                map_type=result.map_type,
                is_public=result.is_public,
                created_at=result.created_at
            )
        return None
    except Exception as e:
        db.rollback()
        print(f"Ошибка при обновлении карты: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def delete_map(db: Session, map_id: UUID):
    """Удалить карту и связи с папками"""
    try:
        # Получаем карту
        db_map = db.query(models.Map).filter(models.Map.map_id == map_id).first()
        if not db_map:
            return None
        
        # Удаляем связи с папками с помощью явного запроса
        delete_stmt = models.folder_maps.delete().where(models.folder_maps.c.map_id == map_id)
        db.execute(delete_stmt)
        db.commit()
        
        # Удаляем карту
        db.delete(db_map)
        db.commit()
        
        return db_map
    except Exception as e:
        db.rollback()
        print(f"Ошибка при удалении карты: {str(e)}")
        raise

# ————————————————————————————————————————————————
# Collections
def get_collection(db: Session, collection_id: UUID):
    """Получить коллекцию по ID"""
    return db.query(models.Collection).filter(models.Collection.collection_id == collection_id).first()

def get_collections(db: Session, skip: int = 0, limit: int = 100):
    """Получить список коллекций с пагинацией"""
    return db.query(models.Collection).offset(skip).limit(limit).all()

def get_collections_by_map(db: Session, map_id: UUID):
    """Получить все коллекции для указанной карты"""
    try:
        collections = db.query(models.Collection).filter(models.Collection.map_id == map_id).all()
        return collections
    except Exception as e:
        print(f"Ошибка при получении коллекций для карты {map_id}: {str(e)}")
        return []

def check_collection_access(db: Session, collection_id: UUID, user_id: UUID, permission: str = "view") -> bool:
    """Проверить, имеет ли пользователь доступ к коллекции с указанным правом"""
    logger = logging.getLogger(__name__)
    
    logger.info(f"Проверка доступа к коллекции {collection_id} для пользователя {user_id} с правом {permission}")
    
    try:
        # Проверяем права через таблицу collection_access
        access_query = text("""
            SELECT 1 FROM topotik.collection_access
            WHERE collection_id = :collection_id 
              AND user_id = :user_id 
              AND permission = :permission
        """)
        
        access = db.execute(
            access_query, 
            {
                "collection_id": str(collection_id),
                "user_id": str(user_id),
                "permission": permission
            }
        ).fetchone()
        
        if access:
            logger.debug(f"Пользователь {user_id} имеет прямые права доступа к коллекции {collection_id}")
            return True
        
        # Если это публичная коллекция и запрашивается просмотр
        if permission == "view":
            collection = get_collection(db, collection_id)
            if collection and collection.is_public:
                logger.debug(f"Коллекция {collection_id} публичная, доступ разрешен")
                return True
        
        # ВАЖНО: Проверяем, является ли пользователь владельцем карты, к которой относится коллекция
        # Это дает полные права на коллекцию
        map_owner_query = text("""
            SELECT 1 FROM topotik.map_access ma
            JOIN topotik.collections c ON c.map_id = ma.map_id
            WHERE c.collection_id = :collection_id 
            AND ma.user_id = :user_id 
            AND ma.permission = 'edit'
        """)
        
        is_map_owner = db.execute(
            map_owner_query, 
            {
                "collection_id": str(collection_id),
                "user_id": str(user_id)
            }
        ).fetchone()
        
        if is_map_owner:
            logger.debug(f"Пользователь {user_id} владеет картой, к которой относится коллекция {collection_id}")
            return True
            
        logger.warning(f"Пользователь {user_id} не имеет доступа к коллекции {collection_id}")
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке доступа к коллекции {collection_id}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def create_collection(db: Session, collection_in: schemas.CollectionCreate, user_id: UUID):
    """Создать новую коллекцию и назначить пользователю права на неё"""
    try:
        # Проверяем доступ к карте
        if not check_map_ownership(db, collection_in.map_id, user_id):
            raise ValueError("У пользователя нет доступа к указанной карте")
        
        # Используем прямой SQL запрос для создания коллекции
        collection_id = uuid.uuid4()
        
        insert_query = text("""
            INSERT INTO topotik.collections (collection_id, map_id, title, is_public, collection_color)
            VALUES (:collection_id, :map_id, :title, :is_public, :collection_color)
            RETURNING collection_id
        """)
        
        db.execute(
            insert_query, 
            {
                "collection_id": str(collection_id),
                "map_id": str(collection_in.map_id),
                "title": collection_in.title,
                "is_public": collection_in.is_public,
                "collection_color": collection_in.collection_color if hasattr(collection_in, 'collection_color') else "#8A2BE2"
            }
        )
        db.commit()
        
        # Добавляем права доступа пользователю-создателю
        access_query = text("""
            INSERT INTO topotik.collection_access (user_id, collection_id, permission)
            VALUES (:user_id, :collection_id, 'edit')
        """)
        
        db.execute(
            access_query, 
            {
                "user_id": str(user_id),
                "collection_id": str(collection_id)
            }
        )
        db.commit()
        
        # Возвращаем созданную коллекцию
        return get_collection(db, collection_id)
    except Exception as e:
        db.rollback()
        print(f"Ошибка при создании коллекции: {str(e)}")
        raise

def update_collection(db: Session, collection_id: UUID, data: dict, user_id: UUID):
    """Обновить коллекцию"""
    try:
        # Проверяем права доступа
        if not check_collection_access(db, collection_id, user_id, "edit"):
            raise ValueError("У пользователя нет прав на редактирование этой коллекции")
        
        collection = get_collection(db, collection_id)
        if not collection:
            return None
        
        # Обновляем только допустимые поля
        allowed_fields = ['title', 'is_public', 'collection_color']
        update_data = {}
        
        for key, val in data.items():
            if key in allowed_fields:
                update_data[key] = val
        
        if not update_data:
            return collection  # Нет полей для обновления
        
        # Формируем SQL-запрос для обновления
        set_clause = ", ".join([f"{key} = :{key}" for key in update_data.keys()])
        update_query = text(f"""
            UPDATE topotik.collections
            SET {set_clause}
            WHERE collection_id = :collection_id
        """)
        
        # Добавляем collection_id в параметры
        update_data["collection_id"] = str(collection_id)
        
        # Выполняем запрос
        db.execute(update_query, update_data)
        db.commit()
        
        # Получаем обновленную коллекцию
        return get_collection(db, collection_id)
    except Exception as e:
        db.rollback()
        print(f"Ошибка при обновлении коллекции {collection_id}: {str(e)}")
        raise

def delete_collection(db: Session, collection_id: UUID, user_id: UUID):
    """Удалить коллекцию и все связанные с ней данные"""
    try:
        # Проверяем права доступа
        if not check_collection_access(db, collection_id, user_id, "edit"):
            raise ValueError("У пользователя нет прав на удаление этой коллекции")
        
        collection = get_collection(db, collection_id)
        if not collection:
            return None
        
        # Удаляем связи с маркерами
        delete_mc_query = text("""
            DELETE FROM topotik.markers_collections
            WHERE collection_id = :collection_id
        """)
        
        db.execute(delete_mc_query, {"collection_id": str(collection_id)})
        
        # Удаляем права доступа
        delete_access_query = text("""
            DELETE FROM topotik.collection_access
            WHERE collection_id = :collection_id
        """)
        
        db.execute(delete_access_query, {"collection_id": str(collection_id)})
        
        # Удаляем саму коллекцию
        db.delete(collection)
        db.commit()
        
        return collection
    except Exception as e:
        db.rollback()
        print(f"Ошибка при удалении коллекции {collection_id}: {str(e)}")
        raise

# ————————————————————————————————————————————————
# Markers
def get_marker(db: Session, marker_id: UUID):
    """Получить маркер по ID"""
    # Получаем маркер из базы данных
    marker = db.query(models.Marker).filter(models.Marker.marker_id == marker_id).first()
    
    if marker:
        # Получаем map_id из связанных коллекций
        try:
            query = text("""
                SELECT c.map_id
                FROM topotik.collections c
                JOIN topotik.markers_collections mc ON c.collection_id = mc.collection_id
                WHERE mc.marker_id = :marker_id
                LIMIT 1
            """)
            
            result = db.execute(query, {"marker_id": str(marker_id)}).fetchone()
            
            # Создаем словарь с данными маркера
            marker_dict = {
                "marker_id": marker.marker_id,
                "latitude": float(marker.latitude),
                "longitude": float(marker.longitude),
                "title": marker.title,
                "description": marker.description
            }
            
            # Добавляем map_id из коллекции, если найден
            if result and result.map_id:
                marker_dict["map_id"] = result.map_id
            
            # Создаем объект Marker из словаря с явно заданным map_id
            return schemas.Marker.parse_obj(marker_dict)
        except Exception as e:
            print(f"Ошибка при получении map_id для маркера {marker_id}: {str(e)}")
            # Если произошла ошибка, возвращаем маркер без map_id
            return marker
    
    return marker

def get_markers_by_map(db: Session, map_id: UUID, skip: int = 0, limit: int = 100):
    """Получить маркеры для карты через коллекции"""
    try:
        # Используем прямой SQL запрос для получения маркеров, связанных с картой через коллекции
        query = text("""
            SELECT DISTINCT m.marker_id, m.latitude, m.longitude, m.title, m.description, c.map_id
            FROM topotik.markers m
            JOIN topotik.markers_collections mc ON m.marker_id = mc.marker_id
            JOIN topotik.collections c ON mc.collection_id = c.collection_id
            WHERE c.map_id = :map_id
            LIMIT :limit OFFSET :offset
        """)
        
        result = db.execute(query, {
            "map_id": str(map_id),
            "limit": limit,
            "offset": skip
        })
        
        markers = []
        for row in result:
            # Создаем словарь с данными маркера, включая map_id
            marker_dict = {
                "marker_id": row.marker_id,
                "latitude": float(row.latitude),
                "longitude": float(row.longitude),
                "title": row.title,
                "description": row.description,
                "map_id": row.map_id  # Добавляем map_id из запроса
            }
            
            # Создаем объект Marker из словаря
            marker = schemas.Marker.parse_obj(marker_dict)
            markers.append(marker)
            
        return markers
    except Exception as e:
        print(f"Ошибка при получении маркеров для карты {map_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def create_marker(db: Session, marker_in: schemas.MarkerCreate):
    """Создать новый маркер"""
    logger = logging.getLogger(__name__)
    
    logger.info(f"Вызов create_marker с координатами [{marker_in.latitude}, {marker_in.longitude}]")
    
    try:
        # Вызываем SQL-функцию вместо прямого создания через ORM
        logger.debug(f"SQL-запрос: topotik.create_marker")
        logger.debug(f"Параметры запроса: latitude={marker_in.latitude}, longitude={marker_in.longitude}, map_id={marker_in.map_id}")
        
        # Преобразуем map_id в строку, если он не None
        map_id_param = str(marker_in.map_id) if marker_in.map_id else None
        
        # Используем явную транзакцию
        try:
            # Выполняем SQL-функцию для создания маркера
            result = db.execute(
                text("""
                    SELECT topotik.create_marker(
                        :latitude, 
                        :longitude, 
                        :title, 
                        :description, 
                        :map_id
                    )
                """),
                {
                    "latitude": marker_in.latitude,
                    "longitude": marker_in.longitude,
                    "title": marker_in.title,
                    "description": marker_in.description,
                    "map_id": map_id_param
                }
            ).scalar()
            
            # Явно коммитим транзакцию после успешного создания маркера
            db.commit()
            
            if not result:
                logger.error("SQL-функция create_marker вернула пустой результат")
                return None
                
            logger.debug(f"Результат SQL-функции: {result}")
            
            # Получаем созданный маркер, обработав результат безопасно
            try:
                # Если result уже UUID, используем его напрямую, иначе преобразуем строку в UUID
                marker_id = result if isinstance(result, UUID) else UUID(str(result))
                marker = get_marker(db, marker_id)
                
                if not marker:
                    logger.error(f"Не удалось загрузить созданный маркер с ID: {marker_id}")
                    return None
                    
                logger.info(f"Маркер успешно создан с ID: {marker.marker_id}")
                return marker
            except Exception as e:
                logger.error(f"Ошибка при получении созданного маркера: {str(e)}")
                db.rollback()
                raise
                
        except Exception as sql_error:
            logger.error(f"Ошибка в SQL-запросе: {str(sql_error)}")
            db.rollback()
            raise
            
    except Exception as e:
        logger.error(f"Общая ошибка при создании маркера: {str(e)}")
        db.rollback()
        raise ValueError(f"Ошибка при создании маркера: {str(e)}")

def update_marker(db: Session, marker_id: UUID, data: dict):
    """Обновить данные маркера"""
    try:
        # Проверяем существование маркера
        m = get_marker(db, marker_id)
        if not m:
            return None
        
        # Обновляем только допустимые поля
        allowed_fields = ['latitude', 'longitude', 'title', 'description']
        update_data = {}
        
        for key, val in data.items():
            if key in allowed_fields:
                update_data[key] = val
        
        if not update_data:
            return m  # Нет полей для обновления
        
        # Формируем SQL-запрос для обновления
        set_clause = ", ".join([f"{key} = :{key}" for key in update_data.keys()])
        update_query = text(f"""
            UPDATE topotik.markers
            SET {set_clause}
            WHERE marker_id = :marker_id
        """)
        
        # Добавляем marker_id в параметры
        update_data["marker_id"] = str(marker_id)
        
        # Выполняем запрос
        db.execute(update_query, update_data)
        db.commit()
        
        # Получаем обновленный маркер
        return get_marker(db, marker_id)
    except Exception as e:
        db.rollback()
        print(f"Ошибка при обновлении маркера {marker_id}: {str(e)}")
        raise

def delete_marker(db: Session, marker_id: UUID):
    """Удалить маркер и все связанные с ним данные"""
    try:
        # Получаем маркер напрямую из ORM, а не через get_marker, 
        # так как get_marker возвращает Pydantic-модель, а не ORM-объект
        m = db.query(models.Marker).filter(models.Marker.marker_id == marker_id).first()
        if not m:
            return None
        
        # Удаляем связи с коллекциями
        delete_mc_query = text("""
            DELETE FROM topotik.markers_collections
            WHERE marker_id = :marker_id
        """)
        
        db.execute(delete_mc_query, {"marker_id": str(marker_id)})
        
        # Удаляем связанные с маркером статьи
        delete_articles_query = text("""
            DELETE FROM topotik.articles
            WHERE marker_id = :marker_id
        """)
        
        db.execute(delete_articles_query, {"marker_id": str(marker_id)})
        
        # Удаляем сам маркер
        db.delete(m)
        db.commit()
        
        return True
    except Exception as e:
        db.rollback()
        print(f"Ошибка при удалении маркера {marker_id}: {str(e)}")
        raise

# ————————————————————————————————————————————————
# Articles
def get_article(db: Session, article_id: UUID):
    return db.query(models.Article).filter(models.Article.article_id == article_id).first()

def get_articles_by_marker(db: Session, marker_id: UUID, skip: int = 0, limit: int = 100):
    """Получить статьи маркера"""
    logger = logging.getLogger(__name__)
    logger.info(f"Запрос статей для маркера {marker_id}")
    
    try:
        # Используем SQL-функцию get_article_by_marker
        result = db.execute(
            text("SELECT * FROM topotik.get_article_by_marker(:marker_id)"),
            {"marker_id": str(marker_id)}
        ).fetchall()
        
        logger.debug(f"Получено {len(result) if result else 0} статей для маркера {marker_id}")
        
        if not result:
            logger.info(f"Статьи для маркера {marker_id} не найдены")
            return []
            
        # Преобразуем результат в модели схемы
        articles = []
        for row in result:
            try:
                article = {
                    "article_id": row.article_id,
                    "marker_id": marker_id,
                    "markdown_content": row.markdown_content,
                    "created_at": row.created_at
                }
                articles.append(article)
                logger.debug(f"Преобразована статья: {article['article_id']}")
            except Exception as row_error:
                logger.error(f"Ошибка при обработке строки результата: {str(row_error)}")
        
        logger.info(f"Успешно получено {len(articles)} статей для маркера {marker_id}")    
        return articles
    except Exception as e:
        logger.error(f"Ошибка при получении статей для маркера {marker_id}: {str(e)}")
        logger.error(traceback.format_exc())
        return []

def create_article(db: Session, article_in: schemas.ArticleCreate):
    """Создать статью для маркера"""
    logger = logging.getLogger(__name__)
    logger.info(f"Создание статьи для маркера {article_in.marker_id}")
    
    try:
        # Начинаем явную транзакцию
        conn = db.connection()
        trans = conn.begin()
        
        # Используем SQL-функцию create_article_for_marker
        result = db.execute(
            text("SELECT topotik.create_article_for_marker(:marker_id, :markdown_content)"),
            {
                "marker_id": str(article_in.marker_id),
                "markdown_content": article_in.markdown_content
            }
        ).scalar()
        
        if not result:
            logger.error(f"Не удалось создать статью для маркера {article_in.marker_id}")
            trans.rollback()
            return None
            
        # Коммитим транзакцию
        trans.commit()
        db.commit()
        
        logger.info(f"Создана статья с ID: {result}")
        
        # Безопасно преобразуем результат в UUID
        article_id = result if isinstance(result, UUID) else UUID(str(result))
        
        # Получаем созданную статью
        articles = get_articles_by_marker(db, article_in.marker_id)
        
        if not articles:
            logger.warning(f"Не удалось получить созданную статью для маркера {article_in.marker_id}")
            # Создаем объект статьи из переданных данных
            return models.Article(
                article_id=article_id,
                marker_id=article_in.marker_id,
                markdown_content=article_in.markdown_content,
                created_at=datetime.now(timezone.utc)
            )
            
        # Возвращаем первую статью (должна быть только одна)
        return models.Article(
            article_id=article_id,
            marker_id=article_in.marker_id,
            markdown_content=article_in.markdown_content,
            created_at=datetime.now(timezone.utc)
        )
    except Exception as e:
        logger.error(f"Ошибка при создании статьи для маркера {article_in.marker_id}: {str(e)}")
        logger.error(traceback.format_exc())
        db.rollback()
        raise ValueError(f"Ошибка при создании статьи: {str(e)}")

def delete_article(db: Session, article_id: UUID):
    article = get_article(db, article_id)
    if not article:
        return False

    db.delete(article)
    db.commit()
    return True

# ————————————————————————————————————————————————
# Sharing
def get_sharing_by_id(db: Session, sharing_id: UUID):
    return db.query(models.Sharing).filter(models.Sharing.sharing_id == sharing_id).first()

def get_folder_by_id(db: Session, folder_id: UUID):
    """
    Получить папку по её идентификатору
    """
    try:
        # Преобразуем UUID в строку
        folder_id_str = str(folder_id)
        print(f"Получение папки по ID: {folder_id_str}")
        
        query = text("""
            SELECT folder_id, title, user_id, parent_folder_id 
            FROM topotik.folders 
            WHERE folder_id = :folder_id
        """)
        
        result = db.execute(query, {"folder_id": folder_id_str}).fetchone()
        
        if result:
            # Проверяем и безопасно преобразуем значения в UUID
            folder_dict = {}
            
            # Обработка folder_id 
            if isinstance(result[0], UUID):
                folder_dict["folder_id"] = result[0]
            else:
                folder_dict["folder_id"] = UUID(str(result[0]))
                
            # Добавляем title
            folder_dict["title"] = result[1]
            
            # Обработка user_id
            if isinstance(result[2], UUID):
                folder_dict["user_id"] = result[2]
            else:
                folder_dict["user_id"] = UUID(str(result[2]))
                
            # Обработка parent_folder_id
            if result[3]:
                if isinstance(result[3], UUID):
                    folder_dict["parent_folder_id"] = result[3]
                else:
                    folder_dict["parent_folder_id"] = UUID(str(result[3]))
            else:
                folder_dict["parent_folder_id"] = None
            
            # Создаем объект Folder
            folder = schemas.Folder(**folder_dict)
            print(f"Папка найдена: {folder.title}")
            return folder
        
        print(f"Папка не найдена: {folder_id_str}")
        return None
    except Exception as e:
        print(f"Ошибка при получении папки по ID: {e}")
        import traceback
        traceback.print_exc()
        return None

def check_folder_ownership(db: Session, folder_id: UUID, user_id: UUID) -> bool:
    """
    Проверяет, принадлежит ли папка указанному пользователю.
    
    folder_id: UUID папки
    user_id: UUID пользователя
    
    Возвращает True, если папка принадлежит пользователю
    """
    try:
        # Преобразуем UUID в строки и печатаем для отладки
        folder_id_str = str(folder_id)
        user_id_str = str(user_id)
        print(f"Проверка владения папкой: folder_id={folder_id_str}, user_id={user_id_str}")
        
        # Используем строки в запросе SQL
        result = db.execute(
            text("""
                SELECT 1 
                FROM topotik.folders 
                WHERE folder_id = :folder_id 
                  AND user_id = :user_id
            """),
            {"folder_id": folder_id_str, "user_id": user_id_str}
        ).fetchone()
        
        if result:
            print(f"Папка {folder_id_str} принадлежит пользователю {user_id_str}")
        else:
            print(f"Папка {folder_id_str} НЕ принадлежит пользователю {user_id_str}")
            
        return result is not None
    except Exception as e:
        print(f"Ошибка при проверке прав доступа к папке: {e}")
        import traceback
        traceback.print_exc()
        return False
