@echo off
echo Запуск интеграционных тестов...
python -m pytest -xvs -m integration test/integration 

pause
pause