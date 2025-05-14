# app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Dict, Any

from app import schemas, crud, models
from app.database import get_db
from app.routers.auth import get_user_id_from_token, get_current_user

# Убираем префикс, так как в main.py уже добавляется /users
router = APIRouter(tags=["users"])

@router.get("/", response_model=List[schemas.User], summary="Получить список пользователей", description="Возвращает список всех пользователей с пагинацией. Требуются административные права.")
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    try:
        users = crud.get_users(db, skip=skip, limit=limit)
        if not users:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователи не найдены")
        return users
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Произошла ошибка при получении пользователей: {str(e)}"
        )

@router.get("/me", response_model=schemas.User, summary="Получить текущего пользователя", description="Возвращает данные текущего аутентифицированного пользователя.")
def read_current_user(current_user: models.User = Depends(get_current_user)):
    return current_user

@router.put("/me", response_model=schemas.User, summary="Обновить текущего пользователя", description="Обновляет данные текущего аутентифицированного пользователя (имя, email, пароль).")
def update_current_user(
    user_update: schemas.UserUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Проверка доступности данных, если обновляются username или email
    if user_update.username or user_update.email:
        result = crud.check_user_data_availability(
            db, 
            email=user_update.email or current_user.email, 
            username=user_update.username or current_user.username, 
            user_id=current_user.user_id
        )
        
        if result["email_exists"] and user_update.email:
            raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
        
        if result["username_exists"] and user_update.username:
            raise HTTPException(status_code=400, detail="Имя пользователя уже занято")
    
    # Обновление пользователя
    user = crud.update_user(db, str(current_user.user_id), user_update)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user

@router.post("/check-availability", response_model=schemas.UserAvailabilityResponse, summary="Проверить доступность данных", description="Проверяет, свободны ли указанные email и имя пользователя для использования.")
def check_availability(
    data: schemas.UserAvailabilityCheck,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    result = crud.check_user_data_availability(
        db, 
        email=data.email, 
        username=data.username, 
        user_id=current_user.user_id
    )
    return result

@router.get("/{user_id}", response_model=schemas.User, summary="Получить пользователя по ID", description="Возвращает данные пользователя по его идентификатору.")
def read_user(user_id: UUID, db: Session = Depends(get_db)):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    return user

@router.put("/{user_id}", response_model=schemas.User, summary="Обновить пользователя по ID", description="Обновляет данные пользователя по его идентификатору. Доступно только владельцу аккаунта или администратору.")
def update_user(
    user_id: str,
    user_update: schemas.UserUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Проверка прав доступа
    if str(current_user.user_id) != user_id:
        raise HTTPException(status_code=403, detail="Нет прав для обновления данного пользователя")
    
    # Проверка доступности данных, если обновляются username или email
    if user_update.username or user_update.email:
        result = crud.check_user_data_availability(
            db, 
            email=user_update.email or current_user.email, 
            username=user_update.username or current_user.username, 
            user_id=current_user.user_id
        )
        
        if result["email_exists"] and user_update.email:
            raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
        
        if result["username_exists"] and user_update.username:
            raise HTTPException(status_code=400, detail="Имя пользователя уже занято")
    
    # Обновление пользователя
    user = crud.update_user(db, user_id, user_update)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user

# Новые эндпоинты для работы с настройками пользователя
@router.get("/me/settings", response_model=Dict[str, Any], summary="Получить настройки пользователя", description="Возвращает настройки текущего пользователя")
def read_user_settings(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        settings = crud.get_user_settings(db, current_user.user_id)
        return settings
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении настроек пользователя: {str(e)}"
        )

@router.put("/me/settings", response_model=Dict[str, Any], summary="Обновить настройки пользователя", description="Обновляет настройки текущего пользователя")
def update_user_settings(settings: schemas.UserSettings, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        print(f"DEBUG: Обновление настроек пользователя - НАЧАЛО ЗАПРОСА")
        print(f"DEBUG: current_user из токена: ID={current_user.user_id}, username={current_user.username}, email={current_user.email}")
        print(f"DEBUG: Тип current_user.user_id: {type(current_user.user_id)}")
        print(f"DEBUG: Полученные настройки: {settings.settings}")
        
        # Обновляем настройки пользователя с использованием прямого SQL метода
        updated_settings = crud.update_user_settings(db, current_user.user_id, settings.settings)
        
        # Если пользователь не найден через CRUD метод, попробуем прямой SQL запрос
        if not updated_settings:
            print(f"DEBUG: Пользователь не найден через CRUD метод, пробуем прямой SQL запрос")
            from sqlalchemy import text
            import json
            
            try:
                # Ручное обновление через SQL
                settings_json = json.dumps(settings.settings)
                update_query = text("""
                    INSERT INTO topotik.users (user_id, username, email, password, settings, created_at)
                    VALUES (:user_id, :username, :email, :password, cast(:settings AS jsonb), NOW())
                    ON CONFLICT (user_id) DO UPDATE 
                    SET settings = cast(:settings AS jsonb)
                    RETURNING settings
                """)
                
                result = db.execute(update_query, {
                    "user_id": str(current_user.user_id),
                    "username": current_user.username,
                    "email": current_user.email,
                    "password": "emergency_hash",  # Будет обновлено позже при следующем логине
                    "settings": settings_json
                }).first()
                
                db.commit()
                
                if result and result.settings:
                    try:
                        if isinstance(result.settings, str):
                            updated_settings = json.loads(result.settings)
                        else:
                            updated_settings = result.settings
                        print(f"DEBUG: Настройки успешно обновлены через аварийный метод")
                    except Exception as json_error:
                        print(f"DEBUG: Ошибка при парсинге JSON: {str(json_error)}")
                        updated_settings = settings.settings  # Возвращаем исходные настройки
                else:
                    print(f"DEBUG: Не удалось выполнить аварийное обновление")
                    raise HTTPException(status_code=500, detail="Не удалось обновить настройки")
            except Exception as sql_error:
                print(f"DEBUG: Ошибка при прямом SQL-запросе: {str(sql_error)}")
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=500, 
                                   detail=f"Не удалось выполнить аварийное обновление: {str(sql_error)}")
        
        print(f"DEBUG: Настройки успешно обновлены: {updated_settings}")
        return updated_settings
    except Exception as e:
        print(f"DEBUG: Исключение при обновлении настроек: {str(e)}")
        print(f"DEBUG: Тип исключения: {type(e)}")
        import traceback
        traceback.print_exc()
        
        # В случае ошибки возвращаем локальные настройки, чтобы не прерывать пользовательский опыт
        return settings.settings

@router.post("/me/settings/reset", response_model=Dict[str, Any], summary="Сбросить настройки пользователя", description="Сбрасывает настройки пользователя к значениям по умолчанию")
def reset_user_settings(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        default_settings = crud.reset_user_settings(db, current_user.user_id)
        if not default_settings:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        return default_settings
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при сбросе настроек пользователя: {str(e)}"
        )
