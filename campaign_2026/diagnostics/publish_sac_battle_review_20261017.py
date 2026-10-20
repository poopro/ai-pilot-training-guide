"""Publish only checked saved-game evidence; never touch policy or physics."""
import datetime
import hashlib
import json
from pathlib import Path
import psutil

ROOT=Path(r'E:\ai_pilot\campaign_2026')
RUN=ROOT/'experiments/opponent_pool/frozen_sac_battle_v2/run_20261017_093943_16bee6'
AUDIT=ROOT/'diagnostics/saved_sac_battle_audit_20261017_094917_10fc24'

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

review=read(RUN/'SAFETY_REVIEW.json');comparison=read(AUDIT/'COMPARISON.json')
assert comparison['verified_comparison'] and comparison['complete_games']==6 and comparison['new_FDM_ticks']==108000
assert read(RUN/'PARENT_EXIT_OBSERVED.json')['actual_exit']==0
assert read(AUDIT/'AUDIT_EXIT.json')['actual_worker_exit']==0 and read(AUDIT/'GUARDIAN_EXIT_OBSERVED.json')['actual_exit']==0
assert all(r['identical_all_actual_blue_commands'] and r['identical_all_numeric_telemetry'] for r in review['within_opening_equivalence'])
assert all(r['attack_ticks']==[0,0] and r['over9G']==[0,0] and r['winner']=='red' and r['event']=='timeout' and r['in_attack_range_ticks']==0 for r in review['results'])
# Capture real processes without treating access denial as dead.
live=[];unknown=[]
for p in psutil.process_iter(['pid','name']):
    if 'python' not in (p.info['name'] or '').lower() or p.pid==__import__('os').getpid():continue
    try:
        cmd=p.cmdline()
        if any(str(ROOT).lower() in a.lower() for a in cmd):live.append(dict(pid=p.pid,create=p.create_time(),cmd=cmd,exe=p.exe(),parent=p.ppid()))
    except psutil.NoSuchProcess:continue
    except psutil.AccessDenied:unknown.append(p.pid)
if live or unknown:raise RuntimeError('Live/unknown Python identity remains; do not publish idle: '+str((live,unknown)))
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
next_action='先離線追蹤保存開局的戰術→bank/速度目標→實際command，找出差異在哪個裁切/分支消失；再選一個因素，用新seed做有界完整配對比較，優先進入152.4–914.4m攻擊距離，暫不盲續訓練。'
next_plan=dict(status='planned_not_implemented',evidence=str(RUN/'SAFETY_REVIEW.json'),
               observed='兩開局內三版本18000幀實際command與數值CSV完全一致；最近1166.8096m/1144.4296m，均未進入914.4m以內；模型戰術值確有不同。',
               hypothesis='out-of-band bank/速度限制可能抹去戰術差異；只有命令等價已證明，裁切根因未證明。',
               next=next_action,method=['只讀已保存packet與戰術，先核對實際執行的StationController來源及唯一set_tactical→act路徑。',
                                      '以隔離離線目標探針記錄裁切前後bank/速度，包含首幀及保存退步時窗；區分合法設計的飽和與接線錯誤。',
                                      '依trace選一項可被實測的修正；新來源契約、2個新開局同initial的baseline/candidate完整配對、90秒/worker及全600秒，不重跑已完成seed。',
                                      '評估進入射程、1度瞄準、事件/積分勝負、過9G及共同高度；通過才作有上限訓練/擴對手。'],
               not_a_promotion=True,no_FDM_started=True,new_training_started=False,retained_deployment='repair_guide')
write(RUN/'NEXT_RESEARCH_PLAN.json',next_plan)
write(RUN/'POST_REVIEW_EXIT_OBSERVED.json',dict(actual_exit=0,tool_session=66601,tool_chunk='eabe79',kind='saved_data_analysis_only',new_FDM_ticks=0,observed_utc=now))
write(RUN/'OFFLINE_REAUDIT_POINTER.json',dict(audit=str(AUDIT),status='completed_verified_actual_guardian_exit0',original_verifier_failed=True))
ledger_path=ROOT/'compute_budgets/2026-10-17.json';ledger=read(ledger_path)
for item in ledger['items']:
    if item['id']==RUN.name:item.update(status='completed_verified_via_independent_saved_data_audit',actual_parent_exit=0,actual_initial_verifier_exit=1,original_verifier_cap_seconds=60,independent_audit=str(AUDIT),original_reservation_retained=True)
    elif item['id']==AUDIT.name:item.update(status='completed_verified_saved_data_audit',actual_guardian_exit=0,actual_post_review_exit=0,original_reservation_retained=True)
    elif item['id']=='run_20261017_093451_16086d':item.update(actual_parent_exit=2,actual_parent_exit_tool='8e4066',verified_comparison=False,original_reservation_retained=True)
write(ledger_path,ledger)
registry_path=ROOT/'seed_registry.json';registry=read(registry_path)
for trial in registry.get('trials',{}).values():
    if trial.get('output')==str(RUN):trial.update(status='completed_verified_development',comparison=str(AUDIT/'COMPARISON.json'),reusable=False)
    elif trial.get('output','').endswith('run_20261017_093451_16086d'):trial.update(status='failed_partial',reusable=False)
write(registry_path,registry)
rpath=ROOT/'research_latest.json';r=read(rpath)
write(ROOT/'diagnostics/research_pointer_before_six_battle_review_20261017.json',r)
r.update(updated_utc=now,status='completed_verified_saved_data_audit',experiment='frozen_sac_battle_v2',run=str(RUN),report=str(RUN/'report.json'),
         comparison=str(AUDIT/'COMPARISON.json'),verified_comparison=True,complete_games=6,new_FDM_ticks=108000,
         actual_parent_exit_code=0,actual_parent_exit_observation=str(RUN/'PARENT_EXIT_OBSERVED.json'),benchmark_return_code=0,
         original_verifier_exit_code=1,original_verifier_failure=str(RUN/'VERIFIER_EXIT.json'),
         independent_saved_data_audit=str(AUDIT),independent_audit_worker_exit=0,independent_audit_guardian_exit=0,
         safety_review=str(RUN/'SAFETY_REVIEW.json'),post_audit=str(RUN/'SAFETY_REVIEW.json'),post_audit_passed=True,
         source_manifest=str(RUN/'CONTRACT.json'),planned_cases=6,matched_pairs_planned=4,matched_initial_openings=2,
         gate=review['gate'],candidate_gate=review['gate'],deployment_allowed=False,retained_deployment='repair_guide',
         source_hashes_verified=True,seed_role='new_development_not_holdout',nonzero_attack_counter_exercised=False,
         next_action=next_action,next_session_plan=str(RUN/'NEXT_RESEARCH_PLAN.json'),training_started=False,
         daily_compute_reserved_hours=ledger['reserved_hours'],daily_compute_reserved_date='2026-10-17',
         supervisor=None,guardian=None,worker=None,active_workload=None,current_process_alert=None,
         current_live_workloads=dict(learners=[],loops=[],evaluations=[],unknown_python=[],observed_utc=now),
         new_run_permitted=True,new_run_block_reason=None,official_validation=False)
write(rpath,r)
pipeline_path=ROOT/'pipeline_latest.json';pipeline=read(pipeline_path)
pipeline['campaign_latest_20261017'].update(status=r['status'],latest_full_battle_review=str(RUN/'SAFETY_REVIEW.json'),latest_comparison=str(AUDIT/'COMPARISON.json'),next_research=str(RUN/'NEXT_RESEARCH_PLAN.json'),model_focus=True,ASUS_LAN_deferred=True,formal_deployment='repair_guide',training_started=False)
write(pipeline_path,pipeline)
summary='''# 最新進度：六場學習對手比較已完成，發現戰術輸出未改變飛行命令

- 規則控制版（零戰術StationController）、5k模型、10k模型，在兩個新開發開局對同一凍結5k紅方，共6場、108,000個真實模擬步；每開局雙方initial SHA一致。這個規則版不是pure repair_guide。
- 三版本在各自同一開局內，18,000幀實際飛行命令與數值軌跡完全一致。模型確有輸出不同戰術，但本批沒有帶來控制或得分優勢。
- 六場雙方命中0、擊落0、墜機0、碰撞0、過9G 0；全為300秒時間到，紅方積分勝。三版本每版0勝/2負，分差兩開局分別-1.9914/-4.6112，不能當未知隊伍勝率。
- 最近距離分別1166.81m與1144.43m，均未進入攻擊距離152.4–914.4m。首要弱點是進入射程；裁切是否抹去戰術差異仍待追蹤，尚非根因定論。
- 六worker與模擬父程序實際0。原60秒核對器逾時退出1已保留；另立180秒離線審查契約，沿用不變的嚴格逐幀/全部模型決策/來源XML/CSV/ACMI核對，91.61秒完成、審查worker及guardian真0，verified_comparison=true/errors[]。未重跑任何對戰；17個原程序身分均已不在。
- 下一步：追蹤戰術→目標→命令的作用，再以新開局測一個控制因素；有改善證據後再訓練。本輪沒有新訓練，兩模型保留，正式基準仍repair_guide。
- 10/17競賽報名提醒已寄；尚無完成證據，原記錄截止10/21。

證據：research_latest.json；experiments/opponent_pool/frozen_sac_battle_v2/run_20261017_093943_16bee6/SAFETY_REVIEW.json；diagnostics/saved_sac_battle_audit_20261017_094917_10fc24/COMPARISON.json。
'''
(ROOT/'latest_result.md').write_text(summary,encoding='utf8')
focus=ROOT/'RACE_FOCUS_20261017.md';text=focus.read_text(encoding='utf8')
text=text.replace('## 下一個小型完整對戰（規劃，未實作／未啟動）','## 已完成的六場比較設計（執行結果見最新段落）')
text += '\n\n## 10/17 09:53 最新：完整學習紅方比較與下一步\n\n'+summary.split('\n',1)[1]+'\n具體新研究計畫：`'+str(RUN/'NEXT_RESEARCH_PLAN.json')+'`；尚未實作下一控制修正或啟動新訓練。原v1單場後處理超時失敗與v2原60秒verifier退出1均保留；不覆寫成成功。\n'
focus.write_text(text,encoding='utf8')
with (ROOT/'REVIEW_LOG.md').open('a',encoding='utf8') as f:
    f.write('\n\n## '+now+' 六場完整凍結學習紅方比較\n\n'+summary.split('\n',1)[1])
    f.write('\n- 假設：blue actor選擇可能改變對固定sac5000紅方的表現。唯一因素為blue actor，左右兩開局各三個actor同雙方initial SHA，兩seed不能獨立估左右效應。\n')
    f.write('- 失敗保存：v1 run_20261017_093451_16086d只首場18000tick物理完成，儲存後全controller replay超過90秒，worker1/parent2；不計完整比較。v2只改核對分工，原物理/控制路徑byte一致且6靜態檢查0；新seed2026310200/1，6worker0/parent實際0(session61003 chunk38434f)，444.625秒。原verifier1(session63271 chunka666a4)，60秒cap；新獨立保存資料審查180秒預留、unchanged strict verifier逐case12–14秒，加cold import共91.61秒、worker0/guardian真0(session27865 chunk7e226f)。原失敗收據未改；無重跑FDM/訓練。\n')
    f.write('- 審查sha：'+sha(AUDIT/'COMPARISON.json')+'；149?來源數不沿用其他實驗，確切manifest見CONTRACT（validated interface23+physics/XML144及本批4來源）。17原身份皆已無/重用，未知退出不補0。\n')
    f.write('- 10/17預留保留為'+str(ledger['reserved_hours'])+'h；包含失敗，不退款。下一步：'+next_action+'\n')
notice_path=ROOT/'review_notice.json';notice=read(notice_path);digest=sha(RUN/'SAFETY_REVIEW.json')
notice.setdefault('events',{})[RUN.name+'|completed_verified_saved_data_audit|'+digest]=dict(status=r['status'],report=str(RUN/'SAFETY_REVIEW.json'),report_sha256=digest,notified_utc=now,channel='ai heartbeat final',message='6場108000tick核對通過，但三版本命令相同、均未進射程、0命中，不盲續訓練；先修戰術作用與接敵。')
write(notice_path,notice)
print(json.dumps(dict(status=r['status'],reserved_hours=ledger['reserved_hours'],verified_comparison=True,active_workload=None,next_action=next_action),ensure_ascii=False))
