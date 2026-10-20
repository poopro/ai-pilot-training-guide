# 最新進度（10/18）

## 2026-10-18T10:50:20.986177+00:00 新17觀測×1bank小模型：3000decision完整訓練，尚未量測戰力

- 全fresh CPU SAC128×128，原13×3模型不相容，未帶舊actor/critic/optimizer/replay。原RepairController殘差API、72度/G/recover/trim/slew維持；每20個60Hz tick只更新一維bank，17特徵僅合法packet/私有自機counter/guard/clock。新reward為公告profile雙方advantage差增量/(10000/60)+真終局winner±180，cutoff不編勝方。
- 新模型完整3000decision/60000真FDM步/338梯度更新；actor SHA改變、model與replay3000重載精確，10組前置檢查及worker/verifier/實際parent均真0，phase {'PRECHECK': 0, 'WORKER': 0, 'VERIFIER': 0}。原900s總限、30s前測/780s learner/90s核對，實際200.515s；7原core身份已無或重用，來源XML/紅方模型不變。
- 實際到達4個排程cell、完整訓練回合3，最後partial見FINAL_REVIEW；不是完整聯賽/公平勝率。每tick計數及裁判、每decision特徵/reward、3000個decision首tick真blue act-command回放核對；其中1462個抽樣與同狀態neutral命令不同。訓練紀錄沒有全幀packet/紅controller回放或ACMI，不冒稱完整對戰審查。
- 藍峰值G 3.669220，零過9G；最低AGL 894.896m為本訓練樣本，沒有公平基準高度比較。訓練回合事件/得分不能當模型勝率。gate=learning_mechanics_verified_strength_unmeasured_no_promotion，未部署、尚無模型優勢證據。
- v1動態class來源反射失敗：precheck0/worker2/parent shell1、0decision/0記錄步（已FDM初始化）。v2修反射後900decision/18000步/75updates，在切換RuleFighter時因command-only API解包失敗，worker2/parent1；partial模型不晉級。v3只前測import package名錯誤真1、無learner/FDM/seedclaim。v4只修正該前測import，生產沿用v3已修正三對手API；實際三對手CPU接線測試通過才新fresh訓練。全部舊來源/失敗收據/原預留保留，不重跑原seed。
- 本日預留累計1.400000h（含上述四次各900s及既有0.4h，不退款），用量只讀一次UTC2026-10-18 10:31:11，較低93%，未用credits/reset。正式repair_guide與兩原模型保留；ASUS/LAN不是前置，無需本人操作。
- 下一項：依NEXT_EVALUATION_PLAN新立900s總/90s每worker/180s嚴格核對的6完整開發場，三對手各neutral-vs-learned同雙方initialSHA配對；新seed/來源模型凍結/獨立deadline/lock/STOP/資源。先看逐對score/event/命中/射程/前半球/共同AGL/最差case，再決定有無理由追加訓練。尚未實作/啟動該比較，不預設較強，不自動部署。

證據：E:\ai_pilot\campaign_2026\experiments\opponent_pool\bank_residual_train_v4\run_20261018_184640_29092b\VERIFICATION.json；E:\ai_pilot\campaign_2026\experiments\opponent_pool\bank_residual_train_v4\run_20261018_184640_29092b\FINAL_REVIEW.json；E:\ai_pilot\campaign_2026\experiments\opponent_pool\bank_residual_train_v4\run_20261018_184640_29092b\BUNDLE_MANIFEST.json；E:\ai_pilot\campaign_2026\experiments\opponent_pool\bank_residual_train_v4\run_20261018_184640_29092b\TERMINAL_AUDIT.json；E:\ai_pilot\campaign_2026\experiments\opponent_pool\bank_residual_train_v4\run_20261018_184640_29092b\NEXT_EVALUATION_PLAN.json。

最近完整公平對戰仍是far_speed原72 1勝1負、速度候選0勝2負/全0命中；本輪完成新訓練，尚未新增公平對戰結果。
