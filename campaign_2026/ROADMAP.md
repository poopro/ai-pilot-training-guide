# 2026 AI 飛行員擂台賽：執行路線

建立：2026-10-11，Asia/Taipei。使用者授權由 Codex 接手本地專案，以 11/7 模擬擂台賽奪冠為唯一競賽目標。勝負仍取決於實際對手與正式裁判，不能從訓練步數推算。

## 現在的選擇與證據

- 尚未正式報名；使用者於 10/12 更正，已確認主辦接受單人參賽。需於 10/21 截止前完成報名。
- 比賽 11/7，11/1 公告賽制。官方技術文件允許 Rule-Base 等自主控制方法；不為了「有 AI 模型」而換上表現較差的 SAC。
- 已驗證的基準是 repair_guide：本機公告版 Host 一場獲勝，HP 180/0。內建對手是平飛 PID，這場只支持接線及該場結果。
- 修正版純引導器本地 20 場：rule 擊落 4/10、舊 RL 擊落 0/10，全部存活。缺口是近距離瞄準、控距與追隨對手下降。
- 舊 opponent_lab 2,000,000 步已完成；最後 20 場比較沒有擊落。繼續同方法沒有充分理由。
- combat_fix 24,000 次策略決策已完成模型/replay 真實重載與 SHA 檢查。新的 precision reward、修正版控制器、15 Hz 策略 / 60 Hz 飛控，前方課程已有成功訊號，完整 official 訓練只完成一場。首輪接續此契約。

## 分階段工作

| 日期 | 執行內容 | 必須看到的證據 |
|---|---|---|
| 10/11–10/14 | 凍結基準與來源；接續修正版 150k decisions；每 50k 比較一次；分析失敗遙測 | 存檔可重載；兩種對手、三距離、兩側，共 12 個配對開局；以完整回合比較 |
| 10/15–10/20 | 針對最主要失敗原因做小型消融；優先控制瞄準、控距與能量；SAC 與規則參數各保留候選 | 每次只改一個主要因素；候選比凍結基準進步，最差對手不退步 |
| 10/21–10/28 | 擴充凍結對手池：原 rule、不同 rule 參數、repair guide、舊 RL、合格新策略；必要時引入對手快照訓練 | 實際多對手聯賽；未見種子；左右開局；分組失敗率和配對結果 |
| 10/29–11/03 | 候選只在通過篩選後進入保留測試與官方 Host；確認滿時分數、碰撞、邊界、通訊重置 | 官方 CSV/ACMI/log/hash；至少六個完整 Host 回合；主辦連線條件；實際比賽電腦離線測試 |
| 11/04–11/06 | 凍結正式版本、打包相依與備份、兩次從零啟動彩排 | 無網路可推理；每回合重啟；可改 IP/PORT；可切回基準；11/6 最後檢查 |
| 11/07 | 使用凍結套件到場參賽，記錄正式裁決 | 人員到場、自備競賽電腦及電源、正式 Host 結果 |

日期是執行檢查點，任何落後都寫入 REVIEW_LOG.md，再按實際剩餘時間縮小改動。11/3 23:59 後停止新研究型訓練，除非修復會阻止參賽的明確問題。11/6 23:59 後停止排程研究。

## 今晚已排定的實驗

接續 `E:/ai_pilot/autopilot/combat_fix/training/run_20261006_192453_c95b/final_0000024000`；獨立副本位於 `E:/ai_pilot/campaign_2026/repair_v1`。每段 50k、最多 60 分鐘，總上限 150k decisions / 四小時，先到者結束；每 10k 或五分鐘保存。三段用不同訓練環境 seed，模型、critic、optimizer、replay 仍依相同契約接續。

每段結束先做 SHA、模型/replay 重載、有限數值檢查，再用固定開發開局比較候選與純引導器。先將候選記為「待檢討」，不把完成训练當成升級條件。若持續落後，下一輪改方法；不重複追加相同大訓練預算。

## 比較與晉級規則

1. 開發篩選至少 12 開局，每開局純引導器與候選各一完整場，共 24 場。包含 rule/RL、3000/6000/9000 呎、兩側；同 seed、初始狀態一致。兩側測試不等於官方 P1/P2 換邊。
2. 只有所有預期回合完整、模型與來源固定、指令有限且合法的報告可以比較。短 smoke、逾時及中斷不得列入成功率。
3. 首選擊落提升且被擊落/墜機不增加。若擊落不退步，平均有效攻擊增加至少 20% 且絕對增加 0.25 秒，可作下一輪候選。任何單一對手退步、低高度與過 G 變差，必須分析，不能用整體平均掩蓋。
4. 開發通過後擴充 4 種凍結對手 × 3 距離 × 2 側 × 3 新種子 = 72 個配對開局（144 場）；硬時間上限兩小時。此擴充對手池與門檻尚待下一階段實作，不能把目前兩種對手 runner 當成已完成。
5. 另留從未用於調參的一组測試；候選凍結才執行。看過的保留集永久降為開發集，記錄 seed role。
6. 本地 advantage/local_win 僅診斷 proxy；正式五分鐘滿時、碰撞、失控、邊界的勝負以 Host 為準。Timeout 不自動等於正式敗場。
7. 通過本地門檻後，仍須官方 Host 多回合與 UDP/重新初始化檢查，才更新正式選擇；保留原始基準與回退套件。

## 排程與用量

本機 runner 每 15–30 秒檢查程序、進度、保存、磁碟、RAM；本機訓練與模擬不呼叫雲端 API。一次只准一個 learner，保存中不可修改凍結來源；停機恢復不重置時間或步數預算。

Codex 低頻監督每天四次；每日一次結果檢討與下一輪決策。每次先讀即時用量一次，採五小時與每週兩窗口中較低的剩餘值：

- >=35%：有新證據時，可分析一項瓶頸、修改一個候選、執行有上限的新實驗。
- 15–35%：只維持已驗證實驗、處理明確失敗與小範圍檢討，不做多代理或廣泛研究。
- <15%：只做最小程序/保存確認，把深度工作記為等待額度；記錄工具回傳的 reset 時間，重置後下一個排程才恢復。
- 用量未知：採保守短檢查，不假設額度無限。不購買 credits、不自動花重置券；現有本機工作仍照原預算執行。

用量是全帳戶共用；不能保證排程不受其他聊天影響。電腦需供電、避免關機/手動睡眠，Codex 桌面程式保持運行，才能執行本地排程。官方說明：https://learn.chatgpt.com/docs/automations?surface=app

## 實驗檢討記錄格式

每次 REVIEW_LOG.md 記：日期、實驗ID、假設、唯一主要變更、訓練/測試預算、來源與模型 hash、完整樣本數、分對手指標、最差案例、結論（繼續/停止/換方法/Host驗證）、下一個具體工作。沒有新證據就不產生重複長文。

## 操作入口

`C:/Users/USER/anaconda3/envs/F16_ai/python.exe E:/ai_pilot/campaign_2026/runner.py status`

提前停止用 `runner.py stop`，等待「已完整儲存」與結果狀態。雙擊「查看競賽進度.cmd」或「停止並保存.cmd」也可。成果與完整命令記在每個 `jobs/campaign_*`；最新狀態入口 `pipeline_latest.json`，人用摘要 `LATEST_RESULT.md`。

正式比賽電腦、現場操作和彩排仍需使用者配合到場；取得實際賽程或最新主辦規則後更新本文件。



## 10/12依新證據更新

- 首段新增50k（總74k）已完整驗證，dev_01完整24场：guide12場3擊落、SAC12場0擊落；不升級。第二段已再新增50k（總124k），model/replay重載通過，dev_02完整24場但候選12場0擊落/0.4秒攻擊；原作業futility_stop，停止同方法，不啟第三段。
- 第一項單因素消融已實作與啟動：同74k actor只在距離<1100m使用残差，其他參數不變；experiments/residual_gate/，六項閘門測試、五項公平比較測試已通過。唯一逾時回合已依原設定補跑一次，recovery_01/report.json完整24場；公平比較通過，但gated候選12場0擊落/3.1167秒，reject_promotion，不進部署。
- 高頻診斷已改變瓶頸判斷：一個最常近距離卻無擊落的guide/RL案例完全重現，10Hz合法觀測顯示水平航向跟蹤誤差比世界pitch誤差大；接近aim時轉向速度與LOS變化不匹配且負載偏低。下一項研究先檢驗水平轉向/負載假設，不能同時混改多個参数或僅調pitch。這仍是單一已選開發case線索。
- OpenCode2與Space Bunny免費模型已實際使用公開數學題；使用者已明確同意三檔原始碼外傳Space Bunny，審查完成但錯誤補丁未採用。最高推理規則已更新，實際Space Bunny max/cost0驗證通過。


## 10/12 20:06 下一項工作順序

先讀 experiments/precision_probe/tracking_analysis/REVIEW.md 和 CALIBRATION_PLAN.json。新同時間點資料顯示bank大致跟上時仍可能缺少轉向速度與負載，先校準turn/load，再判斷是否要改roll控制。只用原控制器做隔離命令通道量測；短校準不是戰鬥晉級測試。


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


## 10/13 00:18 Host快照與實際退出紀錄接入稽核

剩餘18%，只完成證據閘門接線。新Host launcher保存exe bytes/SHA，Player入口另存該launch JSON/Host exe以及contract sources；collector保存收集源碼與輸入session SHA、actual wait退出、PID/建立時間與時間戳。稽核實際核對setting/player/source/exe bytes、啟動前時間、回合綁定退出receipt，缺漏或變動不算六回合。六項必要檢查通過（其中完整資料僅synthetic），歷史真實artifact仍有效且無新六回合資格；沒有開Host/Player/FDM。正向新GUI回合、另一PC/LAN和六回合仍待驗證。新工具只使用repair_guide；不得當bank80或可攜包Host認證，實際執行前仍需額度/當日預算/單一研究/安全門檻。research_latest已記工具與報告路徑，後續不要重做工具。


## 10/13 00:24 報名入口與文件準備

即時剩餘15%，只做行政準備。官方defense-ai.tw/competition重新讀取確認10/21截止，AI飛行員入口為portal/index?track=ai-pilot，本次web被導登入頁，不能據此判斷使用者瀏覽器是否已登入。公開需身分證正反面/學生證，登入表單欄位尚未核對；官網4人文字與使用者已確認单人授權分開記錄。REGISTRATION.md與registration_latest.json已記入口、文件、完成證據門檻；尚未填送或上傳證件，原10/17與10/20提醒維持。此行政核對零FDM/Host/learner。


## 10/13 01:54 新開局結論

24/24、12公平配對、同session實際退出0和verify_fresh退出0。bank80 3擊落對guide2，但RL0/6對0/6且新增1tick過9G，5個RL配對最低高度下降，reject_promotion；pool前置不成立。保留來源與完整證據，正式repair_guide。下一步每日檢討定位244–245秒track/recover瞬時過G，再選單因素安全候選；不是直接擴池/保留/Host或忽略1tick。今日預留40分鐘保留不退。詳見latest_result及新run SAFETY_REVIEW。


## 10/13 Host 逾時監督確認

Computer Use sky已可列出與讀取Host視窗，INIT/雙方READY與GO已實際觀察；START未見生效，0新完成回合。啟動14:00至19:50的等待超過原一小時界線，獨立watchdog尚未建立，已核對身分結束本次Host/Player。保守計入整個等待期間，當日6.5041h/6h，不能退款或改日期消除超支；當日不再研究型運算。下一個Host嘗試必須先有獨立deadline watchdog，控制器、Host与Setting均未改。詳見diagnostics/host_execution_latest.json。


## 10/13 目標改為10/20前可穩定參賽

使用者決定先保留競賽與塔塔加兩個選項，10/19晚間依可靠性證據決定，10/20完成人工步驟。Codex五小時／每週用量改為警告而非研究停止門檻；較低剩餘<=10%時改用已驗證免費OpenCode處理可外傳範圍內的文字與程式審查。每個本地run仍保留單一程序、身分、來源SHA、STOP、資源與wall deadline。新增研究路線為凍結對手聯賽、鏡像自我對戰、JEPA類數值世界模型及Qwen 4B低頻戰術選擇器；均需公平比較，不直接接管60Hz安全控制。完整規格見WIN_BY_1020.md。
