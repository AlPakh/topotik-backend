import os
import boto3
from botocore.client import Config

# Загрузка переменных окружения
S3_ACCESS_KEY_ID = os.getenv('S3_ACCESS_KEY_ID')
S3_SECRET_ACCESS_KEY = os.getenv('S3_SECRET_ACCESS_KEY')
S3_ENDPOINT = os.getenv('S3_ENDPOINT')
S3_REGION = os.getenv('S3_REGION', 'us-west-002')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')

# Создание клиента S3
def get_s3_client():
    session = boto3.session.Session(
        aws_access_key_id=S3_ACCESS_KEY_ID,
        aws_secret_access_key=S3_SECRET_ACCESS_KEY,
        region_name=S3_REGION
    )
    
    s3_client = session.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        config=Config(signature_version='s3v4')
    )
    
    return s3_client

# Проверка настроек S3 при импорте
if not all([S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_ENDPOINT, S3_BUCKET_NAME]):
    import logging
    logging.warning(
        "Не все переменные окружения для S3 настроены. "
        "Функциональность загрузки изображений будет недоступна."
    ) 