@echo off
chcp 65001 >nul
echo 修正版官方連線入口。請先開官方Host並核對udp_config.json的IP與PORT。
echo 這次連線仍須由官方Host判定；每一回合開始前重新啟動此程式。
"C:\Users\USER\anaconda3\envs\F16_ai\python.exe" -X utf8 "E:\ai_pilot\autopilot\combat_fix\player.py" --guide
pause
