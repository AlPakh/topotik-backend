from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.orm import Session
from app import schemas, crud, database, config
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from typing import Optional
from pydantic import BaseModel
from datetime import datetime, timedelta

router = APIRouter(tags=["auth"])
# Используем функцию-фабрику вместо прямого доступа к sessionmaker
get_db = database.get_db

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    username: str
    email: str
    user_id: str

@router.post("/register", response_model=schemas.User, summary="Регистрация нового пользователя", description="Создает нового пользователя с указанными данными, автоматически входит в систему и возвращает данные пользователя.")
def register(user: schemas.UserCreate, response: Response, db: Session = Depends(get_db)):
    if crud.get_user_by_email(db, user.email):
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    
    new_user = crud.create_user(db, user)
    
    # Создаем токен
    access_token = crud.create_access_token({"user_id": str(new_user.user_id)})
    
    # Устанавливаем cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=15 * 24 * 60 * 60,  # 15 дней
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
    
    return new_user

@router.post("/login", response_model=TokenResponse, summary="Аутентификация пользователя", description="Проверяет учетные данные пользователя и возвращает JWT-токен для доступа к защищенным ресурсам.")
def login(
    response: Response,
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    user = crud.authenticate_user(db, login_data.username, login_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Неверные учетные данные")
    
    access_token = crud.create_access_token({"user_id": str(user.user_id)})
    
    # Устанавливаем cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=15 * 24 * 60 * 60,  # 15 дней
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
def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("username")
    return {"message": "Успешный выход из системы"}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# Функция для декодирования токена
def decode_token(token: str):
    try:
        payload = jwt.decode(token, config.settings.SECRET_KEY, algorithms=[config.settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Зависимость, которая извлекает user_id из токена
def get_user_id_from_token(token: str = Depends(oauth2_scheme)):
    payload = decode_token(token)
    return payload.get("user_id")

# Зависимость для получения текущего пользователя
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    user_id = get_user_id_from_token(token)
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
