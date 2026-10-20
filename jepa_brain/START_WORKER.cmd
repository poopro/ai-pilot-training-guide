@echo off
title jepa_brain worker (close this window or run STOP_WORKER.cmd to stop)
cd /d "%~dp0"
if exist jobs\STOP del jobs\STOP
"C:\Users\USER\anaconda3\envs\F16_ai\python.exe" -X utf8 -u worker.py
pause
