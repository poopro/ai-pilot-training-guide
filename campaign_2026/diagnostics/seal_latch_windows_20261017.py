from pathlib import Path
import datetime,sys,json,psutil
ROOT=Path(r'E:\ai_pilot\campaign_2026');SOURCE=ROOT/'experiments/opponent_pool/rear_latch60_v2';RUN=SOURCE/'run_20261017_203915_d840e7'
EXTRACT=ROOT/'diagnostics/latch_window_v1_20261017_213638_941961';AUDIT=ROOT/'diagnostics/latch_window_audit_v1_20261017_213931_a2c1a1'
sys.path.insert(0,str(SOURCE));import battle as b
read,write,sha=b.read,b.write,b.sha
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
write(AUDIT/'PARENT_EXIT_OBSERVED.json',dict(actual_exit=0,tool_chunk='073297',observed_utc=now))
assert read(EXTRACT/'PARENT_EXIT_OBSERVED.json')['actual_exit']==0 and read(AUDIT/'PARENT_EXIT_OBSERVED.json')['actual_exit']==0
assert read(EXTRACT/'WORKER_EXIT.json')['actual_worker_exit']==read(AUDIT/'WORKER_EXIT.json')['actual_worker_exit']==0
assert read(AUDIT/'VERIFICATION.json')['verified_independent_window_audit']
analysis=read(EXTRACT/'ANALYSIS.json');candidates=[r for r in analysis['results'] if r['case']['actor']=='latch60']
assert len(candidates)==2
for case in candidates:
    post=[w for name,w in case['windows'].items() if name!='before5s']
    assert sum(w['rows'] for w in post)==2400
    assert all(w['guard_ticks']==w['g_guard_input_ticks']==w['energy_guard_input_ticks']==w['throttle_at_max_ticks']==0 for w in post)
    assert all(w['forward_nose_ticks']==0 for w in post)
    assert all(w['median_abs_roll_tracking_error_deg']<2 and w['median_speed_goal_kts']==290 for w in post)
b.source_gate(read(RUN/'CONTRACT.json'));assert b.base.inventory()==[]
identities=[]
for folder in (EXTRACT,AUDIT):
    c=read(folder/'CONTRACT.json');receipt=read(folder/'WORKER_EXIT.json');identities.extend([c['guardian'],receipt['identity']]);identities.extend(r['identity'] for r in receipt['descendants'])
ids=list({(i['pid'],i['create']):i for i in identities}.values());checks=[]
for old in ids:
    try:current=b.identity(old['pid'])
    except psutil.NoSuchProcess:current=None
    same=current is not None and all(old[k]==current[k] for k in ('pid','create','cmd','exe'))
    assert not same;checks.append(dict(recorded=old,current=current,original_core_live=False))
write(AUDIT/'TERMINAL_AUDIT.json',dict(observed_utc=now,identities=checks,original_core_identities_absent=True,other_campaign_workloads=[],source_unchanged=True))
findings=dict(status='completed_verified_selected_window_diagnostic',extract=str(EXTRACT),independent_audit=str(AUDIT),selected_rows=10800,source_complete_games=4,new_FDM_ticks=0,controller_projection_calls=0,model_inference_calls=0,training_started=False,candidate_posttrigger_rows=4800,guard_active_ticks=0,G_limiter_input_ticks=0,energy_guard_input_ticks=0,full_throttle_ticks=0,all_candidate_window_median_roll_tracking_error_below_2deg=True,post20to40=[dict(case=r['case']['id'],median_roll_tracking_error_deg=r['windows']['after20to40s']['median_abs_roll_tracking_error_deg'],median_CAS_kts=r['windows']['after20to40s']['median_CAS_kts'],speed_goal_kts=r['windows']['after20to40s']['median_speed_goal_kts'],median_abs_speed_error_kts=r['windows']['after20to40s']['median_abs_speed_error_kts'],median_heading_error_abs_deg=r['windows']['after20to40s']['median_abs_heading_error_deg'],HSL_change_m=r['windows']['after20to40s']['HSL_change_m']) for r in candidates],scope='Four selected -5..+40s windows relative to first actual latch command difference. Full battle safety/gate unchanged. No new fix/counterfactual tested.',inference='In selected candidate windows the inner controller tracks roll/speed goals and no logged safety/G/energy guard is active. This disfavors safety blocking or full-throttle inability as the primary local explanation; pursuit geometry and range-dependent speed targets deserve a controlled test.',not_proven='Removing the 290kt ceiling may reduce turning performance or worsen safety/position. No evidence yet that accelerating wins or that these windows explain every episode.',deployment_allowed=False)
write(EXTRACT/'FINDINGS.json',findings)
plan=dict(status='proposed_not_implemented',basis=str(EXTRACT/'FINDINGS.json'),hypothesis='The hard 290kt speed target outside firing range with |heading error|>45 may constrain energy/repositioning in the saturated pursuit law. Remove that ceiling only and measure; higher speed can also hurt turning and is not presumed beneficial.',single_factor='Only disable the far distance>914.4m heading-based speed ceiling290 in zero-tactical StationController. Retain original unlatched roll72, same pitch/rudder, final speed bounds260..450, and original inner safety/G/trim/slew. No bank60/latch branch or simultaneous controller changes.',implementation_scope='New isolated wrapper before unchanged command. Reconstruct original pre-ceiling speed from legal packet geometry and zero tactical law; outside specified condition emit identical original goals. Verify source formula and exact helper module binding before launch.',baseline='Original zero-tactical unlatched StationController72, not pure repair_guide',candidate='Same72 controller, only far heading speed ceiling removed',red='Fixed frozen sac5000',prerequisites=['No current learner/evaluation; new unique output and unclaimed seed registry entries','Exact frozen source/XML/red model hashes, OS lock, STOP and CPU/RAM/disk/GPU-used flags','Static/saved-packet tests for conditional speed mapping, unchanged bank/pitch/rudder/safety/reset; NumPy scalar JSON and proper ACMI geodetic mapping','Same both-aircraft initial SHA per pair; new development openings including opposite side, not holdout'],planned_games=4,planned_pairs=2,worker_hard_seconds=90,whole_hard_seconds=600,verifier_cap_seconds_preplanned=120,seeds_selected=False,seeds_claimed=False,FDM_started=False,training_started=False,acceptance='Complete games and actual0 receipts with full source/initial/red policy/judge/CSV/ACMI checks; reject any >9G. Compare event/score/hits/death/crash/collision and common AGL per opening. Loss/regression cannot be hidden in average; no promotion from two development openings.',no_parameter_sweep=True,deployment_allowed=False,formal_deployment='repair_guide')
write(EXTRACT/'NEXT_HYPOTHESIS.json',plan)
ledger=read(ROOT/'compute_budgets'/f'{datetime.datetime.now().date().isoformat()}.json')
metrics=findings['post20to40'];lines=[]
for x in metrics:lines.append(f"- {x['case']}：觸發後20–40秒，傾角追蹤誤差中位數{x['median_roll_tracking_error_deg']:.3f}度；速度目標{x['speed_goal_kts']:.0f}節、實際CAS中位數{x['median_CAS_kts']:.3f}節、絕對速度誤差中位數{x['median_abs_speed_error_kts']:.3f}節；方位誤差仍{x['median_heading_error_abs_deg']:.2f}度。")
body=f'''## {now} 保存視窗：追擊目標與實際執行核對

- 只分析四條既有軌跡各首次差異前5秒至後40秒，合計10,800列；沒有新FDM、模型推論、controller投影、訓練或seed claim。沒有重跑四場或全72,000幀控制器追蹤。
- 兩候選觸發後合計4,800列：logged guard、8.5G輸入、失速/能量保護條件及滿油門均0；各候選後續視窗的傾角追蹤誤差中位數都小於2度，速度目標都是290節，目標仍未回到前半球。
{chr(10).join(lines)}
- 本地推論：這些視窗不支持「安全層擋住轉向」或「已滿油門卻無法加速」作為主要解釋。機體有跟到指定目標；應檢查追擊幾何與距離切換的速度目標。這不是完整根因證明，也沒有證明加速會贏。
- 第一階段CSV回讀不是獨立數學審查；另立120秒NumPy unwrap差分、向量化合法座標幾何、fps→節與關鍵中位數獨立核對10,800列，實際worker/guardian皆0。提取8.016秒、審查6.281秒，原120+120秒預留皆計入不退款；今日預留{ledger['reserved_hours']:.6f}h。{len(checks)}個新記錄原core身分已無，來源/XML/模型固定。
- 具體下一假設（尚未實作/啟動）：回到原未latch的72度StationController，只移除距離>914.4m且大方位誤差時的290節速度頂限；保留260–450節總界限與原安全/轉向/俯仰等。先隔離與保存packet檢查，再新開局同initial SHA四場比較；速度增加可能惡化轉彎，沒有預設會成功。這是新因子，不是重跑已否決latch或掃下一bank角度。
- 原latch四場仍否決、不部署；正式repair_guide與原模型保留。10/17報名提醒不重寄；目前無需本人操作。

證據：{EXTRACT/'FINDINGS.json'}；{AUDIT/'VERIFICATION.json'}；下一步：{EXTRACT/'NEXT_HYPOTHESIS.json'}。
'''
for name in ('REVIEW_LOG.md','RACE_FOCUS_20261017.md'):
    with (ROOT/name).open('a',encoding='utf8') as f:f.write('\n\n'+body)
(ROOT/'latest_result.md').write_text('# 最新研究進度（10/17）\n\n'+body,encoding='utf8')
j=read(ROOT/'research_latest.json');j.update(updated_utc=now,latest_latch_window=str(EXTRACT),latest_latch_window_audit=str(AUDIT),current_research_diagnostic=dict(status='completed_verified_selected_window_diagnostic',run=str(EXTRACT),verification=str(AUDIT/'VERIFICATION.json'),actual_worker_exit=0,actual_guardian_exit=0,new_FDM_ticks=0,controller_projection_calls=0),next_session_plan=str(EXTRACT/'NEXT_HYPOTHESIS.json'),next_action='依NEXT_HYPOTHESIS先隔離實作原72規則的遠距290節速度頂限移除，其他目標/安全不改；先保存packet與合法輸出/單次command測試，再新seed/同initial配對四場，90秒每worker、600秒含預先120秒核對。只是待測假設，未啟新FDM或訓練。',next_factor_status='far_speed_ceiling_removal_proposed_not_implemented',next_factor='Only far speed ceiling290; original72 unlatched zero-tactical baseline',candidate_factor='Rear turn-direction latch only; completed rejected mechanism branch',paired_baseline='unlatched_bank60_zero_tactical_station_not_pure_repair_guide',blue_actor_policy_used=False,red_actor_policy_used=True,nonzero_attack_counter_exercised=True,daily_compute_reserved_hours=ledger['reserved_hours'],reservation_id=RUN.name,wall_seconds=read(RUN/'GUARD_EXIT.json')['wall_seconds'],actual_parent_exit_observation=str(RUN/'PARENT_EXIT_OBSERVED.json'),actual_verifier_exit_code=2,verification_mode='independent_saved_data_audit_coordinate_mapping_corrected_original_failure_preserved',current_verifier=dict(mode='independent_saved_data_audit',actual_internal_exit=0,actual_guardian_exit=0,receipt=str(ROOT/'diagnostics/saved_latch_audit_v1_20261017_204803_78cf4a/WORKER_EXIT.json'),parent_observation=str(ROOT/'diagnostics/saved_latch_audit_v1_20261017_204803_78cf4a/PARENT_EXIT_OBSERVED.json'),original_failed_verifier=str(RUN/'VERIFIER_EXIT.json')),latest_usage_observation=read(EXTRACT/'CONTRACT.json')['usage_observation'],active_workload=None,current_live_workloads=dict(learners=[],loops=[],evaluations=[],observed_utc=now))
write(ROOT/'research_latest.json',j)
pipeline=read(ROOT/'pipeline_latest.json');pipeline['updated_utc']=now;pipeline['race_focus_update'].update(latest_diagnostic=str(AUDIT/'VERIFICATION.json'),next_research=str(EXTRACT/'NEXT_HYPOTHESIS.json'),next_factor_status='far_speed_ceiling_removal_proposed_not_implemented');write(ROOT/'pipeline_latest.json',pipeline)
event=EXTRACT.name+'|completed_verified_selected_window_diagnostic|'+sha(EXTRACT/'FINDINGS.json')
for name in ('monitor_notice.json','review_notice.json'):
    notices=read(ROOT/name);notices.setdefault('events',{})[event]=dict(status='completed_verified_selected_window_diagnostic',evidence_sha256=sha(EXTRACT/'FINDINGS.json'),observed_utc=now,channel='ai heartbeat',requires_user_action=False,summary='10800 saved-window rows independently audited; roll/speed follow requested targets, no guard; propose speed-ceiling factor, not executed');write(ROOT/name,notices)
print(json.dumps(dict(findings=metrics,next_plan=str(EXTRACT/'NEXT_HYPOTHESIS.json'),reserved_hours=ledger['reserved_hours'],new_FDM_ticks=0,identities_absent=len(checks)),ensure_ascii=False))
