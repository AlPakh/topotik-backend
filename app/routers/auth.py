from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.orm import Session
from app import schemas, crud, database
from app.settings import settings
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from typing import Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
from uuid import UUID

# Стандартный роутер без специальной настройки CORS
router = APIRouter(
    tags=["auth"],
    responses={
        404: {"description": "Endpoint не найден"}
    }
)

# Используем функцию-фабрику вместо прямого доступа к sessionmaker
get_db = database.get_db

class LoginRequest(BaseModel):
    username: str
    password: str

    class Config:
        # Добавляем конфигурацию для более гибкой валидации
        orm_mode = True
        schema_extra = {
            "example": {
                "username": "user@example.com или username",
                "password": "password123"
            }
        }

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    username: str
    email: str
    user_id: str

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

@router.post("/register", response_model=TokenResponse, summary="Регистрация нового пользователя", description="Создает нового пользователя с указанными данными, автоматически входит в систему и возвращает данные пользователя и токен авторизации.")
def register(user: schemas.UserCreate, response: Response, db: Session = Depends(get_db)):
    if crud.get_user_by_email(db, user.email):
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    
    new_user = crud.create_user(db, user)
    
    # Создаем настройки по умолчанию для нового пользователя
    default_settings = {
        "map": {
            "units": "km",
            "showGrid": False,
            "defaultCity": "Saint Petersburg, Northwestern Federal District, Russia",
            "defaultZoom": 13,
            "defaultCoordinates": {
                "lat": 59.9606739,
                "lng": 30.1586551
            }
        },
        "ui": {
            "theme": "light",
            "fontSize": "medium",
            "language": "ru"
        },
        "editor": {
            "defaultMarkerColor": "#FF5733",
            "autoSave": 5  # автосохранение каждые 5 минут
        },
        "privacy": {
            "defaultMapPrivacy": "private",
            "defaultCollectionPrivacy": "private"
        }
    }
    
    try:
        # Сохраняем настройки по умолчанию
        crud.update_user_settings(db, new_user.user_id, default_settings)
        print(f"Настройки по умолчанию созданы для пользователя {new_user.username}")
    except Exception as e:
        print(f"Ошибка при создании настроек по умолчанию: {str(e)}")
        # Продолжаем выполнение, так как фронтенд имеет резервный механизм
    
    # Создаем токены
    access_token = crud.create_access_token({"user_id": str(new_user.user_id)})
    refresh_token = crud.create_refresh_token({"user_id": str(new_user.user_id)})
    
    # Сохраняем refresh токен в настройках пользователя
    crud.save_refresh_token(db, new_user.user_id, refresh_token)
    
    # Устанавливаем cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=15 * 24 * 60 * 60,  # 15 дней
        samesite="lax",
        secure=False  # установите True для HTTPS
    )
    
    # Устанавливаем refresh токен в куки
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=30 * 24 * 60 * 60,  # 30 дней
        samesite="lax",
        secure=False  # установите True для HTTPS
    )
    
    # Сохраняем имя пользователя в cookies
    response.set_cookie(
        key="username",
        value=new_user.username,
        max_age=15 * 24 * 60 * 60,  # 15 дней
        samesite="lax",
        secure=False  # установите True для HTTPS
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": new_user.username,
        "email": new_user.email,
        "user_id": str(new_user.user_id)
    }

@router.post("/login", response_model=TokenResponse, summary="Аутентификация пользователя", description="Проверяет учетные данные пользователя и возвращает JWT-токен для доступа к защищенным ресурсам.")
def login(
    response: Response,
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    # Отладочная печать полученных данных
    print(f"DEBUG: Полученные данные логина: {login_data.dict()}")
    
    # Проверяем, является ли username email-адресом или логином
    username_or_email = login_data.username
    print(f"DEBUG: Проверяем авторизацию для: {username_or_email}")
    
    user = crud.authenticate_user(db, username_or_email, login_data.password)
    
    if not user:
        print(f"DEBUG: Аутентификация не удалась для: {username_or_email}")
        raise HTTPException(status_code=401, detail="Неверные учетные данные")
    
    print(f"DEBUG: Успешная аутентификация пользователя: {user.username}")
    
    # Создаем токены
    access_token = crud.create_access_token({"user_id": str(user.user_id)})
    refresh_token = crud.create_refresh_token({"user_id": str(user.user_id)})
    
    # Сохраняем refresh токен в настройках пользователя
    crud.save_refresh_token(db, user.user_id, refresh_token)
    
    # Устанавливаем cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=15 * 24 * 60 * 60,  # 15 дней
        samesite="lax",
        secure=False  # установите True для HTTPS
    )
    
    # Устанавливаем refresh токен в куки
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=30 * 24 * 60 * 60,  # 30 дней
        samesite="lax",
        secure=False  # установите True для HTTPS
    )
    
    # Сохраняем имя пользователя в cookies
    response.set_cookie(
        key="username",
        value=user.username,
        max_age=15 * 24 * 60 * 60,  # 15 дней
        samesite="lax",
        secure=False  # установите True для HTTPS
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username,
        "email": user.email,
        "user_id": str(user.user_id)
    }

@router.post("/logout", summary="Выход из системы", description="Удаляет cookies сессии и завершает сеанс пользователя.")
def logout(response: Response, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        # Декодируем токен для получения ID пользователя
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("user_id")
        
        if user_id:
            # Получаем настройки пользователя
            settings_data = crud.get_user_settings(db, user_id)
            
            # Удаляем информацию о refresh токене
            if settings_data and 'security' in settings_data:
                if 'refresh_token' in settings_data['security']:
                    del settings_data['security']['refresh_token']
                    crud.update_user_settings(db, user_id, settings_data)
    except Exception as e:
        print(f"Ошибка при удалении refresh токена: {str(e)}")
    
    # Удаляем куки
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    response.delete_cookie("username")
    
    return {"message": "Успешный выход из системы"}

@router.post("/token/refresh", response_model=TokenResponse, summary="Обновление токена доступа", description="Создает новый токен доступа на основе действительного токена обновления.")
def refresh_access_token(request: schemas.TokenRefreshRequest, response: Response, db: Session = Depends(get_db)):
    """Обновляет access token с помощью refresh token"""
    user_id = crud.validate_refresh_token(db, request.refresh_token)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный или истекший токен обновления",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Получаем данные пользователя
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Создаем новый access token
    access_token = crud.create_access_token({"user_id": str(user.user_id)})
    
    # Устанавливаем куки
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=15 * 24 * 60 * 60,  # 15 дней
        samesite="lax",
        secure=False  # установите True для HTTPS
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username,
        "email": user.email,
        "user_id": str(user.user_id)
    }

# Функция для декодирования токена
def decode_token(token: str):
    try:
        print(f"DEBUG: decode_token вызван с токеном: {token[:20]}...")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        print(f"DEBUG: decode_token: успешное декодирование, payload: {payload}")
        return payload
    except JWTError as e:
        print(f"DEBUG: decode_token: ошибка декодирования JWT: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        print(f"DEBUG: decode_token: неожиданная ошибка: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing token: {str(e)}",
        )

# Зависимость, которая извлекает user_id из токена
def get_user_id_from_token(token: str = Depends(oauth2_scheme)):
    print(f"DEBUG: get_user_id_from_token вызван с токеном: {token[:20]}...")
    payload = decode_token(token)
    user_id = payload.get("user_id")
    print(f"DEBUG: get_user_id_from_token: получен user_id: {user_id}")
    return user_id

# Зависимость для получения текущего пользователя
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    print(f"DEBUG: get_current_user: Извлечение пользователя из токена")
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Недействительные учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Получаем user_id из токена
        print(f"DEBUG: get_current_user: Получаем user_id из токена...")
        user_id = get_user_id_from_token(token)
        print(f"DEBUG: get_current_user: Извлеченный user_id: {user_id}, тип: {type(user_id)}")
        
        if user_id is None:
            print(f"DEBUG: get_current_user: user_id не найден в токене")
            raise credentials_exception
        
        # Пробуем найти пользователя через ORM
        user = crud.get_user(db, user_id)
        print(f"DEBUG: get_current_user: Результат поиска через ORM: {'найден' if user else 'не найден'}")
        
        # Если ORM не нашел, попробуем через SQL
        if not user:
            print(f"DEBUG: get_current_user: Пользователь не найден через ORM, пробуем через SQL")
            from sqlalchemy import text
            check_query = text("SELECT user_id, username, email FROM topotik.users WHERE user_id = :user_id")
            sql_result = db.execute(check_query, {"user_id": str(user_id)}).first()
            print(f"DEBUG: get_current_user: Результат SQL запроса: {sql_result}")
            
            if sql_result:
                print(f"DEBUG: get_current_user: Пользователь найден через SQL! Создаем объект вручную")
                # Если через SQL нашли, но через ORM нет, создаем объект модели вручную
                user = models.User()
                user.user_id = UUID(sql_result.user_id) if isinstance(sql_result.user_id, str) else sql_result.user_id
                user.username = sql_result.username
                user.email = sql_result.email
                print(f"DEBUG: get_current_user: Создан объект пользователя: ID={user.user_id}, username={user.username}")
            else:
                print(f"DEBUG: get_current_user: Пользователь не найден и через SQL")
                
                # Проверим, вообще есть ли пользователи в базе
                count_query = text("SELECT COUNT(*) FROM topotik.users")
                count_result = db.execute(count_query).scalar()
                print(f"DEBUG: get_current_user: Всего пользователей в БД: {count_result}")
                
                # Найдем последнего добавленного пользователя
                latest_query = text("SELECT user_id, username, email FROM topotik.users ORDER BY created_at DESC LIMIT 1")
                latest_result = db.execute(latest_query).first()
                print(f"DEBUG: get_current_user: Последний добавленный пользователь: {latest_result}")
                
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Пользователь не найден"
                )
        
        print(f"DEBUG: get_current_user: Успешно найден пользователь: ID={user.user_id}, username={user.username}, email={user.email}")
        return user
    
    except JWTError as e:
        print(f"DEBUG: get_current_user: ошибка JWT: {str(e)}")
        raise credentials_exception
    except Exception as e:
        print(f"DEBUG: get_current_user: неожиданная ошибка: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении пользователя: {str(e)}"
        )
