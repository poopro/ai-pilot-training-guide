# 凍結對手池：24 個短回合的執行器

這個分支只使用現行 repair_guide：4 個凍結對手 × 3 種距離 × 左右兩側，共24 case；其中6個是guide對guide。每case最多300個60Hz tick（5秒），case wall deadline30秒、整批900秒。它驗證飛機初始化、獨立控制器狀態/RNG與命令介面，不能證明戰鬥勝率、bank80可升級或正式比賽表現。

入口為 launch_smoke.py。它持有全專案 launch.lock、檢查STOP與目前Host/訓練/研究程序、RAM至少2GiB、磁碟至少10GiB、完整來源/XML/紅方模型SHA；正式首次嘗試前寫15分鐘預算及12開發種子。Codex剩餘及每日6h只有警告；新觀察必須距今600秒內。已看過、已嘗試或保留集種子不能重用。

run_smoke.py 的 supervisor 與 worker 都驗證直接父程序PID、建立時間、命令及預留case。獨立 guard.py 監督整批900秒與單case30秒，即使聊天中斷仍可收尾；它在父程序存活時記錄子孫身分/祖先證據，只停止已確認屬於這批的程序。AccessDenied保留未知，阻止宣稱清理成功。

每tick把藍紅兩個四維命令在sendAction前檢查有限且合法邊界；CSV逐tick記錄命令、有限飛行状态與合法26維觀測SHA；ACMI保存每tick雙機軌跡。紅藍控制器與其積分/前幀狀態不能共用，RNG也各自建立。左右pair保留紅方初態、雙方姿態/高度/CAS與初始RNG一致，反轉cross-track且距離差不得超1%。

以下只檢查，不啟FDM、不登記種子或預算：

```powershell
& 'C:\Users\USER\anaconda3\envs\F16_ai\python.exe' -B -X utf8 'E:\ai_pilot\campaign_2026\experiments\opponent_pool\smoke_executor\launch_smoke.py' --check-only
& 'C:\Users\USER\anaconda3\envs\F16_ai\python.exe' -B -X utf8 -m unittest discover -s 'E:\ai_pilot\campaign_2026\experiments\opponent_pool\smoke_executor' -p test_smoke_executor.py -v
```

正式執行須先讀即時Codex用量，填入較低剩餘百分比與其UTC Unix epoch，不得推測或沿用舊值。其他研究/Host仍在運行時不可啟動：

```powershell
# $remainingPercent / $observedUtcEpoch 必須來自當次用量觀察。
& 'C:\Users\USER\anaconda3\envs\F16_ai\python.exe' -B -X utf8 'E:\ai_pilot\campaign_2026\experiments\opponent_pool\smoke_executor\launch_smoke.py' --seed 2026102400 --remaining-percent $remainingPercent --usage-epoch $observedUtcEpoch
# launcher印出實際out路徑並真實退出後，把它設為$smokeOutput再檢查。
& 'C:\Users\USER\anaconda3\envs\F16_ai\python.exe' -B -X utf8 'E:\ai_pilot\campaign_2026\experiments\opponent_pool\smoke_executor\verify_smoke.py' --out $smokeOutput
```

verify_smoke.py 必須核對launcher實際觀察的supervisor退出0、每worker退出0、guard退出0與完成清理、完整24case/12左右pair、來源与產物SHA、每tick雙機CSV/ACMI、有限命令/狀態及獨立控制器契約。缺樣本、逾時、失敗、未知身分、保存錯誤都不能通過。失敗保留證據及種子/預算，不能全批重啟；先檢討原因並建立新trial。

截至本次只完成實作、check-only及mock/自己建立的短命dummy程序測試。mock verifier通過與缺一tick拒絕，並不表示成功FDM路徑已執行。第一次真實執行仍需核對模型載入能否在30秒內完成、JSBSim sendAction攔截與軌跡格式、終態及輸出。本分支未訓練、未修改freeze、未改正式部署。
