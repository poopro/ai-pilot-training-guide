# 10/17 最新方向：集中對戰程式與模型

## 使用者已確認

- 塔塔加未錄取，行程已不衝突；不再做競賽／塔塔加選擇、付款提醒。
- 現階段最需要的是能參賽的模型／規則程式；ASUS／LAN交接暫存，不作本地研究前置，不再要求ASUS自檢。
- 目標是提高11/7表現；10/19檢視戰力證據，10/20整理可執行候選及保留基準。尚無報名完成證據，報名事項另依原10/17、10/20提醒處理。

## 已驗證與目前界線

- portable Host v4固定同機6/6；不能推論未知隊伍勝率。
- 兩個凍結模型old5000、transfer10000都有真訓練／重載證據。18場完整開發比較中，新模型對部分鏡像開局變強，但丟掉rule一次擊落，mirror近距命中131→2，仍mixed、不自動晉級。正式基準repair_guide。
- 退步視窗已保存；首次command差異只有油門不是因果證明，也不意味戰術向量可當四控制residual。
- `diagnostics/frozen_sac_fdm_v1/run_20261017_063110_af2e25`：兩模型各2次同種子reset、每次300真60Hz步，共1200步；實際父／worker／verifier退出0，模型、來源、FDM XML固定、CSV等價JSONL與ACMI保存，首幀／實際sendAction／單次physics／judge／3Hz決策／cache／reset／saved-packet推論重播均通過。兩新開發seed2026310000/1，不是保留集或強弱比較。
- 此短測攻擊tick均0，非零counter的FDM路徑仍需後續實測；不是完整戰鬥／自我對戰訓練或勝率。最冷首次命令約36.53ms、該批暖推論最大約2.26ms，不能稱已保證網路60Hz最壞延遲。上場前需要在START前完成模型載入及初次推論準備。

## 研究取捨

規則追瞄／速度與高度管理、小型戰術模型、短期物理預測均可比較，以完整對戰結果選擇。混合架構是10/17給使用者的工程建議，不是已證明最強或使用者已確認的部署方案。LLM／JEPA暫無本專案戰力證據，保持低優先。

## 已完成的六場比較設計（執行結果見最新段落）

1. 使用剛驗證的frozen SAC紅方橋接，凍結紅方sac5000。將藍方零戰術StationController、old5000、transfer10000三者在同雙方initial SHA的新開發開局比較。零戰術StationController不是pure repair_guide，名稱不可混用。
2. 先做兩個新開發開局、一左一右，共6個完整回合；每場上限18000tick、獨立worker90秒、全批600秒硬限，唯一輸出、seedregistry、OSlock/STOP/獨立watchdog、source/XML/model SHA、RAM2GiB／disk10GiB門檻須先通過。新seed不能沿用本次介面seed；原完成18場與1200tick不重跑。
3. 報逐開局完整事件勝負、攻擊、被擊落／墜機／collision／過9G、score margin及共同曝光最低高度；另標明非零counter是否真的被觸發。任何partial保留，不拼批或補寫退出碼。
4. 根據完整回合最主要弱點，再選一個戰術維度作消融或單因素控制研究。先讀`m1_station.py`的映射，不從首次油門差異直接推導應固定油門或盲掃參數。
5. 有明確目標後才做有上限的新訓練；用混合腳本、歷史凍結及學習對手，完整評估通過後才擴開局、未見保留及必要Host確認。契約變更時不能假裝精確續用critic/optimizer/replay。

## 執行與交付

每次只推進一項具體、可檢討的研究；維持獨立硬時限與完整真退出，避免反覆只做文件或接口而不產生對戰證據。最終交付可執行候選、模型SHA、啟動方式及實測分對手結果。保留回退，不自動把開發候選換成正式部署。11/3 23:59後停止新研究型訓練，11/6 23:59停止研究排程。

舊`WIN_BY_1020.md`保留歷史；其塔塔加與ASUS優先條目已被本文件及最新人類指示取代。


## 10/17 09:53 最新：完整學習紅方比較與下一步


- 規則控制版（零戰術StationController）、5k模型、10k模型，在兩個新開發開局對同一凍結5k紅方，共6場、108,000個真實模擬步；每開局雙方initial SHA一致。這個規則版不是pure repair_guide。
- 三版本在各自同一開局內，18,000幀實際飛行命令與數值軌跡完全一致。模型確有輸出不同戰術，但本批沒有帶來控制或得分優勢。
- 六場雙方命中0、擊落0、墜機0、碰撞0、過9G 0；全為300秒時間到，紅方積分勝。三版本每版0勝/2負，分差兩開局分別-1.9914/-4.6112，不能當未知隊伍勝率。
- 最近距離分別1166.81m與1144.43m，均未進入攻擊距離152.4–914.4m。首要弱點是進入射程；裁切是否抹去戰術差異仍待追蹤，尚非根因定論。
- 六worker與模擬父程序實際0。原60秒核對器逾時退出1已保留；另立180秒離線審查契約，沿用不變的嚴格逐幀/全部模型決策/來源XML/CSV/ACMI核對，91.61秒完成、審查worker及guardian真0，verified_comparison=true/errors[]。未重跑任何對戰；17個原程序身分均已不在。
- 下一步：追蹤戰術→目標→命令的作用，再以新開局測一個控制因素；有改善證據後再訓練。本輪沒有新訓練，兩模型保留，正式基準仍repair_guide。
- 10/17競賽報名提醒已寄；尚無完成證據，原記錄截止10/21。

證據：research_latest.json；experiments/opponent_pool/frozen_sac_battle_v2/run_20261017_093943_16bee6/SAFETY_REVIEW.json；diagnostics/saved_sac_battle_audit_20261017_094917_10fc24/COMPARISON.json。

具體新研究計畫：`E:\ai_pilot\campaign_2026\experiments\opponent_pool\frozen_sac_battle_v2\run_20261017_093943_16bee6\NEXT_RESEARCH_PLAN.json`；尚未實作下一控制修正或啟動新訓練。原v1單場後處理超時失敗與v2原60秒verifier退出1均保留；不覆寫成成功。


## 10/17 12:30 最新裁切診斷（覆蓋先前根因仍待查）


- 離線完整追蹤六場已保存的108,000幀：戰術值有送進控制器，裁切前的轉彎計算也不同；但每一幀的轉彎目標都被限制在±72度，速度目標都被限制為290節。每個開局三版本的最終目標完全相同。
- 這說明這批軌跡的戰術差異在目標裁切處被抹去；不是只靠零命中猜原因。此診斷沒有重跑FDM、沒有新模型推論或訓練；內層command只用記錄器替代，不把記錄器回傳的舊命令冒充新控制重播。
- 診斷67.532秒完成，worker與父程序實際0、來源SHA固定、原PID/建立時間/命令身分已無；VERIFICATION通過。
- 先前六場完整對戰仍有效：三版本各0勝2負、皆時間到由紅方積分勝；雙方0命中/擊落/墜機/碰撞/過9G，最近距離1166.81/1144.43m，未進入攻擊距離。這不是未知隊伍勝率。
- 下一個待測假設：只降低藍方遠距轉彎目標上限72→60，嘗試改變持續繞圈的幾何關係。會先隔離來源，再用兩個新開局、baseline/candidate共4場完整比較；尚未實作或啟動，不能稱已改善。
- 正式基準repair_guide與兩個凍結模型保留，不盲續訓練、不自動部署。10/17報名提醒已寄，尚無報名完成證據。

最新診斷：diagnostics/sac_goal_projection_20261017_122745_b73993/VERIFICATION.json；下一步：同資料夾NEXT_EXPERIMENT.json。


## 2026-10-17T07:37:01.582851+00:00 最新開發比較


- 完整4場、72000模擬步、2個相同initial SHA配對；worker／父程序／獨立核對器實際0，來源/XML/模型/逐幀規則/紅方決策/目標裁切/CSV/ACMI核對通過。
- 唯一變更：藍方距離>914.4m時轉彎目標上限72→60，其餘目標、安全控制與對手不變；基準是零戰術StationController，非pure repair_guide。
- normal：基準timeout/blue、命中0；候選timeout/red、命中0；進入射程0→7604 tick，最近1256.99→455.91m，共同最低AGL差+159.53m，候選過9G 0tick。
- mirrored：基準timeout/red、命中0；候選timeout/red、命中0；進入射程0→7536 tick，最近1187.64→453.31m，共同最低AGL差+1009.26m，候選過9G 0tick。
- 決策：reject_promotion_position_score_regression。兩配對得分大幅退步，原本獲勝的開局變落敗，否決此候選晉級；射程改善不等於較強。下一步追蹤射程內不利朝向的控制時窗，不盲續訓練。
- 沒有新訓練，不自動部署；正式repair_guide及原兩模型保留。這是兩個開發開局，非未知隊伍勝率。
- v1初始化誤載同名candidate.py失敗已保留；v2以絕對路徑預先綁定唯一檔，cold import碰撞測試通過，使用全新種子，沒有重跑原失敗種子。
- 今日預留0.850000h，失敗預留不退款。

證據：E:\ai_pilot\campaign_2026\experiments\opponent_pool\far_bank60_v2\run_20261017_153047_104619\SAFETY_REVIEW.json



## 2026-10-17T10:39:31.099441+00:00 最新追瞄診斷與待測latch


- 已核對四條保存軌跡，共72,000幀；沒有新模擬或訓練。兩個bank60開局各13次轉彎目標反向，都與方位誤差跨越正負180度發生在同一幀；原72度版本各0次。
- 每個bank60開局有27次射程邊界切換，但僅2次反向落在邊界切換前後2秒。射程內方位誤差中位數約139度、目標方位移動約12.86/13.16度每秒，而我機轉向約6.23/5.88度每秒。
- 下一個待測假設：敵機經過正後方時暫時維持原轉向方向，進入前半球再解除。尚未實作、沒有閉迴路改善證據；須先測重置/安全/未觸發前完全相同，再作新開局完整比較。
- 機制試驗將比較latch60與已否決的unlatched60，只能判斷latch作用；仍需之後和原72度版本在相同開局比較，不能直接取代正式repair_guide。
- 原bank60四場退步結論不變；兩個凍結模型與正式基準保留，不盲續訓練或部署。
- v1正常側兩CSV寫完後因NumPy整數無法輸出JSON而退出1，原失敗保留。v2只投影剩餘鏡像兩條，並從原始packet獨立重算核對四條CSV；worker與parent實際0，沒有重跑對戰或正常側controller投影。

證據：diagnostics/pursuit_window_trace_v2_20261017_183554_46bebe/VERIFICATION.json；下一步同資料夾NEXT_HYPOTHESIS.json。


## 2026-10-17T12:50:51.108118+00:00 後半球方向保持：四場完整機制比較

- 假設與唯一改動：目標從正後方跨越±180度時保持原轉向方向，回到前半球解除；只改方向，原far60/near72幅度、速度/俯仰/rudder與內層安全/G/trim不改。零戰術StationController，不是pure repair_guide。
- 新種子2026310600/1，4/4完整、2個相同雙方initial SHA配對、72000真FDM步。四worker／模擬parent實際0；原verifier2／wrapper工具1，錯把ACMI地理緯度與packet地心緯度直接相等，原失敗與COMPARISON=false保留。另立180秒保存資料嚴格審查，按原wrapper與JSBSim WGS84座標轉換修正此檢查，沒有重跑FDM、沒有延長原600秒。新審查worker／guardian實際0，全部紅方模型決策、合法packet、逐幀裁判、CSV所有欄位及ACMI 0/20/terminal姿態核對通過。沒有新訓練。
- normal：unlatched60／latch60勝方 red／red，藍方分差 -17032.155→-22989.783；命中 0→0 tick，射程內敵在前半球 0→0 tick，共同最低AGL差 -385.854m。候選latch觸發1次／啟用14543tick，過9G 0tick。
- mirrored：unlatched60／latch60勝方 red／red，藍方分差 -15566.172→-32569.459；命中 0→0 tick，射程內敵在前半球 0→0 tick，共同最低AGL差 -22.428m。候選latch觸發1次／啟用14147tick，過9G 0tick。
- 決策：reject_latch_no_paired_score_improvement。這只比較已否決bank60與latch60，不能說勝過原72、正式repair_guide或專業隊伍。正式部署與兩凍結模型保留。
- 前置17項測試及3590/3973幀保存packet的真inner-command逐命令完全一致已通過。v1首case因NumPy bool_日誌序列化失敗，父工具退出1、worker2、CSV已有2物理tick，0完整場；原600秒及2026310500/1保留不重用。v2只把heading/body角度正規化Python float，控制AST除型別轉換相同；另外嚴格CSV verifier正確核對None寫成空欄的格式，不放寬任何數值/事件條件。
- 所有14個記錄身分已無，source144+23及本批檔/模型SHA固定。今日預留1.333333h，失敗與離線檢討均計入不退款。
- 下一步：先用本批保存packet分析首次latch前後與其後5/10/20/40秒的LOS/heading角速度、實際bank對目標、CAS/TAS與高度，分辨持續追不上、能量或內層限制造成；僅分析必要視窗，不重投影全72k或重跑四場，不再掃角度/盲續SAC。

證據：E:\ai_pilot\campaign_2026\experiments\opponent_pool\rear_latch60_v2\run_20261017_203915_d840e7\SAFETY_REVIEW.json；新獨立審查 E:\ai_pilot\campaign_2026\diagnostics\saved_latch_audit_v1_20261017_204803_78cf4a\COMPARISON.json；原失敗 E:\ai_pilot\campaign_2026\experiments\opponent_pool\rear_latch60_v2\run_20261017_203915_d840e7\COMPARISON.json。


## 2026-10-17T13:41:23.570704+00:00 保存視窗：追擊目標與實際執行核對

- 只分析四條既有軌跡各首次差異前5秒至後40秒，合計10,800列；沒有新FDM、模型推論、controller投影、訓練或seed claim。沒有重跑四場或全72,000幀控制器追蹤。
- 兩候選觸發後合計4,800列：logged guard、8.5G輸入、失速/能量保護條件及滿油門均0；各候選後續視窗的傾角追蹤誤差中位數都小於2度，速度目標都是290節，目標仍未回到前半球。
- normal_latch60_2026310600：觸發後20–40秒，傾角追蹤誤差中位數1.400度；速度目標290節、實際CAS中位數290.796節、絕對速度誤差中位數0.796節；方位誤差仍154.83度。
- mirrored_latch60_2026310601：觸發後20–40秒，傾角追蹤誤差中位數1.727度；速度目標290節、實際CAS中位數289.728節、絕對速度誤差中位數0.474節；方位誤差仍158.54度。
- 本地推論：這些視窗不支持「安全層擋住轉向」或「已滿油門卻無法加速」作為主要解釋。機體有跟到指定目標；應檢查追擊幾何與距離切換的速度目標。這不是完整根因證明，也沒有證明加速會贏。
- 第一階段CSV回讀不是獨立數學審查；另立120秒NumPy unwrap差分、向量化合法座標幾何、fps→節與關鍵中位數獨立核對10,800列，實際worker/guardian皆0。提取8.016秒、審查6.281秒，原120+120秒預留皆計入不退款；今日預留1.400000h。6個新記錄原core身分已無，來源/XML/模型固定。
- 具體下一假設（尚未實作/啟動）：回到原未latch的72度StationController，只移除距離>914.4m且大方位誤差時的290節速度頂限；保留260–450節總界限與原安全/轉向/俯仰等。先隔離與保存packet檢查，再新開局同initial SHA四場比較；速度增加可能惡化轉彎，沒有預設會成功。這是新因子，不是重跑已否決latch或掃下一bank角度。
- 原latch四場仍否決、不部署；正式repair_guide與原模型保留。10/17報名提醒不重寄；目前無需本人操作。

證據：E:\ai_pilot\campaign_2026\diagnostics\latch_window_v1_20261017_213638_941961\FINDINGS.json；E:\ai_pilot\campaign_2026\diagnostics\latch_window_audit_v1_20261017_213931_a2c1a1\VERIFICATION.json；下一步：E:\ai_pilot\campaign_2026\diagnostics\latch_window_v1_20261017_213638_941961\NEXT_HYPOTHESIS.json。


## 2026-10-17T16:40:35.361014+00:00 遠距速度上限新分支準備，等待記憶體

- 已隔離建立far_speed_v1：僅在距離>914.4m、|heading error|>45時移除290節速度頂限；原未latch的72度轉向、俯仰/rudder、260–450節總界限及內層安全不改。原來源及已否決分支未改。
- 已完成5檔純語法編譯與140個純函式邊界案例（工具eaee28真0）。完整cold-import、真StationController保存packet重播尚未通過；這些純靜態結果不是新FDM/戰力證據。
- full precheck工具ec52dc真1：資源閘門在建立run/預留/child/seedclaim之前拒絕。16:37:59UTC可用RAM1.434GiB、16:39:25UTC1.358GiB，低於既有2GiB門檻；後次CPU77.9%、disk180.345GiB。GPU使用為其他活動，本工作CPU-only，不停止無關程序或降低門檻。
- 無新FDM、模型推論、訓練、seed claim或研究預留；10/17的1.4h歷史帳目保留。規劃seed2026310700/1目前registry碰撞[]，尚未claimed，下一次仍須重查。
- 下一輪：資源恢復後先用120秒獨立guardian執行完整前測，父/worker真0及VERIFICATION通過才凍結新來源、4場新配對，90秒/worker全600秒含120秒核對。準備檔的FDM_launch_allowed=false不能當許可；不得跳過前測。原正式repair_guide不變，暫無需本人操作。

入口：E:\ai_pilot\campaign_2026\experiments\opponent_pool\far_speed_v1\PREPARATION.json；資源收據：E:\ai_pilot\campaign_2026\experiments\opponent_pool\far_speed_v1\PREFLIGHT_RESOURCE_WAIT_20261018.json。


## 2026-10-17T19:36:58.604800+00:00 遠距速度頂限單因素：四場完整開發比較

- 資源已自然恢復；未停止無關程式、未降低RAM2GiB閘門。16項前置檢查與兩原72保存開局各首300幀的真inner-command baseline重現通過，父/worker真0，11.282秒；候選只改速度目標600幀，不是對戰證據。
- 唯一因素：移除距離>914.4m且|heading error|>45時290節速度頂限，保留260–450節總界限、原未latch bank72/俯仰/rudder/安全G/trim/slew。零戰術StationController基準，不是pure repair_guide。
- 全新seed2026310700/1，4/4完整／2同雙方initialSHA配對／72000真FDM步，固定sac5000紅方。parent、四worker、strict verifier、locked wrapper與實際工具退出皆0，source/XML/model/runtime module/逐幀judge/紅方推論/目標映射/CSV全欄及ACMI核對通過；原90s/worker、600s全批與120s核對上限不延長。
- normal：原72／移除速度頂限勝方 red／red；藍分差 -5.622→-5279.894，命中 0→0 tick，射程內 0→0 tick，前半球射程 0→0 tick，共同最低AGL差 +5.793m；候選過9G 0tick、死亡/墜機/collision 0/0/0，首次真命令差異tick1。
- mirrored：原72／移除速度頂限勝方 blue／red；藍分差 8.363→-5017.320，命中 0→0 tick，射程內 0→0 tick，前半球射程 0→0 tick，共同最低AGL差 +640.836m；候選過9G 0tick、死亡/墜機/collision 0/0/0，首次真命令差異tick1。
- 決策：reject_position_score_regression。逐開局取捨保留，不用平均掩蓋；只是兩個開發開局、不是保留集或未知隊伍勝率。沒有新訓練，不部署，正式repair_guide與兩原模型保留。
- 新日預留0.200000h，昨日1.4h及歷史失敗不退款。14個記錄原core身分已無或已重用，不清理重用PID。
- 下一步：否決本速度候選，使用保存首次命令差異與最差case分析相對航跡/瞄準，先形成一個可檢驗假設；不重跑本批、不掃下一速度或盲續SAC。

證據：E:\ai_pilot\campaign_2026\experiments\opponent_pool\far_speed_v1\run_20261018_033053_98bc0f\COMPARISON.json；E:\ai_pilot\campaign_2026\experiments\opponent_pool\far_speed_v1\run_20261018_033053_98bc0f\SAFETY_REVIEW.json；E:\ai_pilot\campaign_2026\experiments\opponent_pool\far_speed_v1\run_20261018_033053_98bc0f\TERMINAL_AUDIT.json。


## 2026-10-17T22:39:18.301151+00:00 遠距速度候選的保存窗口診斷

- 新獨立120s契約/OSlock/STOP/資源與來源模型XML檢查，四條保存軌跡只計算8101個不重複窗口列；0–10s、240–260s及最近距離±5s（終局/首幀會截斷）。標量公式與同worker獨立NumPy幾何/速度/角速度核對通過。worker/guardian實際0，11.172s；3原core身份已無，無新FDM、act/controller投影、模型推論、訓練或seedclaim。
- 兩加速候選後期各1200/1200列raw speed超450，raw中位532.026/547.670kt；實際CAS444.092/450.715、目標450。guard/8.5G輸入0，bank跟蹤中位誤差1.892/2.333度。窗口不支持「完全沒有套用速度/傾角」解釋。
- 同240–260s原72航向角速度6.576/7.155deg/s，候選4.837/4.939；候選heading error139.186/153.516deg。原72各最近距離窗口LOS13.126/14.000deg/s高於自己航向6.632/7.162deg/s。此為保存軌跡局部證據，不把單項當完整因果。
- 敌等效CAS只由ENEMY6地速proxy乘自己CAS/TAS比值，不是敵真CAS/TAS；raw項中位數不可以當逐列加法等式。HSL pre與AGL post分開。候選normal最近在終局、mirror最近在首幀，窗口截斷明標。
- 決策：加速候選仍reject_position_score_regression；無新戰力或勝率，正式repair_guide與兩模型保留。下一個可檢驗假設是「純repair_guide是否比StationController追擊教義更有效」，先比較真實既有基準，不再盲掃速度/bank。這是控制器家族一因素比較，不能把之後差異歸因某一行；尚未實作runner/前測/選seed/開FDM。
- 新日預留0.233333h（新增120秒），歷史預留不退款。用量真UTC2026-10-17 22:33:58，較低剩餘96%，無credits/reset使用。

證據：E:\ai_pilot\campaign_2026\diagnostics\far_speed_window_v1_20261018_063707_c7e30d\ANALYSIS.json；E:\ai_pilot\campaign_2026\diagnostics\far_speed_window_v1_20261018_063707_c7e30d\VERIFICATION.json；E:\ai_pilot\campaign_2026\diagnostics\far_speed_window_v1_20261018_063707_c7e30d\FINDINGS.json；E:\ai_pilot\campaign_2026\diagnostics\far_speed_window_v1_20261018_063707_c7e30d\NEXT_HYPOTHESIS.json。


## 2026-10-18T01:33:45.464497+00:00 規則家族真接線及有界控制差異檢查

- 新隔離rule_family_v1/policy.py解析到原repair_v1/controller.py的RepairController.act及原m1_station.StationController.act；兩者command仍為原RepairController.command，實際class/MRO/檔路徑SHA齊全。藍只收OWN26，明確residual=None，任何非零/錯shape殘差或非零tactic拒絕；沒有改正式來源/模型。
- 兩個保存開局各首300packet，12組真act/command、baseline saved exact、pure direct-source exact、完整prefix reset重現、STARTfalse不動狀態與合成安全parity檢查通過。parent/worker真0，14.547秒，非FDM/戰力。
- 首300兩版命令差異均0，因此另立120s activation契約，先重建必要600歷史幀，再只搜索新增6600保存幀至各3600tick/60s即止；未做完整72k/108k投影。兩版逐幀requested goals、真command輸出與guard完全相同，兩開局各prefix SHA相同、首次差異皆null。parent/worker真0，66.359秒；原三百前測未重跑湊成功數。這是保存共同輸入的反事實controller輸出，不是新FDM送出命令。
- 決策：不啟動目前四場家族替換比較，先確保候選能實際影響操控；不能把前60s等價推到全300s/所有開局。下一個假設是凍結原RepairController既有bank-only residual介面是否能在不改限制/安全的條件下改變真輸出；先neutral exact與±1 API邊界/獨立狀態測試，非掃bank參數。尚未實作，沒有新訓練/模型推論/FDM/seedclaim。
- 舊3維tactical模型不直接當新bank residual、不得沿用critic/optimizer/replay或宣稱精確續訓。control authority通過也不是戰力或閉環9G安全，仍須下一獨立契約。正式repair_guide與兩凍結模型保留，不部署。
- 兩次各120s預留保留，今日合計0.300000h，昨日/失敗帳目不退款；6個記錄原core身分已無或重用，不碰重用PID。用量真UTC2026-10-18 01:26:48，較低85%，無credits/reset使用。

證據：E:\ai_pilot\campaign_2026\diagnostics\rule_family_precheck_v1_20261018_092908_52c797\VERIFICATION.json；E:\ai_pilot\campaign_2026\diagnostics\rule_family_activation_v1_20261018_093119_cda2d7\VERIFICATION.json；E:\ai_pilot\campaign_2026\diagnostics\rule_family_activation_v1_20261018_093119_cda2d7\FINDINGS.json；E:\ai_pilot\campaign_2026\diagnostics\rule_family_activation_v1_20261018_093119_cda2d7\NEXT_RESEARCH_PLAN.json。


## 2026-10-18T04:41:17.423521+00:00 原bank residual有效操控權驗證

- 新獨立120s/OSlock/STOP/資源/source/XML/model/保存artifact SHA閘門；兩保存前綴各300packet，共600唯一輸入、1800個±1/0 API替代列。每個替代由同一neutral歷史act前clone獨立settings/last/積分狀態，直接原RepairController.act與command；沒有改rule_family policy或正式來源。
- neutral0逐列精確等於None及保存原command。normal+1、mirror-1（朝減小bank幅度）使目標72→64，各300個目標變更、285個副翼輸出差異，首次差異皆保存tick16；相反方向各300次被原72界限裁掉。原動態限幅取自凍結source，未新增控制數字或掃角度；不是永久bank64飛行候選。
- 前15幀目標有變但輸出被既有aileron clipping遮住，其中8亦有slew，重疊不相加。原aileron clip/slew另以標量公式核對。其他三個命令通道與pitch/speed/rudder目標完全相同。4非法輸入與9合成安全替代核對通過；8.6G時guard布林false不代表原G elevator limiter沒作用，不能當閉環9G安全。
- worker/guardian實際0，6.656s（7ad0ae）；3原core身分已無，無新FDM、模型推論、訓練或seedclaim。far8degree分支有保存實例，near2.5僅source讀出不當近距飛行證據。
- 決策：有效操控權這個介面前提已成立，沒有新戰力/勝率。下一項新bank-only wrapper與實際60Hz接線短FDM：原RepairController，直接RepairDuel.step四維residual，不走要求3tactics/set_tactical的TacticalDuel.step；新unused seed、兩fresh reset各300tick、neutral/預定API序列，同initialSHA及前100幀一致，240s總/90s worker/60s核對。新runner/contract/test/verifier尚未實作，不能直接啟動。不是學習戰術/完整對戰，通過後才考慮新訓練契約，舊3tactic actor不轉名或帶critic/replay假續訓。
- 今日預留0.333333h，原120s預留不退款；用量UTC2026-10-18 04:37:04較低96%，無credits/reset。正式repair_guide與兩模型保留，不部署。原家族前60s命令等價及四場比較暫緩狀態保留，不能擴稱全300s等價。

證據：E:\ai_pilot\campaign_2026\diagnostics\bank_authority_v1_20261018_123907_985ac0\VERIFICATION.json；E:\ai_pilot\campaign_2026\diagnostics\bank_authority_v1_20261018_123907_985ac0\AUTHORITY.csv；E:\ai_pilot\campaign_2026\diagnostics\bank_authority_v1_20261018_123907_985ac0\FINDINGS.json；E:\ai_pilot\campaign_2026\diagnostics\bank_authority_v1_20261018_123907_985ac0\NEXT_RESEARCH_PLAN.json。


## 2026-10-18T07:39:30.226845+00:00 bank-only真60Hz介面：600步完整驗證

- 全新獨立branch bank_residual_fdm_v1，原RepairController/紅方adapter/model/XML未改。7組前置mapping/時鐘/neutral回退/實際source檢查0後才claim新開局seed2026310800，兩fresh reset各300tick共600真FDM。不是兩場完整戰鬥，兩個5s cutoff皆ongoing/無勝方。
- 使用原RepairDuel.step四維residual，一維bank映射[bank,0,0,0]，每20tick持有；不走3tactics/set_tactical。neutral全0與預定API序列0→-1→+1（100/200completed ticks切換）。同雙方initialSHA、前100個pre/post packet與實際藍紅command完全一致；首次真sent blue command差異201、首次physics packet差異202，非保存反事實結果。
- 每tick一act/command/send/physics/judge、紅completed_tick/privatecounter/3Hz模型、完整藍act-command與紅actor-controller回放、事件/分數、CSV全欄/ACMI WGS84/來源XML/model均嚴格通過，VERIFICATION true/errors[]。
- 藍峰G neutral2.736380／exercise2.493242，紅2.748547／2.750228；兩次皆零命中/過9G。此為5s接線及有限動態安全觀察，不是戰力/長時安全/勝率，預定±1不是bank64戰術成功。
- precheck/worker/verifier與實際parent真0；各phase {'PRECHECK': 0, 'WORKER': 0, 'VERIFIER': 0}，原30s/90s/60s均受獨立240s總限約束，實際42.125s（39687/d3e15a）。7原core身份已無或重用，source固定，不碰重用PID。240s預留保留，今日合計0.400000h，seed已consumed不重跑。
- 下一項：新fresh CPU128x128 SAC、17合法觀測×1bank action，最多3000decision/60000tick，規劃單獨900s含780s learner/90s核對；先實作及測試features/neutral/action/時鐘/reset/私counter/明確judge reward與三對手輪替，再新source/seedpool/OSlock/STOP/資源/watchdog才可啟動。新模型/契約尚未實作，不當已訓練；舊13×3 actor不相容，actor/critic/optimizer/replay全部fresh，不能假續訓。訓練後另凍結完整配對才能判戰力。
- 正式repair_guide及兩原模型保留，不部署、不放寬9G、不盲續舊SAC。真用量UTC2026-10-18 07:29:14較低89%，未用credits/reset。ASUS/LAN不作前置，本輪無需本人操作。

證據：E:\ai_pilot\campaign_2026\experiments\opponent_pool\bank_residual_fdm_v1\run_20261018_153511_6fb16a\VERIFICATION.json；E:\ai_pilot\campaign_2026\experiments\opponent_pool\bank_residual_fdm_v1\run_20261018_153511_6fb16a\SAFETY_REVIEW.json；E:\ai_pilot\campaign_2026\experiments\opponent_pool\bank_residual_fdm_v1\run_20261018_153511_6fb16a\TERMINAL_AUDIT.json；E:\ai_pilot\campaign_2026\experiments\opponent_pool\bank_residual_fdm_v1\run_20261018_153511_6fb16a\NEXT_RESEARCH_PLAN.json。


## 2026-10-18T10:50:20.986177+00:00 新17觀測×1bank小模型：3000decision完整訓練，尚未量測戰力

- 全fresh CPU SAC128×128，原13×3模型不相容，未帶舊actor/critic/optimizer/replay。原RepairController殘差API、72度/G/recover/trim/slew維持；每20個60Hz tick只更新一維bank，17特徵僅合法packet/私有自機counter/guard/clock。新reward為公告profile雙方advantage差增量/(10000/60)+真終局winner±180，cutoff不編勝方。
- 新模型完整3000decision/60000真FDM步/338梯度更新；actor SHA改變、model與replay3000重載精確，10組前置檢查及worker/verifier/實際parent均真0，phase {'PRECHECK': 0, 'WORKER': 0, 'VERIFIER': 0}。原900s總限、30s前測/780s learner/90s核對，實際200.515s；7原core身份已無或重用，來源XML/紅方模型不變。
- 實際到達4個排程cell、完整訓練回合3，最後partial見FINAL_REVIEW；不是完整聯賽/公平勝率。每tick計數及裁判、每decision特徵/reward、3000個decision首tick真blue act-command回放核對；其中1462個抽樣與同狀態neutral命令不同。訓練紀錄沒有全幀packet/紅controller回放或ACMI，不冒稱完整對戰審查。
- 藍峰值G 3.669220，零過9G；最低AGL 894.896m為本訓練樣本，沒有公平基準高度比較。訓練回合事件/得分不能當模型勝率。gate=learning_mechanics_verified_strength_unmeasured_no_promotion，未部署、尚無模型優勢證據。
- v1動態class來源反射失敗：precheck0/worker2/parent shell1、0decision/0記錄步（已FDM初始化）。v2修反射後900decision/18000步/75updates，在切換RuleFighter時因command-only API解包失敗，worker2/parent1；partial模型不晉級。v3只前測import package名錯誤真1、無learner/FDM/seedclaim。v4只修正該前測import，生產沿用v3已修正三對手API；實際三對手CPU接線測試通過才新fresh訓練。全部舊來源/失敗收據/原預留保留，不重跑原seed。
- 本日預留累計1.400000h（含上述四次各900s及既有0.4h，不退款），用量只讀一次UTC2026-10-18 10:31:11，較低93%，未用credits/reset。正式repair_guide與兩原模型保留；ASUS/LAN不是前置，無需本人操作。
- 下一項：依NEXT_EVALUATION_PLAN新立900s總/90s每worker/180s嚴格核對的6完整開發場，三對手各neutral-vs-learned同雙方initialSHA配對；新seed/來源模型凍結/獨立deadline/lock/STOP/資源。先看逐對score/event/命中/射程/前半球/共同AGL/最差case，再決定有無理由追加訓練。尚未實作/啟動該比較，不預設較強，不自動部署。

證據：E:\ai_pilot\campaign_2026\experiments\opponent_pool\bank_residual_train_v4\run_20261018_184640_29092b\VERIFICATION.json；E:\ai_pilot\campaign_2026\experiments\opponent_pool\bank_residual_train_v4\run_20261018_184640_29092b\FINAL_REVIEW.json；E:\ai_pilot\campaign_2026\experiments\opponent_pool\bank_residual_train_v4\run_20261018_184640_29092b\BUNDLE_MANIFEST.json；E:\ai_pilot\campaign_2026\experiments\opponent_pool\bank_residual_train_v4\run_20261018_184640_29092b\TERMINAL_AUDIT.json；E:\ai_pilot\campaign_2026\experiments\opponent_pool\bank_residual_train_v4\run_20261018_184640_29092b\NEXT_EVALUATION_PLAN.json。
