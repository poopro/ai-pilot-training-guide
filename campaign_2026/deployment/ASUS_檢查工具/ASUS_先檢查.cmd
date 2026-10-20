@echo off
chcp 65001 >nul
set "PILOT_PACKAGE=%~dp0repair_guide_portable_20261012"
if not exist "%PILOT_PACKAGE%\runtime\python.exe" set "PILOT_PACKAGE=%~dp0..\repair_guide_portable_20261012"
if not exist "%PILOT_PACKAGE%\runtime\python.exe" goto missing
"%PILOT_PACKAGE%\runtime\python.exe" -I -S -B -X utf8 "%~dp0check_vivobook.py"
set "PILOT_CHECK_EXIT=%errorlevel%"
pause
exit /b %PILOT_CHECK_EXIT%
:missing
echo 請先把 repair_guide_portable_20261012.zip 解壓縮到本資料夾，保留原資料夾名稱。
pause
exit /b 1
