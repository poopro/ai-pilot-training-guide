# Fighter 套件(官方可攜 Player + fighter.py)

以官方 repair_guide 可攜套件為底,新增啟動檔,**每一局開始前雙擊其中一個**(Player 每回合重新啟動,跟官方一樣):

| 啟動檔 | 設定 | 用途 |
|---|---|---|
| `啟動_tuned2.cmd` | 第二輪調參追擊 + 碰撞盾 v3 | **預設上場版本** |
| `啟動_tuned.cmd` | 第一輪調參追擊 + 碰撞盾 v3 | 次選(tuned2 出問題時) |
| `啟動_base_t3.cmd` | 原版 repair_guide 追擊 + 碰撞盾 v3 | 備用(對 lag 型對手 tuned2 / tuned 較弱時) |
| `啟動_tuned_open9.cmd` | tuned + 敵機在左側時開局先轉離 9 秒 | 僅在被 SAC 型尾追者壓制時的第二套設定 |
| `重連_tuned2_僅限回合進行中.cmd` / `重連_tuned_…` / `重連_base_t3_…` | 同上,但一啟動就送 state = 2 | **只有**回合進行中程式當掉、要重連時用;回合開始前不要用 |
| `啟動Player.cmd`(官方原檔) | 原版 repair_guide,無盾 | 最後保底 |

- 網路設定仍然是 `network.json`(官方原檔,未改動)。
- 每個啟動檔先跑 `tools/self_check_fighter.py`:官方完整性檢查 + 新增檔案 SHA256 + 所有設定的合成觀測冒煙測試;失敗就不會啟動 Player。
- 新增檔案只有:`policy/fighter.py`、`tools/player_fighter.py`、`tools/self_check_fighter.py`、`fighter_manifest.json`、各 .cmd、本說明。官方檔案一個位元都沒改。
- `player_fighter.py` 與官方 `player.py` 只差 6 處(匯入 fighter、新增 `--profile` 與 `--resume`、建立控制器、`--resume` 時直接送 state = 2、啟動訊息)。
- 本地研究結果(非 Host 認證,種子 1300000):對官方範例鏡像 tuned2 48-0、tuned 33-15、base_t3 20-28;對 lag 型 base_t3 44-4 最好、tuned2 39-9、tuned 38-10。上場前務必在官方 Host 實測至少一輪。
