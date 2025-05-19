from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.settings import settings

# Синхронное подключение
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Асинхронное подключение (для новых методов)
# Преобразование URL для работы с асинхронным драйвером
async_database_url = settings.DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')
async_engine = create_async_engine(async_database_url, echo=True)
AsyncSessionLocal = sessionmaker(
    bind=async_engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# Функция-фабрика для получения синхронной сессии базы данных
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Функция-фабрика для получения асинхронной сессии базы данных
async def get_async_session():
    async with AsyncSessionLocal() as session:
        yield session

def init_db():
    import app.models  # регистрируем модели
    Base.metadata.create_all(bind=engine)
