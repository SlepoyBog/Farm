@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

echo ========================================
echo   Rollback — AI Content Farm
echo ========================================
echo.

if "%1"=="" (
    echo Использование: rollback.bat [номер_версии]
    echo.
    echo Пример: rollback.bat 3  — откат к версии 3
    echo         rollback.bat last — откат на 1 коммит назад
    echo.
    echo Доступные версии:
    git log --oneline --grep="v" 2>nul | findstr /i "v"
    if errorlevel 1 (
        echo   [нет версионных коммитов]
    )
    echo.
    echo Последние 10 коммитов:
    git log --oneline -10
    goto :eof
)

if "%1"=="last" (
    echo [1/3] Откат на 1 коммит назад (soft reset)...
    git reset --soft HEAD~1
    if errorlevel 1 (
        echo Ошибка: не удалось выполнить reset. Возможно, это первый коммит.
        pause
        exit /b 1
    )
    echo [2/3] Возврат VERSION к предыдущему значению...
    git checkout HEAD@{1} -- VERSION 2>nul
    echo [OK] Готово. Изменения в индексе, редактируйте и коммитьте заново.
    pause
    exit /b 0
)

echo [1/3] Поиск коммита с версией v%1...
for /f "tokens=1 delims= " %%i in ('git log --all --oneline --grep="v%1"') do set COMMIT_HASH=%%i

if "%COMMIT_HASH%"=="" (
    echo Ошибка: версия v%1 не найдена в истории коммитов.
    echo.
    echo Доступные версии:
    git log --oneline --grep="v" 2>nul | findstr /i "v"
    pause
    exit /b 1
)

echo    Найден коммит: %COMMIT_HASH%
echo.

echo [2/3] Создание ветки для отката (rollback-v%1)...
git branch -f rollback-v%1 HEAD
if errorlevel 1 (
    echo Ошибка при создании ветки.
    pause
    exit /b 1
)

echo [3/3] Откат к версии v%1...
git reset --soft %COMMIT_HASH%
if errorlevel 1 (
    echo Ошибка при откате.
    pause
    exit /b 1
)

echo.
echo [OK] Откат к v%1 выполнен. Изменения в индексе.
echo      Проверьте файлы и выполните коммит:
echo      git commit -m "rollback: v%1"
echo.
echo      Версия в VERSION всё ещё текущая — обновите вручную если нужно.
pause
