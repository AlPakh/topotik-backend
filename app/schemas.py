from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from enum import Enum

# ————————————————————————————————————————————————
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[UUID] = None
    exp: Optional[int] = None

# ————————————————————————————————————————————————
class UserBase(BaseModel):
    username: str
    email: Optional[EmailStr] = None

class UserCreate(UserBase):
    password: str

class User(UserBase):
    user_id: UUID
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None

class UserAvailabilityCheck(BaseModel):
    email: str
    username: str

class UserAvailabilityResponse(BaseModel):
    email_exists: bool
    username_exists: bool

# ————————————————————————————————————————————————
class MapType(str, Enum):
    OSM = "osm"
    CUSTOM_IMAGE = "custom_image"

class PermissionType(str, Enum):
    VIEW = "view"
    EDIT = "edit"

class MapBase(BaseModel):
    title: str
    map_type: MapType
    is_public: bool = False

class MapCreate(MapBase):
    folder_id: Optional[UUID] = None
    current_folder_id: Optional[UUID] = None  # ID текущей открытой папки на фронтенде

class MapUpdate(BaseModel):
    title: Optional[str] = None
    map_type: Optional[MapType] = None
    is_public: Optional[bool] = None

class MapMove(BaseModel):
    folder_id: Optional[UUID] = None  # None означает перемещение в корневой каталог

class Map(MapBase):
    map_id: UUID
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# ————————————————————————————————————————————————
class MapAccessBase(BaseModel):
    user_id: UUID
    map_id: UUID
    permission: PermissionType

class MapAccessCreate(MapAccessBase):
    pass

class MapAccess(MapAccessBase):
    map_access_id: UUID

    class Config:
        from_attributes = True

# ————————————————————————————————————————————————
class FolderBase(BaseModel):
    title: str

class FolderCreate(FolderBase):
    parent_folder_id: Optional[UUID] = None

class FolderUpdate(BaseModel):
    title: Optional[str] = None

class FolderMove(BaseModel):
    new_parent_id: Optional[UUID] = None  # None означает перемещение в корневой каталог

class Folder(FolderBase):
    folder_id: UUID
    user_id: UUID
    parent_folder_id: Optional[UUID] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class FolderContent(BaseModel):
    subfolders: List[Folder]
    maps: List[Map]

    class Config:
        from_attributes = True

# ————————————————————————————————————————————————
# Модель для перемещения элементов (папок/карт)
class MoveItem(BaseModel):
    item_id: UUID
    item_type: str  # 'folder' или 'map'
    destination_folder_id: Optional[UUID] = None  # None означает перемещение в корень

# ————————————————————————————————————————————————
class CollectionBase(BaseModel):
    title: str
    map_id: UUID
    is_public: bool = False

class CollectionCreate(CollectionBase):
    pass

class Collection(CollectionBase):
    collection_id: UUID

    class Config:
        from_attributes = True

# ————————————————————————————————————————————————
class CollectionAccessBase(BaseModel):
    user_id: UUID
    collection_id: UUID
    permission: PermissionType

class CollectionAccessCreate(CollectionAccessBase):
    pass

class CollectionAccess(CollectionAccessBase):
    collection_access_id: UUID

    class Config:
        from_attributes = True

# ————————————————————————————————————————————————
class MarkerBase(BaseModel):
    latitude: float
    longitude: float
    title: Optional[str] = None
    description: Optional[str] = None

class MarkerCreate(MarkerBase):
    map_id: UUID  # Привязка к карте через коллекцию

class Marker(MarkerBase):
    marker_id: UUID

    class Config:
        from_attributes = True

# ————————————————————————————————————————————————
class ArticleBase(BaseModel):
    marker_id: UUID

class ArticleCreate(ArticleBase):
    pass

class Article(ArticleBase):
    article_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

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
        from_attributes = True

# ————————————————————————————————————————————————
class GenericResponse(BaseModel):
    success: bool
    message: str
