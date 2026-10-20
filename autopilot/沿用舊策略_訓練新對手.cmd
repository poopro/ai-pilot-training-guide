@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
echo 沿用已驗證第三版的飛行策略，重新建立 critic 和 replay。
echo 本次最多新增十萬步或六十分鐘；紅方混合規則式與凍結 SAC 對手。
echo Ctrl+C 會保存；請不要直接關閉視窗。也可雙擊「停止新對手訓練並保存」。
"C:\Users\USER\anaconda3\envs\F16_ai\python.exe" -X utf8 "%~dp0opponent_lab\train_opponents.py" --steps 100000 --p2 mixed --device auto --max-minutes 60
if errorlevel 1 goto failed
echo 訓練存檔完成。接著做固定開發評估，最多十分鐘。
"C:\Users\USER\anaconda3\envs\F16_ai\python.exe" -X utf8 "%~dp0opponent_lab\training_control.py" evaluate --only-if-completed
if errorlevel 1 echo 評估未完成，模型仍保留；請查看評估報告。
goto end
:failed
echo 訓練有錯誤，請保留訊息並查看 result.json。尚存的 checkpoint 不會被覆蓋。
:end
pause
