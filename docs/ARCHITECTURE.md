# 架構與分工對照

| 路徑 | 內容 | 如何理解 |
|---|---|---|
| `campaign_2026/repair_v1` | 原修復控制器、安全限制、評估及 Player | campaign 保留基準；維持可回退 |
| `campaign_2026/experiments/rules_v20261014` | 具名本地規則與 judge | LINE 1 度／AGL／right_bin 是研究 profile，不等於正式 Host 認證 |
| `campaign_2026/experiments/opponent_pool` | 凍結對手、完整配對、bank 殘差訓練與核對器 | run 內的 CONTRACT、exit、VERIFICATION／COMPARISON 才界定證據 |
| `campaign_2026/diagnostics` | 保存軌跡診斷、獨立保存資料審查、Host 監督 | 離線重算不算新對戰；歷史失敗保留 |
| `jepa_brain` | 物理 arena、規則／BFM 調參、早期預測網路、對手池 | 資料夾名不代表 JEPA 已勝過規則 |
| `jepa_brain/portable` | fighter、player、NumPy 戰術選擇移植與封裝工具 | 依賴原取得的主辦方介面；不是獨立官方套件 |
| `flybrain` | Claude 的連結體研究、反事實分支標籤、ridge／MLP 戰術選擇 | 連結體沒有獨立增益證據；ridge 與 MLP 是候選 |
| `flybrain/ro`、`labels`、`runs*` | 各版本權重、標籤、實驗逐場結果 | 不能混用訓練、選模、確認或自對戰樣本 |
| `autopilot` | 較早期控制、對手研究與監督工具 | 歷史上下文，未因此成為新推薦版本 |
| `early_workspace` | 更早的資料收集、穩定模型、trainer 與原型 | 舊 action／reward 語意不保證與新介面相容 |
| `host_test_20261019` | 已保存的 Host 測試工具／紀錄（經公開清理） | 連線、安全、正式勝負、對手強度需分開 |
| `project_tools` | 本地 dashboard 等工具 | 供理解監督與入口，不代表已部署服務 |

## 兩個不同的學習介面

- 舊模型：13 個觀測、3 維 tactical 語意。
- bank17：17 個合法觀測、1 維 bank action，映射成原控制器 `[bank,0,0,0]` residual，每 20 個物理 tick 更新。

新 bank17 的 actor、critic、optimizer、replay 都是 fresh。不能把舊 13×3 模型改名為新模型，或稱為精確續訓。

## Claude 候選的控制鏈

合法 packet → 原始特徵與 EMA → ridge／MLP 選項決策 → 有限戰術與持有時間 → fighter 規則控制與安全層 → command。

`opt_ridge:tuned` 與 `opt_mlp:tuned` 的選項頭不同；不是 campaign bank residual 的一行替換。LEAD／BREAK 等戰術的 bank 契約亦需個別核對，不可把不同上限下的結果稱為單因素消融。
