# TRACELOG — 執行者交接紀錄

此檔是跨執行者的唯一真相來源。新執行者（含未來的 codex / opencode）請先讀這裡再動任何東西。

---

## 執行者沿革

| 期間 | 執行者 | 產出 | 狀態 |
|---|---|---|---|
| ~09/18 – 10/04 | OpenCode (space-bunny-free)，經 codex 協作 | `work/`、`lag/`、`dashboard.py`、`autopilot/`、`combat_v3/`、`combat_fix/`（RepairController，SHA `fff336a83896a977`） | 已凍結 |
| 10/05 – 10/14 | codex | `campaign_2026/` 全樹、`repair_v1` 凍結快照、`g_latch` 候選（`GGuardLatchBank80`）、291 個測試、6 場官方 Host 取證、`m2_regate` 之前的各種 gate | **額度用盡，10/14 停止** |
| 10/14 22:54 – | OpenCode (space-bunny-free)，直接執行 | `win/`（budget / notify / win_loop / ROADMAP_WIN / m2_regate / m3_mirror_league） | 進行中 |

---

## codex 停止時的狀態（交接要點）

**它做到的最有價值的事**（不要重做）：

1. **官方 Host 規則實測釘死**，這是整個專案唯一的硬事實：
   - `hp_initial = 180`，`score_kills = damage_ticks / 60`（誤差 0.0）
   - 攻擊累積 180 tick = 3.0 秒 = 擊殺
   - **真實攻擊錐是 1°，不是公告寫的 2°**（1.0° 預測 2.0833s vs 實際傷害 2.0833s，0 分歧；2.0° 有 638 分歧）
   - **累積式非連續**：forensics 有 4 段獨立傷害區間（11/61/39/14 tick）
   - 證據：`autopilot/combat_fix/official_validation/`、`autopilot/diagnostics/host_20261005_1847/metrics.json`
2. `RepairController`（SHA `fff336a83896a977`）—— 確定性引導器，機鼻角 113°→0.2°、最低高度 763m→4040m，**6/6 通過官方 Host**
3. `GGuardLatchBank80`（`experiments/g_latch_development/safe_candidate.py`）—— bank 80 + 8.5G/8.0G latch
4. 291 個測試案例，含 20 個純守衛程序 PID 歸屬測試
5. `delegations/` 記錄了它委外給 space-bunny-free 的 9 次任務與完整 audit trail

**它做錯或沒做完的事**：

1. **6/6 Host 全勝的意義被高估了**。Host 內建 P2 的 boot log 寫著
   `[BOOT] Random level-flight PID controller ready (SAC disabled)` —— 那是主辦方的練習靶機，不是對手。
   證據：`official_validation/*/p2_runtime_terminal.log` 第一行。
2. **`g_latch` 候選被錯誤否決**。否決理由是逐場最低高度退步，但官方優勢分公式**完全沒有高度項**。
   重算後候選最差高度 776.7m **高於** guide 的 772.3m。見 `win/m2_regate.json`。
3. **從未測過會反擊的對手**。`enemy_attack_seconds` 在所有歷史評估中都是 0.0。
   對手池聯賽（72 配對 / 144 場）設計好了但一次沒跑。
4. SAC 訓練線在 `futility_stop` 停在 100k/150k decisions，2M 步那條線（113 個 bundle、1.2GB）零戰鬥回報。

---

## 本輪（10/14 23:00）新增

| 檔案 | 用途 |
|---|---|
| `ROADMAP_WIN.md` | 奪冠策略。核心：累積制 doctrine、北極星 = 單場累積 tick |
| `win/budget.py` | RAM / 排定工時 / 供應商配額。**只警告，永遠不停** |
| `win/notify.py` | 事件帳本 + `needs_you.json` + 可選 email（gmail 未授權時降級） |
| `win/win_loop.py` | 實驗佇列編排器，RAM 過低則等待而非殺程序，24h 背書升級 |
| `win/m2_regate.py` | 零算力重算 M2 gate，**已通過** |
| `win/m3_mirror_league.py` | 鏡像聯賽 runner（新增會反擊的 P2） |

**凍結規則（不可違反）**：

- `repair_v1/` 的 9 個 SHA 由 `BASELINE.json` 釘死。`m3_mirror_league.py` 用**子類**加鏡像對手，
  **絕不修改** `repair_v1/` 任何檔案。
- `official_validation` 欄位在架構上恆為 `false`，不得為了好看改成 `true`。
- 種子分三類：`observed`（已用）、`holdout`（保留，候選凍結前不得執行）、`development`（本輪用）。
  讀了 holdout 就必須改標為 development。

---

## 使用者授權範圍（10/14 22:38）

- 「forget about the 5hr limit」→ 預算降級為 **warning only**；保留 24h 單一工作背書避免 FDM 真的卡死無人知。
- 「use opencode to do the job」→ 本機訓練不依賴任何供應商；`win_loop.py` 預留委外但目前無需。
- 「send me an email」→ **做不到**，gmail MCP 無 OAuth token。
  通知實際通道：`win/NOTICES/events.jsonl`、`win/needs_you.json`、本對話。
  要真的收 email，使用者必須先執行 `hermes mcp login gmail`（僅此一件需要使用者親自做的事）。
- 「change its worktime」→ codex 已額度用盡，執行權已移交 opencode。

## 停損條件

只有這三種情況會停下來找人：

1. 報名未送出（10/21 截止，`registration_latest.json: form_submitted=false`）
2. gmail 未授權 → 通知無法走 email
3. 需要第二台電腦 / LAN 驗證（比賽是兩台機對打，從未測過）

其餘全權處理。
