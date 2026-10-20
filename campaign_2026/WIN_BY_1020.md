> 10/17 最新人類指示：塔塔加未錄取，已無行程衝突；主力集中模型／規則對戰表現。ASUS/LAN暫存，不是本地研究前置。10/19改為模型進度檢視，10/20整理可執行候選。以 `RACE_FOCUS_20261017.md` 與最新research pointer為準；以下舊塔塔加決策與ASUS優先順序只作歷史，不再執行。

# 10/20 前可穩定參賽推進方案

## 目標與決策日期

- 10/20 前把系統推到「能穩定啟動、連線、完成官方 Host 回合、保存可回退版本」；10/19 晚間依證據決定競賽或塔塔加，10/20 處理付款及必要人工步驟。
- 最終目標仍是提高奪冠機會，但所有勝率說法都必須來自完整、公平、固定來源的比較。
- 正式部署目前仍是 `repair_guide`。bank80 因新開局出現 1 個 60 Hz tick 過 9G，維持拒絕升級。

## 執行原則

- Codex 五小時與每週額度只作警告，不再作研究停止門檻。較低剩餘值 <=10% 時記錄警告，將可由文字、程式審查與報告完成的工作交給已驗證免費的 `opencode/space-bunny-free#max`。
- OpenCode 仍只能使用 `opencode_task.py`，每次確認 input/output/cache 費用都是 0；只可外傳使用者已授權的 `controller.py`、`env.py`、`interface.py`，不得傳遙測、其他來源、個資或秘密。
- 本地模擬不因 Codex 額度停擺，但一次只執行一個 learner／研究評估。每個 run 必須有 STOP、PID／建立時間／命令身分、來源 SHA、資源門檻、硬性 wall deadline 與可回復的正式基線。
- 10/13 已發生的 6.5676 小時帳目不刪除或退款；新的運算從下一個台灣日獨立登記。原每日 6 小時作警告與規劃欄，不再單獨阻止有明確假設及硬時限的研究，但禁止無上限、無比較設計或盲目掃參數。
- 10/19 晚間做競賽／塔塔加 go/no-go；10/20 完成塔塔加繳費決定與競賽報名必要人工步驟；AI 飛行員官網截止仍是 10/21。

## 優先順序

### 10/14 已完成與正在補足

- 舊環境 repair_guide 固定來源官方 Host 六場已完整通過，六場 P1勝、零過G；不等於封裝套件、LAN或未知參賽隊伍勝率。
- G latch 新開發24場已核對實際退出0、12配對、149來源/初始/紅方/逐tick與POST_AUDIT：候選3擊落對原1，rule3/6對1/6，RL各0/6，無死亡/墜機/過G。五個高度退步、最差低319m尚需方法檢討，正式仍repair_guide。
- 對手v5短測已完整24案/12左右配對/7200tick，含6個guide自我對戰；所有真退出與接口/CSV/ACMI核對通過。每場僅5秒，完整戰鬥聯賽仍待驗證；原partial與修復失敗種子/預留保留。
- portable v1套件實際連線完成103.767s的P1原始獲勝回合，但P2收據schema與cached子孫捕捉未通過，collector/guard真退出2，不計套件6場。v2修復只在準備且協作額度中斷，不能稱已就緒；原2115檔、ZIP與Host不改。另一電腦/LAN及從零彩排仍待驗證。

### 10/15 最新規則與目前阻塞

- 使用者提供的LINE匯出10/14答覆確認：START第一幀累積、collision>crash>kill>timeout、三維距離<15m立即終止、攻擊1度/500與3000ft邊界包含、機體X軸、固定權重30000/10000/100/1、無擊殺時比較S_advantage、正式CMD只收state2。這是匯出證據，未獨立主辦即時核對；詳見diagnostics/LINE_RULES_REVIEW_20261015.json。
- 舊凍結base參考分數權重、2度預設、50ft毀機及缺碰撞不能稱正式一致。campaign使用顯式1度的舊比較仍保存，但下一版需隔離新規則契約、分開計擊落與回合勝負；不能改寫運行中來源或舊SHA。
- 三個相同m4 learner目前已退出，三個win_loop仍閒置、queue空；共享9個ZIP及progress已隔離保存，不當作已驗證模型。啟動所有權未確認，既有整理問題及通知信已送出；回答前不停止loop、不改live source、不加新learner/Host/評估。
- near75首個run因workload_overlap而parent真退出1，未建立worker；guardian真退出沒有handle觀察，不能補0。保留原20min預留，無75度動態結果，下一trial先解決程序/來源契約。

### P0：可靠參賽路徑

1. 在任何新 Host 啟動前完成獨立 watchdog。它必須在對話／核准等待期間仍有效，核對並管理自己建立的 Host、Player1 與內建 Player2 子孫程序，逾時時由最深子程序往上停止，絕不碰無關程序。
2. 以原 `repair_guide` 完成新的公告版 Host 正向回合；保存設定、來源、PID、實際退出碼、CSV、ACMI、log 與稽核結果。
3. 累積至少 6 個獨立固定來源 Host 回合，再做另一台電腦／LAN 與兩次從零啟動彩排。任何一步失敗都保留證據，不把 partial 算成功。

### P1：修正已知安全退步

1. 以已觀察的 RL 6000 ft（6000呎，約1829公尺）鏡像開局，各跑 guide／bank80 一場，唯一變更是加入 60 Hz 遙測；控制法、來源、初始 SHA 不變。
2. 先重現終態及 overload counter，才定位 244–245 秒的精確 tick、模式、指令、負載、高度與能量。
3. 根據證據只改一個安全因素，建立新候選；用新開發種子公平比較，通過安全與分對手門檻才可進擴充對手池。

### P2：讓敵機真正會打

建立凍結對手聯賽，而不是只打一個固定紅方：

- 腳本機動：純追擊、提前量追擊、break turn、剪刀機動、high/low yo-yo、能量保持、低空恢復。
- 歷史策略：原 rule、原 RL、`repair_guide`、通過門檻的歷史候選快照。
- 鏡像自我對戰：藍紅同一策略但分離內部狀態與亂數，交換左右／距離／高度／速度。為避免只會破解自己，訓練與評估必須混合腳本及歷史對手。
- 建議訓練抽樣起點：50% 鏡像／近期快照、30% 歷史凍結策略、20% 腳本極端機動；實際比例必須以小型消融比較決定。
- 晉級必須分別報告每一類對手的擊落、攻擊時間、存活、墜機、過 G、最低高度；平均數不能掩蓋單一對手退步。

### P3：模型研究分支

#### JEPA 類狀態世界模型

- 不直接套用影片版 V-JEPA。以 JSBSim 數值狀態和控制動作學習 latent transition／future prediction，再用短視窗規劃選戰術目標。
- 60 Hz 底層仍由可驗證安全控制器執行；世界模型只在較低頻率提出目標或候選機動。
- 第一階段只做離線 next-state／multi-step prediction 與推理延遲評估；沒有優於簡單基線前不進戰鬥部署。

#### Qwen 4B 戰術決策器

- 候選先採官方可取得的 Qwen 4B 級模型，確認授權、RTX 3060 12GB 實際記憶體及延遲後再凍結精確型號。
- 不讓 LLM 直接產生 60 Hz 連續操縱面。它最多以約 0.5–2 Hz 根據壓縮狀態選擇 `pursue／lead／lag／break／scissors／yo-yo／recover` 等離散戰術，底層安全控制器執行。
- 必須比較：`repair_guide`、目前 SAC／殘差、JEPA 類 planner、Qwen 4B tactical selector。使用同初始 SHA、同對手、同時間上限，另量測最壞推理延遲與超時 fallback。
- 若推理超時、輸出不合法或沒有可重現優勢，立即 fallback 至 `repair_guide`；不得把語言模型自述當戰力證據。

## 10/19 Go／No-Go 最低條件

- 至少一個新官方 Host 完整回合，且啟動、UDP、GAME OVER、CSV、ACMI 和退出碼全數可核對。
- 正式套件能從乾淨啟動完成連線，並有現場故障時可在數分鐘內切回的 `repair_guide`。
- 沒有未處理的墜機／過 9G／低高度安全退步被平均成績掩蓋。
- 即使實力仍不足奪冠，使用者仍願意為實戰與交流上場；若基本可靠性未通過，建議塔塔加。

## 通知與電子郵件

- 正常進度與無變化保持安靜。
- 出現無法自行解決的阻塞、需要使用者登入／驗證／提交證件／操作硬體、需要使用者在兩個方向做選擇，或需要在期限前採取行動時：在本聊天通知，並寄信給已連接 Gmail 帳號（`to: me`）。
- 郵件主旨以 `【AI飛行員需要你處理】` 開頭，內文用繁體中文、非技術語言，逐步列出：發生什麼、為什麼需要你、要按哪裡或做什麼、期限、完成後回覆什麼證據。
- 以 `email_notice.json` 的事件 ID／狀態／證據 SHA 去重；同一問題不重寄。若 Gmail 不可用，在聊天明確告知並保存未寄出的通知內容。

### 10/15 12:36 隔離準備更新

- portable_host_v2凍結來源及18項靜態測試已真退出0，詳見diagnostics/portable_host_v2/PREPARATION.json；未啟Host/FDM，真實程序樹/收證/清理及套件回合仍待實測。既有整理idle loop的確認未回覆前，只進行隔離靜態工作。

### 10/15 23:13 監督更新

- 原三個win_loop已無相符存活身分，其中舊PID20448已重用，禁止按舊PID停止；沒有由本輪清理舊loop，退出碼未知。新run既有確認閘門保留。
- portable v2最新只讀preflight逾時45秒，無新Host/FDM；18靜態測試不替代此未完成檢查，下一步先只讀定位慢點。


## 10/15 OpenCode 接續優先順序

- 唯讀檢視 OpenCode SQLite 的 Defense AI Pilot training setup 對話，最後相關請求為本地慢速RL；沒有新外傳。舊資料庫與 win/、模型均保留。
- 找到 M3 run1 9/54失敗、run2 90/90、run3_perturbed90/90、run4_4actor180/180報告。不同actor各cell種子無重疊，無完整runner訓練當時凍結，保留探索資料，不當公平配對或職業隊伍勝率。
- M4關鍵API錯誤已靜態重現：預先StationController.act後，把cmd送入期待residual的parent.step，導致20tick共40次act。隔離v2改成只設定tactical，再由parent對零residual呼叫一次，20tick20次。
- 同時修同一API契約的步進後裁判計數/明列reward、每回合seeded對手抽樣、reset鏡像狀態、guard觀測、on_step終局統計。11項實際方法+fake physics測試真0，沒有新FDM或learner。不是安全動態、訓練或勝率證據。
- M2 regate的promote語義明寫前進鏡像測試，不是部署，採納此界線；高度取捨記錄保留，不把所有舊對手說成直線靶機。
- 原三個loop均無相符存活身分，舊整理問題已無需停止目標；使用者要求keep後接續隔離工作，不再以此過期確認阻塞。舊PID20448已重用，絕不可按舊PID停止。
- 下一步：獨立deadline單例M4 worker與真FDM介面短測；正式collision/crash/event/timeout score契約，再同初始SHA公平小比較及有限新訓練。portable v2前置檢查45s逾時仍未解。正式repair_guide，不重跑已完成批次。


## 10/15 M4真FDM介面門檻已完成

- 假設：修正版每60Hz tick只執行一次StationController.act、實際sendAction與該輸出完全相同，父裁判post-step計數傳至戰術層；相同seed reset清空狀態。控制固定零戰術向量，沒有新learner/策略搜尋。
- 新隔離m4_interface_v1，沿用v5 byte-identical獨立guard演算法並擴充exe/parent身份；8項靜態閘門測試真0。OS lock/STOP/2GiB RAM/10GiB disk/來源與紅方XML凍結/種子registry/每worker45s/全體180s硬限通過。
- run_20261015_232701_f27ecd：rule/mirror/frozenRL各一worker，每worker同seed reset兩次、每次300tick，共1800個自機60Hz tick。三個新開發seed2026103100..3102已attempted；不是holdout/公平戰鬥聯賽。
- launcher/supervisor/3worker/guard/verifier全部真退出0。VERIFICATION errors[]，3類初始/final SHA逐次完全重現；每tick act/send/judge=1，實際輸出誤差0，無P2 fallback，CSV/ACMI與來源核對通過，無自建程序殘留。
- 限制：每次只有5秒，全部攻擊tick0，非零攻擊累積路徑尚未由此FDM驗證；沒有完整戰鬥/勝率/學會/官方契約證據。正式仍repair_guide，訓練CLI仍拒絕無監督啟動。
- 預留3分鐘保留不退款，今日ledger7.6956h（6h僅警告，已縮成短診斷）；實際wall見report。下一步正式judge契約與非零counter/Gym callback路徑、單例有界訓練worker及小配對；不重跑本批。


## 新裁判/訓練契約接續

- 前一goal turn分類為progress：完成1800個真FDM介面tick、全部真退出及完整核對；本輪未重跑該批。
- 主辦正式下載端點取得AI空戰飛行競賽公告文件_1008.pdf，ZIP CRC與PDF SHA已保存。視讀相關第7–10頁：新版權重/kill倍率/距離Pt/50m與15m均核對，PDF的2度與10/14群組管理員1度答覆不一致，保留具名profile，採較新1度做研究但不宣布Host正式一致。
- 新experiments/rules_v20261014/judge.py隔離實作START/當幀結算/Collision>Crash>Kill>Timeout/180累積tick/10000*Tatt-100*TG+rawΣPt/30000*(1+(300-Tkill)/300)/timeout及同時擊殺優勢勝負。22純數值事件測試真0。
- replay_blue_counter.py唯讀重算兩個已保存真60Hz藍方軌跡，共35317列，166與180tick完全重現、589個每秒/終態檢查點相符。2度前綴門檻較早，僅列差異，不是新2度完整回合或勝率。
- 舊資料缺red完整60Hz狀態，不能偽造全S_advantage；AGL/HSL基準、位置因子500/1500m端點、非碰撞雙墜機與取消擊落顯示分仍明示未確認。沒有新FDM/learner，不增加訓練/評估預留，不部署。
- 下一步：新M4 adapter整合裁判與完整雙方逐幀遙測，有界非零/事件FDM診斷，同初始SHA小配對及有限新訓練。portable preflight45s逾時仍保留。


## 10/16 裁判接通後的追瞄修正路線

- 上輪goal為progress：下載新版PDF、22規則測試及保存非零counter重算完成；本輪實作M4v3 adapter，保持控制器，新增合法自身時鐘為第13觀測。
- m4_rules_interface_v1/run_20261016_000620_fffa59：三個正式幾何5秒worker各重設兩次真exit0，但後方fixture seed2026101603首600tick始終TA>=1.199888度，射程內600tick、0攻擊，worker2、parent2、guard0。批次partial4/5，最後一case未啟；全部種子與4min預留保留。PARTIAL_AUDIT重算雙方計分/控制資料相符，2400新tick，不宣稱整批通過，不重跑。
- 有證據縮為單一新對準fixture，來源m4_aligned_counter_v1、seed2026101610，僅在reset後首physics前把自身heading對準合法LOS，沒有改counter/reward/G或後續state。兩次均180tick累積180命中、blue_kill、真terminal/won映射正確，初始/final全雙方封包重現。launcher/parent/worker/guard/verifier真0，VERIFICATION errors[]；360新tick，全雙方60Hz計分回放、實際命令、13觀測、單次act與單調ACMI通過。是非正式後方接線fixture，不是競賽能力或勝率。
- 今日10/16共預留4min+90s=0.091667h，不退款；未開始新learner。精確身份終態皆不在/已重用，未停止不相干程序。舊m4_interface1800tick的三份ACMI在reset後時間倒退，另寫ACMI_TIME_REVIEW，不改舊raw；原命令/物理counter證據仍成立，視覺時間軸未通過，新worker已用episode offset修正。
- 機理靜態重現：M1以unsigned3D鼻角加bank，headingerror=-1.2deg時竟產生+0.96deg bank；隔離V4唯一控制改為signed heading_error，對稱+/-1.2得+/-5.28deg，垂直誤差不虛構水平bank。尚無V4新FDM，不宣稱修復戰力。
- 另準備正確學習契約reward_wrapper：真winner+/-10與gamma*Phi(next)-Phi(now)，真terminal Phi=0，Phi=Sadv差/10000，learner gamma必須匹配.9995。8項候選/獨立望遠鏡和式測試真0；避免把大量中間積分當成終局獲勝，尚未用在learner。13維不能拿舊12維模型精確續訓，舊共享replay/critic/optimizer不接。
- 下一步已寫V4/NEXT_PAIRED_DIAGNOSTIC.json：新seed2026101620/1621、左右+/-1.2物理fixture、V3/V4同初始全packetSHA配對，固定0tactical、4case/每case2reset/最多600tick、總240s，未實作/未claim。再新正式幾何開發與有界fresh SAC，正式仍repair_guide；portable45s與Host/LAN仍待。


## 10/16 signed yaw 真FDM配對與fresh SAC試跑
- 新m4_yaw_pair_v1 run_20261016_002509_917302四worker/兩開局/3960新自機tick，所有launcher/parent/worker/guard/verifier實際0，完整VERIFICATION errors[]。兩個reset只是可重現性，不能當四個獨立開局。
- 相同雙方初始packetSHA、固定零戰術，唯一signed nose項：左-1.2度原版600tick0命中，V4在481tick累積180；右+1.2兩版均180，V4晚3tick/0.05s，共同曝光177vs180命中。左右共同最低AGL差-1.5144m/-0.0208m，V4 peakG1.508/1.112且0過9G。已保存SAFETY_REVIEW；承認右側小退步，只允許有界探索，不宣稱全面優於或正式開局安全/勝率。
- m4_train_pilot_v1隔離新executor，6項plan/seed/guard靜態測試真0、7py compile。初次freeze因utf8-sig別名失敗，已改utf-8-sig；失敗時沒有FDM/claim。
- 10/16 00:39:19真正啟動run_20261016_003919_a5c748：fresh13維SAC128x128 CPU、gamma.9995匹配winner potential shaping；5000decision/最多100000自機tick，單一learner，原900s guard/840s worker/810s內部期限含25s保存餘裕。規則研究profile LINE1deg/AGL/right_bin，非Host認證。正式repair_guide不動。
- policyseed2026101650與256episode seed2026200000..0255全先登記；rule/mirror/frozenRL x3000/6000/9000ft每9episode平衡，但5000decision未必涵蓋9cell，必報實際coverage。未用預留仍保留，不稱holdout。今日新增15min預留不退款。
- 用量2026-10-15 16:39UTC較低剩餘25%，primary reset1792094944/week1792654206，僅作警告；本次未用OpenCode外傳、credits或reset券。啟動時occupied[]、RAM3.95GB/disk196GB，來源凍結；worker24816/create1792082361.789251、parent17736，身份由launch與active_worker完整核對，guard armed/unknown[]。先監督同程序，真exit後核對bundle/replay/逐tick；更新權重不是學會或獲勝證據。


## 10/16 fresh SAC試跑終態（2026-10-15T16:45:18.151324+00:00）
- run_20261016_003919_a5c748真正完成5000decision、100000自機60Hz tick、500次梯度更新；actorSHA確實改變、replay5000，model/replay重載與13x3/gamma/確定推論核對通過。
- launcher/supervisor/worker/guard/verifier全部真0；VERIFICATION verified_fresh_training_pilot=true/errors[]，逐tick連續/單次act-send/G/最低高度/來源/工件hash與exact程序全終態核對。外部工具exit證據f9fb63與600c45，沒有停止無關程序。
- peakabsG7.676705、0過9G、最低AGL797.6088m；實際workerwall279.297s，原15min預留保留，今日預留0.408333h。9cell排程實際只訪問6cell，5個完整訓練回合+最後第6回合10000tick ongoing前綴，絕不把前綴算完整或宣稱9cell聯賽完成。
- FINAL_REVIEW與BUNDLE_MANIFEST凍結來源/新模型/回放/13觀測/gamma與完整hash。訓練中的對手結果含探索與變動政策，不能當固定模型勝率或宣稱已更強；正式repair_guide不動。
- 下一步單獨凍結final SAC vs同V4零戰術、rule/mirror/frozenRL6000ft、3個新開局6case同initialpacketSHA公平完整本地回合；保留分對手/最差case/G/高度與真exit，通過才擴池/未見保留與Host。不盲續learner。portable高優先尚待前置45s慢點與真packageHost/LAN彩排。


## 10/16 frozenfinal戰術比較與guard讀檔恢復（2026-10-15T16:58:16.977496+00:00）
- 新m4_final_eval_v1原計畫6case，真launch已登記3新seed2026300000..2及600s預留。四worker完整actual0（rule/鏡像兩對共70616tick），第五啟動瞬間guard active_worker phase PermissionError13而failclosed；原parent真15、guard2、外部shell1，不能假造0或6/6。四worker雙方score/control逐幀重算通過，PARTIAL_DATA_AUDIT只作保存/探索，verified_comparison=false。第五無實際worker waitexit，不補0；第六未啟。exact原身份皆不在/已重用，未停無關程序，舊源/raw/3seed/600s預留保留，不全輪重跑。
- 隔離m4_final_eval_recovery_v2唯一executor修正：active_worker檔案PermissionError最多250ms重試，受原期限與STOP約束；持續錯誤仍failclosed、psutilAccessDenied不忽略。7個故障/AST恢復/計畫測試真0，guard其他語意與v5相同。
- 新seed2026300010只做RL6000ft兩場原300s，240s獨立guard/90sworker/OSlock/STOP/來源XML紅方模型/資源/父子身分，沒有learner，未重跑原四場。兩worker/parent/guard/launcher/verifier真0；VERIFICATION errors[]、36000新tick、同雙方initialSHA、完整雙方score/event/實際確定策略/單次act/send/CSV/ACMI/來源核對。
- RL零戰術22命中tick、finalSAC26，皆timeout藍方積分勝/0擊落、0過9G；peakabsG7.6043→7.3933，最低AGL779.5844→785.0848m（共同曝光+5.5004m）。只有+4tick/0.0667s小正訊號，不能叫整體戰力/勝率改善，候選不晉級，正式repair_guide。
- 原partial原始探索值rule31→180命中、candidateblue_kill；鏡像0→22，均零過9G；但原parent15未通整批gate，只保留不能拼成新6/6或正式比較。外部exit證據e66774/7a1927。今天10/16預留共0.641667h、兩次原預留都不退款。
- 下一優先：定位portable_v2的45s前置檢查慢點，先不啟FDM、隔離修可靠前置；再原硬限下真packageHost/乾淨啟動/LAN彩排。戰力仍需多樣凍結對手/多初始高度距離/未見保留集，不能盲續SAC或自動部署。


## 10/16 08:30 portable真Host接續與精確終局工具盤點
- 上個goal為progress，已完成fresh5000訓練與一對RL公平比較；本輪沒有重跑。
- 前次45s preflight逾時未重現：新的只讀profiler在原45s內13.468s真exit0，主要frozen_profile12.64s逐2115檔hash/resolve。profiler自己的父Python被正確列busy，該測量不是允許Host的gate；不放寬時間或改原套件。
- v2 portable_20261016_010307_05d6734c已啟真Host，但mark-start被Player的未列入conhost子程序拒絕。代理仍誤按START，已坦承操作錯誤並核對own guard後寫v2 STOP；真watchdog2，observer shell1，全原程序已核對不在/重用。此回合0有效，不事後補START或算成功，原12min預留保留。
- 隔離v3加入prelaunch conhost SHA/snapshot及exact own Player/collector/Host鏈，Host/P2仍須Hostroot，不放寬unknown。首次23tests因freeze未先建立真1，建立freeze後23tests真0（5.588s），非FDM證據。
- v3 portable_20261016_082436_fe5a8fee真arm0、Windowswait handle在INIT前掛上，inventory全true，mark-start工具f8288c真0後獨立UI按START、RUNNING實見。套件runtime -I-S/selfcheck/原2115files與ZIP均未改。
- 真173.083s/10384列Host完成，raw winner1.0，freshP2/CSV/ACMI/先驗profile其餘全部核對。但官方GUI終局另啟taskkill.exe /PID7396 /T /F關閉其直接已知internalP2，v3因未預先快照這個子程序而inventory拒絕；collector2、guard2、Windows真wait observer shell1（8eeeac）。不能算有效package回合，原12min預留保留。FAILURE_REVIEW與精確terminal audit記全部原identity不在或重用，不碰無關程序。
- v4已隔離修該唯一盤點缺口：觀察、不執行taskkill；只接受已核對cachedGUI、命令精確/PID已記錄且同parent的internalP2 /T /F、目標完整identity和事前WindowsbinarySHA/快照，其他目標/flags/祖先/bytes仍拒絕。不global-whitelist系統工具。28靜態/故障/真wait非0/readonlypreflight測試真0（770e92，5.273s），沒有v4新Host，0/6有效。
- 後續直接v4真preflight/arm、observer beforeINIT、mark-start必須實際0且先檢查結果，之後才獨立UI START。原6場舊環境不借；v2/v3 raw不回跑/不重新分類。正式repair_guide不動，candidate不部署，LAN/另一PC與兩次乾淨彩排仍待。
- 最新用量2026-10-16 00:21:33UTC較低65%（primary used35/weekused22），reset1792115407/1792654206，沒有credits/reset券；前次8%提醒按舊reset去重。10/16總預留1.075000h不退款。


## 10/16 09:40 RAM閘門與保存Host計分實證（2026-10-16T01:42:54.063771+00:00）
- v4真arm在任何新run/guard/Host前exit1，f5da96，RAM_below_2GiB。現讀可用0.936GiB，DCS working set約8094MiB，沒有停止遊戲/其他程序或降低門檻。無新的720s預留，前置工具實際6.085s後補帳，原帳目不退款。Gmail已寄本人me，message1a14259a27977066，event portable_v4_ram_floor_20261016去重；指示完成/保存飛行後正常退出DCS、等30s、回覆聊天。RAM恢復>=2GiB即可自行重核對，不必等人工重授權，不重寄同問題。
- 沒有空等：用puremath串流保存v3的10384列CSV（SHA1a53b070...c84c6），無新FDM/Host/learner。main audit0.937s、30s預留保留。該CSV來源packagegate仍因collector2/guard2不合格，不能重新分類。
- bodyX/sphericalNED的當幀1deg擊中預測180tick，與HP下降180tick逐幀零不符；2deg預測1201tick、多1021，支持這個已安裝Host在這條軌跡用1deg。不是全賽事Host版本認證，紅方0命中無辨識力。
- 重要新問題：當前frozen judge Pt用角度denominator90。保存Host的兩個幾何分量實測符合 `(180-angle)/180 if angle<=90 else0`，分別乘distancefactor；位置angle=180-other_noseTA。10384列兩機成分最大差約6.45e-6（球面NED近似），舊Pt對Host的絕對差累加藍425.968/紅95.588。這是原始資料推論，需再核對10/08PDF第10頁公式，不能直接冒稱已正式一致。
- CSV的Score_Kills是累積攻擊秒數：HP下降=60*delta該欄，最大誤差2.31e-14，不當三次擊落。FinalAdvantage逐幀delta符合10000*delta攻擊秒-100*deltaG欄+當幀AttackAdvantage+PositionAdvantage，誤差<8.6e-12；無過G事件所以G係數不能由此辨識。首可見time0.033兩方FinalAdvantage約683.5，原因未確認，不捏造START前因果或重設原資料。
- 保留HOST_RULES_AUDIT_20261016_INITIAL/新audit/FACTOR_PROBE/POSITION_PROBE與解析失敗後修正紀錄（純語法else0→else 0，失敗未跑資料）。原rules/adapter/reward/model/hash不改，5000模型仍僅舊契約開發候選；在位置計分核對與新隔離契約前不接critic/optimizer/replay、不盲續訓練。
- 下一步：RAM足夠時v4真Host收證；RAM不足時可做PDF對照與新規則純數值/保存CSV驗證，不啟重型程序、不停無關DCS。正式repair_guide、有效package0/6維持。今日預留1.085024h。


## 10/16 09:47 第一場完整可攜套件Host通過
- 本輪v4初次arm因可用RAM0.936GiB拒絕，未生新Host/guard；已依授權寄ELI5本人me。使用者回覆done後實讀RAM8.667GiB/occupied[]，問題已解除，不再等重授權或重寄。
- fresh v4 portable_20261016_094406_3a3b7d3a，原720s獨立watchdog/包內runtime-I-S/sourcecache與conhost+taskkillprelaunchSHA/OSlock/STOP/資源通過；Windows真wait在INIT前掛，inventory全true；mark-start6dd6bb真0後獨立UISTART，實見RUNNING。arm9483ee真0。
- 真Host 80.35s、4820列，rawP1勝，HP[180.0, 0.0]；兩機over9G ticks[0, 0]，maxabsG[3.4528400258392966, 4.00838455392084]。collector0、guard0與Windows真wait工具43f0e7退出0，全部11checks及own-childinventory通過，精確含console/terminaltaskkill/P2的cleanup全停，原identity全不在或重用，無無關程序被停止。sourcefreeze未變，FINAL_AUDIT保存。
- aggregate工具752fce真0，v4有效package1/6，profilehash15e0bd4a1783a1071a7a43456e2d871593299707886157054cf110bd756ed76a，舊6場與v1/v2/v3失敗都未借用，不是正式賽事認證/未知隊伍勝率；SAC未部署，仍repair_guide。
- RAM等待期間savedCSV實測1deg180hit逐幀零不符，但位置角度180Host推論與本地90不同。已視讀10/08PDF第10頁（印頁9），明確TA/AA皆(90-angle)/90、angle<90，故frozen本地Pt符合公告；應分類公告與installedconnectionHost版本分歧，不稱舊judgecodingbug。RULES_PUBLICATION_HOST_DIVERGENCE保存PDFSHA與視讀影像。原研究/模型/回放不改；若另立Host180契約需新critic/replay，不能偷偷改正式訓練目標。
- 下一步續做其餘5個獨立同fixedprofile新Host回合，保留每次原720s預留與實際退出，再做兩次乾淨啟動/LAN另一PC。正式規則一致性及擴池/未見保留仍待。10/16預留共1.285024h不退款。
# 2026-10-16 可攜套件六場本機驗證完成

- 已完成6個新v4獨立Host回合，同一凍結profile；不計入舊環境或v1/v2/v3失敗回合。
- 原始判決六場P1勝、HP180:0，雙方零過9G；每場完整CSV/ACMI、collector/watchdog/真Windows wait退出0、自建子程序精確清理通過。
- 六場模擬時間：80.350、102.933、288.617、160.200、82.717、80.750秒。
- 正式保留repair_guide。這證明目前本機的可攜runtime/Host連線與回合收證可靠性，不是專業隊伍勝率或賽事認證。
- 原2115檔與ZIP未修改。LAN/另一台Windows電腦，以及從零解壓後兩次乾淨啟動尚待驗證。
- 官方PDF的位置計分90度公式與此連線Host實測180度版本不同，研究仍依具名publication90/LINE1deg契約，不偷偷改研究目標。
- 正在進行新SAC5000對規則機/鏡像的4場、2個同開局配對比較。只有完整終態真退出與逐tick來源/初始狀態核對通過後才檢討，尚未啟動一萬decision訓練。

證據：diagnostics/portable_host_v4/SIX_ROUND_REVIEW.json 與 GATE_LATEST.json。

## 10/16 一萬decision訓練及新舊模型比較
- m4_actor_transfer_10k_v1/run_20261016_102640_412524：10000decision/200000tick/1125updates/11完整訓練回合、9個opponent-distance cell全訪問、peak8.5534G/零過9G、模型/replay重載通過。launcher/parent/worker/guard/verifier真0；actor-only轉移，critic/optimizers/replay重新建立，不稱精確續訓。模型SHA6c7ceea74457557be60f4156313cf1d75ffff20196159ae8fe22a7809190c012。
- m4_rule_mirror_eval_v1/run_20261016_102257_9f7cd7完整4場2pairs：舊5000對zero tactical，鏡像180hit擊落vs4hit逾時；rule均0hit但5000 margin低2182，共同高度候選較高，零過9G。只准單一bounded10000學習，不晉級。
- m4_transfer_eval_v1/run_20261016_103651_4fcfa9：完整6/6、3pair/101151tick，同雙方initialSHA，來源/模型/actualactor/逐tick雙方裁判/CSV/ACMI，launcherparentworkersguardverifier真0。新10000 vs舊5000：rule3000ft 3vs6hit、scoremargin-555.891、共同minAGL-19.840m；mirror6000ft兩者blue_kill，新快32.383s，共同minAGL-19.815m（仍3556m）；RL9000ft 23vs6hit、margin+3561.252、共同minAGL+3.974m。全零過9G/死亡/墜機。不平均掩蓋rule退步，不部署，三pair不等於勝率。
- 已抓出frozen v1 verifier摘要把實際blue_kill/red_kill/crash tags寫成泛kill/crash造成kill0。原event/winner/逐tick重算正確，原報告/來源不改；EVENT_POST_AUDIT與SAFETY_REVIEW由實際終局CSV補正計數，真0 b7a9ee。新grid修正摘要tag且故障/plan/AST測試通過。
- RANGE_ALIGNMENT_DIAGNOSTIC為保存資料描述：rule新模型在有效距離4406tick（舊4217）但1deg僅3tick（舊6），2deg16vs22、5deg136vs216；不能歸因某一channel，下一步先凍結模型擴開局，不盲續訓練。
- m4_grid_eval_v1新18game/9pair，rule/mirror/rl×3000/6000/9000ft、新seed2026300300..308，900s總/90s每case新計畫；不是延長舊run，不是holdout或已證明左右覆蓋。主代理已真launch session16812，先核對目前pointer/identity，運行中只監督，不改/重啟/並行。
- ASUS Vivobook無獨顯由人類確認，CPU Player不需獨顯但尚需該機實測。ASUS_CPU_Player_檢查包_20261016.zip已封裝原2115檔未改，主PC新解壓自檢/CPU合成p99約0.6ms成功；Windows CRLF與batch保留exit0/缺套件exit1實測。先前stdin型別/CRLF測試失敗已保存BATCH_EXIT_VERIFICATION，不算通過。ASUS/LAN尚未驗證；Gmail步驟message1a14295a4b2d1390已寄，email_notice去重，等ASUS新vivobook_readiness.json，不再重問是否有第二台。

## 10/16 11:05 完整18場grid終態與決策
- 18/18、9pair、313300自機tick，原900s總/90s每case，實際FDM批次820.984s；launcher 276c90真0、verifier 3be15f真0。VERIFICATION true/errors[]；固定兩模型/來源/XML/紅方/同雙方initial/actualactor/逐tick雙方judge/CSV/ACMI完整，21原程序身份均已無或重用。
- old5000 vs new10000：rule三場擊落1→0/命中206→176；mirror0→2/209→362；RL0→0/4→27。全零死亡/墜機/過9G。任何優勢只適用此9個開發開局。
- 明確退步：rule9000 oldbluekill→newtimeout，180→144命中；mirror3000 131→2命中，共同最低AGL低113.097m（新最低仍4028m）。rule3000也積分退步。不能用總擊落2vs1掩蓋這些退步。decision=mixed_candidate_not_promoted_no_blind_training，正式repair_guide保留、兩SAC凍結備用。
- 下一步先保存退步case分析，再對真正凍結SAC紅方做一個短時序介面驗證，之後才強對手聯賽/更多初始側/未見保留；不是繼續大量訓練。
- frozen_sac_opponent_v1：10項fakeactor/合成packet/AST真0（394b32/.211s）、sourcegate真0（0a931f/.860s），初次utf8-sig codec typo真1已記錄。新adapter ownpacket/counter/clock/controller/reset全獨立；0/20/...3Hz，duplicate不計；尚無真model/StationController/RNG路徑/FDM接線/learnedselfplay。
- Codex 03:04:07UTC剩9%按reset1792133464警告，重置2026-10-16 06:51:04UTC（台灣14:51:04），未credits/reset券。已走唯一opencode_task.py的新CPU來源審查delegations/20261016_110512_be0f，僅已授權repair_v1/controller.py，沒有內部遙測/模型外傳；Space Bunny live catalog最高max/實際session cost0、源未變、真exit0 a98dee、60.36s。LOCAL_DISPOSITION保留有限值/重設/固定60Hz條件，修正模型增益代數假設與alpha+gamma代理解讀；無補丁套用。校準draft未重試。
- ASUS包修正版SHA c6840b276e1f23254017ba13132b90a3c2d2cf7114fcb93be71aa43e9b96a7f8，主機新解壓+batch成功0/缺套件1真測，ASUS/LAN尚待該機report；Gmail步驟已寄且去重。
- 今日預留3.074900075h不退款。兩排程已更新現況/下一步，原rrule時刻/期限不改；goals應用狀態usageLimited未自行改為完成或重置。

| 對手 | 距離ft | old命中 | new命中 | 共同高度差m | 共同積分margin差 |
|---|---:|---:|---:|---:|---:|
| rule | 3000 | 0 | 0 | 291.043 | -2670.945 |
| rule | 6000 | 26 | 32 | 335.867 | 2776.209 |
| rule | 9000 | 180 | 144 | -28.975 | -11519.400 |
| mirror | 3000 | 131 | 2 | -113.097 | -21863.778 |
| mirror | 6000 | 51 | 180 | 8.149 | 28507.927 |
| mirror | 9000 | 27 | 180 | -40.516 | 30420.664 |
| rl | 3000 | 4 | 13 | -7.023 | 1216.598 |
| rl | 6000 | 0 | 14 | 16.807 | 4195.877 |
| rl | 9000 | 0 | 0 | -0.728 | 745.687 |
