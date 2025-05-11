# app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

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
