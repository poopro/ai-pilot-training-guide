@echo off
setlocal
chcp 65001 >nul
"C:\Users\USER\anaconda3\envs\F16_ai\python.exe" -X utf8 "%~dp0opponent_lab\training_control.py" stop
pause
