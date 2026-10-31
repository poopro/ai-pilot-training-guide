# 對手基準組（Benchmark）— Nailong Aerospace Research Group，2026-10-31

給隊友用來測自己的模型（例如微調後的 Korea V2）：同一批種子、同一套判定，對我們所有對手各打 N 局。
所有數字都來自本地判定程式（`campaign_2026/experiments/rules_v20261014/judge.py`，依 10/08 公告與 LINE 管理員答覆實作），**不是主辦方認證**。

## 1. 安裝

1. Python 3.10+：`pip install jsbsim numpy`（不需要 torch、不需要 GPU）。
2. 主辦方的 `AirCombat_Train_Test` 資料夾（每隊都有，**不在這個 repo**）：
   `set AIRCOMBAT_DIR=<路徑>\AirCombat_Train_Test`（Linux：`export AIRCOMBAT_DIR=...`）。
   **還要把 `jepa_brain/setup/combat_v3.zip` 解壓到 `AirCombat_Train_Test` 裡面**（變成 `AirCombat_Train_Test\combat_v3\`）。`combat_v3` 是我們 10/3 在官方資料夾裡寫的觀測／判定介面，主辦方資料包裡沒有；它會讀官方的 `envs/jsbsimEnv/jsbsimFdm.py` 和 `aircraft/`，所以必須放在官方資料夾裡。
3. 韓國隊模型（只有要用 `kr:`／`krl:` 時才需要；**權重不在這個 repo**，請自己下載原始 repo）：
   `git clone https://github.com/idearendil/2026_AI_Pilot_Challenge-1st_Solution`，然後
   `set KR_MODELS=<clone>\final_team_models`。
4. 在 `jepa_brain/` 底下執行。

## 2. 怎麼跑

```
python league2.py OUT.jsonl <藍方 arm> '<紅方1>;<紅方2>;...' <每個對手局數(6 的倍數)> <起始種子>
```

- 每局開局：同高度 10–20k ft、反向平行、側向 3000／6000／9000 ft、340 KCAS、敵機在左或右（6 種組合輪流）。
- 輸出每局一行 JSON：`event`（blue_kill／red_kill／timeout／collision／blue_crash…）、`winner`、`atk_b`／`atk_r`（錐內 tick）、`margin`、`min_agl_b`、`overg_b`。
- **比較兩個版本一定要用同一個起始種子**，只看「一方贏、另一方輸」的局。

### 測你自己微調的韓國型模型

把你的模型做成跟韓國隊一樣的資料夾（`model.pt`＋`claude_code/` 觀測程式，非 GRU），放到 `KR_MODELS` 底下，例如 `my_v3/`，然後當藍方：

```
python league2.py runs/my_v3_vs_pool.jsonl krl:my_v3 '<下面第 3 節的對手字串>' 6 8400000
```

- `krl:` = **合法觀測**：敵機姿態只用速度／加速度估計（跟比賽 Host 給的資料一致）。`kr:` = 直接讀敵機真實姿態（作弊版，只做研究）。
- 載入程式：`kr_red.py`（不用 torch 的安全 unpickler，只還原數字矩陣；4×21 bins argmax、10 Hz）。

## 3. 對手清單（紅方字串）

| 等級 | 紅方字串 | 是什麼 |
|---|---|---|
| ★★★★ 最強 | `krl:gylee_46k_headon`、`krl:junhwa_wide1_v2`、`krl:junhwa_exploiter_survive_v1`、`krl:gylee_20k`、`krl:junhwa_final`、`krl:gylee_69k` | 韓國 TOPGUN 2026 第一名隊伍的 PPO 模型（需 KR_MODELS） |
| ★★★ 規則式最強 | `arm=fin4:runs/tune05`、`arm=fin4:runs/tune04_fin12d`（T17） | 我們的收尾控制器（3D 升力向量瞄準＋迎頭靠右錯開＋低空拉起），調參第 5／第 4 輪 |
| ★★★ | `arm=tuned2f:aa_max=180:enter_deg=180:exit_deg=180:enter_m=3000:exit_m=3500:turn_cas=340:n_cap=8.0:merge_off_m=400:rec_v2=1` | F4R：唯一過官方 Host（F4，6/6 擊落）的版本＋低空拉起 |
| ★★★ 垂直機動 | `adv:t17vs_00` … `adv:t17vs_05`、`adv:t17vp_00` … `adv:t17vp_07` | 對抗搜尋找到的紅方：會 split-S、Immelmann、斜面環、zoom 爬升 |
| ★★★ 帶收尾 | `adv:t17fp_00` … `07`、`adv:t17fs_00` … `07` | 紅方也帶收尾控制器（fp 拿分型、fs 射擊型） |
| ★★ 急轉型 | `adv:fin1_00` … `07`、`adv:fin2_00` … `07`、`adv:f1s_0` … `3`、`adv:f2w80_00` … `05`、`adv:f4rs_00` … `05` | 坡度拉到 81–88°、被咬就急轉的追擊者 |
| ★★ 我們的舊版 | `arm=tuned2`、`arm=tuned2w:80` | 演化調參的追擊法（72°／80° 滾轉上限） |
| ★ 腳本 | `guide`（官方範例鏡像）、`lead`、`lag`、`level`、`weave`、`mix`、`breaker`、`defender`、`hturn`、`pp0` … `pp5` | 便宜的多樣性 |
| ★ SAC | `sacn:22400000` … `sacn:26400000` | 嵐用官方 train.py 練的 SAC（會從後方咬住）；需要 AirCombat_Train_Test/model 裡的存檔 |

建議的對手比例（拿來訓練時）：韓國模型＋自我對打約 60%、T17／tune05 約 20%、`adv:` 約 15%、腳本約 5%。

一組常用字串（22 種，跟下面的基準結果同一組）：

```
lead;level;weave;pp0;pp5;mix;breaker;defender;hturn;guide;lag;pp2;sacn:25600000;adv:fin1_01;adv:fin2_02;adv:fin2_04;adv:f2w80_00;adv:t17fp_00;adv:t17fs_00;adv:t17vs_04;adv:t17vp_03;arm=fin4:runs/tune04_fin12d;arm=tuned2
```

## 4. 已知基準結果（原始 jsonl 在 `runs/eval_fin/`）

| 藍方 | 對手 | 結果 |
|---|---|---|
| Korea V2（`krl:gylee_20k`） | 上面那組 22 種，各 6 局（`kv2_ours.jsonl`） | **127–0，擊落 127，被擊落 0**；擊落中位約 45 秒、最慢 196 秒；最低離地 508 m |
| Korea V2 | 其他韓國模型（`kv2_vs_kr.jsonl`，跑到一半容器重啟，共 57 局） | 44–13，擊落 9，被擊落 0；對 gylee_20k 自己 6–6 |
| T17 | 6 個韓國模型，合法觀測，各 12 局（`krl_T17.jsonl`） | 14–58；被擊落 44（20k 0–12、46k 0–12、exploiter 1–11、wide1 0–12、final 4–8、69k 9–3） |
| T17 | 我們的留出對手（不含韓國） | 309–3；最難 15 種 180–0 |

**要贏原版 Korea V2 才算進步**：新模型與 `krl:gylee_20k` 用同一個種子、同一組對手各打一次，比較勝場、擊落、被擊落。

## 5. 其他工具

- `acmi_export.py OUTDIR --blue <arm> --reds a,b --games 3`：輸出 Tacview 重播。
- `adv_search.py search --blue <arm> --red vert --obj shoot`：用 CMA-ES 找最能打敗某個藍方的紅方參數（結果存 `adv_pool/`）。
- `judge4.py`：共同留出判定。

## 6. 注意

- 韓國隊的權重沒有 license，這個 repo 不重新散布，只放連結與載入程式。
- 這裡的數字全部是本地模擬器；上場前一定要用官方 Host 實測。
