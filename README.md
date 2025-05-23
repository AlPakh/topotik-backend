 # Topotik Backend

Backend-часть приложения Topotik для создания интерактивных карт с метками.

## Требования

- Python 3.8+
- PostgreSQL
- Backblaze B2 (или другое хранилище, совместимое с S3)

## Установка и запуск

1. Клонировать репозиторий:
```bash
git clone https://github.com/AlPakh/topotik-backend.git
cd topotik-backend
```

2. Создать виртуальное окружение и активировать его:
```bash
python -m venv venv
# В Windows:
venv\Scripts\activate
# В Linux/Mac:
source venv/bin/activate
```

3. Установить зависимости:
```bash
pip install -r requirements.txt
```

4. Настроить переменные окружения (создать файл `.env` на основе `.env.example`):
```
DATABASE_URL=postgresql://user:password@localhost/topotik_db
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

S3_ACCESS_KEY_ID=your-s3-key
S3_SECRET_ACCESS_KEY=your-s3-secret
S3_ENDPOINT=your-s3-endpoint
S3_REGION=your-s3-region
S3_BUCKET_NAME=your-bucket-name
```

5. Запустить сервер:
```bash
uvicorn app.main:app --reload
```

Документация API будет доступна по адресу `http://localhost:8000/docs`

## Запуск тестов

В проекте реализованы юнит-тесты для основных компонентов системы:

1. Тесты для схем данных (Pydantic-моделей)
2. Тесты для компонентов аутентификации
3. Тесты для маркеров, коллекций, карт и статей

### Подготовка к запуску тестов

1. Установите зависимости для тестирования:
```bash
pip install pytest pytest-asyncio pytest-cov
```

2. Создайте тестовую базу данных:
```bash
# В PostgreSQL
CREATE DATABASE topotik_test_db;
```

3. Создайте файл `.env.test` с настройками для тестовой базы данных:
```
DATABASE_URL=postgresql://user:password@localhost/topotik_test_db
SECRET_KEY=test-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### Запуск тестов

Запуск всех тестов:
```bash
python -m pytest
```

Запуск с подробной информацией:
```bash
python -m pytest -v
```

Запуск отдельного файла с тестами:
```bash
python -m pytest test/test_auth.py
```

### Проверка покрытия кода

Для проверки покрытия кода тестами:
```bash
python -m pytest --cov=app test/
```

Проверка покрытия для конкретного модуля:
```bash
python -m pytest --cov=app.schemas test/
```

## Структура проекта

- `app/` - основной код приложения
  - `config/` - конфигурация приложения
  - `routers/` - маршруты API
  - `services/` - сервисные функции
  - `models.py` - модели SQLAlchemy
  - `schemas.py` - схемы Pydantic
  - `crud.py` - функции для работы с базой данных
  - `main.py` - точка входа приложения
- `test/` - тесты
  - `conftest.py` - фикстуры и настройки для тестов
  - `test_*.py` - файлы с тестами