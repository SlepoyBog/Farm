@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

cd /d "%~dp0"

echo ========================================
echo   AI Content Farm - БОЕВОЙ ЗАПУСК
echo   15 постов · полный цикл
echo ========================================

echo [1/4] Установка зависимостей...
pip install -r requirements.txt >nul 2>&1

echo [2/4] Генерация и публикация 15 постов...
python src/main.py --full
if %errorlevel% neq 0 (
    echo [!] Ошибка генерации. Логи: logs/process.log
    exit /b 1
)

echo [3/4] Цикл обратной связи (сбор метрик)...
python src/feedback_loop.py

echo [4/4] Деплой сайта на GitHub Pages...
git add site/ -A
git commit -m "Auto-update site" >nul 2>&1
git push origin main >nul 2>&1

echo.
echo Готово! Опубликовано 15 постов.
