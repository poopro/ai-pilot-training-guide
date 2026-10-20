# 近距離bank75：兩個已知開局、四場隔離診斷

已完成12項無FDM測試，root的v5程序真實退出後，prepare及check-only均退出0。MANIFEST與PREPARATION已凍結，trial為`near75_known_cf_5a197df1ff174636`；最後check顯示ready_to_start=true、沒有重疊工作。尚未啟動本診斷，動態假設未證實。root啟動前仍須確認最新程序狀態與即時用量。

比較的是此次重新完整執行的`bank80_latch`基準與`bank75_latch`候選。候選只將近距離bank_limit的80改75，遠距離仍72；command、G latch、trim、gain、安全閾值與slew全部繼承相同基準。沒有學習模型、參數掃描或部署替換。

| 已知development開局 | 兩個明確actor | 每場最大模擬tick |
|---|---|---:|
| rule／3000ft／mirrored／seed 2026101400 | bank80_latch、bank75_latch | 18000 |
| RL／9000ft／mirrored／seed 2026101412 | bank80_latch、bank75_latch | 18000 |

這是`known_development_counterfactual`，不稱fresh或holdout。只讀這兩個已保存candidate開局的result/input檔核對initial SHA，不重跑原24場，也不將原24場成績當此次新基準。鏡像開局不等於官方角色交換。

沿用g_latch_smoke的guardian、supervisor、worker與60Hz記錄器，僅在新程序內綁定新來源／case plan／actor class與6分鐘case上限。原凍結149檔、來源／XML、紅方模型、原run及正式部署均保留。執行前、worker中與驗證後核對SHA。prepare及start有OS啟動鎖，supervisor有OS learner鎖；STOP、資源壓力及其他Host／portable／selfplay研究程序會阻擋或結束本次診斷。

整體原始monotonic deadline為20分鐘，每場wall cap6分鐘；同時保存epoch供顯示。原時限涵蓋啟動與等待，不因WinError5 atomic retry而重算。atomic replace最多6次、等待有上限；NoSuchProcess保留PID與命令，建立時間未知則明記未知。不能把程序消失當退出0。用量與每日預算採警告，root仍須先讀即時額度；只有明確有界診斷，不自動擴大。

root操作入口（在另一個研究程序真退出後）：

```powershell
$python = 'C:\Users\USER\anaconda3\envs\F16_ai\python.exe'
$tool = 'E:\ai_pilot\campaign_2026\experiments\near_bank75_diagnostic\launch_diagnostic.py'
& $python -B -X utf8 $tool prepare
& $python -B -X utf8 $tool check --remaining-percent 10
```

`check`不啟FDM。準備通過後，root可依剛讀取的實際remaining值執行一次start：

```powershell
& $python -B -X utf8 $tool start --remaining-percent 10
```

start回傳新run絕對路徑。**立即在guardian仍活著時啟動observer，讓exec session持續持有Windows process handle：**

```powershell
& $python -B -X utf8 $tool observe-guardian --job '<start回傳的新run路徑>'
```

observer只接受新run的guardian_spawn.json，核對PID／create time／command，再用OpenProcess、GetProcessTimes、WaitForSingleObject與GetExitCodeProcess取得真實退出。失去handle、程序已消失或身份不吻合不能補0。此observer不啟FDM或改控制器。guardian真退出後才執行：

```powershell
& $python -B -X utf8 $tool verify --job '<同一新run路徑>'
```

verify要求guardian真退出0與handle身份收據、supervisor和四個worker真正Popen wait退出0、完整合法回合、同initial SHA、來源／XML／red SHA、60Hz逐tickCSV、累積attack counter與ACMI終態一致。每case報告HSL／AGL最低高度、attack tick與秒數、峰值absG、過9G tick、death與crash；candidate任何一tickabsG>9都拒絕。

假設可反證：rule共同曝露時間的最低HSL高度須比此次新bank80_latch基準改善，且RL candidate攻擊至少166tick。失敗就不支持假設。即使通過，也只允許另登記新development測試；尚不能說保留原三個rule擊殺優勢，更不能部署或估奪冠概率。

12項單元測試與真Windows mock observer證據見TEST_EVIDENCE.json。mock只是短暫sleep程序，不是FDM或真正guardian四場正向驗證。程式與來源已完成凍結；本次尚無新FDM或動態成績。
