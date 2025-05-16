import httpx
from fastapi import APIRouter, HTTPException, Depends
from app.routers.auth import get_current_user
from app.database import get_db
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import logging
from datetime import datetime, timedelta

router = APIRouter(tags=["location"])

# Создаем простой кэш для результатов геолокации, чтобы снизить нагрузку на ipapi.co
# Структура: {"ip_address": {"data": {...}, "expires_at": datetime}}
location_cache = {}
CACHE_EXPIRY = timedelta(hours=24)  # Кэш действует 24 часа

@router.get("/geoip", summary="Получить местоположение по IP", description="Проксирует запрос к ipapi.co и возвращает данные о местоположении пользователя")
async def get_location_by_ip(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Получает местоположение пользователя по IP через ipapi.co
    """
    try:
        # Определяем IP пользователя (в реальном случае это был бы IP из запроса)
        # В данном случае просто используем запрос к ipapi.co без указания IP
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Проверяем есть ли валидный кэш для этого запроса
            cache_key = "default_ip"  # В реальном приложении используйте IP клиента
            
            if cache_key in location_cache and location_cache[cache_key]["expires_at"] > datetime.now():
                # Используем кэшированные данные
                return location_cache[cache_key]["data"]
            
            # Делаем запрос к ipapi.co
            response = await client.get("https://ipapi.co/json/")
            
            if response.status_code != 200:
                # Логируем проблему
                logging.error(f"Ошибка получения данных геолокации: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, 
                                    detail=f"Ошибка получения данных геолокации от ipapi.co: {response.text}")
            
            data = response.json()
            
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