# 私人網路端點交接（2026-10-17）

> 本檔只供目前設為 private 的 `poopro/ai-pilot-training-guide` repo 內已授權協作者使用。不要複製到公開 README、Issue、截圖或外部報告。上傳前已即時核對 repo visibility=private；若未來變成 public，立即移除此檔並改用私人訊息交接。

## 已知端點

| 電腦 | 介面 | IPv4 | Gateway | 網路類型 | 證據 |
|---|---|---:|---:|---|---|
| ASUS Vivobook | Wi-Fi | 192.168.173.202 | 192.168.173.32 | Public | ASUS 操作者在私人對話回報；ASUS Codex 仍須在本機重新核對網卡 |
| 主電腦 | Ethernet | 192.168.173.200 | 192.168.173.32 | Public | 主電腦本機 `ipconfig` 即時核對 |

主電腦目前也有 Radmin VPN `26.164.21.38`，本次走共同 gateway 的 Ethernet/Wi-Fi LAN，不使用 VPN 位址。主電腦 ping ASUS `192.168.173.202` 兩次均成功；這只證明 IP 可達，不證明 UDP Player/Host 已連線。

## 測試埠

- ASUS Player 綁定 OBS 接收端：UDP 8199
- 主電腦 Host CMD 接收端：UDP 8099
- 使用者已同意本次以這兩個預設值作為測試候選；仍需在新 LAN Host 實際啟動後核對 listener 和雙向封包。

## 主電腦現在的狀態

- 主電腦目前沒有 Host/Player 測試程序。
- 主電腦 UDP 8199／8099 沒有 listener；TCP 也沒有這兩個埠的 listener。
- Windows 網路類型為 Public；本次尚未改網路類型、防火牆或任何安全設定。
- 目前 `portable_host_v4` **只接受 loopback**：其 preflight 明確要求 ASUS Player 的 `network.json` 為 `listen_ip=127.0.0.1`、`host_ip=127.0.0.1`，否則拒絕。已凍結的 Host `Setting.txt` 也把 P1 OBS 目的 IP 設為 `127.0.0.1`。因此 v4 的 6/6 是同一台電腦的可攜重現，不能直接當 LAN Host 使用；不得修改 v4 或原 ZIP 來繞過檢查。
- LAN 必須先建立與 v4 完全隔離的新 Host 設定/監督分支，保留 Host、Player、原套件基準與 watchdog 證據。此分支尚未建立或驗證。

## 下一步

1. ASUS Codex 完成套件 SHA、自檢、實際 Wi-Fi 網卡核對及套件外 `network.lan.json`／600 秒限時 Player 啟動器預檢；因 Host 尚未就緒，不啟動 Player，回報 `LOCAL_READY_LAN_PENDING`。
2. 主電腦先建立獨立 LAN Host profile：Host P1 OBS 目的地指向 ASUS 私有 IP；Host CMD 仍在主電腦接收；兩端 port 使用上述候選值。保留原始 Host 設定與 v4 冻結檔，不做全域防火牆修改。
3. 主電腦只在新 Host profile 的 source hash、Host 進程觀察/watchdog、收證與限時清理均完成預檢後通知 ASUS agent。
4. 兩端都就緒後才開一場限時測試；完整新 Host 終局、CSV/ACMI、實際雙向資料及實際退出碼齊備才標成 `LAN_ROUND_VERIFIED`。

## 不可宣稱的結果

- 目前尚未完成 LAN 對戰。
- ping 成功、兩台共用 gateway、CPU 本機檢查通過、UDP send 沒報錯或 Host READY 都不等於一場完整回合。
- 六場 v4 同機測試不代替 ASUS/LAN 測試或正式競賽勝率。
