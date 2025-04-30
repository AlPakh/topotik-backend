# app/routers/maps.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from app import schemas, crud
from app.database import SessionLocal
from app.routers.auth import get_user_id_from_token  

router = APIRouter(prefix="/maps", tags=["maps"])
get_db = SessionLocal

@router.get("/", response_model=List[schemas.Map])
def list_maps(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_maps(db, skip=skip, limit=limit)

@router.get("/{map_id}", response_model=schemas.Map)
def get_map(map_id: UUID, db: Session = Depends(get_db)):
    m = crud.get_map(db, map_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Map not found")
    return m

@router.post("/", response_model=schemas.Map, status_code=status.HTTP_201_CREATED)
def create_map(map_in: schemas.MapCreate, db: Session = Depends(get_db), user_id: UUID = Depends(get_user_id_from_token)):
    return crud.create_map(db, map_in, user_id)

@router.put("/{map_id}", response_model=schemas.Map)
def update_map(map_id: UUID, map_in: schemas.MapCreate, db: Session = Depends(get_db)):
    return crud.update_map(db, map_id, map_in.dict())

@router.delete("/{map_id}", response_model=schemas.Map)
def delete_map(map_id: UUID, db: Session = Depends(get_db)):
    return crud.delete_map(db, map_id)
