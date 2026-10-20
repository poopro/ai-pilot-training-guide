# v4：只查驗到本批 supervisor 的祖先鏈

v3 真實單案 `run_20261014_202846_6d8021` 在 FDM 前停止：guard 先取得 child.parents() 的整條祖先鏈，對全部祖先讀取 PID／建立時間／命令，再截斷到 supervisor。這個順序超出本批範圍，讀到 supervisor 上方的 svchost.exe（PID 3112），遇 AccessDenied 後把合法子孫判成未知。原 run、來源契約、已使用 seed2026102501 與一分鐘預算保留，不重用。

v4 的 owned_ancestor_chain 改用逐層 parent()。每層查驗 PID／建立時間／命令，抵達精確 supervisor 就立即返回；不呼叫 supervisor.parent()，不讀上方服務或系統程序。必要鏈的 AccessDenied 仍傳回未知並拒絕通過；同 PID 但建立時間／命令不同、祖先循環或不通往 supervisor 的鏈，均不建立清理授權。磁碟 active_worker 聲明仍不能授權清理無關程序。

其餘行為沿用 v3：原子 replace 最多 8 次重試，sleep 合計最多0.39秒；存檔失敗仍處理 STOP、預留時固定的 monotonic deadline 與已確認子孫。單案最多300 tick，從 Popen 前開始30秒；診斷整體從預算預留時開始60秒，最高整批上限仍900秒。保留 RAM 2GiB／磁碟10GiB、OS lock、各級 STOP、來源/XML/模型/執行器 SHA、種子與預算、即時用量及精確父子身分閘門。run_smoke.py／verify_smoke.py 與 v3 bytes 完全相同。正式 repair_guide 與模型未修改。

20項故障注入測試通過，含原13項與7項祖先範圍反例；測試未建立 FDM、未預留真 seed／預算、未終止真正工作程序。v4 尚未執行真 FDM。

只讀入口：

```powershell
& 'C:\Users\USER\anaconda3\envs\F16_ai\python.exe' -B -X utf8 'E:\ai_pilot\campaign_2026\experiments\opponent_pool\smoke_executor\v4\launch_smoke.py' --check-only --seed 2026102600 --diagnostic-case-index 2
& 'C:\Users\USER\anaconda3\envs\F16_ai\python.exe' -B -X utf8 -m unittest discover -s 'E:\ai_pilot\campaign_2026\experiments\opponent_pool\smoke_executor\v4' -p test_guard_repair.py -v
```

index2 是 rule／6000ft／normal，實際 seed2026102601。主工作讀取當次用量後，才移除 --check-only 並傳入 --remaining-percent 與 --usage-epoch 啟動一案。真正退出後以本目錄 verify_smoke.py --out 查驗 supervisor／worker／guard 真實 Popen 退出、CSV／ACMI、SHA 與清理證據。單案成功不代表完整24案、self-play戰鬥勝率或正式Host認證。
