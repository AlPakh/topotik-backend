@echo off
REM Скрипт для запуска бэкенда в Windows

REM Создание и активация виртуального окружения
python -m venv .venv
call .venv\Scripts\activate.bat

REM Установка зависимостей
pip install -r requirements.txt

REM Запуск сервера
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 