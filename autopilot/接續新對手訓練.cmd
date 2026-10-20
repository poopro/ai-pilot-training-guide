@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
echo 同設定接續最近的新對手完整存檔：模型、optimizer、replay 和步數。
echo 再新增最多十萬步或六十分鐘；不是重置舊模型。
"C:\Users\USER\anaconda3\envs\F16_ai\python.exe" -X utf8 "%~dp0opponent_lab\train_opponents.py" --resume-latest --steps 100000 --p2 mixed --device auto --max-minutes 60
if errorlevel 1 goto failed
"C:\Users\USER\anaconda3\envs\F16_ai\python.exe" -X utf8 "%~dp0opponent_lab\training_control.py" evaluate --only-if-completed
goto end
:failed
echo 無法接續，請保留上方訊息。改設定時應使用策略移植，不要硬載入舊 replay。
:end
pause
