# bank80 G保護 latch：兩場開發 smoke

只新增一項控制因素：`abs(G)>8.5` 啟動既有G limiter，直到 `abs(G)<8.0` 才解除。原bank80轉彎方法、trim、slew、恢復、其他安全因素保持原算法。原凍結控制器與正式部署檔案不修改。

只安排原RL／6000呎（約1829公尺）／鏡像開局兩場：**未修bank80 vs latch候選**。資料中的 `guide` 是配對slot名稱，實際控制器為未修bank80。之前的純guide僅描述，不能說成這次公平比較或重跑原完整診斷。

```powershell
$py='C:\Users\USER\anaconda3\envs\F16_ai\python.exe'
$tool='E:\ai_pilot\campaign_2026\experiments\g_latch_smoke\launch_smoke.py'
& $py -B -X utf8 $tool --check-only
```

check-only只讀來源、AST唯一變更、已驗證原證據、同初始SHA與現有程序；不啟動模擬器。Host或其他研究仍在執行時，顯示 `ready_to_start=false`，start會拒絕並行。

正式小試命令為 `start`，最多20分鐘、每場300秒；先建立獨立guardian，由guardian親自建立並等待supervisor，保存真正的parent與worker退出receipt。OS lock、PID/建立時間/完整命令、固定來源SHA、STOP、磁碟/RAM與固定deadline會保護此run；不開learner。

```powershell
& $py -B -X utf8 $tool start
# 等兩場及guardian退出後核對：
& $py -B -X utf8 $tool verify --job 'E:\ai_pilot\campaign_2026\experiments\g_latch_smoke\run_...'
```

停止請在run資料夾放 `STOP`。來源改變、worker/parent沒有真實正常退出、缺tick或初始SHA不同，都不能產生有效smoke證據。未修bank80必須重現原1tick過G與所有原metrics；新候選逐tick記錄latch，使用前一tick的實際G核對狀態。任何結果都不自動部署，也不代表奪冠機率。
