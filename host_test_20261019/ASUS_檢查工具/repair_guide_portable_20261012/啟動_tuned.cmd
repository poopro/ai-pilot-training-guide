@echo off
chcp 65001 >nul
title Fighter - tuned
"%~dp0runtime\python.exe" -I -S -B -X utf8 "%~dp0tools\self_check_fighter.py" --quiet
if errorlevel 1 goto failed
"%~dp0runtime\python.exe" -I -S -B -X utf8 "%~dp0tools\player_fighter.py" --network "%~dp0network.json" --profile tuned
:failed
pause
