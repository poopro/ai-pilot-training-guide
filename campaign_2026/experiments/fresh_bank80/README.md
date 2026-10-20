# 凍結bank80候選：新開局驗證工具

狀態：工具準備完成，10項閘門檢查通過；尚未執行新開局FDM或產生新勝率結果。

## 下一輪工作

先讀PREPARATION.json與seed_registry.json。候選与原command不變；只改開局種子，12開局×guide/candidate=24完整場，兩種對手、三個距離、正常/鏡像側，150秒/場、總40分鐘硬上限。擬定seed=2026101300（產生1300/1301/1302/1310/1311/1312），僅相對於專案已記錄case inputs尚未出現，不能稱全歷史未見或保留集。

檢查入口（不啟動模擬，也不扣預算）：

```powershell
& 'C:\Users\USER\anaconda3\envs\F16_ai\python.exe' -B -X utf8 'E:\ai_pilot\campaign_2026\experiments\fresh_bank80\launch_fresh.py' --check-only
```

10/13以後，Codex先讀即時五小時與每週用量，取較低剩餘值，必須>=35%，觀察時間距啟動<=600秒。實際啟動命令由Codex填入工具剛回傳的剩餘百分比與UTC Unix epoch，不沿用10/12舊觀察：

```powershell
& 'C:\Users\USER\anaconda3\envs\F16_ai\python.exe' -B -X utf8 'E:\ai_pilot\campaign_2026\experiments\fresh_bank80\launch_fresh.py' --seed 2026101300 --remaining-percent <即時較低剩餘百分比> --usage-epoch <剛觀察的UTC秒數>
```

這是參數樣板，尖括號必須換成真實數值。

啟動器持有campaign的OS lock，先檢查其他learner/評估、STOP、RAM/磁碟、142檔候選快照與原Python/XML/紅方hash。先將40分鐘計入當日compute_budgets，再消耗登記六個新種子；失敗或中斷不退還預留額度或重用種子。當日餘額不夠、剩不到40分鐘到午夜、10/13以前或11/3以後即拒絕。私有worker需父PID/建立時間/命令列、直接父子關係、預算項目與已規劃case/source皆一致，不能獨立繞過launcher執行。

## 完成後

用研究pointer定位該run，等工具確實回報程序退出0；再呼叫verify_fresh.py --parent-exit-code 0。它會拒絕仍活著的父程序、不完整24場、缺少12對、不同initial SHA、來源/紅方變動、CSV/ACMI缺損。新guide是新開局，不能要求與舊seed結果相同，也不能冒稱重現舊場。

COMPARISON.json只支持這批新開發集；仍需共同時間高度、recover時擊落與失去rule擊落的檢討，之後才擴充凍結對手池、從未評估的保留集与官方Host。此工具不自動部署，也不啟動新SAC。

已保留10/12原版benchmark與候選快照；這個新的supervisor指紋是隔離評估程式契約，沒有更改飛控動態或actor。PREPARATION.json記明目前只驗證閘門與mock邊界，未完成新FDM成功路径。
