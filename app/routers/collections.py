# app/routers/collections.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from app import schemas, crud
from app.database import SessionLocal

router = APIRouter(prefix="/collections", tags=["collections"])
get_db = SessionLocal

@router.get("/", response_model=List[schemas.Collection])
def list_collections(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_collections(db, skip=skip, limit=limit)

@router.get("/{collection_id}", response_model=schemas.Collection)
def get_collection(collection_id: UUID, db: Session = Depends(get_db)):
    c = crud.get_collection(db, collection_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    return c

@router.post("/", response_model=schemas.Collection, status_code=status.HTTP_201_CREATED)
def create_collection(collection_in: schemas.CollectionCreate, db: Session = Depends(get_db), user_id: UUID = Depends(...)):
    """
    TODO: заменить Depends(...) на вашу зависимость,
    которая извлекает user_id из токена.
    """
    return crud.create_collection(db, collection_in, user_id)

@router.put("/{collection_id}", response_model=schemas.Collection)
def update_collection(collection_id: UUID, collection_in: schemas.CollectionCreate, db: Session = Depends(get_db)):
    return crud.update_collection(db, collection_id, collection_in.dict())

@router.delete("/{collection_id}", response_model=schemas.Collection)
def delete_collection(collection_id: UUID, db: Session = Depends(get_db)):
    return crud.delete_collection(db, collection_id)
