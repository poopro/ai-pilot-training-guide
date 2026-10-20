@echo off
chcp 65001 >nul
"%~dp0runtime\python.exe" -I -S -B -X utf8 "%~dp0tools\self_check.py" --quiet
pause
