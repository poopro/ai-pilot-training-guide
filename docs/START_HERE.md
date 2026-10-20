# 新成員先讀這份

## 專案在做什麼

我們用 JSBSim 模擬 F-16 空戰，比較規則控制、小型學習策略與短期預測，目標是提高 2026 年 11 月競賽表現。所有本地勝負都有特定對手、種子與規則版本，不能當成對其他隊伍的勝率。

## 建議閱讀順序

1. [目前狀態與證據界線](STATUS_20261021.md)：先知道哪些真的完成、哪些仍失敗或未驗證。
2. [架構與資料夾對照](ARCHITECTURE.md)：分清 campaign、規則調參、Claude 選項戰術員。
3. `flybrain/README.md`：Claude 研究的完整說明、消融與負面結果。
4. `jepa_brain/bfm.py`、`jepa_brain/portable/fighter.py`、`flybrain/portable/fighter_opt.py`：研究版、可攜版與戰術員接線。
5. `campaign_2026/repair_v1/controller.py`、`campaign_2026/experiments/rules_v20261014/judge.py`、`campaign_2026/experiments/opponent_pool/bank_residual_train_v4/`：原安全控制、具名裁判與新的 bank 學習介面。
6. [如何取得完整快照](REPRODUCING.md)、[公開範圍與去重](PUBLICATION.md)。

有些歷史路徑會因去重而只有 manifest 別名，先還原再讀該位置。搜尋完整清單：`manifests/snapshot.json` 的 `files[].path`。

## 第一個交接任務建議（尚未執行）

先確認正在評估的是哪一個凍結控制器、哪個模型與哪個 judge profile，再提出一個有界的公平比較。Claude 的 ridge／MLP、campaign 的 SAC bank 殘差，不能把不同對手池的數字直接排成排行榜。

目前值得檢查的具體缺口：

- campaign 的 bank17 六場物理模擬已完成，但原嚴格核對器逾時失敗。應另立保存資料審查契約，保留原失敗；不需要重跑六場。
- Claude 的 portable 選項戰術員需要區分它自身的 Host 接線證據，與其他 fighter／果蠅選配版本的 Host 接線證據。
- 共同對手池、左右開局、同雙方 initial SHA、完整事件／得分／共同 AGL，才是選候選的依據。

這些是下一步建議，並非本次發布已完成的實驗。
