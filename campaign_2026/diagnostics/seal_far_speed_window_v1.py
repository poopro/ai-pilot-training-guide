"""Seal actual observed exit and interpretation; never launches a simulation."""
from pathlib import Path
import datetime,json,sys,psutil
ROOT=Path(r'E:\ai_pilot\campaign_2026');SOURCE=ROOT/'experiments/opponent_pool/far_speed_v1'
sys.path.insert(0,str(SOURCE));import battle as b
read,write,sha=b.read,b.write,b.sha
def main(out):
    spec=read(out/'CONTRACT.json');a=read(out/'ANALYSIS.json');v=read(out/'VERIFICATION.json');exit=read(out/'WORKER_EXIT.json')
    assert v['verified_selected_saved_packet_math'] and v['errors']==[] and a['selected_rows']==v['selected_rows']==8101
    assert exit['actual_worker_exit']==0 and exit['reason'] is None and exit['absent']
    assert sha(ROOT/'diagnostics/far_speed_window_guardian_v1.py')==spec['diagnostic_source_sha256']
    assert sha(ROOT/'diagnostics/far_speed_window_worker_v1.py')==spec['analysis_worker_sha256']
    run=Path(spec['source_run']);b.source_gate(read(run/'CONTRACT.json'))
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    write(out/'PARENT_EXIT_OBSERVED.json',dict(actual_exit=0,observation_source='unified exec Windows process wait',session_id=90706,chunk_id='10ed8e',observed_utc=now,actual_wall_seconds=11.172,identity=spec['guardian']))
    ids=[spec['guardian'],exit['identity']]+[d['identity'] for d in exit['descendants']];audit=[]
    for old in ids:
        try:current=b.identity(old['pid'])
        except psutil.NoSuchProcess:current=None
        same=current is not None and all(old[k]==current[k] for k in ('pid','create','cmd','exe'));assert not same
        audit.append(dict(recorded=old,current=current,original_core_live=False))
    assert b.base.inventory()==[]
    write(out/'TERMINAL_AUDIT.json',dict(observed_utc=now,identities=audit,all_original_core_absent=True,source_fixed=True,other_campaign_workloads=[]))
    late=[dict(case=x['case']['id'],**x['windows']['late240to260s']) for x in a['results']]
    findings=dict(status='completed_verified_saved_windows',analysis=str(out/'ANALYSIS.json'),verification=str(out/'VERIFICATION.json'),selected_rows=8101,
        actual_worker_exit=0,actual_parent_exit=0,wall_seconds=11.172,
        evidence=['In both speed-unclipped late windows all1200 raw goals exceed450; median raw532.026/547.670, enemy-equivalentCAS proxy441.229/439.059 plus desired-closeCAS term96.124/108.611 (medians not additive identities).',
        'Late actualCAS444.092/450.715 follows target450; guard and8.5G input zero; actualbank tracks within median1.892/2.333degrees. Not a simple failure to apply speed or bank in these windows.',
        'At the same240–260s times original72 CAS290.076/290.337, heading-rate6.576/7.155deg/s versus accelerated4.837/4.939; candidate median headingerror139.186/153.516 versus70.833/60.908. These are paired trajectory observations, not isolated speed-cause proof.',
        'Candidate normal minimum occurs at terminaltick18000, mirrored minimum at firstposttick1. Their clipped closest windows are not two full +/-5s events. No extrapolated future samples.',
        'Original72 closest-window LOS rates13.126/14.000deg/s exceed own heading rates6.632/7.162; shows a pursuit geometry/turn-response gap in those windows, not a reason to blindly raise speed or bank.'],
        limitations=['Only8101 unique selected saved rows, not fullflight causal attribution. Stream-reading artifacts is not controller replay or new combat.',
        'Enemy-equivalentCAS is enemy velocity-magnitude proxy times own CAS/TAS ratio, not measured enemyCAS/TAS or true enemy heading.',
        'HSL pre-command versus AGL post-step kept separate. Side seeds differ; no independent left/right causal claim.',
        'Scalar trace calculations were independently audited using vector NumPy in the same bounded worker, not an independent second simulation/process.',
        'No trained model, improved combat score or winning correction produced by this diagnostic.'],
        deployment_allowed=False,new_FDM_ticks=0,controller_calls=0,model_inference_calls=0,training_started=False,seed_claims=[])
    write(out/'FINDINGS.json',findings)
    plan=dict(status='proposed_not_implemented',hypothesis='The current StationController doctrine may be weaker against the frozenSAC opponent than the retained pure repair_guide. Test the two existing rule controllers directly before changing further speed/bank constants or training on an ineffective action channel.',
        rationale='Acceleration reaches its target but does not solve pursuit. All recent complete far60/latch/speed variants regress; compare the actual retained baseline with StationController rather than optimizing a rejected branch. No claim pure repair_guide will win.',
        single_factor='Blue guidance controller family only: frozen zero-tactical StationController original72 versus exact retained RepairController.act with residual=None. Shared inherited command/safety/G/trim/slew remain frozen. Not a one-line ablation or attribution to one doctrine subterm.',
        baseline='station_zero original72, NOT pure repair_guide',candidate='pure repair_guide frozen repair_v1/controller.py; must verify actual runtime source and no tactical injection',
        red='same frozen sac5000, independent controller/clock/cache/reset/privatecounter',
        next_work='Build isolated wrapper and precheck actual RepairController.act wiring. Verify singleact/command/send, source/reset, legalOWN26 policy, actual runtime class/MRO and fresh state, no extra tactics or reused controller state. No source edits to frozen original.',
        FDM_launch_allowed=False,reason='No pure-guide comparison runner/precheck/contract or new seeds have been implemented/claimed; new guarded precheck required first.',
        contingent_full_comparison=dict(new_unused_openings=2,explicit_sides=['normal','mirrored'],same_both_initial_SHA_within_each_pair=True,games=4,seconds_per_worker=90,total_hard_seconds=600,strict_verification_seconds_included=120,
            gates=['unique_output','unused_seedregistry','OSlock','STOP','resources','source_XML_red_model_SHA','independent_original_watchdog','actual_exits0','fulljudge/event/score/CSV/ACMI','runtime_controller_class_and_source_receipt'],
            reports=['wins/losses','attack/kill/death/crash/collision/over9G','scoremargin','inrange/frontinrange','commonAGL','worstcase'],candidate_over9G='reject',deployment_allowed=False),
        no_speed_or_bank_sweep=True,no_blind_SAC=True,no_replay_completed_batches=True,new_training_allowed=False,seed_claims=[],uncertainty='Proposed comparison only; no evidence of pure-guide advantage over this frozen opponent.')
    write(out/'NEXT_HYPOTHESIS.json',plan)
    lp=ROOT/'compute_budgets'/f'{datetime.datetime.now().date().isoformat()}.json';ledger=read(lp)
    for item in ledger['items']:
        if item['id']==out.name:item.update(status='completed_verified_saved_window_diagnostic',actual_parent_exit=0,actual_worker_exit=0,actual_wall_seconds=11.172,selected_rows=8101)
    write(lp,ledger)
    next_action='保存窗口已核對：先隔離建立pure repair_guide與原72零戰術StationController的真接線前測，再新開局完整配對固定sac5000；不是再掃速度/bank，不續SAC。新runner/前測尚未實作，不可直接啟FDM。'
    j=read(ROOT/'research_latest.json');j.update(updated_utc=now,active_workload=None,current_process_alert=None,current_live_workloads=dict(learners=[],loops=[],evaluations=[],observed_utc=now),latest_far_speed_window=str(out),latest_saved_diagnostic=dict(run=str(out),verification=str(out/'VERIFICATION.json'),findings=str(out/'FINDINGS.json'),actual_parent_exit=0,actual_worker_exit=0,selected_rows=8101,scope='saved_selected_packets_only_no_new_FDM'),next_action=next_action,next_session_plan=str(out/'NEXT_HYPOTHESIS.json'),next_factor_status='proposed_rule_controller_comparison_not_implemented',daily_compute_reserved_hours=ledger['reserved_hours'],latest_usage_observation=spec['usage_observation'])
    write(ROOT/'research_latest.json',j)
    p=read(ROOT/'pipeline_latest.json');p['updated_utc']=now;p['race_focus_update'].update(latest_saved_diagnostic=str(out/'FINDINGS.json'),next_research=str(out/'NEXT_HYPOTHESIS.json'),next_factor_status='proposed_rule_controller_comparison_not_implemented',formal_deployment='repair_guide',training_started=False);write(ROOT/'pipeline_latest.json',p)
    note=f'''## {now} 遠距速度候選的保存窗口診斷

- 新獨立120s契約/OSlock/STOP/資源與來源模型XML檢查，四條保存軌跡只計算8101個不重複窗口列；0–10s、240–260s及最近距離±5s（終局/首幀會截斷）。標量公式與同worker獨立NumPy幾何/速度/角速度核對通過。worker/guardian實際0，11.172s；3原core身份已無，無新FDM、act/controller投影、模型推論、訓練或seedclaim。
- 兩加速候選後期各1200/1200列raw speed超450，raw中位532.026/547.670kt；實際CAS444.092/450.715、目標450。guard/8.5G輸入0，bank跟蹤中位誤差1.892/2.333度。窗口不支持「完全沒有套用速度/傾角」解釋。
- 同240–260s原72航向角速度6.576/7.155deg/s，候選4.837/4.939；候選heading error139.186/153.516deg。原72各最近距離窗口LOS13.126/14.000deg/s高於自己航向6.632/7.162deg/s。此為保存軌跡局部證據，不把單項當完整因果。
- 敌等效CAS只由ENEMY6地速proxy乘自己CAS/TAS比值，不是敵真CAS/TAS；raw項中位數不可以當逐列加法等式。HSL pre與AGL post分開。候選normal最近在終局、mirror最近在首幀，窗口截斷明標。
- 決策：加速候選仍reject_position_score_regression；無新戰力或勝率，正式repair_guide與兩模型保留。下一個可檢驗假設是「純repair_guide是否比StationController追擊教義更有效」，先比較真實既有基準，不再盲掃速度/bank。這是控制器家族一因素比較，不能把之後差異歸因某一行；尚未實作runner/前測/選seed/開FDM。
- 新日預留{ledger['reserved_hours']:.6f}h（新增120秒），歷史預留不退款。用量真UTC2026-10-17 22:33:58，較低剩餘96%，無credits/reset使用。

證據：{out/'ANALYSIS.json'}；{out/'VERIFICATION.json'}；{out/'FINDINGS.json'}；{out/'NEXT_HYPOTHESIS.json'}。
'''
    for name in ('REVIEW_LOG.md','RACE_FOCUS_20261017.md'):
        with (ROOT/name).open('a',encoding='utf8') as f:f.write('\n\n'+note)
    (ROOT/'latest_result.md').write_text('# 最新進度（10/18）\n\n'+note+'\n最近完整對戰：far_speed_v1四場全部核對通過，原72為1勝1負，速度候選0勝2負、雙方全0命中/過9G；候選拒絕。\n',encoding='utf8')
    event=out.name+'|completed_verified_saved_windows|'+sha(out/'FINDINGS.json')
    for name in ('monitor_notice.json','review_notice.json'):
        notices=read(ROOT/name);notices.setdefault('events',{})[event]=dict(status='completed_verified_saved_windows',report=str(out/'FINDINGS.json'),evidence_sha256=sha(out/'FINDINGS.json'),notified_utc=now,channel='ai heartbeat',requires_user_action=False);write(ROOT/name,notices)
    print(json.dumps(dict(diagnostic=str(out),verified=True,selected_rows=8101,identities_absent=len(ids),reserved_hours=ledger['reserved_hours'],next_plan=str(out/'NEXT_HYPOTHESIS.json')),ensure_ascii=False))
if __name__=='__main__':main(Path(sys.argv[1]))
