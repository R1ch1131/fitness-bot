@echo off
chcp 65001 > nul
title Hevy & YAZIO AI Coach Bot
cd /d "%~dp0"
echo ========================================================
echo Запуск персонального Telegram-бота тренера (Hevy + YAZIO)
echo ========================================================
"C:\Users\cfyz1\AppData\Local\Python\bin\python.exe" bot.py
pause
