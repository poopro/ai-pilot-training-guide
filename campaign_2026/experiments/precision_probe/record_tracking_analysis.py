from pathlib import Path
import hashlib,json
ROOT=Path(r'E:\ai_pilot\campaign_2026')
folder=ROOT/'experiments'/'precision_probe'/'tracking_analysis'
r=json.loads((folder/'ANALYSIS.json').read_text(encoding='utf-8'))
assert r['sample_count']==3000 and r['full_original_round_reproduced'] and r['no_new_simulator_ticks']
assert r['aiming_high_bank_error_within5']['samples']==62
summary='''# 同時間點轉彎診斷

本次只分析已保存的 r000_rl_3000_normal_2026101110_guide 完整回合；原始輸入SHA、初始狀態和最終指標均核對一致。沒有新模擬、訓練或控制器改動。

## 結果

- 有效距離且機鼻誤差<=10度、實際bank>=45度：198個10Hz樣本，約80%的負載絕對值低於1。這是取樣比例，不是physics tick攻擊時間。
- 其中bank指令誤差<=5度的62樣本：bank誤差中位2.63度、實際bank中位69.14度；航向角速度絕對值中位1.93度/秒，LOS變化中位13.34度/秒，兩者同時刻差的絕對值中位12.86度/秒，負載絕對值中位0.73。
- 因此「只要消除roll誤差就能跟上」沒有得到支持。此案例即使bank已跟上，也可能轉得不夠快。優先量測turn/load響應，再決定是否要改roll控制。
- 取樣航向有限差分與body-rate換算的Euler yaw速度，絕對差中位0.0053度/秒、95百分位0.0915度/秒；目前大幅yaw/LOS差不太可能只是角速度換算錯誤。這不等於舵面符號校準或全時域精度证明。
- 圖中226.6秒附近曾對準，但heading rate跟不上LOS，之後機鼻誤差擴大。只有此選定的已看開發回合，不能外推勝率或宣告因果。

## 下一次小校準的規格

待Codex即時額度>=35%，採用原FDM與原RepairController.command，不改物理、裁判、安全guard、舵面範圍或slew。全新隔離資料夾，最多10短案例、每case150秒硬限、總10分鐘硬限；另計0.167小時，加已預留4.75小時後當日合計4.917小時，小於6小時。不得產生第二個learner。

建議7個命令通道校準：bank0的基準，以及bank30/50/70各兩個診斷條件。共同初始12000ft/320CAS、相同seed與完整IC，先15模擬秒共同暖機，再20秒固定bank測試。兩條件皆保持同一track模式與控制增益，一條nose pitch固定0度，另一條僅作對照的path pitch target=當下alpha；這是量測設計，不能當作已證明合法瞄準修正或直接部署。未進入共同穩定狀態或觸发guard亦須報告，不剔除後只呈現好結果。

記錄每個60Hz控制tick前後合法OWN20+ENEMY6、四個command、實際與目標bank/pitch、CAS/TAS、alpha/beta、p/q/r、Euler/有限差分rates、signed及absolute load、積分狀態、guard模式、高度。不讓敵方隱藏姿態或不可用地形進策略。核對控制60Hz、每case初始化SHA、FDM/sourceSHA與退出碼。partial不能當完整校準；不能從短校準當作完整戰鬥晉級。

若load正常而roll誤差仍支配yaw差，才回到roll增益/積分假設。若bank已跟上但負載偏低仍限制yaw，研究一個turn/load項並設定高度/G/機鼻垂直誤差的撤回門檻。任何候選必須原24場完整開發配對，再未見種子及官方Host；不可精確續跑舊critic/replay到新控制契約。
'''
(folder/'REVIEW.md').write_text(summary,encoding='utf-8')
plan={'kind':'command_channel_calibration_not_combat_score','status':'ready_for_implementation_after_usage_check',
    'source_controller':str(ROOT/'repair_v1'/'controller.py'),
    'source_controller_sha256':hashlib.sha256((ROOT/'repair_v1'/'controller.py').read_bytes()).hexdigest(),
    'bank_targets_deg':[0,30,50,70],'speed_cas_kts':320,'initial_altitude_msl_ft':12000,
    'common_warmup_sim_seconds':15,'test_sim_seconds':20,'max_cases':10,
    'case_wall_seconds':150,'total_wall_seconds':600,'physics_control_hz':60,
    'daily_compute_reserved_after_launch_hours':4.916666666666667,'daily_limit_hours':6,
    'required_codex_remaining_percent':35,'no_learner':True,'deployment_allowed':False,
    'why':'Bank-tracked aiming samples still show large simultaneous LOS minus yaw rate; measure load/turn response before roll PI.'}
(folder/'CALIBRATION_PLAN.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
with (ROOT/'REVIEW_LOG.md').open('a',encoding='utf-8') as f:
    f.write('\n\n## 2026-10-12 20:06 同時間點遙測分析\n')
    f.write('- 本輪使用量實讀五小時剩26%、週剩72%，自然重置20:30:26；只做既有資料的小範圍檢討，沒有新模擬/訓練/外部模型呼叫。上一輪最高effort啟動器與真實session驗證屬實質進展。\n')
    f.write('- 3000個合法10Hz樣本：高bank瞄準樣本198個；其中bank误差<=5度的62個仍有yaw/LOS同時刻差中位12.86度/秒，load絕對值中位0.73。這提供優先校準turn/load、暫不採roll PI的新線索。有限差分yaw與Euler換算的差中位0.0053、p95=0.0915度/秒。\n')
    f.write('- 原始telemetry/result/original_result SHA前後不變；圖表已視覺核對。完整分析、限制與下一項校準規格在experiments/precision_probe/tracking_analysis/。不把取樣比例當攻擊時長，不宣稱因果、勝率或已完成FDM校準。\n')
road=ROOT/'ROADMAP.md';text=road.read_text(encoding='utf-8')
text=text.replace('第二段已再新增50k（總124k），model/replay重載通過，dev_02仍在比較。若連續符合事前落後規則，停止同方法，不硬跑第三段。','第二段已再新增50k（總124k），model/replay重載通過，dev_02完整24場但候選12場0擊落/0.4秒攻擊；原作業futility_stop，停止同方法，不啟第三段。')
text=text.replace('須等完整24場，COMPARISON.json只可判定是否進新保留測試，不能直接宣布部署或勝率。','唯一逾時回合已依原設定補跑一次，recovery_01/report.json完整24場；公平比較通過，但gated候選12場0擊落/3.1167秒，reject_promotion，不進部署。')
text=text.replace('原始碼外傳待使用者明確同意，其他本機研發可持續，不以此作全專案阻塞。','使用者已明確同意三檔原始碼外傳Space Bunny，審查完成但錯誤補丁未採用。最高推理規則已更新，實際Space Bunny max/cost0驗證通過。')
text+='\n\n## 10/12 20:06 下一項工作順序\n\n先讀 experiments/precision_probe/tracking_analysis/REVIEW.md 和 CALIBRATION_PLAN.json。新同時間點資料顯示bank大致跟上時仍可能缺少轉向速度與負載，先校準turn/load，再判斷是否要改roll控制。只用原控制器做隔離命令通道量測；短校準不是戰鬥晉級測試。\n'
road.write_text(text,encoding='utf-8')
print(json.dumps({'review':str(folder/'REVIEW.md'),'no_new_simulation':True,'next':'turn/load calibration after fresh usage check'},ensure_ascii=False))
