import os
import boto3
from botocore.client import Config
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Загружаем переменные окружения в начале файла
load_dotenv()

# Установка переменных окружения для отключения контрольных сумм
os.environ['AWS_S3_CHECKSUM_ALGORITHM_ENABLED'] = 'false'

class S3Settings(BaseSettings):
    s3_access_key_id: str = os.getenv('S3_ACCESS_KEY_ID', '')
    s3_secret_access_key: str = os.getenv('S3_SECRET_ACCESS_KEY', '')
    s3_endpoint: str = os.getenv('S3_ENDPOINT', '')
    s3_region: str = "eu-north-1"
    s3_bucket_name: str = os.getenv('S3_BUCKET_NAME', '')

# Создаем экземпляр настроек
settings = S3Settings()

# Загрузка переменных окружения (для обратной совместимости)
S3_ACCESS_KEY_ID = os.getenv('S3_ACCESS_KEY_ID')
S3_SECRET_ACCESS_KEY = os.getenv('S3_SECRET_ACCESS_KEY')
S3_ENDPOINT = os.getenv('S3_ENDPOINT')
S3_REGION = os.getenv('S3_REGION', 'us-west-002')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')

# Логирование доступных настроек S3
import logging
logging.info(f"S3 настройки из переменных окружения:")
logging.info(f"S3_ACCESS_KEY_ID: {'Задано' if S3_ACCESS_KEY_ID else 'Не задано'}")
logging.info(f"S3_SECRET_ACCESS_KEY: {'Задано' if S3_SECRET_ACCESS_KEY else 'Не задано'}")
logging.info(f"S3_ENDPOINT: {S3_ENDPOINT or 'Не задано'}")
logging.info(f"S3_REGION: {S3_REGION or 'Не задано'}")
logging.info(f"S3_BUCKET_NAME: {S3_BUCKET_NAME or 'Не задано'}")

# Создание клиента S3
def get_s3_client():
    # Упрощенная конфигурация S3
    s3_config = Config(
        signature_version='s3v4',
        s3={
            'addressing_style': 'path',
            'payload_signing_enabled': False
        }
    )
    
    session = boto3.session.Session(
        aws_access_key_id=S3_ACCESS_KEY_ID,
        aws_secret_access_key=S3_SECRET_ACCESS_KEY,
        region_name=settings.s3_region  # Используем регион из настроек
    )
    
    s3_client = session.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        config=s3_config
    )
    
    return s3_client

# Проверка настроек S3 при импорте
if not all([S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_ENDPOINT, S3_BUCKET_NAME]):
    import logging
    logging.warning(
        "Не все переменные окружения для S3 настроены. "
        "Функциональность загрузки изображений будет недоступна."
    ) 