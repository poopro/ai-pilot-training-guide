@echo off
chcp 65001 >nul
REM ============================================================
REM  AI Pilot WIN campaign control
REM    1 = run the queue once      2 = run forever (every 5 min)
REM    3 = status                  4 = what needs YOU
REM    5 = rerun the M2 crash-gate re-analysis (free, no simulation)
REM ============================================================
cd /d "%~dp0"
set PY=C:\Users\USER\anaconda3\envs\F16_ai\python.exe

if "%~1"=="1"  goto run
if "%~1"=="2"  goto loop
if "%~1"=="3"  goto status
if "%~1"=="4"  goto needs
if "%~1"=="5"  goto regate
echo 1=run  2=loop  3=status  4=needs-you  5=rerun-M2
pause
exit /b

:run
%PY% -X utf8 win_loop.py run
goto done
:loop
%PY% -X utf8 win_loop.py loop --gap 300
goto done
:status
%PY% -X utf8 win_loop.py status
goto done
:needs
%PY% -X utf8 notify.py
goto done
:regate
%PY% -X utf8 m2_regate.py
goto done
:done
echo.
pause
