@echo off
title Tarkov Compass
cd /d "%~dp0"
if not exist tracker.pid (echo Tracker lijkt niet te draaien.& pause & exit /b)
set /p PID=<tracker.pid
taskkill /PID %PID% /F >nul 2>nul
del tracker.pid >nul 2>nul
echo Tracker gestopt.
timeout /t 2 >nul
