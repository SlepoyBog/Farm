@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0.."

if "%1"=="" (
    set MSG=Auto-update
) else (
    set MSG=%*
)

REM Read current version
set /p VERSION=<VERSION
set /a NEXT_VERSION=VERSION+1

echo ========================================
echo   Commit v%NEXT_VERSION%
echo ========================================
echo.

echo [1/5] Чтение текущей версии: v%VERSION% → v%NEXT_VERSION%

echo [2/5] Обновление VERSION...
echo %NEXT_VERSION% > VERSION

echo [3/5] Добавление файлов...
git add -A

echo [4/5] Коммит...
git commit -m "v%NEXT_VERSION%: %MSG% [skip ci]"
if errorlevel 1 (
    echo [!] Нечего коммитить или ошибка.
    exit /b 1
)

echo [5/5] Пуш в GitHub...
git push origin main
if errorlevel 1 (
    echo [!] Ошибка пуша. Проверьте подключение к GitHub.
    pause
    exit /b 1
)

echo.
echo [OK] v%NEXT_VERSION% закоммичена и запущена.
echo      Хеш: 
git rev-parse HEAD
pause
