# 最後需要你完成的官方測試

本輪已通過本地封包與 Player 測試，尚未取得官方 Host 裁判結果。Host 啟動期間出現 SmartScreen，AI 未操作安全提示。請先由你確認程式來源與安全提示；本文件不要求關閉防護或改 Windows 安全設定。

依 Host 的 `readme_part1.txt`，同機測試步驟：

1. 等本輪 `最新結果.md` 顯示收尾，確認選擇的本地控制器。
2. 雙擊 `E:\ai_pilot\autopilot\啟動最佳本地控制器.cmd`。預設接收 OBS 8199，回送 CMD 8099，雙方 IP 為 127.0.0.1。這組設定已核對 Host Setting.txt，正式現場仍以主辦方設定為準。
3. 在官方 Host 資料夾啟動 `JSB_host_GUI_publish.exe`，按 `INIT PLAYERS STATE`，等待 P1／P2 READY 與 GO。Host 會自動啟動 P2，別另外再開一個 P2。
4. READY 倒數結束後仍要按 `START`；完成整個回合，記下 Host 的擊落／墜機／優勢與勝負。只有拿到這些結果才可說正式驗證通過。
5. 按 `STOP` 後查看 Host 的 `output_acmi`。在 Tacview 核對兩架飛機、顏色、時間與事件；Host 顏色依實際畫面。
6. 下一場先用 `E:\ai_pilot\autopilot\停止本地控制器.cmd` 停 Player，再啟動一次，清掉控制器回合狀態。公開 OBS 沒有可靠回合 ID，目前不自動猜測是否重開一場。

官方 Host 完整路徑：

`E:\ai_pilot\2026 AI 飛行員  相關資料\AI空戰競賽系統安裝及測試指引\AI空戰競賽系統安裝及測試指引\AirCombat_Train_Test\D.比賽用主辦方連線程式_驗證是否符合能正確連線`

若需改現場 IP／port，建立另外一份網路 JSON，保留原 `combat_v3\udp_config.json`。CMD 可傳 `--network "完整網路設定路徑"` 給最佳控制器入口；這只變更接線，不改模型、觀測或獎勵。

請保存：Host 設定、兩方版本、開始／結束時間、完整回合結果、Host ACMI、Player stdout／stderr。碰撞門檻、平局重賽、位置優勢平均或累加的歧義，需用 Host 結果與主辦方說明確認。
