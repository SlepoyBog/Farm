@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

cd /d "%~dp0"

echo ========================================
echo   AI Content Farm - Боевой режим
echo   15 статей в полный цикл
echo ========================================

echo [1/4] Установка зависимостей...
pip install -r requirements.txt >nul 2>&1

echo [2/4] Генерация и публикация 15 статей...
python src/main.py --full
if %errorlevel% neq 0 (
    echo [!] Ошибка генерации. Лог: logs/process.log
    exit /b 1
)

echo [3/4] Цикл обратной связи (сбор метрик)...
python src/feedback_loop.py

echo [4/4] Деплой и фиксация версии...
call scripts\commit_version.bat "full run, 15 articles"

echo.
echo Готово! Опубликовано 15 статей.
