@echo off
title Tarkov Compass
setlocal
cd /d "%~dp0"
REM Sluit alleen oudere processen van deze trackerfamilie; geen willekeurige Python-programma's.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$me=$PID; Get-CimInstance Win32_Process ^| Where-Object { ($_.Name -match 'python(w)?\\.exe|TarkovCompass\\.exe') -and ($_.CommandLine -match 'tracker_(mvp|v[0-9]+)\\.py|tarkov_compass|TarkovCompass') } ^| ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {} }" >nul 2>nul
set "PYW=%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe"
if exist "%PYW%" goto run
set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if exist "%PYW%" goto run
set "PYW=%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe"
if exist "%PYW%" goto run
where pythonw >nul 2>nul && (start "" pythonw "%~dp0tracker_mvp.py" & exit /b 0)
where py >nul 2>nul && (start "" /min py -3 "%~dp0tracker_mvp.py" & exit /b 0)
where python >nul 2>nul && (start "" /min python "%~dp0tracker_mvp.py" & exit /b 0)
echo Python 3 is niet gevonden. Installeer Python 3.11+ en probeer opnieuw.
pause
exit /b 1
:run
start "" "%PYW%" "%~dp0tracker_mvp.py"
exit /b 0
