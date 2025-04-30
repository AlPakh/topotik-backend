# app/routers/markers.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from app import schemas, crud
from app.database import SessionLocal

router = APIRouter(prefix="/markers", tags=["markers"])
get_db = SessionLocal

@router.get("/", response_model=List[schemas.Marker])
def list_markers(map_id: UUID, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_markers_by_map(db, map_id, skip=skip, limit=limit)

@router.get("/{marker_id}", response_model=schemas.Marker)
def get_marker(marker_id: UUID, db: Session = Depends(get_db)):
    m = crud.get_marker(db, marker_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marker not found")
    return m

@router.post("/", response_model=schemas.Marker, status_code=status.HTTP_201_CREATED)
def create_marker(marker_in: schemas.MarkerCreate, db: Session = Depends(get_db)):
    return crud.create_marker(db, marker_in)

@router.put("/{marker_id}", response_model=schemas.Marker)
def update_marker(marker_id: UUID, marker_in: schemas.MarkerCreate, db: Session = Depends(get_db)):
    return crud.update_marker(db, marker_id, marker_in.dict())

@router.delete("/{marker_id}", response_model=schemas.Marker)
def delete_marker(marker_id: UUID, db: Session = Depends(get_db)):
    return crud.delete_marker(db, marker_id)
