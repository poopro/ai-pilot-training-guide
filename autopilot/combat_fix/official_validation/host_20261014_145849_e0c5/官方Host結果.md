# 官方公告版 Host 實測

我方 Player1 使用 repair_guide 純引導器，沒有 RL。官方 Host、Setting.txt 與控制器均未修改。

CSV：8,022 列；模擬時間 133.717 秒。完整五分鐘：False；Host 提前裁決：True。

| Host 原始欄位 | 我方 Player1 | 內建 Player2 |
| --- | ---: | ---: |
| hp | 180.000000 | 0.000000 |
| score_kills | 3.000000 | 0.000000 |
| advantage | 39138.331657 | 820.496264 |
| attack_advantage | 0.995576 | 0.000000 |
| position_advantage | 0.994680 | 0.000000 |
| gforce_overload | 0.000000 | 0.000000 |
| min_altitude_m | 5546.667090 | 5587.150843 |

Host winner 原值：`1.0`；保留原值，不擅自推定代碼。

這是官方提供的本機公告版 Host 實測；不是正式賽事認證，也不是固定測試集勝率。

score_kills 保留 Host 原始欄位數字；不把分數 3 解讀為擊落三架飛機。

核對項目：`{"finite": true, "strictly_increasing_sim_time": true, "full_round_or_host_early_adjudication": true, "player1_state2": true, "player1_moved": true}`。

原始 CSV、ACMI、程式 SHA256、Player／Host log 與 session.json 均保存在同資料夾。
