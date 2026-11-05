@echo off
rem StreamGrab - sessiz baslatici (konsol penceresi acilmaz)
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" -m streamgrab.main

