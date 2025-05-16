from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator, UUID4
from enum import Enum
import logging

# Настройка логирования
logger = logging.getLogger(__name__)

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
    settings: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

class UserSettings(BaseModel):
    settings: Dict[str, Any]

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
    background_image_id: Optional[UUID4] = None

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
    collection_color: Optional[str] = "#8A2BE2"

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
    map_id: Optional[UUID] = None  # Виртуальное поле, заполняемое динамически из связанной коллекции

    @model_validator(mode='after')
    def log_marker_fields(self):
        """Логирует поля маркера для отладки"""
        logger.debug(f"Создание/валидация объекта Marker со значениями: {self.model_dump()}")
        if hasattr(self, 'map_id') and self.map_id is not None:
            logger.debug(f"map_id присутствует: {self.map_id}, тип: {type(self.map_id)}")
        else:
            logger.debug("map_id отсутствует или None")
        return self

class MarkerCreate(MarkerBase):
    pass

class Marker(MarkerBase):
    marker_id: UUID

    @field_validator('map_id', mode='before')
    @classmethod
    def validate_map_id(cls, v):
        """Валидирует map_id, преобразуя его из строки в UUID при необходимости"""
        logger.debug(f"Валидация map_id: {v}, тип: {type(v)}")
        if v is None:
            return None
        if isinstance(v, str):
            try:
                result = UUID(v)
                logger.debug(f"map_id преобразован из строки в UUID: {result}")
                return result
            except ValueError as e:
                logger.error(f"Ошибка преобразования map_id из строки в UUID: {e}")
                raise
        return v

    class Config:
        from_attributes = True
        # Явно указываем, что поле map_id может заполняться из источников, отличных от атрибутов модели
        populate_by_name = True
        # Дополнительный флаг для работы с произвольными типами
        arbitrary_types_allowed = True

# ————————————————————————————————————————————————
class ArticleBase(BaseModel):
    marker_id: UUID
    markdown_content: Optional[str] = None

class ArticleCreate(ArticleBase):
    pass

class Article(ArticleBase):
    article_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

# ————————————————————————————————————————————————
class GenericResponse(BaseModel):
    success: bool
    message: str

# Схемы для работы с изображениями
class ImageBase(BaseModel):
    file_name: str
    mime_type: str
    file_size: int

class ImageCreate(ImageBase):
    pass

class ImageResponse(ImageBase):
    image_id: UUID4
    s3_key: str
    created_at: datetime
    url: Optional[str] = None

    class Config:
        from_attributes = True

class ImageListResponse(BaseModel):
    images: List[ImageResponse]

class ImageDeleteResponse(BaseModel):
    success: bool

# ————————————————————————————————————————————————
class MapResponse(MapBase):
    map_id: UUID4
    created_at: datetime
    background_image_url: Optional[str] = None
    
    class Config:
        from_attributes = True
