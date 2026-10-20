# M4 v2：慢速戰術 RL 介面修正準備

來源為使用者在 OpenCode 建立的 M4 分支，保留原 win/ 與全部模型。此分支尚未執行 FDM 或訓練，直接執行會拒絕啟動。

## 已修與已驗證

- 舵面指令不再被當成殘差重新套用；每物理 tick 由父環境呼叫控制器一次。
- 使用父裁判的步進後累積攻擊數；移除重複幾何計數及未聲明的 inherited reward。現為 diagnostic tick reward 與明列的安全罰分，尚非官方完整勝負目標。
- 每 episode 依 seeded RNG 抽對手，reset 清空鏡像內部狀態，guard 觀測跟隨實際步驟。
- episode/best-tick 統計在 SB3 真正呼叫的 on_step 更新，不再把恆0當訓練結果。
- 11 項 AST 載入實際方法的 fake-parent 邊界測試真退出0；含原版40次對新版20次控制呼叫重現。不是飛行成功或學會戰鬥。

## 下一步

依 CONTRACT.json 補有獨立期限的單例 worker，再做短真 FDM 介面驗證及同初始 SHA 配對。正式裁判契約與多樣對手通過後才啟動新的有限訓練。原共享模型不能精確續用 replay/critic/optimizer。正式仍 repair_guide。
