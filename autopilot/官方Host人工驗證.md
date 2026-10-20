# 官方公告版 Host 驗證與重跑步驟

2026-10-06 已完成一場 repair_guide 純引導器實測。Host 在 100.45 秒自動裁決 Player1 勝：我方 HP=180、對方 HP=0、我方 score_kills=3、advantage=37108.674。不是正式賽事認證，也不是多對手勝率。

完整 CSV、ACMI 與程式指紋見 [本次結果](<E:/ai_pilot/autopilot/combat_fix/official_validation/host_20261006_204436_608d/官方Host結果.md>)。score_kills=3 保留 Host 原值，不解讀為擊落三架。

## 下次重跑

1. 確認舊 Host 已 STOP 並關閉，旧 Player 已停止；不要同時開兩套。
2. 雙擊 `E:\ai_pilot\autopilot\combat_fix\連官方Host_修正版純引導器.cmd`。這是 repair_guide，沒有 RL，接收 8199、回送 8099。
3. 雙擊 `E:\ai_pilot\autopilot\combat_fix\啟動官方Host.cmd`。入口會從官方資料夾啟動並保存 Host stdout/stderr；避免從 Codex 安裝目錄啟動。
4. 按 INIT，等左右兩側綠色 READY，再等 GO，才按 START。Host 自動啟動 P2，不要另開 P2。
5. 讓倒數五分鐘或 Host 提前裁決結束回合；勿為了湊五分鐘改裁判或忽略提前勝負。
6. 保存 Host 新產生的 CSV 和 output_acmi 回放。核對 time、兩方 HP、Score_Kills、Score_FinalAdvantage、system_Final_whoiswinner；GUI 倒數不是完整性證據。
7. 下一回合先停止並重啟 Player，清掉引導器狀態。公開 OBS 沒有可靠回合 ID。

本次已保存控制器、Host 二進位 SHA256、Setting.txt、Player 和 Host 程序身分。原控制器參數、官方設定與二進位未修改。全域舊入口保留；請使用上述修正版入口。

正式現場 IP／port 仍以主辦方設定為準，額外建立網路 JSON，不覆寫既有設定。公告版內建 P2 的單場勝負不代表可擊敗所有 RL 對手。
