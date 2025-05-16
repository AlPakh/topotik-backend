import uuid
from sqlalchemy import (
    Column, String, Text, Enum, ForeignKey, DateTime, Integer, DECIMAL, Table, Boolean, JSON
)
from sqlalchemy.dialects.postgresql import UUID, BYTEA
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

MapTypeEnum = Enum('osm', 'custom_image', name='map_type_enum', schema='topotik')
AccessLevelEnum = Enum('private', 'link', 'public', name='access_level_enum', schema='topotik')
ResourceTypeEnum = Enum('map', 'collection', 'folder', name='resource_type_enum', schema='topotik')
PermissionLevelEnum = Enum('view', 'edit', name='permission_level_enum', schema='topotik')
PermissionEnum = Enum('view', 'edit', name='permission_enum', schema='topotik')

class User(Base):
    __tablename__ = "users"
    __table_args__ = {'schema': 'topotik'}
    
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    settings = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    images = relationship("Image", back_populates="owner")
    folders = relationship("Folder", back_populates="owner")
    map_access = relationship("MapAccess", back_populates="user")
    collection_access = relationship("CollectionAccess", back_populates="user")

# ————————————————————————————————————————————————
markers_collections = Table(
    "markers_collections",
    Base.metadata,
    Column("marker_id", UUID(as_uuid=True), ForeignKey("topotik.markers.marker_id"), primary_key=True),
    Column("collection_id", UUID(as_uuid=True), ForeignKey("topotik.collections.collection_id"), primary_key=True),
    schema='topotik'
)

# Промежуточная таблица для связи папок и карт
folder_maps = Table(
    "folder_maps",
    Base.metadata,
    Column("folder_id", UUID(as_uuid=True), ForeignKey("topotik.folders.folder_id"), primary_key=True),
    Column("map_id", UUID(as_uuid=True), ForeignKey("topotik.maps.map_id"), primary_key=True),
    schema='topotik'
)

class Folder(Base):
    __tablename__ = "folders"
    __table_args__ = {'schema': 'topotik'}
    
    folder_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    user_id = Column(UUID(as_uuid=True), ForeignKey("topotik.users.user_id"), nullable=False)
    parent_folder_id = Column(UUID(as_uuid=True), ForeignKey("topotik.folders.folder_id"), nullable=True)
    title = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    owner = relationship("User", back_populates="folders")
    parent = relationship("Folder", remote_side=[folder_id], backref="subfolders")
    maps = relationship("Map", secondary=folder_maps, back_populates="folders")

class Map(Base):
    __tablename__ = "maps"
    __table_args__ = {'schema': 'topotik'}
    
    map_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    title = Column(String(100), nullable=False)
    map_type = Column(MapTypeEnum, nullable=False)
    is_public = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    collections = relationship("Collection", back_populates="map", cascade="all, delete-orphan")
    folders = relationship("Folder", secondary=folder_maps, back_populates="maps")
    access = relationship("MapAccess", back_populates="map", cascade="all, delete-orphan")

class MapAccess(Base):
    __tablename__ = "map_access"
    __table_args__ = {'schema': 'topotik'}
    
    map_access_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    user_id = Column(UUID(as_uuid=True), ForeignKey("topotik.users.user_id"), nullable=False)
    map_id = Column(UUID(as_uuid=True), ForeignKey("topotik.maps.map_id"), nullable=False)
    permission = Column(PermissionEnum, nullable=False)
    
    user = relationship("User", back_populates="map_access")
    map = relationship("Map", back_populates="access")

class Collection(Base):
    __tablename__ = "collections"
    __table_args__ = {'schema': 'topotik'}
    
    collection_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    map_id = Column(UUID(as_uuid=True), ForeignKey("topotik.maps.map_id"), nullable=False)
    title = Column(String(100), nullable=False)
    is_public = Column(Boolean, nullable=False, default=False)
    collection_color = Column(String(20), nullable=True, default="#8A2BE2")

    map = relationship("Map", back_populates="collections")
    markers = relationship("Marker", secondary=markers_collections, back_populates="collections")
    access = relationship("CollectionAccess", back_populates="collection", cascade="all, delete-orphan")

class CollectionAccess(Base):
    __tablename__ = "collection_access"
    __table_args__ = {'schema': 'topotik'}
    
    collection_access_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    user_id = Column(UUID(as_uuid=True), ForeignKey("topotik.users.user_id"), nullable=False)
    collection_id = Column(UUID(as_uuid=True), ForeignKey("topotik.collections.collection_id"), nullable=False)
    permission = Column(PermissionEnum, nullable=False)
    
    user = relationship("User", back_populates="collection_access")
    collection = relationship("Collection", back_populates="access")

class Marker(Base):
    __tablename__ = "markers"
    __table_args__ = {'schema': 'topotik'}
    
    marker_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    latitude = Column(DECIMAL(9,6), nullable=False)
    longitude = Column(DECIMAL(9,6), nullable=False)
    title = Column(String(100))
    description = Column(Text)

    collections = relationship("Collection", secondary=markers_collections, back_populates="markers")
    articles = relationship("Article", back_populates="marker", cascade="all, delete-orphan")

class Article(Base):
    __tablename__ = "articles"
    __table_args__ = {'schema': 'topotik'}
    
    article_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    marker_id = Column(UUID(as_uuid=True), ForeignKey("topotik.markers.marker_id"), nullable=False)
    markdown_content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    marker = relationship("Marker", back_populates="articles")

class Sharing(Base):
    __tablename__ = "sharing"
    __table_args__ = {'schema': 'topotik'}
    
    sharing_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    resource_id = Column(UUID(as_uuid=True), nullable=False)
    resource_type = Column(ResourceTypeEnum, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("topotik.users.user_id"), nullable=True)
    access_token = Column(String(255))
    access_level = Column(PermissionLevelEnum, nullable=False, default="view")

    user = relationship("User")

class Image(Base):
    __tablename__ = "images"
    __table_args__ = {'schema': 'topotik'}
    
    image_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    user_id = Column(UUID(as_uuid=True), ForeignKey("topotik.users.user_id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    s3_key = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="images")
