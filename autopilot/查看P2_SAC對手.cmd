@echo off
setlocal
chcp 65001 >nul
echo 藍色 P1 是你的純引導器；紅色 P2 使用現有 SAC 模型與引導器。
echo 先計算一場五分鐘本地對戰，再開啟 Tacview 回放。這不會開始訓練。
echo 這是既有凍結模型，不代表已完成新的強對手訓練。
"C:\Users\USER\anaconda3\envs\F16_ai\python.exe" "%~dp0opponent_lab\duel_lab.py" --p2 rl --blue guide --seed 20264000 --open-tacview
if errorlevel 1 echo 執行失敗，請保留上方錯誤訊息。
pause
