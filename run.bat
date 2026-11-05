@echo off
rem StreamGrab - gelistirme baslaticisi (konsollu, hatalari gorursun)
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo .venv bulunamadi. Once: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m streamgrab.main
if errorlevel 1 pause

