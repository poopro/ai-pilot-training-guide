@echo off
cd /d "%~dp0"
if not exist jobs mkdir jobs
echo stop> jobs\STOP
echo STOP requested. The worker will end the running job and exit within a few seconds.
pause
