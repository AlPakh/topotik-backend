import uuid
from sqlalchemy import (
    Column, String, Text, Enum, ForeignKey, DateTime, Integer, DECIMAL, Table
)
from sqlalchemy.dialects.postgresql import UUID, BYTEA
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

MapTypeEnum = Enum('osm', 'custom_image', name='map_type_enum')
AccessLevelEnum = Enum('private', 'link', 'public', name='access_level_enum')
BlockTypeEnum = Enum('text', 'image', 'video', 'link', name='block_type_enum')
ResourceTypeEnum = Enum('map', 'collection', name='resource_type_enum')
PermissionLevelEnum = Enum('view', 'edit', name='permission_level_enum')

class User(Base):
    __tablename__ = "users"
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    maps         = relationship("Map", back_populates="owner")
    collections  = relationship("Collection", back_populates="owner")
    images       = relationship("Image", back_populates="owner")

# ————————————————————————————————————————————————
markers_collections = Table(
    "markers_collections",
    Base.metadata,
    Column("marker_id", UUID(as_uuid=True), ForeignKey("markers.marker_id"), primary_key=True),
    Column("collection_id", UUID(as_uuid=True), ForeignKey("collections.collection_id"), primary_key=True),
)

class Map(Base):
    __tablename__ = "maps"
    map_id       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    title        = Column(String(100), nullable=False)
    map_type     = Column(MapTypeEnum, nullable=False)
    image_url    = Column(Text)
    access_level = Column(AccessLevelEnum, nullable=False, default="private")
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    owner        = relationship("User", back_populates="maps")
    markers      = relationship("Marker", back_populates="map", cascade="all, delete-orphan")
    collections  = relationship("Collection", back_populates="map", cascade="all, delete-orphan")

class Collection(Base):
    __tablename__ = "collections"
    collection_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    map_id        = Column(UUID(as_uuid=True), ForeignKey("maps.map_id"), nullable=False)
    user_id       = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    title         = Column(String(100), nullable=False)
    access_level  = Column(AccessLevelEnum, nullable=False, default="private")

    map    = relationship("Map", back_populates="collections")
    owner  = relationship("User", back_populates="collections")
    markers= relationship("Marker", secondary=markers_collections, back_populates="collections")

class Marker(Base):
    __tablename__ = "markers"
    marker_id  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    map_id     = Column(UUID(as_uuid=True), ForeignKey("maps.map_id"), nullable=False)
    latitude   = Column(DECIMAL(9,6), nullable=False)
    longitude  = Column(DECIMAL(9,6), nullable=False)
    title      = Column(String(100))
    description= Column(Text)

    map         = relationship("Map", back_populates="markers")
    collections = relationship("Collection", secondary=markers_collections, back_populates="markers")

class Article(Base):
    __tablename__ = "articles"
    article_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    marker_id  = Column(UUID(as_uuid=True), ForeignKey("markers.marker_id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    marker = relationship("Marker", back_populates="articles")
    blocks = relationship("Block", back_populates="article", cascade="all, delete-orphan")

class Block(Base):
    __tablename__ = "blocks"
    block_id   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    article_id = Column(UUID(as_uuid=True), ForeignKey("articles.article_id"), nullable=False)
    type       = Column(BlockTypeEnum, nullable=False)
    content    = Column(Text)
    order      = Column(Integer)

    article = relationship("Article", back_populates="blocks")

class Sharing(Base):
    __tablename__ = "sharing"
    sharing_id   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    resource_id  = Column(UUID(as_uuid=True), nullable=False)
    resource_type= Column(ResourceTypeEnum, nullable=False)
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    access_token = Column(String(255))
    access_level = Column(PermissionLevelEnum, nullable=False, default="view")

    user = relationship("User")

class Image(Base):
    __tablename__ = "images"
    image_id   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    mime_type  = Column(String(100), nullable=False)
    file_size  = Column(Integer)
    data       = Column(BYTEA, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="images")
