@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo ========================================
echo   AI Content Farm - ТЕСТОВЫЙ ЗАПУСК
echo   1 пост · для отладки
echo ========================================
echo.
echo Для полного цикла: run_prod.bat
echo.

cd /d "%~dp0"

echo [1/2] Установка зависимостей...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Ошибка при установке зависимостей!
    pause
    exit /b 1
)

echo.
echo [2/2] Запуск генерации (1 пост)...
echo.
python src/main.py

if %errorlevel% neq 0 (
    echo.
    echo Ошибка. Проверьте логи в папке logs/.
    pause
    exit /b 1
)

echo.
echo Готово! Пост опубликован.
pause
