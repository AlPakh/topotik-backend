# app/routers/folders.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Dict, Any

from app import schemas, crud
from app.database import get_db
from app.routers.auth import get_user_id_from_token

router = APIRouter(tags=["folders"])

@router.get("/user", response_model=List[schemas.Folder], summary="Получить все папки пользователя", description="Возвращает список всех папок, принадлежащих текущему пользователю")
def get_user_folders(
    db: Session = Depends(get_db), 
    user_id: UUID = Depends(get_user_id_from_token)
):
    """Получить список папок пользователя"""
    return crud.get_user_folders(db, user_id)

@router.get("/structure", response_model=List[Dict], summary="Получить иерархическую структуру папок", description="Возвращает иерархическую структуру папок и карт пользователя в формате, удобном для отображения в UI")
def get_folder_structure(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_user_id_from_token)
):
    """Получить структуру папок и карт пользователя"""
    return crud.get_user_folder_structure(db, user_id)

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