# 四種凍結對手比較工具

## 目前狀態

工具已建立，11項離線必要檢查通過。尚未執行四對手FDM回合；不得寫成聯賽完成、穩定勝率或正式Host認證。來源/模型固定，現候選與凌晨新開局工具保持原樣。

## 比較設計

| 對手ID | 行為 |
|---|---|
| rule | 原RuleFighter，保持原設定 |
| rl | 原凍結SAC殘差模型與原PacketController |
| repair_guide | 原RepairController，無SAC殘差 |
| rule_bank60 | RuleFighter隔離副本，只把遠距追擊bank上限72降為60；近距、閃避、速度、高度邏輯不變 |

四對手×三距離×左右兩側×三種子=72配對；每配對guide/candidate兩臂，144完整場。候選仍是距離<1100m的bank72→80，其餘不變。左右開局不是官方P1/P2換邊。

## 啟動前必須完成

1. fresh_bank80新開局的COMPARISON實際退出0、verified_comparison=true、24/24與12對完整，metric/outcome_safety/per_opponent全部通過。
2. 在同run資料夾寫SAFETY_DECISION.json，包含comparison_sha256、review_complete=true、recommendation=expand_frozen_opponents，以及有依據的altitude_assessment與recovery_assessment。這是本地證據檢討，不要求使用者重複批准。若安全退步不可接受，不發出此建議。
3. 即時Codex兩窗口較低剩餘>=35%，觀察不超過10分鐘；當日先保守預留2h，所有嘗試都計入每日6h。日界線前不足2h不開跑。日期限10/13–11/3。
4. STOP不存在、單一運算程序、磁碟>=10GiB、RAM>=2GiB；PID/建立時間/命令核對，AccessDenied為未知。
5. 原142檔快照、POOL_FREEZE全部來源/XML/監督程式與紅方模型SHA核對。已看過/嘗試/保留種子均拒絕。

## 入口

```powershell
& 'C:\Users\USER\anaconda3\envs\F16_ai\python.exe' -B -X utf8 'E:\ai_pilot\campaign_2026\experiments\opponent_pool\launch_pool.py' --check-only
```

真正啟動由Codex讀即時用量後傳入--remaining-percent與--usage-epoch。不得手填過期數字、直呼worker或以改run重置預算。預設基礎seed2026102100，36個seed僅為新開發集；首次嘗試即記已用，無法當保留集。

每場150秒/18000個60Hz tick、全部2h硬限。只停止自己建立且身分確認的子程序；保存CSV/ACMI及完整性證據。不完整與逾時不列成功率，也不整批盲目重跑。

真正取得父程序exit0後才執行verify_pool.py --parent-exit-code 0。不得用狀態檔或benchmark_return_code替代實際退出。分析器核對144/144、72配對、初始SHA與對手初始RNG SHA一致、來源/模型、種子登記/每日預算、原始result/CSV/ACMI、四對手分組與逐配對退步。

完成後仍須檢討最差對手與高度/恢復，再凍結候選進入未見保留集、>=6官方Host回合、可離線套件及現場彩排。禁止自動替換正式部署。

## 已核對的範圍

11項檢查包含：完整平衡配對；不完整/錯初始/RNG/對手/seed/退出拒絕；原reset/metrics/timeout/summary AST不變；原候選bytes一致；rule變體除far bank常數外AST一致；真實控制器對既有合法26維觀測輸出一致且有限；2h與holdout閘門；新開局前置；AccessDenied未知；低用量拒絕；實際父子身分mock工作接受與錯預算/清單拒絕；安全決策僅接受對應SHA。

正向worker路徑測試使用mock，沒有FDM。真實原修正版控制器指令檢查沒有建立飛機。新增四對手成功FDM路徑與表現仍待實測。最初產生器縮排錯誤先被AST拒絕，修正並重新核對後才凍結，失敗未啟動任何模擬。
