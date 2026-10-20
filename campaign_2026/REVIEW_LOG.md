# 競賽實驗檢討

## 2026-10-11 接手

使用者確認：已完成報名、主辦已同意單人參賽。專案優先目標更新為準備 11/7 AI 飛行員模擬擂台賽並爭取奪冠。

實際盤點修正過期資訊：舊 opponent_lab 2M 已完成，最後完整20場没有擊落；不選此路線直接擴大續訓。改用 combat_fix 24k 新契約，其真實完整對抗訓練只有一場，容易課程有成功訊號。

首輪假設：修正版低層控制＋連續precision reward＋足夠完整開局學習，比已失效的舊契約有改善機會。先新增150k decisions，三段固定配對比較；需實際結果才決定續訓或改方法。

OneDrive 原專案可讀但不可新增檔；新程式、來源副本與 artifacts 改放 E:/ai_pilot/campaign_2026。原模型/程式/Host保留。

## 2026-10-12 更正與續作
使用者更正：尚未報名，已確認單人資格。授權使用本機 OpenCode 的 Space Bunny 模型分擔程式工作。前次 E 槽部署被自動審核因額度不足攔下，沒有執行且未啟動訓練；今日額度重置後完成部署，19 個配對/監督測試全部通過。


## 2026/10/12 18:58 — 已實際開始訓練與驗證

- 作業 job_20261012_184123_68be 已於18:41啟動：最多150k新增decisions/4h，三段各50k；已通過19項runner/benchmark測試。第一段完成新增50k，總74k。不是勝率成果。
- final_0000074000 已實際重載：model/replay SHA正確，replay 50k，樣本有限值，actor可產生有限指令，verified_01.json passed=true。現在進行dev_01的24場完整配對評估，完成前不宣稱優於基準。
- sandbox讀程序可能AccessDenied，runner status會顯示False；使用允許的主機讀取重新核對PID/建立時間/命令後已確認訓練活著。監督排程已加入權限未知不得當作死亡、不得因此重啟的規則。
- ai與ai-2已改正為尚未報名但單人資格已確認，截止10/21；過期一次性ai-3已停用，其餘低頻監督及每日20:30檢討繼續。
- OpenCode免費模型清單與公開連線已驗證。V1和自訂deny全部工具模式收到403；使用官方V2 2.0.27內建plan、工具需批准且deny edit/subagent已成功。公開數學模組實作正在執行。專案原始碼傳送被自動核准要求明確同意，對話問題待答，未傳送該三檔。


## 2026/10/12 19:09 — Space Bunny 真實完成工作

- 公開數學任務 delegations/20261012_185725_bab5 完成，約176秒。session中繼資料確認 provider opencode / model space-bunny-free，reported cost=0；保留 model_evidence.json，不由模型名称推算費用。
- 產出precision_math.py與測試；原始測試有4處錯誤（500/5的CPA、pitch符號、roll -90軸、任意向量當機首）。依幾何修正後30項測試通過。新 diagnostics/observation_diagnostics.py 只讀26個合法觀測，21份既有初始資料與舊幾何差異最大1.44e-9；尚未接入飛行控制、沒有勝率改善證據。
- 第一輪部分遙測顯示SAC對rule幾乎沒進入1100m內：6場僅2個近距離CSV樣本，guide有224。這是目前部分評估的瓶頸線索，不把1Hz樣本當精確秒數。完整評估完再決策；既定兩次完整落後停止規則繼續生效。
- 下個單一因素候選可研究：禁止SAC在遠距離攔截階段施加残差，僅在近距離且鼻向合理時啟用；先以同一凍結actor做隔離消融，不能改active repair_v1，不能精確續跑不同契約的critic/replay。此項尚未實作或驗證。


## 2026/10/12 19:13 — dev_01完整結果与決定

- dev_01 completed，24/24完整場，12個配對開局且同初始hash；guide 12場3擊落，candidate 12場0擊落。兩者12/12存活、0被擊落、0墜機。平均有效攻擊guide 0.8333秒、candidate 0.2097秒。只屬本地開發比較，無正式賽勝率或奪冠率。
- 規則對手：guide3/6、candidate0/6；RL對手皆0/6。guide最小高度777.94m、candidate773.47m；仍要檢查正式Host邊界與地形差異。
- 決定：拒絕本候選升級，保留凍結guide。這是第一次完整明顯落後；依事前設定進入第二段50k，第二次符合落後條件則futility_stop，不為湊滿150k強行續跑。程序身分與建立時間已確認，train_02正常。
- diagnostics/dev_01_complete.json保存完整取樣漏斗。對rule候選近距離樣本僅2、guide224；對RL候選有662個近距離樣本但1度內比例約0.0060，guide1057個且約0.0019。故候選遠距離攔截退化，guide對RL的精確鼻向追蹤也仍需改善。CSV比例只是取樣診斷，不能當射擊時長。
- 下一項單因素實驗先隔離測試遠距離SAC残差閘門，其他訓練/控制参数固定；不直接替換現行基準。未實作、未驗證。


## 2026/10/12 19:27 — 隔離消融與10Hz診斷

- 已實作單因素range gate，只在1100m內使用同一凍結74k actor；gate.py六項測試通過。experiments/residual_gate/run_20261012_191703_f102已核對實際程序身分，24場配對/40分鐘上限；不是新的learner。原4h加此評估40min及probe150sec預留共4.708h，仍低於日研究6h。
- 新benchmark保留原bundle來源嚴格核對，原actor僅predict。不同控制器不可當相同訓練契約resume。新增compare_gate.py，要求原初始hash、模型hash、依賴hash、guide結果重現以及24/24完整；通過只能進新保留測試，不能直接部署。
- 單一guide/RL開發case r000_rl_3000_normal_2026101110_guide完成18000tick、3000個10Hz樣本；無控制變更，初始hash與原完整指標完全重現（0擊落、0被擊落、0墜機，攻擊0.5333秒）。所有合法觀測計算與原幾何差最大2.44e-10度。
- 此case有效距離內1818樣本：鼻向誤差中位26.18度；水平heading誤差24.84度，世界pitch誤差1.34度。當nose<=10的274樣本，視線與航向角速度差中位約7.35度/秒，pilot load絕對值中位約0.40。線索更偏向水平追蹤/卸載後轉彎速度不足，不能僅認定垂直pitch精度問題；只有此已選開發case，尚未證明普遍原因。
- 診斷詳見experiments/precision_probe/ANALYSIS.json和case/telemetry.csv（合法OWN20+ENEMY6），不把10Hz樣本比例當真實攻擊秒數。此輪先完成range gate，不同時混改控制参数。下一項可驗證近距離航向轉速匹配与lift/load假设；必須先確認模型rudder符號和安全限制，再一次只變一項。
- 本輪開始Codex實讀主窗口剩餘48%、週窗口76%；主窗口自然重置台北10/12 20:30:26。沒有使用credits或重置券。


## 2026-10-12 19:50 完整結果與原始碼審查
- 新增100k決策後，74k與124k完整model/replay/manifest實際重載皆通過；兩次評估各24/24完整，原程序已結束、六階段退出碼0。依既定無改善門檻futility_stop，拒絕追加50k，不部署候選。
- 同組12場：guide 3擊落/10.0秒；raw74k 0/2.5167秒；raw124k 0/0.4秒。這是開發集結果，不是正式勝率。
- range gate唯一逾時guide回合依原凍結來源、模型、seed、18000tick、150秒上限補跑一次，退出0且初始SHA重現。原partial report與23個有效回合保留；recovery_01/report.json完整24場，所有公平比較檢查通過。gated74k 0擊落/3.1167秒，仍低於guide，reject_promotion。
- 使用者明確同意三個原始碼傳給Space Bunny。審查完成201.39秒，實際免費模型、成本0；未修改來源。發現草案roll積分符號、控制與取樣頻率、觀測維度及數項物理/方法判讀錯誤，未採用補丁，詳見delegations/20261012_194445_a586/LOCAL_REVIEW.md。
- 五小時額度實讀剩34%、週剩74%；自然重置10/12 20:30:26。這段完成小型失敗恢復與結果核對，沒有新learner、付費備援、credits或重置券。原4h+gate40min+probe150sec+retry150sec預留4.75h，仍小於日6h；等待時間不冒充新增模擬運算。下一項先量測roll/load/turn response，不依草案盲目改PI或續訓。


## 2026-10-12 19:58 OpenCode 最高推理設定
- 使用者要求每個模型一律最高支援推理強度。啟動器已加入即時免費價格與 variant 解析，Space Bunny 實際使用 max，session證據確認成本0。六項必要測試通過，原版已备份；未修改訓練來源，也未採用先前錯誤補丁。模糊的其他旗艦名稱使用者答覆 nvm，維持 Space Bunny。


## 2026-10-12 20:06 同時間點遙測分析
- 本輪使用量實讀五小時剩26%、週剩72%，自然重置20:30:26；只做既有資料的小範圍檢討，沒有新模擬/訓練/外部模型呼叫。上一輪最高effort啟動器與真實session驗證屬實質進展。
- 3000個合法10Hz樣本：高bank瞄準樣本198個；其中bank误差<=5度的62個仍有yaw/LOS同時刻差中位12.86度/秒，load絕對值中位0.73。這提供優先校準turn/load、暫不採roll PI的新線索。有限差分yaw與Euler換算的差中位0.0053、p95=0.0915度/秒。
- 原始telemetry/result/original_result SHA前後不變；圖表已視覺核對。完整分析、限制與下一項校準規格在experiments/precision_probe/tracking_analysis/。不把取樣比例當攻擊時長，不宣稱因果、勝率或已完成FDM校準。


## 2026-10-12 20:18 校準工具草稿與必要修正
- 本輪開始五小時剩20%、週剩72%，未啟新模擬/learner。Space Bunny max原三檔同授權草稿第一次缺code；一次有理由重試後交付code，實際模型max/cost0，來源不變。
- 草稿經本地核對發現yaw換算錯、暖機未記錄、mode只設一次等量測錯誤；已隔離修正，六項mock契約測試通過。初次test因sandbox temp權限而失败，移至明確可寫workspace temporary dir後通過。不是FDM或性能驗證。
- experiments/turn_calibration/保存reviewed worker、adapter草稿、tests、README/latest；parent supervisor尚未實作，ready_to_execute=False。下一次即時額度>=35時補齊父層硬界線/來源/身分，再執行7個命令通道校準；不追加相同SAC，也不把最高effort當正確證明。


## 10/12 20:50 真實校準完成與單因素戰鬥比較

- 原7案例及追加3案例均實際退出0，共21000個60Hz自機tick；兩者initial/warmup SHA一致，重複bank70的所有物理與指令欄逐值相同（排除wall_s）。仍是12000ft、320CAS的短命令校準，不是勝率。
- 最後5秒轉向中位：70/nose0=6.039度/秒，80/nose0=10.421；80/path_alpha=9.884。80/nose0高度最低3028.33m、abs load最高3.621，無guard；掉高度較多，需要完整戰鬥評估。alpha診斷不能直接當瞄準補丁。
- 新候選只提高近距離<1100m bank上限72→80，其他指令控制、G/高度保護、trim、俯仰、速度、遠距離設定不變。單因素來源还原及50個遠距指令相同檢查通過，沒有SAC或新learner。
- experiments/near_bank80/run_20261012_2050：原開發12個開局、guide/candidate共24完整場，每場150秒、全部40分鐘上限；來源與XML模型資料凍結，初始SHA配對核對。運行中不可修改來源、重啟或升級。
- 當日保守運算預留5.75h/6h；本比較後剩15分鐘，今天不再追加研究型訓練或完整聯賽。每日6h不可透過換run重置。


## 10/12 21:05 bank80完整比較與決策

父程序4460實際退出0，24/24完整、12對初始SHA一致、原guide12場初始/結果/步數精確重現，原Python來源与凍結紅方一致，新FDM XML也固定。COMPARISON.json verified_comparison=true。

近距離上限72→80的唯一改動：candidate12場4擊落、13.5秒有效攻擊；guide12場3擊落、10秒，兩者0被擊落/墜機/過9G。Rule3/6→3/6，RL0/6→1/6；rule/3000正常新增擊落、鏡像失去擊落，RL/6000鏡像新增擊落。分對手結果與paired_attack.png已保存。

安全檢討仍必要：candidate最低764.48m vs guide777.94m。RL新增擊落終點處於recover，不足以證明精準瞄準修復。rule鏡像回合原guide提前擊落，全部回合最低高度差-732.84m有暴露時間差；共同229.32秒的1Hz抽樣最低高度差仍-230.08m。RL低高度抽樣均在recover，candidate一些case低於800的列更多。1Hz列數不是精確持續時間；正式Host邊界/碰撞尚未驗證。

決策：有潛力的凍結開發候選，等待新開局與安全驗證；正式部署保留repair_guide。來源/XML及報告已拷貝SHA核對到candidates/near_bank80_20261012，這是審計快照而非已完成可部署離線套件。NEXT_VALIDATION.json待新日預算驗證24場，接著實作4對手聯賽、未見保留集与官方Host至少6回合。今天預留5.75h/6h，沒有額外新learner或再掃參數。


## 10/12 22:45 新開局驗證工具準備完成

experiments/fresh_bank80/已建立候選完全相同的新評估副本、launch_fresh.py與verify_fresh.py。每日預算依Asia/Taipei日界線登記，必須先扣40分鐘，尚餘不足即拒絕；跨午夜不足40分鐘不啟動，失敗與換run不能重置。seed_registry.json整合專案case inputs七個已觀察種子、另保留六個未執行holdout種子；此範圍不證明全歷史訓練未見。新開局擬定2026101300等六個seed，首次嘗試即登記為開發/已消耗。

十項必要閘門檢查通過，含實際OS鎖第二程序拒絕、低額度/不完整/初始SHA/已見或holdout seed拒絕、AccessDenied未知、合法与非法父子身分。原run_worker、reset、metrics、timeout AST與10/12版本完全一致，候選bytes與凍結快照一致。合法父子測試使用mock執行，沒有FDM；新worker成功FDM路徑與新開局表現仍待執行。check-only已實際確認今日5.75h不足再預留40分鐘，沒有訓練或模擬啟動，原已完成比較不變。

最初暫存目錄權限與子程序UTF8問題已修正；相關失敗與修復寫PREPARATION.json。下一輪使用工具入口，先讀即時額度與新日預算；不要再手工改凍結10/12程式。完整驗證後才進對手池/保留集/官方Host。


## 10/12 22:50 排程時區校正與一次驗證

原排程的時間欄被工具按UTC解讀。以截至10/13台灣時間00:36的一次時間窗驗證：本地00:35字面設定沒有未來執行而被拒絕，UTC16:35設定被接受。Windows也確認為Taipei Standard Time。現已將低頻監督與每日檢討的時間欄轉為UTC，保存後換算結果為原定台灣00:30/06:30/12:30/18:30與20:35，不再用本地時間字面填入工具。

新一次排程ai-4「AI飛行員：新開局驗證」於10/13台灣00:35執行，僅有這次有效時間窗。讀新日預算與即時額度，符合門檻才執行24場/40分鐘；完成或不再需要時刪除此一次排程。其他執行已啟動/完成同trial則不重複。ai-3舊reset一次排程維持PAUSED。所有时间與API驗證範圍記入PREPARATION.json；實際執行仍需電腦/程式/檔案及權限可用。


## 10/12 23:04 已保存軌跡檢討

四場既有CSV/ACMI對COMPARISON的SHA核對與逐tick對齊完成，原始檔分析前後未改、零新增FDM。失去rule擊落的候選在1秒已偏移姿態；158秒guide誤差26.84度、candidate51.98度，之後candidate未再出現1100m內抽樣，而guide最後接近並擊落。新增RL擊落在154秒track已累積2.983333秒攻擊；184.1833秒recover只完成剩餘一個60Hz tick。這補充終態安全檢討，仍不能證明瞄準一般化，低高度需驗證。

證據：experiments/near_bank80/saved_trajectory_review/ANALYSIS.json、REVIEW.md、aligned_samples.csv、paired_trajectories.png、early20s.png。保持現候選與新開局工具凍結。待新開局结果後才決定是否測唯一因素「bank80增加機首<45度資格」，不能同時改俯仰/trim/安全。這項假設尚未實作或測試。


## 10/12 23:16 四種凍結對手工具準備

experiments/opponent_pool/為隔離副本，rule、凍結RL、repair_guide、只降低遠距bank上限72→60的rule_bank60。72配對/144場、36個新開發seed，全部2h、每日仍6h。只有fresh_bank80完整驗證與基於證據的SAFETY_DECISION.json通過，且即時用量/來源/程序/預算閘門允許，才可啟動。11項離線檢查通過，含原helper AST、原候選bytes、變體唯一常數、真實控制器合法指令、配對/RNG初始、實際父子mock、前置決策SHA。沒有FDM、learner或新seed登記；正向worker仍待真實FDM驗證。最初AST縮排失敗已修正後凍結。check-only確認今天5.75h不足2h、fresh前置未完成，不啟動研究。

已有POOL_FREEZE來源/XML/模型清單、launch_pool.py、benchmark_pool.py、verify_pool.py與README.md，不再從零實作或改凍結fresh工具。先等10/13新開局實測與安全檢討，之後選擇擴充驗證或換方法；正式部署仍repair_guide。


## 10/12 23:36 原引導器離線回退套件

deployment/repair_guide_portable_20261012帶Python3.10.21、NumPy1.26.4與原控制器，2115檔SHA；控制器類別與RoundState AST不變，只有匯入路徑/不使用的模型分支/可選wall timer與隔離啟動旗標改動。原路徑與含中文空白另一副本都實際自我檢查退出0，實際Python模組與DLL無原Conda依賴；兩個private-loopback Player退出0，120個有狀態輸出與原guide一致、INIT/READY/重複/無效/缺OBS/重啟通過。zip CRC通過。初次ignore_environment旗標檢查失敗已保留log並修成明確-I-S後驗證。

這是回退Player套件，不含bank80、SAC、JSBSim或訓練；尚未驗證另一電腦/LAN/官方Host新回合。歷史Host一回合原CSV/ACMI SHA重新核對，不能算此可攜包Host驗證或當新六回合。HOST_PROTOCOL.json固定目前Host exe/Setting/readme SHA及P1 ports。封裝與部署驗證保守預留10分鐘也列入每日6h；當日合計5.916667h，不退款，未增FDM/Host研究。fresh/pool候選及正式部署未改。報告：deployment/portable_guide_verification_20261012/PREPARATION.json。


## 10/12 23:51 Host完整性小修補與自然重置排程

目前即時用量較低剩餘33%，依15–35%只做小範圍處理。舊Host collector把GAME OVER記錄在結果但未列進完成checks，新增diagnostics/audit_host_evidence.py作後續必要稽核；沒有改歷史原始檔。既有一回合CSV/ACMI/log/終態重新核對通過；7項反例與去重檢查通過，缺GAME OVER、CSV/log勝方矛盾、短未裁決場拒絕，同一session六次只算一次。舊session未保存validation_exit_code與Host Setting SHA，保留未知，不能自動用它通過新的六回合固定來源門檻；仍承認它是已完成的一份公告Host回合證據。新Host回合0、FDM0。1分鐘驗證預留列入當日額，合计5.933333h/6h。

五小時自然reset為10/13台灣01:30:34；原ai-4台灣00:35會早於重置且目前33%低於啟動門檻，已原id更新為台灣01:35的一次時間窗。原prompt、thread與ACTIVE維持，新增真實用量/重置說明，保存RRULE/prompt/thread讀回一致。執行時仍重新讀用量與10/13預算，已有同trial不重啟。日期/時間證據寫schedule_latest.json與fresh_bank80/PREPARATION.json；其他研究來源未改。

後續Host結果必須經此auditor，再使用固定來源/Setting、實際退出觀察、獨立session與完整CSV/ACMI/log形成至少六回合門檻；尚不是參賽認證或穩定勝率。正式部署仍repair_guide。


## 10/13 00:03 使用者進度入口小修正

即時較低剩餘24%，僅改人用查看競賽進度.cmd，另建唯讀status_campaign.py；舊入口只看已停止SAC且候選標記寫死。新入口讀研究/訓練/當日預算/保存排程，核對PID、建立時間、命令；AccessDenied標無法驗證。完整報告與24場/12配對、實際退出0才列成績，並標開發集非正式勝率。真正啟動腳本實際執行通過；不完整配對與未知退出反例拒絕。原cmd已備份，runner/fresh launcher/pool freeze/COMPARISON四檔SHA前後一致。未啟FDM/learner或改正式部署。證據diagnostics/status_refresh_20261013.json。


## 10/13 00:10 Host稽核欄位與原始資料去重小修補

即時最低剩餘22%，只補既有Host證據閘門。非空雜湊原本可能接受yes，現要求非空來源mapping與每個64位hex SHA，退出碼必須實際int0而非bool；同CSV即使改session身分仍只算一回合。歷史真實CSV/log/ACMI仍有效，新六回合門檻仍拒絕未知setting/exit。反例與合成合法metadata/六份獨立CSV聚合分支通過；合成資料不算Host證據。歷史檔SHA前後一致、零Host/FDM/learner。雜湊格式不等於來源證明，下一步仍須新session事前設定/來源保存與實際退出觀察。原稽核程式已備份；證據diagnostics/host_strict_metadata_20261013.json。


## 10/13 00:15 官方Host啟動前設定保存

最低即時剩餘21%，只完成小範圍證據保存補丁。diagnostics/launch_host_recorded.py為原launcher隔離副本，Popen AST與cwd/命令保持原樣；先保存Setting.txt bytes/SHA與Host exe SHA，再啟動，立即核對原設定與exe未改並記inputs_before_launch/launch。原launcher、Host、Player與歷史回合不改。啟動官方Host並保存設定.cmd為新增人用入口。check-only實際退出0、沒有開Host/GUI/FDM或新session；不代表真正Host啟動/讀取設定已驗證。新session的Player來源核對與collector實際退出觀察仍待接上。證據diagnostics/host_prelaunch_capture_20261013.json。


## 10/13 00:15 新Host回合來源與收集退出碼接線

最低剩餘20%，補隔離start_host_player_recorded與collect_host_recorded。新Player要求v2啟動前setting/Host SHA並保存contract source copies；Popen AST原樣。標START只代表操作員界線，不冒稱UI觀察。collect以Popen.wait真實退出碼寫receipt，unknown不當0，前後檢查來源與設定，接既有Host audit。真實CLI拒絕當前舊launch/session，沒有開Host/Player或改歷史；兩個synthetic子程序實際退出0/23驗證wait。正向新Host流程仍待實際GUI/回合，不能算六回合完成。證據diagnostics/host_capture_bridge_20261013.json與HOST_CAPTURE_README.md。


## 10/13 00:18 Host快照與實際退出紀錄接入稽核

剩餘18%，只完成證據閘門接線。新Host launcher保存exe bytes/SHA，Player入口另存該launch JSON/Host exe以及contract sources；collector保存收集源碼與輸入session SHA、actual wait退出、PID/建立時間與時間戳。稽核實際核對setting/player/source/exe bytes、啟動前時間、回合綁定退出receipt，缺漏或變動不算六回合。六項必要檢查通過（其中完整資料僅synthetic），歷史真實artifact仍有效且無新六回合資格；沒有開Host/Player/FDM。正向新GUI回合、另一PC/LAN和六回合仍待驗證。新工具只使用repair_guide；不得當bank80或可攜包Host認證，實際執行前仍需額度/當日預算/單一研究/安全門檻。research_latest已記工具與報告路徑，後續不要重做工具。


## 10/13 00:18 新日實際啟動前核對

launch_fresh.py --check-only實際退出0：候選與runtime SHA通過、六個擬定開發seed合規、10/13目前0h預留可容納40分鐘、日期與當日wall-time充足。只做preflight，沒有建立預算ledger、消耗seed或FDM/learner。較低即時剩餘17%，仍小於35%研究啟動門檻；自然reset epoch1791826234（台灣01:30:34），ai-4維持01:35執行時再讀額度及所有真正啟動門檻。原比較與正式guide未變。證據diagnostics/fresh_preflight_20261013_0018.json。


## 10/13 00:24 報名入口與文件準備

即時剩餘15%，只做行政準備。官方defense-ai.tw/competition重新讀取確認10/21截止，AI飛行員入口為portal/index?track=ai-pilot，本次web被導登入頁，不能據此判斷使用者瀏覽器是否已登入。公開需身分證正反面/學生證，登入表單欄位尚未核對；官網4人文字與使用者已確認单人授權分開記錄。REGISTRATION.md與registration_latest.json已記入口、文件、完成證據門檻；尚未填送或上傳證件，原10/17與10/20提醒維持。此行政核對零FDM/Host/learner。


## 10/13 01:54 新開局24場實測與完整核對

同一工具session12692觀察到實際退出0，24/24完整與12個公平配對；verify_fresh實際退出0，來源/紅方/initial SHA及CSV/ACMI通過，verified_comparison=true。候選仍是原凍結bank80，未使用actor或開learner。新seed首次實測後為開發集，不是保留集。

| 對手（各6場） | 原引導器擊落／攻擊秒 | bank80擊落／攻擊秒 | 安全結果 |
|---|---|---|---|
| rule | 2／6.0 | 3／9.0 | 兩者無墜機、被擊落或過9G |
| RL | 0／0.6333 | 0／2.55 | 候選新增過9G 0.0167秒（1個60Hz tick） |

總計引導器2/12擊落、6.6333秒；候選3/12、11.55秒。兩者0被擊落/墜機。最低高度770.84m對765.15m；5個RL配對最小高度下降4.19–30.50m。RL全12場皆完整300秒，不能以rule平均掩蓋RL安全退步。

新增過G在RL6000鏡像candidate。1Hz CSV累積計數於244–245秒上升，抽樣模式由track轉recover，高度818.55→783.98m；抽樣最大load7.309並不是實際瞬時峰值，不能据此刪去60Hz已記下的過G。瞬時峰值、精確tick與模式仍待隔離診斷。

判定reject_promotion：metric通過，outcome_safety與per_opponent不通過。正式部署維持repair_guide，擴充對手池前置不成立，沒有進保留集或官方Host。原開發4/12對3/12及recover擊落不能當新種子一般化成功。每日檢討先定位瞬時過G，再選單因素安全方法；不重跑相同24場或放寬門檻。

當日預留40分鐘/6小時，實測wall812秒；預留不退回。證據：experiments/fresh_bank80/run_20261013_013609_5218/COMPARISON.json與SAFETY_REVIEW.json。

報名仍未完成，已確認可單人；10/21截止，準備見REGISTRATION.md。可攜原guide與新Hostcapture工具已備，但另一PC/LAN與至少六個官方回合仍待真實驗證。


## 2026-10-13T11:50:31.154361+00:00 Host GUI actual attempt
Computer Use sky available, launched unchanged Host/P1, INIT and both READY/GO observed. START not verified; remained STOPPED. Inter-step wait exceeded one-hour deadline; preserved partial evidence, zero completed rounds, verified-owned process cleanup. Conservatively charge full attempt elapsed time; no new research today. Need autonomous deadline watchdog before next attempt; no host/package/candidate promotion.


2026-10-13T11:54:19.898100+00:00 monitor: found owned internal-P2 descendants 8236(parent23036) and20040(parent8236). Exact create/command/exe/archived parent verified before terminate; both confirmed exited. Preserve conservative elapsed daily charge through final descendant cleanup; no research restart. Independent watchdog must include verified descendants, not only Host GUI/launcher/P1.


## 10/13 23:41 10/20方案與Host watchdog工具

使用者將Codex五小時窗改成警告而非停止門檻；較低剩餘<=10%時轉用已驗證免費OpenCode處理授權範圍內的審查／整理。本地run仍保留單程序、來源SHA、STOP、資源與硬deadline。新增WIN_BY_1020.md：10/19晚間go/no-go，10/20可靠性期限；研究分支包括多樣凍結對手＋鏡像self-play、JEPA類數值世界模型、Qwen 4B低頻戰術選擇器。三者都不能繞過60Hz安全控制或公平比較。

Host可靠性先行：新增host_watchdog.py與arm_host_watchdog.py，實際launcher現在要求watchdog token，Player入口會核對watchdog PID/建立時間/命令。watchdog先於Host啟動，追蹤本次token的Host、P1及Host子孫，STOP/deadline/collector終態時按深度收尾。AST 4檔通過；check-only退出0；兩個mock身分測試通過（精確身分會停止，命令變更拒絕停止）；獨立deadline smoke在約1秒後真實退出0並寫receipt。尚未執行新的Host GUI/START或內建P2正向路徑，不能算Host驗證。


## 10/13 20:34 每日檢討（運算預算已達上限）

即時剩餘93%，但當日實際保守計帳6.5676h/6h，兩個門檻需同時通過；本次未啟動訓練、評估、校準或恢復。fresh24完整比較與Host失敗都已檢討/通知，不重跑。先保存下一個允許日的具體順序：Host啟動前須獨立deadline監督並涵蓋已核對內建P2後代；其後才用已看過的RL6000鏡像guide/candidate兩場（300s/場、20min預留）做60Hz觀察解析，唯一變更為記錄精度、原控制法byte不變。先重現原結果和counter，再定位244–245s過G，之後才能選單因素安全候選。工具尚未實作或執行；不是新結果或保留集。計畫diagnostics/daily_review_plan_20261013.json。

## 2026-10-14 00:38 台灣時間：新 Host 回合證據缺口

- 公告版 Host 實際完成提前裁決：Player1 勝、HP 180 對 0、116.633 秒、6,997 列、雙方 0 過 G。
- CSV、ACMI、來源/Host/設定快照與 collector 真實退出 0 均核對；watchdog 完整停止自己建立的程序。
- 嚴格稽核唯一失敗是主要 Host stdout 沒有 `[GAME OVER]`。Player2 runtime log 顯示 Host 轉為 STOPPED，但本輪啟動前沒有把該 log 納入 receipt，因此本輪不計入六場門檻。
- 下一步：把獨立終止佐證納入啟動前 receipt 與 collector/audit，測試後以相同 repair_guide 跑新回合。

## 2026-10-14 06:33：Host自動收證通過與60Hz診斷

- 第一個新固定來源完整Host回合通過所有稽核，1/6：repair_guide、P1勝、HP180:0、94.933s、5695列、0過G。CSV/ACMI/來源/設定/終態P2事前收據核對，auto collector退出0、watchdog實際退出0並完成自建程序清理。主要stdout仍無GAME OVER，使用啟動前已記錄且與本次子程序/初始位置/CSV綁定的P2 STOPPED收據。
- 6000ft（1828.8m）RL鏡像原case兩場各18000tick，逐tick與原initial/final metrics/counter一致；worker退出0，驗證器退出0。supervisor本身退出碼未觀察，明確不補0。
- 候選峰值9.0812036G在tick14692、244.8667s、recover、高度787.58m；guide峰值6.5700807G。實際輸出升降舵仍-0.5015，前幾格因absG跌回8.5以下使限載分支解除；slew每格0.08只改目標，因果修正仍待實驗。
- Space Bunny max/實際cost0審查完成；採納slew與無hysteresis為待測假設，拒絕未查JSBSim符號就把負signedG當bunt，以及mock低速錯觸energy_recover等推論。
- 下一步：五個新Host固定來源回合；隔離候選只新增8.5啟動/8.0解除的g保護latch，先開發重現與新種子公平比較，再決定擴池。正式repair_guide不自動替換。

## 2026-10-14T06:40:43.464663+00:00：固定來源 Host 2/6

- winner=1.0、HP 180.0:0.0、83.15秒、overload=0.0；自動collector/watchdog真實退出0、全部精確自建程序已清理。
- 所有已計回合重新稽核，固定profile与raw round身份核對；證據 E:\ai_pilot\autopilot\combat_fix\official_validation\host_20261014_143645_bedc。

## 2026-10-14T06:45:26.175584+00:00：固定來源 Host 3/6

- winner=1.0、HP 180.0:0.0、114.617秒、overload=0.0；自動collector/watchdog真實退出0、全部精確自建程序已清理。
- 所有已計回合重新稽核，固定profile与raw round身份核對；證據 E:\ai_pilot\autopilot\combat_fix\official_validation\host_20261014_144142_d414。

## 2026-10-14T06:50:03.984385+00:00：固定來源 Host 4/6

- winner=1.0、HP 180.0:0.0、145.183秒、overload=0.0；自動collector/watchdog真實退出0、全部精確自建程序已清理。
- 所有已計回合重新稽核，固定profile与raw round身份核對；證據 E:\ai_pilot\autopilot\combat_fix\official_validation\host_20261014_144542_1cca。

## 2026-10-14：G保護latch兩場真實比較

- 單因素8.5G啟動/8.0G解除，同初始SHA、固定原RL、2×18000tick、兩worker/parent/guardian/verifier真實退出0，未修bank80原metrics完全重現。
- 基線峰9.0812G/過G1tick，候選8.7381G/過G0；0擊落/0被擊落/0墜機。attack1.45→1.0667s（-26.44%），min高度775.7045→775.1043m（-0.6002m）。
- 決策：已知開局過G消除，但攻擊取捨與泛化未證；不得部署或稱勝率提升。下一步凍結候選，使用新開發種子做repair_guide配對比較，逐對手與最差case檢討。

## 2026-10-14T06:58:48.054754+00:00：固定來源 Host 5/6

- winner=1.0、HP 180.0:0.0、169.2秒、overload=0.0；自動collector/watchdog真實退出0、全部精確自建程序已清理。
- 所有已計回合重新稽核，固定profile与raw round身份核對；證據 E:\ai_pilot\autopilot\combat_fix\official_validation\host_20261014_145407_177e。

## 2026-10-14T07:03:13.778497+00:00：固定來源 Host 6/6

- winner=1.0、HP 180.0:0.0、133.717秒、overload=0.0；自動collector/watchdog真實退出0、全部精確自建程序已清理。
- 所有已計回合重新稽核，固定profile与raw round身份核對；證據 E:\ai_pilot\autopilot\combat_fix\official_validation\host_20261014_145849_e0c5。

## 2026-10-14 15:05：新24場開發比較啟動

- baseline真正純repair_guide，candidate固定bank80+G latch；rule/RL×3距離×左右，共12pairs24場，新seedbase2026101400是開發集。
- 已保守預留40分鐘、seed標attempted，獨立guardian已武裝並持有parent wait handle；PID/建立時間/完整命令與固定來源核對。運行中不改來源、不重啟原seed。
- 假設：已知開局安全改善能保留，同時仍勝過純guide；反證門檻包括任何candidate過9G、分對手擊落/死亡/墜機退步，逐對最低高度退步要review，絕不自動部署。

## 2026-10-14：24場完成與補充完整性稽核

- 唯一研究變更為bank80候選的8.5/8.0 G latch。24/24、12配對、固定149來源/紅方與初始SHA；parent、24worker、guardian真0，verifier與POST_AUDIT通過。保留40分鐘預留，實際wall 922.9875664710999秒，不退款。
- rule擊落1/6→3/6，RL0/6→0/6；attack合計4.3333→14.0667秒；雙方0被擊落/墜機/過9G。五個高度退步，最差rule3000鏡像共同300秒低319.318m（CSV HSL；原judge AGL低319.317m），候選latch0tick，不能歸因latch。
- 決策metric_pass_safety_review_pending，正式repair_guide。下一步先研究保存高度取捨與RL攻擊不足，禁止重跑已完成24、把已看seed稱holdout或自動部署。
- 對手smoke首次真FDM partial：兩完整300tick、第三worker1、parent2、guard1；guard.log為WinError5 atomic replace，已交本地executor修復。15分鐘預留保留、12seed不重用，未宣布24完成或self-play勝率。

## 2026-10-14：對手guard單案整合檢討

- v3單案 run_20261014_202846_6d8021，launcher真exit15、supervisor15、guard2；無worker/result/report，無FDM。原新seed2026102501及1min預留保留，不重用。
- 已核對CIM：guard讀到3112為svchost高祖先，不在owned supervisor下；查所有parents身份造成不必要AccessDenied。只在v4限制祖先核對至確切owned target，target以下未知仍拒絕。無ai_pilot相關Python/Host殘留。
- 保存高度分析已證worst尾段270–300s沒有80度binding；不能宣稱瞬間nearbank因果。RL9000mirror166累積攻擊tick、四段均因角度出1度退出，judge門檻180且不重置，差14tick。唯一下一候選假設near cap80→75，保持G latch/所有安全；仍待已知反事實診斷和新的開發比較。

## 2026-10-14 20:34：guard範圍修復與真FDM單案通過

- v4新seed2026102601，rule6000normal，300tick，actual launcher/parent/worker/guard/verifier0。VERIFICATION errors[]、verified_single_case_diagnostic=true，未完成24或左右pair、不計self-play聯賽/勝率。無存檔錯誤，guard wall2.687s，supervisor_missing代表身分已消失；parent退出0來自launcher wait，不由missing推定。
- v4完整來源新契約與CSV/ACMI核對；原partial及v3失敗保留，不退款/重用seed。下一v5新12seed完整短批，portableHost仍未launch；80→75既有開局單因素診斷工具準備中。

## 2026-10-14：鏡像與四對手短批完整通過

- v5 run_20261014_204421_9a31c4：24case/12左右pairs/12新開發seed，rule/RL/repair_guide/rule_bank60各6、selfplay6、總7200tick；launcher/parent/24worker/guard/verifier真0，SHA/逐tick有限commands/CSV/ACMI/獨立control/RNG通過。15min預留保留。
- 這是每場5秒接口與初始物理短測，不是完整戰鬥/自我對戰訓練或勝率；後續須完整凍結對手联賽。
- portable v1已連線實際完成103.767s/P1 raw勝/6225CSV rows，但collector2/guard2且freshP2 identity schema不匹配，cachedHost子孫未完整捕捉，不計套件6場門檻。Windows observer真exit2、CIM無殘留；v2新來源修復準備中，原failed raw完整保留。

## 2026-10-15：LINE最新規則與並行訓練異常

- 使用者LINE匯出10/14管理員回覆：START第一幀累積；事件優先collision>crash>kill>timeout；三維距離<15m立即碰撞終止；1度及500/3000ft邊界包含；姿態X軸；固定權重30000/10000/100/1；正式state2限定，自訂connector允許。這是提供的匯出證據，未獨立主辦即時查證。
- 凍結base config的參考weights2000/1000/10/1000、2度預設、50ft crash及未建碰撞不能標正式一致；目前campaign顯式1度override仍有效，不改既有SOURCE/hash；下一版需独立規則契約和正式winner/timeoutadvantage。
- new win_loop3份及m4 learner3份PID/create/cmd/CIM/TRACE已核對，全部default實驗m4_tactical相同output；shared progress不能作單一learn進度，同path模型暫不verified。來源所有權啟動記錄未確認，本輪未停止/改active source/開新FDM，已請使用者確認整理成一份繼續並寄Gmail去重通知。
- near75原start之supervisor真exit1、wait_reason workload_overlap，STOP及failed before worker；guardian真exit未觀察，不補0。原20min預留/knowncase試驗保留，無比較/學會證據，不能整輪重啟。

## 2026-10-15 06:32：共享訓練終態與隔離保存

- CIM/psutil核對：原三個m4 learner已不存在，三個原win_loop PID/create/cmd仍活且queue=[]。沒有自行停止/重啟；learner消失本身不能證明退出0。TRACE有三筆completed/exit0但step_id共享、end不含PID，不升格成逐PID完整退出收據。
- 已隔離保存9個ZIP checkpoint及progress，共10份；來源/副本SHA一致且9ZIP CRC合法。只讀SB3 JSON metadata，未unpickle/reload/evaluate；各檔最後writer不明，不能稱精確續訓、成功戰鬥或部署候選。
- legacy日誌計時已按台灣日回補，並行副本各計入、不退款；本日累計 7.6456h，超6h僅警告。現有整理確認仍待使用者回答，當前只需整理三個idle loop，沒有活learner可保留或停止。不重寄同一Gmail通知。


## 2026-10-15 12:36：portable v2 隔離靜態驗證

- 原因：v1 原始回合完成但 P2 收據鍵值與 cache 子孫範圍失敗，不計成功；檢查已存在的隔離 v2 修復，不改原包或 v1。
- 包內 runtime -I -S -B 執行18測試，真退出0，unittest報26.113秒；來源與本地vendor已凍結。包含實際無害Python exit7 handle等待，其餘為mock/舊證據讀取，沒有新Host、FDM或learner。
- 覆蓋自建root下cache Host/P2直接祖先、事前binary SHA、外部同名排除、漏捕/改bytes/重用PID/AccessDenied/缺exit收據拒絕；v1仍不合格。
- 結論：只通過靜態邊界檢查，未驗證v2真實Host收證及清理，不部署、不當作package6/6。
- 程序仍三個已核對idle loop、queue空、無learner/Host，既有人工整理確認未回覆；不重問/不寄第二封。下一步待同意且重核對後整理，再fresh preflight與實際portable Host。


## 2026-10-15 23:13：原排程身分已不在，preflight未完成

- 原8040/15644已查無，20448已為不同建立時間的其他程序；原三個loop均無相符存活身分，沒有由本輪停止任何程序，原退出碼未知，禁止依舊PID清理。queue空、無campaign Python殘留。
- portable v2包內runtime只讀check在45秒上限未完成，由本輪subprocess逾時清理自己啟動的check；未啟Host/FDM、沒有完整preflight report，不宣稱新來源檢查通過。既有18項靜態結果保留。
- RAM抽樣2.02→2.89GiB波動，不改資源門檻；新run既有確認閘門保留。下一步只讀定位preflight慢點，再作有界修復，不自動重跑相同比較或部署。


## 2026-10-15 23:20：使用者指定接續 OpenCode 成果

- 唯讀檢視 OpenCode SQLite 的 Defense AI Pilot training setup 對話，最後相關請求為本地慢速RL；沒有新外傳。舊資料庫與 win/、模型均保留。
- 找到 M3 run1 9/54失敗、run2 90/90、run3_perturbed90/90、run4_4actor180/180報告。不同actor各cell種子無重疊，無完整runner訓練當時凍結，保留探索資料，不當公平配對或職業隊伍勝率。
- M4關鍵API錯誤已靜態重現：預先StationController.act後，把cmd送入期待residual的parent.step，導致20tick共40次act。隔離v2改成只設定tactical，再由parent對零residual呼叫一次，20tick20次。
- 同時修同一API契約的步進後裁判計數/明列reward、每回合seeded對手抽樣、reset鏡像狀態、guard觀測、on_step終局統計。11項實際方法+fake physics測試真0，沒有新FDM或learner。不是安全動態、訓練或勝率證據。
- M2 regate的promote語義明寫前進鏡像測試，不是部署，採納此界線；高度取捨記錄保留，不把所有舊對手說成直線靶機。
- 原三個loop均無相符存活身分，舊整理問題已無需停止目標；使用者要求keep後接續隔離工作，不再以此過期確認阻塞。舊PID20448已重用，絕不可按舊PID停止。
- 下一步：獨立deadline單例M4 worker與真FDM介面短測；正式collision/crash/event/timeout score契約，再同初始SHA公平小比較及有限新訓練。portable v2前置檢查45s逾時仍未解。正式repair_guide，不重跑已完成批次。


## 2026-10-15 23:29：M4 v2真FDM介面短診斷完成

- 假設：修正版每60Hz tick只執行一次StationController.act、實際sendAction與該輸出完全相同，父裁判post-step計數傳至戰術層；相同seed reset清空狀態。控制固定零戰術向量，沒有新learner/策略搜尋。
- 新隔離m4_interface_v1，沿用v5 byte-identical獨立guard演算法並擴充exe/parent身份；8項靜態閘門測試真0。OS lock/STOP/2GiB RAM/10GiB disk/來源與紅方XML凍結/種子registry/每worker45s/全體180s硬限通過。
- run_20261015_232701_f27ecd：rule/mirror/frozenRL各一worker，每worker同seed reset兩次、每次300tick，共1800個自機60Hz tick。三個新開發seed2026103100..3102已attempted；不是holdout/公平戰鬥聯賽。
- launcher/supervisor/3worker/guard/verifier全部真退出0。VERIFICATION errors[]，3類初始/final SHA逐次完全重現；每tick act/send/judge=1，實際輸出誤差0，無P2 fallback，CSV/ACMI與來源核對通過，無自建程序殘留。
- 限制：每次只有5秒，全部攻擊tick0，非零攻擊累積路徑尚未由此FDM驗證；沒有完整戰鬥/勝率/學會/官方契約證據。正式仍repair_guide，訓練CLI仍拒絕無監督啟動。
- 預留3分鐘保留不退款，今日ledger7.6956h（6h僅警告，已縮成短診斷）；實際wall見report。下一步正式judge契約與非零counter/Gym callback路徑、單例有界訓練worker及小配對；不重跑本批。


## 10/15 新版裁判契約與來源核對

- 前一goal turn分類為progress：完成1800個真FDM介面tick、全部真退出及完整核對；本輪未重跑該批。
- 主辦正式下載端點取得AI空戰飛行競賽公告文件_1008.pdf，ZIP CRC與PDF SHA已保存。視讀相關第7–10頁：新版權重/kill倍率/距離Pt/50m與15m均核對，PDF的2度與10/14群組管理員1度答覆不一致，保留具名profile，採較新1度做研究但不宣布Host正式一致。
- 新experiments/rules_v20261014/judge.py隔離實作START/當幀結算/Collision>Crash>Kill>Timeout/180累積tick/10000*Tatt-100*TG+rawΣPt/30000*(1+(300-Tkill)/300)/timeout及同時擊殺優勢勝負。22純數值事件測試真0。
- replay_blue_counter.py唯讀重算兩個已保存真60Hz藍方軌跡，共35317列，166與180tick完全重現、589個每秒/終態檢查點相符。2度前綴門檻較早，僅列差異，不是新2度完整回合或勝率。
- 舊資料缺red完整60Hz狀態，不能偽造全S_advantage；AGL/HSL基準、位置因子500/1500m端點、非碰撞雙墜機與取消擊落顯示分仍明示未確認。沒有新FDM/learner，不增加訓練/評估預留，不部署。
- 下一步：新M4 adapter整合裁判與完整雙方逐幀遙測，有界非零/事件FDM診斷，同初始SHA小配對及有限新訓練。portable preflight45s逾時仍保留。


## 2026-10-16 00:20：新裁判接通，暴露追瞄符號問題

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


## 2026-10-16T11:48:43.089416+00:00 GitHub CPU Player交付

使用者要求另一台PC可從GitHub下載。已建立私人repo並發布36,256,095bytes ZIP；遠端asset digest與本機SHA一致：ba42890cc6de6d615ef79634c078d13c9f31929454e40598897f9f2f7069b047。2115基準檔逐檔核對、主PC新解壓probe實際退出0/p99 0.422ms；未修改原套件或controller。僅新增外層操作文件，移除主PC範例報告；無官方Host、訓練模型或個人遙測外傳。初次suffix掃描遇NumPy原廠測試CSV/PKL拒絕，核對manifest後僅容許該vendor tests/data，非研究資料。GitHub發布與寄信已完成，ASUS實機及LAN仍待使用者執行。發布頁：https://github.com/poopro/ai-pilot-cpu-player/releases/tag/cpu-player-20261016；Gmail message 1a1448a9a3633688。無新訓練/FDM。


## 2026-10-16T15:11Z 保存資料退步診斷

GRID_REGRESSION_WINDOW_REVIEW_20261016.json：四份原CSV SHA固定、命中逐tick重算一致，補共同曝光時間避免舊模型提早擊落造成偏差。兩退步case首次控制分歧皆只在油門，當時記錄observation SHA相同；尚不能推論後續失準由油門造成。鏡像3000新模型射程內時間較多，卻只有2tick進1度窗，優先假設速度/能量戰術影響瞄準窗保持，後續須隔離單因素驗證，不掃參數/不盲續訓練。分析真exit0；無FDM、無模型推論、無新訓練。程序盤點未見campaign runner，RAM約5.94GiB。ASUS待新實機報告，GitHub交付已通知，不重寄。


## 2026-10-16T15:14Z 真CPU工廠探測：RNG隔離未通過

獨立watchdog/launch.lock/STOP/120秒硬限/資源與來源模型SHA/唯一輸出已建立。run frozen_sac_cpu_probe_20261016_231331_e45d41：實際watchdog shell1、worker1，15.683秒結束，原worker身份已無。第一個模型工廠建立後RNG fingerprint不一致，尚未到任何command；不能說真模型推論、StationController.act或FDM時序通過。來源未改、無FDM/訓練；120秒預留不退款。factory在取snapshot前import stable_baselines3是待隔離原因，不是已證實根因。下一步新隔離v2與分stream指紋，先修冷載入RNG隔離，不擴聯賽。原失敗與契約保留，不直接改原凍結factory。


## 2026-10-16T16:37:09.507185+00:00 凍結SAC紅方真CPU工廠通過

隔離v2唯一production差異：stable_baselines3首次import移入Python/NumPy/Torch RNG還原區域；原v1來源不改。新run frozen_sac_cpu_probe_v2_20261017_003552_e2ae02，120秒預留、實際31.480秒，watchdog shell/worker真0、worker精確身份已無，來源模型/輸入/結果SHA核對。兩個真SAC模型各100次StationController.act/5次predict，加reset新物件與首命令精確重現、duplicate不變、三種RNG指紋還原皆通過。這是合成時鐘重複合法packet的CPU接口，不是FDM/聯賽/勝率，原失敗保留；聚合fingerprint與新逐stream方法不同，不過度宣稱已確定唯一根因。首個v2前置缺test_adapter.py在worker/預留前真1，補回原SHA後單次新CPU探測通過。10/17預留120秒不退款。下一步只做獨立硬限短FDM首幀/step時序/雙方私人狀態驗證，正式仍repair_guide。


## 2026-10-16T20:18:25.021957+00:00 ASUS Codex交接文件

使用者要求GitHub提供另一台Codex的MD操作交接。CODEX_HANDOFF.md與README已commit/push e7ca26c；GitHub API確認blob93d33c05abcc59123c2986b1413f65a7e433bef4，另附在原release Assets並更新說明。涵蓋私人repo登入、下載SHA、包內runtime、真退出碼/120s期限/精確程序、ASUS新報告與LAN待確認條件。不修改原ZIP或部署程式，無新研究/FDM。交接URL https://github.com/poopro/ai-pilot-cpu-player/blob/main/CODEX_HANDOFF.md 。


## 2026-10-16T20:22:45.073808+00:00 使用者更正交接入口

已依使用者要求將主要MD入口放回原公開專案poopro/ai-pilot-training-guide，CODEX_SECOND_PC_SETUP.md與README已commit/push d216e41、API核對blob fecf8ba4061cf9a93435a693582e6d0b61a42ae4。流程改為一次完成下載SHA/CPU自檢/LAN準備/有硬時限啟動器/條件齊備時實際LAN回合，不在CPU檢查後就停止；缺Host端點或配合才最終一次彙整人工事項。私人執行套件維持原release，不將控制器/位址/個資搬到公開repo。無新訓練/FDM。

## 2026-10-16T21:04:11.1576575Z ASUS LAN 交接與主機相容性檢查

使用者確認本次採預設測試候選埠：ASUS 收 OBS UDP 8199、主電腦收 CMD UDP 8099。主電腦 Ethernet 192.0.2.10/gateway 192.0.2.10 與 ASUS 回報 Wi-Fi 192.0.2.10/gateway 192.0.2.10 在同一子網；主電腦對 ASUS ping 2/2 成功，只證明基本 IP 可達。主機目前無 Host/Player 測試程序，UDP/TCP 8199/8099 均無 listener；兩端網路類型為 Public，未改安全或防火牆設定。

**阻塞項目：portable_host_v4/portable_host.py 對 network.json 強制 loopback 127.0.0.1，凍結 Host Setting.txt 的 P1 OBS 目的 IP 亦為 127.0.0.1；不可修改 v4 或原 ZIP 來繞過。v4 的 6/6 僅為同機重現，不能算 LAN。** 下一步：ASUS Codex 依新 GitHub 一次性交接指南完成本機檢查與套件外 LAN 設定/啟動器預檢，先停在 LOCAL_READY_LAN_PENDING；主電腦另需建獨立、凍結、限時、可收證的 LAN Host profile，再通知 ASUS 端開測。Public profile 不建立 firewall rule、不降安全設定；如需要最小例外交由本人確認。

GitHub poopro/ai-pilot-training-guide visibility 已即時核對為 private。CODEX_SECOND_PC_SETUP.md 更新commit 22aea5cdd7b7bd1077114d9d8befa59bb52be6d、blob 9bf6bfc20df23050b20c68bdd6f925b4146e87a；私有端點報告 eports/asus-cpu-player-setup-2026-10-17/LAN_ENDPOINTS_PRIVATE.md blob 1ade0866ae709ac17692430de5aee99b8f71026。公開操作文件不含任何實際IP；私人端點只存於該已確認private repo與本機 diagnostics/ASUS_LAN_HANDOFF_PRIVATE_20261017.md。需在後續每次上傳前重新核對 visibility。

沒有啟動 Host/Player、沒有 LAN 對戰、沒有改防火牆/網路類型/原始套件；尚無勝率或跨機驗證結論。

## 2026-10-17 主電腦 LAN Host 副本準備

- 使用者已提供 ASUS Wi-Fi `192.0.2.10`、主電腦 Ethernet `192.0.2.10`、共同 gateway `192.0.2.10`；本次使用者同意的測試候選 UDP 埠為 ASUS OBS 8199、主電腦 CMD 8099。不得再把端點資訊描述成缺失。
- 主電腦建立 `diagnostics/lan_host_v1/host_instance`，僅複製發布 Host exe/icon/readme/Setting 至隔離副本與空 `output_acmi`。唯一內容設定變更為副本 `PLAYER1_OUTPUT_IP` 127.0.0.1→ASUS .202；CMD 綁定維持 0.0.0.0:8099，P1 OBS port 8199，P2 設定維持原值。
- `STATIC_VERIFICATION.json` 13/13 checks 通過：來源設定未改、Host exe/icon/readme複本 bytes一致、只有 P1 OBS IP 改動、v4 source freeze/原套件 manifest/ZIP hash不變、8199/8099目前無 UDP listener、無 Host process。主機 Ethernet IP .200 / gateway .32，ping ASUS .202 2/2；這不是 UDP/LAN 回合證明。
- 可用 RAM 約5.83 GiB；Windows Public profiles enabled，未改防火牆、網路類型或路由器；Host/Player未啟動。
- 剩餘：建立獨立 LAN supervisor/watchdog/collector；ASUS CPU readiness 與實際 Player listener 未驗證；Public profile 防火牆路徑未配置；需協調限時窗口。見 `diagnostics/lan_host_v1/PREPARATION.json`。


## 10/17 06:33 模型優先與凍結SAC紅方FDM接通
- 人類已確認塔塔加未錄取、無行程衝突，要求主力模型／規則對戰程式；ai/ai-2保持原UTC時刻，移除塔塔加選擇與ASUS前置，讀新RACE_FOCUS。
- 新獨立frozen_sac_fdm_v1，source23files+physics/XML144項凍結；新seed2026310000/1已attempted；OSlock/STOP/CPU/RAM2GiB/disk10GiB/獨立240s guardian。preflight真0，無其他活研究。
- run_20261017_063110_af2e25兩模型各2×300tick共1200，worker0、parent實際0(eb2570/session74217)、verifier0(d708f9)，25.594s parent，1.072383s verifier，240s預留保留；今日總預留0.1h。
- 命令來自完成n步後的own26packet，下一步一次act/send/physics；judge poststep；0/20/...3Hz，duplicate無變動，final state300有一個未送出的第301命令以關閉最後counter。實際命令／sim時間／controller獨立／reset相同SHA與新actor savedpacket重播精確相符。四份JSONL與ACMI保存，0過G、0命中，非零FDM攻擊路徑仍未觸發，不能稱戰力或自我對戰訓練。冷首36.5313ms、暖最大2.2587ms非最壞實時保證。
- 精確guardian/worker/owned conhost原identity均已不在，不補子程序退出碼、不停止無關程序。保持原模型與repair_guide。
- 下一項：新六場完整公平開發比較，三種藍方對固定學習紅方，兩新開局含左右；未實作／未claim，原18場與本1200tick不重跑。

- 10/17競賽報名提醒已按原授權寄me，Gmail message[redacted-gmail-id]，email_notice/review_notice去重。使用者尚未回覆完成證據，狀態不改已報名。



## 2026-10-17T01:53:01.751744+00:00 六場完整凍結學習紅方比較


- 規則控制版（零戰術StationController）、5k模型、10k模型，在兩個新開發開局對同一凍結5k紅方，共6場、108,000個真實模擬步；每開局雙方initial SHA一致。這個規則版不是pure repair_guide。
- 三版本在各自同一開局內，18,000幀實際飛行命令與數值軌跡完全一致。模型確有輸出不同戰術，但本批沒有帶來控制或得分優勢。
- 六場雙方命中0、擊落0、墜機0、碰撞0、過9G 0；全為300秒時間到，紅方積分勝。三版本每版0勝/2負，分差兩開局分別-1.9914/-4.6112，不能當未知隊伍勝率。
- 最近距離分別1166.81m與1144.43m，均未進入攻擊距離152.4–914.4m。首要弱點是進入射程；裁切是否抹去戰術差異仍待追蹤，尚非根因定論。
- 六worker與模擬父程序實際0。原60秒核對器逾時退出1已保留；另立180秒離線審查契約，沿用不變的嚴格逐幀/全部模型決策/來源XML/CSV/ACMI核對，91.61秒完成、審查worker及guardian真0，verified_comparison=true/errors[]。未重跑任何對戰；17個原程序身分均已不在。
- 下一步：追蹤戰術→目標→命令的作用，再以新開局測一個控制因素；有改善證據後再訓練。本輪沒有新訓練，兩模型保留，正式基準仍repair_guide。
- 10/17競賽報名提醒已寄；尚無完成證據，原記錄截止10/21。

證據：research_latest.json；experiments/opponent_pool/frozen_sac_battle_v2/run_20261017_093943_16bee6/SAFETY_REVIEW.json；diagnostics/saved_sac_battle_audit_20261017_094917_10fc24/COMPARISON.json。

- 假設：blue actor選擇可能改變對固定sac5000紅方的表現。唯一因素為blue actor，左右兩開局各三個actor同雙方initial SHA，兩seed不能獨立估左右效應。
- 失敗保存：v1 run_20261017_093451_16086d只首場18000tick物理完成，儲存後全controller replay超過90秒，worker1/parent2；不計完整比較。v2只改核對分工，原物理/控制路徑byte一致且6靜態檢查0；新seed2026310200/1，6worker0/parent實際0(session61003 chunk38434f)，444.625秒。原verifier1(session63271 chunka666a4)，60秒cap；新獨立保存資料審查180秒預留、unchanged strict verifier逐case12–14秒，加cold import共91.61秒、worker0/guardian真0(session27865 chunk7e226f)。原失敗收據未改；無重跑FDM/訓練。
- 審查sha：6a8b86c3290e52f51fe56708ee5bc429f582099366106e3576b87233c741efbd；來源數不沿用其他實驗，確切manifest見CONTRACT（validated interface23+physics/XML144及本批4來源）。17原身份皆已無/重用，未知退出不補0。
- 10/17預留保留為0.48333333333333334h；包含失敗，不退款。下一步：先離線追蹤保存開局的戰術→bank/速度目標→實際command，找出差異在哪個裁切/分支消失；再選一個因素，用新seed做有界完整配對比較，優先進入152.4–914.4m攻擊距離，暫不盲續訓練。



## 2026-10-17T04:30:21.553059+00:00 保存軌跡的戰術目標裁切追蹤


- 離線完整追蹤六場已保存的108,000幀：戰術值有送進控制器，裁切前的轉彎計算也不同；但每一幀的轉彎目標都被限制在±72度，速度目標都被限制為290節。每個開局三版本的最終目標完全相同。
- 這說明這批軌跡的戰術差異在目標裁切處被抹去；不是只靠零命中猜原因。此診斷沒有重跑FDM、沒有新模型推論或訓練；內層command只用記錄器替代，不把記錄器回傳的舊命令冒充新控制重播。
- 診斷67.532秒完成，worker與父程序實際0、來源SHA固定、原PID/建立時間/命令身分已無；VERIFICATION通過。
- 先前六場完整對戰仍有效：三版本各0勝2負、皆時間到由紅方積分勝；雙方0命中/擊落/墜機/碰撞/過9G，最近距離1166.81/1144.43m，未進入攻擊距離。這不是未知隊伍勝率。
- 下一個待測假設：只降低藍方遠距轉彎目標上限72→60，嘗試改變持續繞圈的幾何關係。會先隔離來源，再用兩個新開局、baseline/candidate共4場完整比較；尚未實作或啟動，不能稱已改善。
- 正式基準repair_guide與兩個凍結模型保留，不盲續訓練、不自動部署。10/17報名提醒已寄，尚無報名完成證據。

最新診斷：diagnostics/sac_goal_projection_20261017_122745_b73993/VERIFICATION.json；下一步：同資料夾NEXT_EXPERIMENT.json。

- 完整6×18000幀用原StationController.act與原bearing history投影；實際_build_blue載入路徑為凍結m4_tactical_v4/m1_station.py，不能事後補成舊worker當時__file__收據。command換記錄器，只捕獲目標，不重播內層控制。每幀setter→act相等、bank前後公式與speed裁切重算相等；near/inband全0。正常側rawbank約-298至-169度；鏡像約152至296度；全被夾至±72。速度裁切前約350至451節，全被限到290。鏡像10k的break門檻9820tick有觸發，仍沒改變目標。
- 120秒原harddeadline/JobLock/STOP/source144+23+4/CPU RAM disk/固定來源/唯讀舊packet SHA，新輸出獨立；沒有新seed claim、FDM或模型predict。原來源未改。session28492 chunk0a886f實際parent0，worker0，67.532秒；3個原identity已無，未知退出不補0。120秒預留保留，今日總0.5166666666666667h。診斷sha 718dbdf958e56c31b67ecfceecf6f9043a8a790ec5aa70fd4a6e1ad22c8d68a4。
- 下一factor只是預先寫定假設：遠距bank cap72→60。目的改變飽和幾何，不宣稱更好或參數最佳；不得把降低角度等同安全保證，仍檢查9G/高度/逐開局輸贏，無改善則拒絕。


## 2026-10-17T07:37:01.582851+00:00 四場遠距bank60單因素開發結果


- 完整4場、72000模擬步、2個相同initial SHA配對；worker／父程序／獨立核對器實際0，來源/XML/模型/逐幀規則/紅方決策/目標裁切/CSV/ACMI核對通過。
- 唯一變更：藍方距離>914.4m時轉彎目標上限72→60，其餘目標、安全控制與對手不變；基準是零戰術StationController，非pure repair_guide。
- normal：基準timeout/blue、命中0；候選timeout/red、命中0；進入射程0→7604 tick，最近1256.99→455.91m，共同最低AGL差+159.53m，候選過9G 0tick。
- mirrored：基準timeout/red、命中0；候選timeout/red、命中0；進入射程0→7536 tick，最近1187.64→453.31m，共同最低AGL差+1009.26m，候選過9G 0tick。
- 決策：reject_promotion_position_score_regression。兩配對得分大幅退步，原本獲勝的開局變落敗，否決此候選晉級；射程改善不等於較強。下一步追蹤射程內不利朝向的控制時窗，不盲續訓練。
- 沒有新訓練，不自動部署；正式repair_guide及原兩模型保留。這是兩個開發開局，非未知隊伍勝率。
- v1初始化誤載同名candidate.py失敗已保留；v2以絕對路徑預先綁定唯一檔，cold import碰撞測試通過，使用全新種子，沒有重跑原失敗種子。
- 今日預留0.850000h，失敗預留不退款。

證據：E:\ai_pilot\campaign_2026\experiments\opponent_pool\far_bank60_v2\run_20261017_153047_104619\SAFETY_REVIEW.json

- 來源manifest：E:\ai_pilot\campaign_2026\experiments\opponent_pool\far_bank60_v2\run_20261017_153047_104619\CONTRACT.json；comparison SHA 6b2add7e6c526cfb148538876aa3d261e3cecb6baa136a925559b068d4360057。原600秒含4worker與預先規劃120秒核對cap，未增加時限。原v1 shell真1、worker2、guardian intended2不可混作精確觀察；無完整場次，2seed/600秒預留保留。v2唯一修正為絕對路徑提前綁定投影檔，原物理/reset/control AST及cold import碰撞測試通過；新種子2026310400/1，不拼批。



## 2026-10-17T10:39:31.099441+00:00 保存追瞄軌跡的wrap反轉診斷


- 已核對四條保存軌跡，共72,000幀；沒有新模擬或訓練。兩個bank60開局各13次轉彎目標反向，都與方位誤差跨越正負180度發生在同一幀；原72度版本各0次。
- 每個bank60開局有27次射程邊界切換，但僅2次反向落在邊界切換前後2秒。射程內方位誤差中位數約139度、目標方位移動約12.86/13.16度每秒，而我機轉向約6.23/5.88度每秒。
- 下一個待測假設：敵機經過正後方時暫時維持原轉向方向，進入前半球再解除。尚未實作、沒有閉迴路改善證據；須先測重置/安全/未觸發前完全相同，再作新開局完整比較。
- 機制試驗將比較latch60與已否決的unlatched60，只能判斷latch作用；仍需之後和原72度版本在相同開局比較，不能直接取代正式repair_guide。
- 原bank60四場退步結論不變；兩個凍結模型與正式基準保留，不盲續訓練或部署。
- v1正常側兩CSV寫完後因NumPy整數無法輸出JSON而退出1，原失敗保留。v2只投影剩餘鏡像兩條，並從原始packet獨立重算核對四條CSV；worker與parent實際0，沒有重跑對戰或正常側controller投影。

證據：diagnostics/pursuit_window_trace_v2_20261017_183554_46bebe/VERIFICATION.json；下一步同資料夾NEXT_HYPOTHESIS.json。

- v1原120秒/worker1/parent真1(session20860 chunka8fa84)、27.188s，失敗發生在normal candidate trace CSV完成後的JSON print，np.int32 TypeError；不改成完整成功。v2原120秒/worker0/parent真0(session32357 chunk006889)、58.875s，只新增mirror36000保存幀投影。normal2CSV SHA先凍結，audit以原legal packet獨立重算bearing/heading error/EMA LOS rate/feedforward/bank目標及每列g.requested/applied，72000列一致；本次actual來源劇本未改、無新模型predict或FDM/seed claim。
- 六個已記錄原identity均已無/重用，未知退出不補0；v1+v2各120秒預留不退款，當日0.9166666666666666h。TRACE_AUDIT SHA 7e7d5f7b4c50d820b7b2c9acde59ae2305e67d229ab85eb1c9f555f11d0aa82c；診斷只揭露保存軌跡的反轉機制，latch是否能贏需新閉迴路驗證。pre-step in-band7603/7535對原post-step7604/7536差1有明確初末曝光解釋。


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

- bank_residual_fdm_v1後置metadata helper首次因重複episodes keyword在parse階段真exit1（36d1d0），無執行或新FDM；僅隔離helper改episode_count後真0（e0c535）。原precheck/worker/verifier/parent0收據未改，SEAL_HELPER_FAILURE.json保留。



## 2026-10-18T10:50:20.986177+00:00 新17觀測×1bank小模型：3000decision完整訓練，尚未量測戰力

- 全fresh CPU SAC128×128，原13×3模型不相容，未帶舊actor/critic/optimizer/replay。原RepairController殘差API、72度/G/recover/trim/slew維持；每20個60Hz tick只更新一維bank，17特徵僅合法packet/私有自機counter/guard/clock。新reward為公告profile雙方advantage差增量/(10000/60)+真終局winner±180，cutoff不編勝方。
- 新模型完整3000decision/60000真FDM步/338梯度更新；actor SHA改變、model與replay3000重載精確，10組前置檢查及worker/verifier/實際parent均真0，phase {'PRECHECK': 0, 'WORKER': 0, 'VERIFIER': 0}。原900s總限、30s前測/780s learner/90s核對，實際200.515s；7原core身份已無或重用，來源XML/紅方模型不變。
- 實際到達4個排程cell、完整訓練回合3，最後partial見FINAL_REVIEW；不是完整聯賽/公平勝率。每tick計數及裁判、每decision特徵/reward、3000個decision首tick真blue act-command回放核對；其中1462個抽樣與同狀態neutral命令不同。訓練紀錄沒有全幀packet/紅controller回放或ACMI，不冒稱完整對戰審查。
- 藍峰值G 3.669220，零過9G；最低AGL 894.896m為本訓練樣本，沒有公平基準高度比較。訓練回合事件/得分不能當模型勝率。gate=learning_mechanics_verified_strength_unmeasured_no_promotion，未部署、尚無模型優勢證據。
- v1動態class來源反射失敗：precheck0/worker2/parent shell1、0decision/0記錄步（已FDM初始化）。v2修反射後900decision/18000步/75updates，在切換RuleFighter時因command-only API解包失敗，worker2/parent1；partial模型不晉級。v3只前測import package名錯誤真1、無learner/FDM/seedclaim。v4只修正該前測import，生產沿用v3已修正三對手API；實際三對手CPU接線測試通過才新fresh訓練。全部舊來源/失敗收據/原預留保留，不重跑原seed。
- 本日預留累計1.400000h（含上述四次各900s及既有0.4h，不退款），用量只讀一次UTC2026-10-18 10:31:11，較低93%，未用credits/reset。正式repair_guide與兩原模型保留；ASUS/LAN不是前置，無需本人操作。
- 下一項：依NEXT_EVALUATION_PLAN新立900s總/90s每worker/180s嚴格核對的6完整開發場，三對手各neutral-vs-learned同雙方initialSHA配對；新seed/來源模型凍結/獨立deadline/lock/STOP/資源。先看逐對score/event/命中/射程/前半球/共同AGL/最差case，再決定有無理由追加訓練。尚未實作/啟動該比較，不預設較強，不自動部署。

證據：E:\ai_pilot\campaign_2026\experiments\opponent_pool\bank_residual_train_v4\run_20261018_184640_29092b\VERIFICATION.json；E:\ai_pilot\campaign_2026\experiments\opponent_pool\bank_residual_train_v4\run_20261018_184640_29092b\FINAL_REVIEW.json；E:\ai_pilot\campaign_2026\experiments\opponent_pool\bank_residual_train_v4\run_20261018_184640_29092b\BUNDLE_MANIFEST.json；E:\ai_pilot\campaign_2026\experiments\opponent_pool\bank_residual_train_v4\run_20261018_184640_29092b\TERMINAL_AUDIT.json；E:\ai_pilot\campaign_2026\experiments\opponent_pool\bank_residual_train_v4\run_20261018_184640_29092b\NEXT_EVALUATION_PLAN.json。
