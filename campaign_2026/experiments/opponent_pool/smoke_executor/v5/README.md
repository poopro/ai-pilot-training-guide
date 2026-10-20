# v5：24案短批準備（尚未執行）

v4 單案 `run_20261014_203352_611acd` 已完成真正 FDM 300tick：launcher、supervisor、worker、guard 真實退出均0；verify退出0，verified_single_case_diagnostic=true，errors=[]。來源、CSV、ACMI均通過核對，guard沒有存檔錯誤。這只驗證 rule／6000ft／normal 一案及 guard 修復，不能代表完整24案或self-play勝率。

v5 從凍結 v4 隔離建立。guard.py（含只查驗到 supervisor 的祖先邊界、Windows replace有界重試、STOP／原預留monotonic截止／精確子孫清理）bytes與v4相同。RAM>=2GiB、磁碟>=10GiB、OS lock、各級STOP、來源/XML/模型/SHA、用過/保留seed、即時用量與預算、父子PID/建立時間/命令及真實Popen退出閘門均保留。worker/supervisor只增加計畫模式契約檢查；正式repair_guide、模型、POOL_FREEZE與v4 code/run未修改。

完整模式為4對手（rule／rl／repair_guide／rule_bank60）×3距離（3000／6000／9000ft）×左右2側，共24案、12左右配對、12種子。其中guide對guide共6案（3正常＋3鏡像）。每案最多300個60Hz tick、Popen前開始30秒；整批自預留預算時固定900秒。準備計畫不預留種子/預算，也不建FDM。

新base seed2026102700，12個實際種子：2700、2701、2702、2710、2711、2712、2720、2721、2722、2730、2731、2732（皆加前綴202610）。全部以現行registry检查；任何已觀察、已嘗試或保留集碰撞均拒絕。首次真正執行才預留15分鐘，任何失敗仍記已嘗試，不能盲目重跑。

只讀完整模式：

```powershell
& 'C:\Users\USER\anaconda3\envs\F16_ai\python.exe' -B -X utf8 'E:\ai_pilot\campaign_2026\experiments\opponent_pool\smoke_executor\v5\launch_smoke.py' --check-only --seed 2026102700
& 'C:\Users\USER\anaconda3\envs\F16_ai\python.exe' -B -X utf8 -m unittest discover -s 'E:\ai_pilot\campaign_2026\experiments\opponent_pool\smoke_executor\v5' -p 'test_*.py' -v
```

可選單案只讀模式是在同入口增加 `--diagnostic-case-index 0..23`，限定1案、300tick、30秒／整體60秒。執行計畫、base seed、模式、預算必須匹配凍結CONTRACT；單案不能被分類成完整24案成功。

28項离線測試通過：保留20項故障反例，另8項核對完整/單案計畫、錯分類/預算/seed拒絕，以及v4安全閘門AST與guard bytes不變。測試未建FDM、未預留真種子或預算、未終止真正工作程序。

v5尚未執行FDM，完整24案、左右配對與guide自我對戰結果均未驗證。主工作正在portable Host獨立回合；不能同時啟本批。之後主工作重新讀取即時用量與occupancy，才移除--check-only並傳入--remaining-percent／--usage-epoch。真正退出後以本目錄verify_smoke.py --out查驗完整24/12、每tick命令/觀測/CSV/ACMI、控制器/RNG獨立、來源與產物SHA，以及supervisor/worker/guard真實退出和清理。結果仍不得宣稱戰鬥勝率、正式Host認證或部署許可。
