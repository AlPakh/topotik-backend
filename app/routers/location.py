import httpx
from fastapi import APIRouter, HTTPException, Depends, Request
from app.routers.auth import get_current_user
from app.database import get_db
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import logging
from datetime import datetime, timedelta
import json

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
        "latitude": 59.938784,
        "longitude": 30.314997,
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
        # Логируем все заголовки запроса
        logging.info("Request headers:")
        for header_name, header_value in request.headers.items():
            logging.info(f"  {header_name}: {header_value}")
            
        # Получаем IP-адрес пользователя из запроса
        client_ip = request.client.host
        logging.info(f"Initial client IP from request.client.host: {client_ip}")
        
        # Определяем IP, учитывая возможные прокси (без фильтрации)
        forwarded_for = request.headers.get("X-Forwarded-For")
        real_ip = request.headers.get("X-Real-IP")
        cf_connecting_ip = request.headers.get("CF-Connecting-IP")  # Cloudflare
        
        logging.info(f"X-Forwarded-For header: {forwarded_for}")
        logging.info(f"X-Real-IP header: {real_ip}")
        logging.info(f"CF-Connecting-IP header: {cf_connecting_ip}")
        
        # Используем заголовки для определения IP, принимаем любой IP без фильтрации
        if forwarded_for:
            client_ip = forwarded_for.split(',')[0].strip()
            logging.info(f"Using IP from X-Forwarded-For: {client_ip}")
        elif real_ip:
            client_ip = real_ip
            logging.info(f"Using IP from X-Real-IP: {client_ip}")
        elif cf_connecting_ip:
            client_ip = cf_connecting_ip
            logging.info(f"Using IP from CF-Connecting-IP: {client_ip}")
            
        # Используем любой полученный IP, даже если он выглядит как локальный
        logging.info(f"Final client IP to use for geolocation: {client_ip}")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Проверяем есть ли валидный кэш для этого запроса
            cache_key = client_ip
            
            if cache_key in location_cache and location_cache[cache_key]["expires_at"] > datetime.now():
                logging.info(f"Using cached data for IP: {client_ip}")
                # Добавляем IP в ответ для диагностики
                cached_response = location_cache[cache_key]["data"]
                cached_response["client_ip"] = client_ip
                return cached_response
            
            # Формируем URL для запроса к api.ipapi.is
            api_url = f"https://api.ipapi.is/?q={client_ip}"
            logging.info(f"Making request to: {api_url}")
            
            # Делаем запрос к api.ipapi.is с указанием IP пользователя
            response = await client.get(api_url)
            
            # Логируем статус ответа
            logging.info(f"API response status: {response.status_code}")
            logging.info(f"API response headers: {dict(response.headers)}")
            
            if response.status_code != 200:
                # Логируем проблему
                logging.error(f"Ошибка получения данных геолокации: {response.status_code} - {response.text}")
                # Возвращаем данные по умолчанию при ошибке и добавляем IP в ответ
                default_response = DEFAULT_LOCATION.copy()
                default_response["client_ip"] = client_ip
                default_response["error"] = True
                default_response["error_details"] = f"API вернул статус {response.status_code}: {response.text}"
                return default_response
            
            try:
                data = response.json()
                # Логируем полный ответ от API
                logging.info(f"Full API response data: {json.dumps(data)}")
                
                # Проверяем, есть ли ключевые поля в ответе
                if 'location' not in data or 'city' not in data.get('location', {}):
                    logging.warning("Missing location data in API response, returning fixed response")
                    default_response = DEFAULT_LOCATION.copy()
                    default_response["client_ip"] = client_ip
                    default_response["error"] = True
                    default_response["error_details"] = "Ответ API не содержит необходимых данных о местоположении"
                    return default_response
                
                # Добавляем IP в ответ для диагностики
                data["client_ip"] = client_ip
                
                # Кэшируем результат
                location_cache[cache_key] = {
                    "data": data,
                    "expires_at": datetime.now() + CACHE_EXPIRY
                }
                
                return data
            except json.JSONDecodeError:
                logging.error(f"Invalid JSON in API response: {response.text}")
                default_response = DEFAULT_LOCATION.copy()
                default_response["client_ip"] = client_ip
                default_response["error"] = True
                default_response["error_details"] = "Некорректный JSON в ответе API"
                return default_response
            
    except httpx.RequestError as e:
        # Обрабатываем ошибки соединения
        logging.error(f"Ошибка соединения при запросе геолокации: {str(e)}")
        default_response = DEFAULT_LOCATION.copy()
        default_response["client_ip"] = client_ip if 'client_ip' in locals() else "неизвестен"
        default_response["error"] = True
        default_response["error_details"] = f"Ошибка соединения: {str(e)}"
        return default_response
        
    except Exception as e:
        # Общая обработка других ошибок
        logging.error(f"Непредвиденная ошибка при запросе геолокации: {str(e)}")
        logging.exception(e)  # Логируем полный стектрейс
        default_response = DEFAULT_LOCATION.copy()
        default_response["client_ip"] = client_ip if 'client_ip' in locals() else "неизвестен"
        default_response["error"] = True
        default_response["error_details"] = f"Непредвиденная ошибка: {str(e)}"
        return default_response