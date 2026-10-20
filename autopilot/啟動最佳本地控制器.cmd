@echo off
setlocal
chcp 65001 >nul
"C:\Users\USER\anaconda3\envs\F16_ai\python.exe" "E:\ai_pilot\autopilot\launch_player.py" %*
pause
