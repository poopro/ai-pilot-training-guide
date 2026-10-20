from pathlib import Path
import json,hashlib
ROOT=Path(r'E:\ai_pilot\campaign_2026')
EXP=ROOT/'experiments'/'turn_calibration'
DELEG=ROOT/'delegations'/'20261012_201252_6a0d'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
s=read(DELEG/'state.json');delivery=read(DELEG/'DELIVERY.json')
assert s['verified_model_effort_and_zero_cost'] and s['variant']=='max' and s['source_unchanged']
assert delivery['delivery_complete'] and not delivery['runtime_verified']
assert all(sha(Path(v['source']))==v['sha256'] for v in s['inputs'])
v={'status':'worker_prepared_FDM_unverified','model_transport_status':s['status'],
    'model_selector':s['selector'],'model_evidence':str(DELEG/'model_evidence.json'),
    'max_model_attempts':2,'attempts_used':2,'source_unchanged':True,
    'generated_worker':str(DELEG/'worker_draft_unreviewed.py'),'generated_worker_sha256':sha(DELEG/'worker_draft_unreviewed.py'),
    'reviewed_worker':str(EXP/'calibration_worker.py'),'reviewed_worker_sha256':sha(EXP/'calibration_worker.py'),
    'adapter_draft':str(EXP/'calibration_adapter.py'),'adapter_sha256':sha(EXP/'calibration_adapter.py'),
    'contract_gate_tests_passed':6,'test_scope':'Mock adapter only, no simulator ticks or control performance proof',
    'test_file':str(EXP/'test_calibration_worker.py'),
    'simulator_ticks_executed':0,'learner_started':False,'FDM_runtime_verified':False,
    'parent_supervisor_implemented':False,'ready_to_execute':False,
    'source_consent':str(ROOT/'delegations'/'20261012_194445_a586'/'CONSENT.json'),
    'official_validation':False,'combat_score_eligible':False,
    'next_action':'Implement dedicated fresh worker CLI and parent OS lock/source/identity/hard wall bounds, then real 7-case FDM calibration after fresh usage >=35%.'}
(ROOT/'calibration_draft_latest.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
(EXP/'latest.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
review='''# 轉彎校準工具準備狀態

這個資料夾尚未執行 FDM 校準，沒有模型訓練或勝率結果。

- Space Bunny 第一次max草稿只有說明、缺程式碼，已保存DELIVERY拒絕結果。一次針對缺漏的重試成功交付243行草稿，實際session確認max/cost0；不再重試。
- 本地核對並修正：錯誤Euler yaw公式、暖機CSV漏記、每tick恢復track模式以符合原act行為、嚴格形狀/舵面界線、Euler奇異與非有限JSON拒絕、目標值分為requested/effective、trim分母與原式一致、完成時STOP/150s再核對。原控制器/環境/ICD來源均未修改。
- 六項mock adapter測試通過，涵蓋body q在bank時對yaw影響、奇異/形狀拒絕、2100列含900暖機與1200測試、guard不剔除、controller歷史保留、非法舵面不advance、STOP/時間界線、獨立案例初始/暖機SHA一致。這些不證明真實FDM飛控穩定、負載定義或真實舵面符號。
- calibration_adapter.py 是本地介接草稿，使用原runtime及兩個原FDM；每tick own與bank0/path-hold reference各step一次，沒有裁判或learner。JSBSim類別確有get_delta_t方法，實際建構仍待校準時驗證。

## 尚需完成後才能執行

實作父層CLI/supervisor：新worker process每個case各建立同initial adapter/controller；7case，bank0 baseline及30/50/70乘nose0/path_alpha。150s每case硬限、600s全輪硬限；STOP與owned PID/create/cmd、OS實驗鎖、來源/SHA初始化前後、原3檔不變、完整2100行CSV與result退出碼核對。原reviewed worker未驗parent流程，不能直接宣稱ready_to_execute。注意model輸出的243行原draft超出220行要求，不把長度合規當成功證據。

待即時用量>=35%後，讀tracking_analysis/CALIBRATION_PLAN.json。總只預留10分鐘，日研究預留4.917h<6h。runtime查核/不可达要回報unknown，不能restart舊已結束SAC。完整短校準也固定combat_score_eligible=False，通過後才設計單一控制改動及24場完整戰鬥配對。
'''
(EXP/'README.md').write_text(review,encoding='utf-8')
with (ROOT/'REVIEW_LOG.md').open('a',encoding='utf-8') as f:
    f.write('\n\n## 2026-10-12 20:18 校準工具草稿與必要修正\n')
    f.write('- 本輪開始五小時剩20%、週剩72%，未啟新模擬/learner。Space Bunny max原三檔同授權草稿第一次缺code；一次有理由重試後交付code，實際模型max/cost0，來源不變。\n')
    f.write('- 草稿經本地核對發現yaw換算錯、暖機未記錄、mode只設一次等量測錯誤；已隔離修正，六項mock契約測試通過。初次test因sandbox temp權限而失败，移至明確可寫workspace temporary dir後通過。不是FDM或性能驗證。\n')
    f.write('- experiments/turn_calibration/保存reviewed worker、adapter草稿、tests、README/latest；parent supervisor尚未實作，ready_to_execute=False。下一次即時額度>=35時補齊父層硬界線/來源/身分，再執行7個命令通道校準；不追加相同SAC，也不把最高effort當正確證明。\n')
print(json.dumps({'status':v['status'],'contract_tests':6,'simulator_ticks':0,'ready_to_execute':False},ensure_ascii=False))
