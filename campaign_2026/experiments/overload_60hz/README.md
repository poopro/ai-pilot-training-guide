# 原過 G 單 tick 重現診斷

只重播已觀察的 RL／6000 **呎**（約1829公尺）／鏡像開局，seed 2026101311；原引導器和原 bank80 候選各一場。維持控制器、對手、模型 XML、初始狀態與來源 bytes，只新增60Hz逐tick遙測。沒有新候選、SAC learner、保留集或自動部署。

預設與 `--check-only` 都只做檔案、來源與程序檢查，**不建立 JSBSim 模擬器**。核對的是已保存的 initial SHA；實際重播是否完全重現，要等完整兩場、正常退出與驗證器通過。

```powershell
$py = 'C:\Users\USER\anaconda3\envs\F16_ai\python.exe'
$tool = 'E:\ai_pilot\campaign_2026\experiments\overload_60hz\launch_diagnostic.py'
& $py -B -X utf8 $tool --check-only
```

正式重播時使用 `start`。它先建立獨立 watchdog，再啟動監督程序；固定20分鐘總期限，每場300秒，只有兩場。START前核對沒有其他 learner、研究評估或Host；每個stage都凍結來源。已用過的開局只標成重播診斷，不能當新的保留集。

```powershell
& $py -B -X utf8 $tool start
# 等兩場與監督程序正常退出後：
& $py -B -X utf8 $tool verify --job 'E:\ai_pilot\campaign_2026\experiments\overload_60hz\run_...'
```

提前停止，在該 run 資料夾建立 `STOP`。獨立 watchdog 在對話停止、supervisor 消失、STOP或固定deadline時仍會收尾。只按 PID、建立時間、完整命令核對自己的程序，先停深層子程序，絕不以「所有Python」清理。

驗證器要求：兩場正常退出、每tick無缺漏、合法有限指令、同原initial SHA、同原終態与所有final metrics、精確counter重現。原guide過G=0tick；bank80過G=1tick。只有全部相同才產生 `VERIFIED_REPRODUCTION.json`；內容包含244–245秒逐tick視窗與真正峰值。

Codex額度與每日6小時僅警告。此次明確重播在當日帳本保守預留20分鐘，仍受独立硬性deadline與資源門檻約束。
