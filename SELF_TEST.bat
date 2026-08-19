@echo off
cd /d "%~dp0"
py -3 self_test.py 2>nul || python self_test.py
pause
