from pathlib import Path
import hashlib,json
from datetime import datetime,timezone

ROOT=Path(r'E:\ai_pilot\campaign_2026')
JOB=ROOT/'jobs'/'job_20261012_184123_68be'
GATE=ROOT/'experiments'/'residual_gate'/'run_20261012_191703_f102'/'recovery_01'
DELEG=ROOT/'delegations'/'20261012_194445_a586'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')

s=read(JOB/'state.json');assert s['status']=='futility_stop' and s['new_decisions']==100000
reports=[read(JOB/f'dev_{i:02d}'/'report.json') for i in [1,2]]
assert all(r['benchmark_complete'] and len(r['cases'])==24 for r in reports)
assert all(read(JOB/f'verified_{i:02d}.json')['passed'] for i in [1,2])
assert reports[0]['source_sha256']==reports[1]['source_sha256']
for r in reports:
    assert r['requested_max_steps']==18000 and r['physics_hz']==60
    for row in r['cases']:
        assert row['score_eligible'] and row['full_round_completed']
        pair=[x for x in r['cases'] if x['pair_key']==row['pair_key']]
        assert len(pair)==2 and pair[0]['initial_sha256']==pair[1]['initial_sha256']
assert [x['initial_sha256'] for x in reports[0]['cases']]==[x['initial_sha256'] for x in reports[1]['cases']]
comparison=read(GATE/'COMPARISON.json');assert comparison['verified_comparison']
assert comparison['candidate_gate']=='reject_promotion'
oc=read(DELEG/'state.json');evidence=read(DELEG/'model_evidence.json')
assert oc['status']=='completed' and oc['source_unchanged']
assert all(x['model']['id']=='space-bunny-free' and x['model']['providerID']=='opencode' and x['cost']==0 for x in evidence['assistant_metadata'])
consent={'received_date_taipei':'2026-10-12','answer':'同意傳送這三個專案原始碼',
    'destination':'OpenCode opencode/space-bunny-free','scope':oc['inputs'],
    'source':'explicit human answer in this conversation','other_private_files_authorized':False,
    'no_secrets_or_personal_data':True,'no_source_edit_permission':True}
write(DELEG/'CONSENT.json',consent)
decision={'updated_utc':datetime.now(timezone.utc).isoformat(),'job':str(JOB),
    'training_status':s['status'],'new_decisions':s['new_decisions'],
    'verified_full_evaluations':2,'candidate_gate':'reject_promotion',
    'guide_deployment_preserved':True,'official_validation':False,
    'source_sha256':reports[0]['source_sha256'],
    'reports':[{'path':str(JOB/f'dev_{i:02d}'/'report.json'),'sha256':sha(JOB/f'dev_{i:02d}'/'report.json'),
        'totals':r['summary']['totals']} for i,r in zip([1,2],reports)],
    'gate_comparison':str(GATE/'COMPARISON.json'),'gate_comparison_sha256':sha(GATE/'COMPARISON.json'),
    'gate_recovery_original_attempt_preserved':True,'gate_recovery_exit_code':read(GATE/'state.json')['observed_exit_code'],
    'opencode_result':str(DELEG/'result.md'),'opencode_result_sha256':sha(DELEG/'result.md'),
    'opencode_patch_accepted':False,'opencode_actual_model_cost':evidence['assistant_metadata'],
    'compute_reserved_hours':4.75,'daily_compute_limit_hours':6,
    'next_action':'Measure legal-observation roll/load/turn response in an isolated bounded FDM calibration before a single controller change; no raw SAC continuation.'}
write(ROOT/'diagnostics'/'oct12_decision.json',decision)
review='''# Space Bunny 原始碼審查的本地核對

本次三檔外傳已獲使用者明確同意。工作完整完成，來源未變；實際 session 確認 space-bunny-free、回報成本 0。原回覆為草案，未採用其補丁。

## 判讀與修正

- 建議 roll_integral 以正 roll_error 累積，卻在 aileron 中減去 integral；這與現有正比例項相反。例如固定 +10 度誤差、零 roll_rate 時，累積正 integral 會降低正 aileron。不能採用這個符號。
- 實際 env.step 每個物理 tick 呼叫控制器，HZ=60、dt=1/60；10Hz 是診斷記錄頻率。決策重複只重複 SAC action，沒有降低控制器频率。草案把兩者混淆，且「10Hz 時乘60低估六倍」的方向也錯。
- 10.25度 bank error 的中位數不能推出 roll_rate 恰為32度/秒，動態 aileron 也不能假設為0。因此未證明 PI 能改善目前近距離誤差。
- near 分支瞄準的是機鼻與世界 LOS，不能僅因未加 alpha 就判為錯。遠距離 alpha+gamma 分支是飛行路徑控制，兩者任務不同。
- 8.5G 控制限制比 9G 計分門檻更保守，原文稱更寬鬆不正確。
- policy_state 實際20維；草案寫18維錯誤。現有配對各用相同固定 p2，並實際核對相同初始 SHA；mixed 分支 RNG 不影響這些固定對手配對。
- official_validation=False 是本地模擬與官方 Host 的證據界線，不是需要改成 True 的缺陷。
- coordinated turn feedforward 的速度需求是實際運動速度；不能只因速度迴路使用 CAS 就把 TAS feedforward 視為單位錯誤。
- 有可驗證價值的線索：roll追蹤、load/turn authority、積分飽和、guard順序、MSL/AGL假設。其影響仍需量測；不能從單一回合的不同統計中位數宣告因果。
- 審查 REQUEST 誤寫開發距離1500/3000/6000ft；實際 benchmark 固定3000/6000/9000ft，以原始 input/report 為準。本次回覆的定量推論不得據此當作驗證。

## 下一項工作

先做隔離的控制器校準：用既有 FDM、原物理與原控制器，固定初始化及seed，最多10個短案例、每個150秒硬限、總運算10分鐘預留。先量測60Hz控制與有限差分Euler rate是否一致、穩定翼平的load、30/50/70度bank時load/航向角速度與安全guard。只記錄合法OWN20+ENEMY6供控制診斷；不把不可用地形/敵方姿態加入策略。

若證據支持 roll lag，再設計一次僅改一個控制項的候選。若主要是卸載/轉彎權限，不盲加roll積分；先立新假設與撤回門檻。先小校準，再原24場完整開發配對，通過後才新種子保留測試與官方Host。不得精確續跑舊replay/critic到變更過的控制契約。
'''
(DELEG/'LOCAL_REVIEW.md').write_text(review,encoding='utf-8')
ocdoc=ROOT/'OPENCODE.md'
text=ocdoc.read_text(encoding='utf-8')
text=text.replace('controller.py、env.py、interface.py 的同意問題已在對話提出；取得明確答覆前只用公開規格與一般數學題。','使用者已於10/12明確同意 repair_v1/controller.py、repair_v1/env.py 與 combat_v3/interface.py 這三個檔案傳給 Space Bunny，範圍與 SHA 記錄於 delegations/20261012_194445_a586/CONSENT.json。其他內部檔案不在這次同意範圍。')
text=text.replace('原始碼審查尚未執行。','授權三檔原始碼審查已完成，實際模型與成本確認為 space-bunny-free / 0，補丁經本地核對拒絕，詳見該工作 LOCAL_REVIEW.md。')
text=text.replace('這份工作規則不代表內部檔案已獲外傳同意。只有對話中的使用者答覆才能改變該狀態。','外傳授權以對話中的使用者明確答覆為準；本次只同意上述三檔，不代表其他內部資料也獲同意。')
ocdoc.write_text(text,encoding='utf-8')
with (ROOT/'REVIEW_LOG.md').open('a',encoding='utf-8') as f:
    f.write('\n\n## 2026-10-12 19:50 完整結果與原始碼審查\n')
    f.write('- 新增100k決策後，74k與124k完整model/replay/manifest實際重載皆通過；兩次評估各24/24完整，原程序已結束、六階段退出碼0。依既定無改善門檻futility_stop，拒絕追加50k，不部署候選。\n')
    f.write('- 同組12場：guide 3擊落/10.0秒；raw74k 0/2.5167秒；raw124k 0/0.4秒。這是開發集結果，不是正式勝率。\n')
    f.write('- range gate唯一逾時guide回合依原凍結來源、模型、seed、18000tick、150秒上限補跑一次，退出0且初始SHA重現。原partial report與23個有效回合保留；recovery_01/report.json完整24場，所有公平比較檢查通過。gated74k 0擊落/3.1167秒，仍低於guide，reject_promotion。\n')
    f.write('- 使用者明確同意三個原始碼傳給Space Bunny。審查完成201.39秒，實際免費模型、成本0；未修改來源。發現草案roll積分符號、控制與取樣頻率、觀測維度及數項物理/方法判讀錯誤，未採用補丁，詳見delegations/20261012_194445_a586/LOCAL_REVIEW.md。\n')
    f.write('- 五小時額度實讀剩34%、週剩74%；自然重置10/12 20:30:26。這段完成小型失敗恢復與結果核對，沒有新learner、付費備援、credits或重置券。原4h+gate40min+probe150sec+retry150sec預留4.75h，仍小於日6h；等待時間不冒充新增模擬運算。下一項先量測roll/load/turn response，不依草案盲目改PI或續訓。\n')
print(json.dumps({'saved':str(ROOT/'diagnostics'/'oct12_decision.json'),'training':s['status'],'gate':comparison['candidate_gate'],'opencode_patch':'rejected_after_local_review'},ensure_ascii=False))
