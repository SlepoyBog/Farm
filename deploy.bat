@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

cd /d "%~dp0"

echo ========================================
echo   Deploy site to GitHub Pages
echo ========================================
echo.

echo [1/4] Проверка изменений...
git status

echo.
echo [2/4] Добавление файлов сайта...
git add -A

echo.
echo [3/4] Регистрация версии...
call scripts\commit_version.bat "deploy site"

echo.
echo Готово! Будет доступно через 1-2 минуты.
pause
