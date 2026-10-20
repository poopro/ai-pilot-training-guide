"""Record wiring success and the negative activation result, not combat gains."""
from pathlib import Path
import datetime,json,sys,psutil
ROOT=Path(r'E:\ai_pilot\campaign_2026');SOURCE=ROOT/'experiments/opponent_pool/far_speed_v1';NEW=ROOT/'experiments/opponent_pool/rule_family_v1'
sys.path.insert(0,str(SOURCE));import battle as b
read,write,sha=b.read,b.write,b.sha
def main():
    pre=ROOT/'diagnostics/rule_family_precheck_v1_20261018_092908_52c797';out=ROOT/'diagnostics/rule_family_activation_v1_20261018_093119_cda2d7'
    v=read(out/'VERIFICATION.json');assert v['verified_bounded_prefix_activation_search'] and v['errors']==[] and not v['command_difference_observed']
    assert v['total_tested_saved_frames']==7200 and v['history_only_frames']==600 and v['new_suffix_saved_frames']==6600
    assert all(x['goal_difference_ticks']==0 and len(set(x['prefix_output_sha256'].values()))==1 for x in v['results'])
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    write(out/'PARENT_EXIT_OBSERVED.json',dict(actual_exit=0,session_id=68456,chunk_id='e72bf6',actual_wall_seconds=66.359,observed_utc=now,observation_source='unified exec process wait'))
    all_ids=[]
    for directory in (pre,out):
        spec=read(directory/'CONTRACT.json');e=read(directory/'WORKER_EXIT.json')
        assert e['actual_worker_exit']==read(directory/'PARENT_EXIT_OBSERVED.json')['actual_exit']==0 and e['reason'] is None and e['absent']
        assert sha(ROOT/'diagnostics'/('rule_family_precheck_guardian_v1.py' if directory==pre else 'rule_family_activation_guardian_v1.py'))==spec['diagnostic_source_sha256']
        for p,h in spec['new_sources'].items():assert sha(Path(p))==h
        b.source_gate(read(Path(spec['source_run'])/'CONTRACT.json'))
        ids=[spec['guardian'],e['identity']]+[d['identity'] for d in e['descendants']];audit=[]
        for old in ids:
            try:current=b.identity(old['pid'])
            except psutil.NoSuchProcess:current=None
            assert current is None or not all(old[k]==current[k] for k in ('pid','create','cmd','exe'))
            audit.append(dict(recorded=old,current=current,original_core_live=False));all_ids.append(old)
        write(directory/'TERMINAL_AUDIT.json',dict(observed_utc=now,identities=audit,all_original_core_absent=True,source_fixed=True))
    assert b.base.inventory()==[]
    findings=dict(status='wiring_verified_no_control_difference_in_tested_prefixes',precheck=str(pre/'VERIFICATION.json'),activation=str(out/'VERIFICATION.json'),
        actual_parent_exits=[0,0],actual_worker_exits=[0,0],actual_wall_seconds=[14.547,66.359],
        findings=['Real pure RepairController and zero-tactical StationController wiring/reset/safety parity passed12 check groups over two saved300-packet prefixes.',
        'The two real controllers produced identical requested goals and actual command outputs at every one of the3600 common saved packets per opening; output SHA equal within each opening.',
        'The activation search reconstructed the already checked first300-frame history per opening, then checked6600 additional suffix packets. It stopped at60s/case; not all300s.',
        'These are counterfactual controller calls on saved legal input, not newly sent FDM actions. No new combat games, learned inference or training occurred.'],
        decision='Do not spend four new full games on the proposed family swap yet. Replacing the class alone has no observed authority in the tested prefix; no stronger model/rule result claimed.',
        limitations=['No proof the two controllers remain equivalent later in300s or on every opening/opponent.',
        'Synthetic lowalt/energy/8.6G parity is source behavior testing, not closed-loop over9G safety evidence.',
        'Policy wrappers and temporary controller states are isolated; formal sources/models unchanged.'],
        new_FDM_ticks=0,new_model_inference_calls=0,training_started=False,seed_claims=[],deployment_allowed=False)
    write(out/'FINDINGS.json',findings)
    next_plan=dict(status='proposed_not_implemented',hypothesis='The learned controller needs a verified path to change an actual command when baseline guidance is saturated. Test the existing frozen RepairController bank-residual input before any new training or four-game family comparison.',
        single_factor='Offline input-contract authority check only: original RepairController.act with bank-only residual versus residual=None; other residual components0. Keep the controller file, existing dynamic residual limits/final72 bank bound and inherited command/safety/trim/slew unchanged.',
        rationale='Family swap showed zero goal/output difference on two60s prefixes, consistent with earlier M4 tactical-goal clipping. Do not repeat an ineffective policy channel or tune another permanent speed/bank.',
        test='New bounded saved-packet diagnostic. Exact-source direct controller, neutral history; clone private controller state before a call for bank residual -1/0/+1 using existing API limits, never change original limits. Compare true act/command outputs and goals; zero residual must exactly reproduce residual=None. Probe legal finite input, private settings/state, inherited safety and reset. First-difference/clipping/slew reports, no simulation.',
        inputs='At most two saved300-packet prefixes (common legal OWN26), no full72k/108k projection. Any history reconstruction is labeled and not counted as new combat evidence.',
        hard_wall_seconds=120,required_gates=['new_unique_output','reserve_before_worker','OSlock','STOP','resources','fixed_sources_XML_models_and_saved_artifacts','independent_watchdog','actual_parent_worker_exit0','source_and_exact_identity_terminal_audit'],
        no_new_FDM=True,no_model_inference=True,no_seed_claim=True,no_parameter_sweep=True,training_allowed=False,FDM_launch_allowed=False,
        pass_is_not_strength='Nonzero control influence is only an interface requirement. It does not show improvement or dynamic9G safety. A subsequent bounded training/fair comparison needs its own new contract/opponent diversity/unused seeds/full score and safety evidence.',
        model_compatibility='Existing old5k/10k actors have3 tactical outputs with different semantics; do not relabel them as a bank residual, reuse their critic/optimizer/replay, or claim exact resume. Any new action-space training plan must explicitly resolve compatibility; no training yet.',
        retained_formal='repair_guide',deployment_allowed=False,reason='Source/API authority diagnostic not implemented; no numerical control patch or new learner approved as a result.')
    write(out/'NEXT_RESEARCH_PLAN.json',next_plan)
    prep=read(NEW/'PREPARATION.json');prep.update(status='wiring_verified_prefix_family_swap_has_no_effect',activation_run=str(out),activation_verification=str(out/'VERIFICATION.json'),first_counterfactual_difference_ticks=[None,None],tested_prefix_ticks_each=3600,
        FDM_launch_allowed=False,reason='No actual controller-output or goal difference through60s on either saved opening. Four-game family comparison deferred rather than launch a null change; not proof of full300s equivalence.',next_plan=str(out/'NEXT_RESEARCH_PLAN.json'),source_unchanged=True)
    write(NEW/'PREPARATION.json',prep)
    lp=ROOT/'compute_budgets'/f'{datetime.datetime.now().date().isoformat()}.json';ledger=read(lp)
    for item in ledger['items']:
        if item['id'] in (pre.name,out.name):item.update(status='completed_verified_wiring_and_prefix_activation' if item['id']==out.name else 'completed_verified_saved_packet_wiring',actual_parent_exit=0,actual_worker_exit=0,actual_wall_seconds=66.359 if item['id']==out.name else 14.547)
    write(lp,ledger)
    next_action='pure guide/Station真接線已通過，但兩開局各前60秒目標與命令完全相同，先不開四場無已知差異的家族比較。下一項僅用保存packet驗證凍結RepairController原有bank-only residual的有效操控權與neutral精確回退，未實作/未訓練/未開FDM。'
    j=read(ROOT/'research_latest.json');j.update(updated_utc=now,active_workload=None,current_process_alert=None,current_live_workloads=dict(learners=[],loops=[],evaluations=[],observed_utc=now),latest_rule_family_precheck=str(pre),latest_rule_family_activation=str(out),
        latest_saved_diagnostic=dict(run=str(out),verification=str(out/'VERIFICATION.json'),findings=str(out/'FINDINGS.json'),actual_parent_exit=0,actual_worker_exit=0,scope='counterfactual_original_controller_calls_on_saved_prefixes',new_FDM_ticks=0),
        next_action=next_action,next_session_plan=str(out/'NEXT_RESEARCH_PLAN.json'),next_factor_status='no_rule_family_output_difference_through_tested60s_authority_check_proposed',daily_compute_reserved_hours=ledger['reserved_hours'],latest_usage_observation=read(out/'CONTRACT.json')['usage_observation'])
    write(ROOT/'research_latest.json',j)
    p=read(ROOT/'pipeline_latest.json');p['updated_utc']=now;p['race_focus_update'].update(latest_saved_diagnostic=str(out/'FINDINGS.json'),next_research=str(out/'NEXT_RESEARCH_PLAN.json'),next_factor_status=j['next_factor_status'],formal_deployment='repair_guide',training_started=False);write(ROOT/'pipeline_latest.json',p)
    note=f'''## {now} 規則家族真接線及有界控制差異檢查

- 新隔離rule_family_v1/policy.py解析到原repair_v1/controller.py的RepairController.act及原m1_station.StationController.act；兩者command仍為原RepairController.command，實際class/MRO/檔路徑SHA齊全。藍只收OWN26，明確residual=None，任何非零/錯shape殘差或非零tactic拒絕；沒有改正式來源/模型。
- 兩個保存開局各首300packet，12組真act/command、baseline saved exact、pure direct-source exact、完整prefix reset重現、STARTfalse不動狀態與合成安全parity檢查通過。parent/worker真0，14.547秒，非FDM/戰力。
- 首300兩版命令差異均0，因此另立120s activation契約，先重建必要600歷史幀，再只搜索新增6600保存幀至各3600tick/60s即止；未做完整72k/108k投影。兩版逐幀requested goals、真command輸出與guard完全相同，兩開局各prefix SHA相同、首次差異皆null。parent/worker真0，66.359秒；原三百前測未重跑湊成功數。這是保存共同輸入的反事實controller輸出，不是新FDM送出命令。
- 決策：不啟動目前四場家族替換比較，先確保候選能實際影響操控；不能把前60s等價推到全300s/所有開局。下一個假設是凍結原RepairController既有bank-only residual介面是否能在不改限制/安全的條件下改變真輸出；先neutral exact與±1 API邊界/獨立狀態測試，非掃bank參數。尚未實作，沒有新訓練/模型推論/FDM/seedclaim。
- 舊3維tactical模型不直接當新bank residual、不得沿用critic/optimizer/replay或宣稱精確續訓。control authority通過也不是戰力或閉環9G安全，仍須下一獨立契約。正式repair_guide與兩凍結模型保留，不部署。
- 兩次各120s預留保留，今日合計{ledger['reserved_hours']:.6f}h，昨日/失敗帳目不退款；6個記錄原core身分已無或重用，不碰重用PID。用量真UTC2026-10-18 01:26:48，較低85%，無credits/reset使用。

證據：{pre/'VERIFICATION.json'}；{out/'VERIFICATION.json'}；{out/'FINDINGS.json'}；{out/'NEXT_RESEARCH_PLAN.json'}。
'''
    for name in ('REVIEW_LOG.md','RACE_FOCUS_20261017.md'):
        with (ROOT/name).open('a',encoding='utf8') as f:f.write('\n\n'+note)
    (ROOT/'latest_result.md').write_text('# 最新進度（10/18）\n\n'+note+'\n最近完整對戰仍為far_speed_v1四場：原72為1勝1負，速度候選0勝2負、雙方0命中/過9G，候選拒絕。此輪沒有新對戰/勝率或訓練成果。\n',encoding='utf8')
    event=out.name+'|no_rule_family_prefix_effect|'+sha(out/'FINDINGS.json')
    for name in ('monitor_notice.json','review_notice.json'):
        notices=read(ROOT/name);notices.setdefault('events',{})[event]=dict(status='no_rule_family_prefix_effect',report=str(out/'FINDINGS.json'),evidence_sha256=sha(out/'FINDINGS.json'),notified_utc=now,channel='ai heartbeat',requires_user_action=False);write(ROOT/name,notices)
    print(json.dumps(dict(precheck_verified=True,activation_verified=True,command_difference_observed=False,new_FDM_ticks=0,recorded_identities=len(all_ids),daily_reserved_hours=ledger['reserved_hours'],next_plan=str(out/'NEXT_RESEARCH_PLAN.json')),ensure_ascii=False))
if __name__=='__main__':main()
