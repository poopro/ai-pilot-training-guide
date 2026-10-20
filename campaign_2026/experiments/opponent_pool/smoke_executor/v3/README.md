# guard 存檔故障：隔離的 v3 單案診斷

原始 `run_20261014_195159_f7d760`、legacy 工具與 v2 均保留。根因是 guard 每輪使用原子 os.replace 更新 guard.json，在 Windows 被暫時拒絕取代時，未捕捉 PermissionError 而真實退出 1；第三個 worker 在 FDM 前確認獨立 guard 已不存活，因此拒絕執行。紀錄證明 WinError 5，未證明是哪個讀取者造成鎖定。

v3 只允許一個既有合法 case、新的開發 seed；最多 300 tick、單案從 Popen 前開始 30 秒，單案整體從預算預留時開始 60 秒（上限契約仍為 900 秒）。獨立 guard 使用預留時固定的 monotonic deadline；不因 guard 晚啟动延長預算。Windows replace 最多重試 8 次，合計 sleep 不超過 0.39 秒；永久失敗仍履行 STOP、截止與精確 owned descendant 清理。最終無法存檔退出 3，AccessDenied／無法確認退出保留未知，驗證不通過。

guard 以 PID、建立時間、完整命令及實際祖先鏈建立子孫證據；磁碟 active_worker 聲明不授權停止無關程序。父程序在列舉子程序時消失，也繼續清理已確認子孫。launcher 兩次 wait timeout 後保存 actual exit=null，不能假裝退出 0。RAM>=2GiB、磁碟>=10GiB、專案 OS lock、各級 STOP、來源/XML/模型/執行器 SHA、已用/保留 seed、即時用量與預算、父子身分等原閘門持續有效。正式 repair_guide、POOL_FREEZE 與模型未修改。

以下指令只讀，不啟 FDM、不預留 seed 或預算：

```powershell
& 'C:\Users\USER\anaconda3\envs\F16_ai\python.exe' -B -X utf8 'E:\ai_pilot\campaign_2026\experiments\opponent_pool\smoke_executor\v3\launch_smoke.py' --check-only --seed 2026102500 --diagnostic-case-index 2
& 'C:\Users\USER\anaconda3\envs\F16_ai\python.exe' -B -X utf8 -m unittest discover -s 'E:\ai_pilot\campaign_2026\experiments\opponent_pool\smoke_executor\v3' -p test_guard_repair.py -v
```

index 2 為 rule、6000ft、normal；該計畫實際 seed=2026102501。它重現原第三 case 的介面位置，保留已嘗試的 2026102400–2026102432 種子及原 15 分鐘預留項目。

真正執行僅由主工作讀取當次用量後使用同一入口，去掉 --check-only 並加入 --remaining-percent 與 --usage-epoch。事後使用 v3/verify_smoke.py --out 審核真實 Popen supervisor/worker/guard 退出、SHA 與每 tick CSV/ACMI。單案成功只能證明該案的介面及 guard 修復路徑；verified_interface_smoke 永遠不會由單案變為 true，更不代表 self-play 勝率、完整 24 案或正式 Host 認證。

13 項故障注入測試通過。這批測試沒有建飛機、沒有訓練、沒有真正終止工作程序；精確清理反例以模擬程序樹驗證。尚未執行 v3 真 FDM 診斷。
