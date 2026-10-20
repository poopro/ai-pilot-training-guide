from pathlib import Path
import json,sys,datetime,psutil
ROOT=Path(r'E:\ai_pilot\campaign_2026');SOURCE=ROOT/'experiments/opponent_pool/far_speed_v1'
sys.path.insert(0,str(SOURCE));import battle as b
read,write,sha=b.read,b.write,b.sha
def main(out):
    c=read(out/'COMPARISON.json');r=read(out/'SAFETY_REVIEW.json');spec=read(out/'CONTRACT.json');phase=read(out/'LOCKED_VERIFIER_EXIT.json')
    assert c['verified_comparison'] and c['errors']==[] and c['complete_games']==4
    assert read(out/'PARENT_EXIT_OBSERVED.json')['actual_exit']==read(out/'VERIFIER_PARENT_EXIT_OBSERVED.json')['actual_exit']==read(out/'VERIFIER_EXIT.json')['actual_exit']==phase['actual_guarded_wrapper_exit']==0
    assert phase['reason'] is None and phase['absent'];b.source_gate(spec)
    ids=[spec['guardian'],read(out/'VERIFICATION_PHASE_CONTRACT.json')['wrapper'],phase['identity'],read(out/'VERIFIER_EXIT.json')['identity']]
    for receipt in read(out/'report.json')['cases']:
        assert receipt['actual_worker_exit']==0 and receipt['worker_and_descendants_absent'];ids.append(receipt['identity']);ids.extend(d['identity'] for d in receipt['descendants'])
    ids.extend(d['identity'] for d in phase['descendants']);ids=list({(i['pid'],i['create']):i for i in ids}.values());audit=[]
    for old in ids:
        try:current=b.identity(old['pid'])
        except psutil.NoSuchProcess:current=None
        same=current is not None and all(old[k]==current[k] for k in ('pid','create','cmd','exe'));assert not same
        audit.append(dict(recorded=old,current=current,original_core_live=False))
    assert b.base.inventory()==[]
    if any(x['over9G'][0] for x in r['results'] if x['case']['actor']=='far_speed_unclipped'):assert r['gate']=='reject_candidate_safety_or_death'
    now=datetime.datetime.now(datetime.timezone.utc).isoformat();write(out/'TERMINAL_AUDIT.json',dict(observed_utc=now,identities=audit,other_campaign_workloads=[],source_unchanged=True,all_original_core_absent=True))
    next_action=('先用本批保存遙測分析逐對最差命中/高度/score視窗，凍結候選；再設有上限的新對手或新開局驗證，不部署或盲續訓練。' if r['gate'].startswith('promising') or r['gate'].startswith('mixed') else '否決本速度候選，使用保存首次命令差異與最差case分析相對航跡/瞄準，先形成一個可檢驗假設；不重跑本批、不掃下一速度或盲續SAC。')
    plan=dict(status='saved_data_review_planned_no_new_simulation',source=str(out/'SAFETY_REVIEW.json'),gate=r['gate'],next_action=next_action,focus='Use actual changed-speed ticks, actual command difference, in-range body angles, score and common-height exposure; distinguish pursuit geometry from simply being closer/faster.',new_FDM_started=False,training_started=False,no_parameter_sweep=True,deployment_allowed=False)
    write(out/'NEXT_REVIEW.json',plan)
    lp=ROOT/'compute_budgets'/f'{datetime.datetime.now().date().isoformat()}.json';ledger=read(lp)
    for item in ledger['items']:
        if item['id']==out.name:item.update(status='completed_verified_development',actual_parent_exit=0,actual_verifier_exit=0,actual_parent_wall_seconds=read(out/'GUARD_EXIT.json')['wall_seconds'],actual_verification_phase_wall_seconds=phase['wall_seconds'],original_600s_reservation_retained=True)
    write(lp,ledger)
    reg=read(ROOT/'seed_registry.json')
    for item in reg['trials'].values():
        if item.get('output')==str(out):item.update(status='completed_verified_development',comparison=str(out/'COMPARISON.json'),gate=r['gate'],reusable=False)
    write(ROOT/'seed_registry.json',reg)
    j=read(ROOT/'research_latest.json');j.update(updated_utc=now,status='completed_verified_development',experiment='far_speed_v1',run=str(out),report=str(out/'report.json'),comparison=str(out/'COMPARISON.json'),verified_comparison=True,gate=r['gate'],candidate_gate=r['gate'],safety_review=str(out/'SAFETY_REVIEW.json'),source_manifest=str(out/'CONTRACT.json'),source_hashes_verified=True,actual_parent_exit_code=0,actual_parent_exit_observation=str(out/'PARENT_EXIT_OBSERVED.json'),parent_exit_receipt=str(out/'PARENT_EXIT_OBSERVED.json'),benchmark_return_code=0,actual_verifier_exit_code=0,verification_mode='locked_strict_verifier_within_original600_and_phase120',current_verifier=dict(actual_internal_exit=0,actual_guarded_exit=0,actual_phase_wrapper_exit=0,receipt=str(out/'VERIFIER_EXIT.json'),phase_receipt=str(out/'LOCKED_VERIFIER_EXIT.json'),actual_phase_observation=str(out/'VERIFIER_PARENT_EXIT_OBSERVED.json')),wall_seconds=read(out/'GUARD_EXIT.json')['wall_seconds'],active_workload=None,current_process_alert=None,current_live_workloads=dict(learners=[],loops=[],evaluations=[],observed_utc=now),supervisor=None,guardian=None,worker=None,complete_games=4,completed_pairs=2,new_FDM_ticks=c['new_FDM_ticks'],nonzero_attack_counter_exercised=c['nonzero_attack_counter_exercised'],next_action=next_action,next_session_plan=str(out/'NEXT_REVIEW.json'),next_factor_status='completed_single_factor_development_not_deployed',daily_compute_reserved_hours=ledger['reserved_hours'],daily_compute_reserved_date=datetime.datetime.now().date().isoformat(),terminal_process_audit=str(out/'TERMINAL_AUDIT.json'),deployment_allowed=False,retained_deployment='repair_guide',training_started=False,latest_usage_observation=spec['usage_observation']);write(ROOT/'research_latest.json',j)
    p=read(ROOT/'pipeline_latest.json');p['updated_utc']=now;p['race_focus_update'].update(latest_comparison=str(out/'COMPARISON.json'),latest_safety_review=str(out/'SAFETY_REVIEW.json'),candidate_gate=r['gate'],next_research=str(out/'NEXT_REVIEW.json'),next_factor_status='completed_single_factor_development_not_deployed',formal_deployment='repair_guide',training_started=False);write(ROOT/'pipeline_latest.json',p)
    prep=read(SOURCE/'PREPARATION.json');prep.update(status='consumed_completed_verified_development',FDM_launch_allowed=False,completed_run=str(out),new_FDM_ticks=c['new_FDM_ticks'],worker_or_seed_launched=True,reason='Completed new bounded development; earlier resource-only refusal retained in its own report',gate=r['gate'],same_trial_must_not_restart=True);write(SOURCE/'PREPARATION.json',prep)
    lines=[]
    for pair in r['pairs']:
        candidate=next(x for x in r['results'] if x['case']['opening']==pair['opening'] and x['case']['actor']=='far_speed_unclipped')
        lines.append(f"- {pair['side']}：原72／移除速度頂限勝方 {pair['baseline_winner']}／{pair['candidate_winner']}；藍分差 {pair['baseline_margin']:.3f}→{pair['candidate_margin']:.3f}，命中 {pair['baseline_attacks'][0]}→{pair['candidate_attacks'][0]} tick，射程內 {pair['baseline_in_range']}→{pair['candidate_in_range']} tick，前半球射程 {pair['baseline_front_in_range']}→{pair['candidate_front_in_range']} tick，共同最低AGL差 {pair['common_minimum_AGL_delta_m']:+.3f}m；候選過9G {pair['candidate_over9G'][0]}tick、死亡/墜機/collision {candidate['blue_deaths']}/{candidate['blue_crashes']}/{candidate['collisions']}，首次真命令差異tick{pair['first_actual_command_difference_tick']}。")
    text=f'''## {now} 遠距速度頂限單因素：四場完整開發比較

- 資源已自然恢復；未停止無關程式、未降低RAM2GiB閘門。16項前置檢查與兩原72保存開局各首300幀的真inner-command baseline重現通過，父/worker真0，11.282秒；候選只改速度目標600幀，不是對戰證據。
- 唯一因素：移除距離>914.4m且|heading error|>45時290節速度頂限，保留260–450節總界限、原未latch bank72/俯仰/rudder/安全G/trim/slew。零戰術StationController基準，不是pure repair_guide。
- 全新seed2026310700/1，4/4完整／2同雙方initialSHA配對／{c['new_FDM_ticks']}真FDM步，固定sac5000紅方。parent、四worker、strict verifier、locked wrapper與實際工具退出皆0，source/XML/model/runtime module/逐幀judge/紅方推論/目標映射/CSV全欄及ACMI核對通過；原90s/worker、600s全批與120s核對上限不延長。
{chr(10).join(lines)}
- 決策：{r['gate']}。逐開局取捨保留，不用平均掩蓋；只是兩個開發開局、不是保留集或未知隊伍勝率。沒有新訓練，不部署，正式repair_guide與兩原模型保留。
- 新日預留{ledger['reserved_hours']:.6f}h，昨日1.4h及歷史失敗不退款。{len(ids)}個記錄原core身分已無或已重用，不清理重用PID。
- 下一步：{next_action}

證據：{out/'COMPARISON.json'}；{out/'SAFETY_REVIEW.json'}；{out/'TERMINAL_AUDIT.json'}。
'''
    for name in ('REVIEW_LOG.md','RACE_FOCUS_20261017.md'):
        with (ROOT/name).open('a',encoding='utf8') as f:f.write('\n\n'+text)
    (ROOT/'latest_result.md').write_text('# 最新對戰結果（10/18）\n\n'+text,encoding='utf8')
    event=out.name+'|'+r['gate']+'|'+sha(out/'SAFETY_REVIEW.json')
    for name in ('monitor_notice.json','review_notice.json'):
        notices=read(ROOT/name);notices.setdefault('events',{})[event]=dict(status=r['gate'],report=str(out/'SAFETY_REVIEW.json'),evidence_sha256=sha(out/'SAFETY_REVIEW.json'),notified_utc=now,channel='ai heartbeat',requires_user_action=False);write(ROOT/name,notices)
    print(json.dumps(dict(gate=r['gate'],pairs=r['pairs'],results=r['results'],reserved_hours=ledger['reserved_hours'],identities_absent=len(ids)),ensure_ascii=False))
if __name__=='__main__':main(Path(sys.argv[1]))
