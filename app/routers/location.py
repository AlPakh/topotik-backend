import httpx
from fastapi import APIRouter, HTTPException, Depends, Request
from app.routers.auth import get_current_user
from app.database import get_db
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import logging
from datetime import datetime, timedelta

router = APIRouter(tags=["location"])

# Создаем простой кэш для результатов геолокации, чтобы снизить нагрузку на API
# Структура: {"ip_address": {"data": {...}, "expires_at": datetime}}
location_cache = {}
CACHE_EXPIRY = timedelta(hours=24)  # Кэш действует 24 часа

# Данные о местоположении по умолчанию (Санкт-Петербург)
DEFAULT_LOCATION = {
    "location": {
        "is_eu_member": False,
        "calling_code": "7",
        "currency_code": "RUB",
        "continent": "EU",
        "country": "Russia",
        "country_code": "RU",
        "state": "Saint Petersburg",
        "city": "Saint Petersburg",
        "latitude": 59.9606739,
        "longitude": 30.1586551,
        "zip": "190000",
        "timezone": "Europe/Moscow",
        "local_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+03:00"),
        "local_time_unix": int(datetime.now().timestamp()),
        "is_dst": False
    }
}

@router.get("/geoip", summary="Получить местоположение по IP", description="Возвращает данные о местоположении пользователя")
async def get_location_by_ip(request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Получает местоположение пользователя по IP через api.ipapi.is
    """
    try:
        # Получаем IP-адрес пользователя из запроса
        client_ip = request.client.host
        
        # Определяем реальный IP, учитывая возможные прокси
        forwarded_for = request.headers.get("X-Forwarded-For")
        real_ip = request.headers.get("X-Real-IP")
        
        # Выводим отладочную информацию
        logging.info(f"Client IP from request: {client_ip}")
        logging.info(f"X-Forwarded-For header: {forwarded_for}")
        logging.info(f"X-Real-IP header: {real_ip}")
        
        # Используем X-Forwarded-For или X-Real-IP, если они доступны
        if forwarded_for:
            # X-Forwarded-For может содержать несколько IP, берем первый (самый левый)
            client_ip = forwarded_for.split(',')[0].strip()
            logging.info(f"Using IP from X-Forwarded-For: {client_ip}")
        elif real_ip:
            client_ip = real_ip
            logging.info(f"Using IP from X-Real-IP: {client_ip}")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Проверяем есть ли валидный кэш для этого запроса
            cache_key = client_ip  # Используем реальный IP клиента как ключ кэша
            
            if cache_key in location_cache and location_cache[cache_key]["expires_at"] > datetime.now():
                # Используем кэшированные данные
                logging.info(f"Using cached data for IP: {client_ip}")
                return location_cache[cache_key]["data"]
            
            # Формируем URL для запроса к api.ipapi.is
            api_url = f"https://api.ipapi.is/?q={client_ip}"
            logging.info(f"Making request to: {api_url}")
            
            # Делаем запрос к api.ipapi.is с указанием IP пользователя
            response = await client.get(api_url)
            
            # Логируем статус ответа
            logging.info(f"API response status: {response.status_code}")
            
            if response.status_code != 200:
                # Логируем проблему
                logging.error(f"Ошибка получения данных геолокации: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, 
                                    detail=f"Ошибка получения данных геолокации от api.ipapi.is: {response.text}")
            
            data = response.json()
            logging.info(f"Received response data: {str(data)[:200]}...")  # Логируем первые 200 символов
            
            # Кэшируем результат
            location_cache[cache_key] = {
                "data": data,
                "expires_at": datetime.now() + CACHE_EXPIRY
            }
            
            return data
            
    except httpx.RequestError as e:
        # Обрабатываем ошибки соединения
        logging.error(f"Ошибка соединения при запросе геолокации: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Сервис геолокации недоступен: {str(e)}")
        
    except Exception as e:
        # Общая обработка других ошибок
        logging.error(f"Непредвиденная ошибка при запросе геолокации: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при обработке запроса геолокации: {str(e)}") 