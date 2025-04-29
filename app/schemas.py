from typing import List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr

# ————————————————————————————————————————————————
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[UUID] = None

# ————————————————————————————————————————————————
class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class User(UserBase):
    user_id: UUID
    created_at: datetime

    class Config:
        orm_mode = True

# ————————————————————————————————————————————————
class MapBase(BaseModel):
    title: str
    map_type: str
    image_url: Optional[str]
    access_level: Optional[str] = "private"

class MapCreate(MapBase):
    pass

class Map(MapBase):
    map_id: UUID
    user_id: UUID
    created_at: datetime

    class Config:
        orm_mode = True

# ————————————————————————————————————————————————
class CollectionBase(BaseModel):
    title: str
    map_id: UUID
    access_level: Optional[str] = "private"

class CollectionCreate(CollectionBase):
    pass

class Collection(CollectionBase):
    collection_id: UUID
    user_id: UUID
    created_at: datetime

    class Config:
        orm_mode = True

# ————————————————————————————————————————————————
class MarkerBase(BaseModel):
    map_id: UUID
    latitude: float
    longitude: float
    title: Optional[str]
    description: Optional[str]

class MarkerCreate(MarkerBase):
    pass

class Marker(MarkerBase):
    marker_id: UUID

    class Config:
        orm_mode = True

# ————————————————————————————————————————————————
class ArticleBase(BaseModel):
    marker_id: UUID

class ArticleCreate(ArticleBase):
    pass

class Article(ArticleBase):
    article_id: UUID
    created_at: datetime

    class Config:
        orm_mode = True

# ————————————————————————————————————————————————
class BlockBase(BaseModel):
    article_id: UUID
    type: str
    content: Optional[str]
    order: Optional[int]

class BlockCreate(BlockBase):
    pass

class Block(BlockBase):
    block_id: UUID

    class Config:
        orm_mode = True
