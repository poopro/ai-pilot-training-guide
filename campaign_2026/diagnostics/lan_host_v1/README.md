# 主電腦 ASUS LAN Host profile v1

狀態：靜態設定已準備；Host 尚未啟動，沒有完成 LAN 回合。

## 使用者已提供且已套用的端點
- ASUS Wi-Fi：192.0.2.10
- 主電腦 Ethernet：192.0.2.10
- 兩端 gateway：192.0.2.10
- ASUS 收 OBS：UDP 8199
- 主電腦收 CMD：UDP 8099

## 隔離與保存
- `host_instance/` 是原發布 Host 的獨立副本，只有副本的 `Setting.txt` 將 `PLAYER1_OUTPUT_IP` 從 `127.0.0.1` 改為 ASUS `192.0.2.10`。
- 原發布 Host、portable_host_v4、原 ZIP 與 Player package 均未修改。
- P1 CMD 綁定維持 `0.0.0.0:8099`，P2 維持原本 loopback profile。
- 詳細 SHA 與設定記錄在 `LAN_HOST_PROFILE.json`。

## 尚未啟動的原因
主電腦 Windows 網路類型目前是 Public。未添加任何防火牆例外，也未確認 ASUS Player 已通過本機檢查。LAN 回合需要在新的獨立 supervisor/watchdog 下執行，涵蓋 Host 和內建 P2，並保存雙向網路、終局、CSV/ACMI、實際退出碼及精確清理證據。這些執行監督工具尚未完成，因此本 profile 目前只供靜態檢查，不能直接按 Host 開始測試。

## 下個主電腦步驟
在不改 v4 的前提下，建立 LAN 專用 supervisor：只監督本 profile 的 Host/P2；對 Host/P2 使用硬性期限和精確 PID/建立時間/命令/祖先核對；確認收集器能識別新 CSV/ACMI；先完成無 Host 的 fail-closed 預檢。防火牆只在需要時提出最小範圍規則，不自動改 Public profile。
