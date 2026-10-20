@echo off
chcp 65001 >nul
title Fighter - base_t3 RESUME (mid-round only)
"%~dp0runtime\python.exe" -I -S -B -X utf8 "%~dp0tools\self_check_fighter.py" --quiet
if errorlevel 1 goto failed
"%~dp0runtime\python.exe" -I -S -B -X utf8 "%~dp0tools\player_fighter.py" --network "%~dp0network.json" --profile base_t3 --resume
:failed
pause
