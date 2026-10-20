# 選項戰術員 × 你的 tuned 追擊：最終結果與建議（2026-10-19）

> 目標：2026 神盾盃 AI 飛行員擂台賽（11/07–08）。這份是 `flybrain_README.md` 6.15–6.22 的濃縮版，給賽前決策用。所有結果都是**本地 judge `line_20261014_1deg`**（非 Host 認證）、腳本 / 舊 checkpoint 對手；**沒有 Host 實機驗證**。

## 一句話

近距離才介入的「選項戰術員」疊在你的 tuned 追擊上，對腳本對手池從 158-58 變成 207–209 / 216（0 場被擊落），在 3 批沒用過的種子上都重現。但**多數勝場來自「近距離不要一直純 PURSUE」**（隨機戰術也有 141 / 162）；學習的貢獻在 lead 型對手、分差與「對手也會戰術」的對局；**果蠅連結體本身沒有獨立貢獻的證據**。

## 推薦

| | A. ridge v1（`opt_ridge:tuned`） | B. MLP v4（`opt_mlp:tuned`） |
|---|---|---|
| 腳本池 216 場（種子 1030000） | 209-7，分差 2,992 | 209-7，分差 4,154 |
| lead 型對手 | **22-2** | 18-6 |
| 自對戰（對會戰術的對手） | 被 MLP v3 剋（12-36）；對 v4 21-27 | 勝 v3 35-13、勝 ridge v3 34-14；對 ridge v1 27-21 |
| 模型大小 / 延遲 | 54×7 權重，0.25 ms | 約 4 萬權重，0.24 ms |

- **預設 A**：最簡單、沒有已知弱點。
- **對手會做戰術切換時改 B**（代價：lead 型少贏約 4 場 / 24）。
- BO3 輪與輪之間可換（建議，未驗證）：第一局 A，若看到對手在近距離持續切換戰術，第二局 B；遇到 SAC 25.6M 型遠距離逃離者兩者都沒有優勢，可回到 plain `tuned`。
- **果蠅 DN 版不建議上線**：總勝場同 A / B，但 lead 弱點可重現（15-9、2 場碰撞輸），還要 numba + 剪枝連結體 + 2–3 ms。

## 重要對照與修正

1. **隨機戰術對照**（近距離 15% 機率隨機挑 LEAD / BREAK_IN / LAG / LOW_YOYO 鎖 2 秒，不看任何狀態）：141-21，guide / lag 69-3。→ 我先前把鏡像局 24-0 歸功於「反事實標籤」說過頭了。學到的頭對隨機：逐場 13 對 3（MLP）、17 對 3（ridge）；lead 型隨機 6-12、學到的 15-3。
2. **對手也會戰術時**（頭對頭循環賽，凍結控制器 + shield 相同、只換頭，600 場）：MLP v3 69.8%、MLP v2a 63.5%、ridge v1 53.6%、ridge v3 52.1%、**隨機 10.9%**；plain tuned / base_t3 打戰術紅方 0-24。→ 腳本池太弱、會把頭的差別壓平；但頭與頭之間不是全序（v3 勝 ridge、v4 勝 v3、v4 ≈ ridge）。
3. **DN（果蠅）**：離線上沒有原始特徵以外的資訊；閉迴路總勝場同 ridge；SAC 25.6M 上三批都較好（17–18 勝 / 24；後兩批對 base_t3 逐場 13 對 2）但 lead 上三批都較差，兩者大致抵銷。
4. **第二輪 DAgger（自對戰 16 場 + lead 10 場，MLP roll-in）**：MLP v4 比 v3 強；**同一批標籤餵給 ridge 反而變差**（25-47）；ridge+MLP 平均沒有比較好；調高 tau 讓自對戰崩（17-7 → 1-23）。
5. **沒解決**：sac:25.6M（沒進步也沒退步）；lead 型對手上 MLP / DN 弱於 ridge。

## 檔案（`E:\ai_pilot\flybrain\`）

- `portable\fighter_opt.py`（單檔，numpy 即可）+ `portable\player_fighter_opt.py`：放在你的 `fighter.py` 旁邊，`--profile opt_ridge:tuned`（或 `opt_mlp:tuned`）。不覆蓋 `jepa_brain\` 任何檔案。
- 可攜版與 harness 逐場一致（ridge 12/12，MLP v4 18/18，用你 10/18 的 `fighter.py` 重跑），與你自己的 `fly_feat` 逐場一致（6/6，兩個獨立實作），平均每次 `act()` 0.25 ms；決策層任何例外都改飛 PURSUE、不會讓 player 崩潰。
- 重現：`run_*.sh`（每個評估的指令與種子）；彙整：`pair_report.py`、`explore\{c1,rr,rr2,m4,tau}_table.py`。

## 賽前待辦（依價值）

1. Host 實機驗證：先 shadow（只記錄戰術員會選什麼）→ 10 場實機；看延遲、`act()` 呼叫次數對 sim tick 比例、Host 攻擊 tick 判定是否和本地 judge 一致。
2. 通過後：在 campaign 凍結 sac5000 紅方上做 go / no-go 成對測試；用 `branch_labels.py --pilot tuned` 對你真正會打的對手補標，重訓（ridge 約 1 分鐘、MLP 約 3 分鐘）。
3. 不建議再投入：SAC 25.6M 遠距標籤、更複雜的頭、EMA 感覺通道、果蠅 + 原始特徵混合頭、調高 tau、ridge + MLP 平均。

## 紅線

沒有 Host 驗證與延遲量測之前，不要取代正式比賽用的控制器。
