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
git add site/ -A

echo.
echo [3/4] Коммит...
git commit -m "Auto-update site (%date%)"

echo.
echo [4/4] Пуш в GitHub...
git push origin main

echo.
echo Готово! Будет доступно через 1-2 минуты.
pause
