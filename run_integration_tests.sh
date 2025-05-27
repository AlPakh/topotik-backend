#!/bin/bash

# Запуск интеграционных тестов
echo "Запуск интеграционных тестов..."
python -m pytest -xvs -m integration test/integration