"""Seal true exits and source-preserving offline control-authority evidence."""
from pathlib import Path
import datetime,json,sys,psutil
ROOT=Path(r'E:\ai_pilot\campaign_2026');SOURCE=ROOT/'experiments/opponent_pool/far_speed_v1'
sys.path.insert(0,str(SOURCE));import battle as b
read,write,sha=b.read,b.write,b.sha
def main(out):
    spec=read(out/'CONTRACT.json');v=read(out/'VERIFICATION.json');e=read(out/'WORKER_EXIT.json')
    assert v['verified_existing_bank_residual_authority'] and v['errors']==[] and v['unique_saved_input_frames']==600 and v['alternative_action_rows']==1800
    assert e['actual_worker_exit']==0 and e['reason'] is None and e['absent']
    assert sha(ROOT/'diagnostics/bank_authority_guardian_v1.py')==spec['diagnostic_source_sha256']
    for p,h in spec['new_sources'].items():assert sha(Path(p))==h
    b.source_gate(read(Path(spec['source_run'])/'CONTRACT.json'))
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    write(out/'PARENT_EXIT_OBSERVED.json',dict(actual_exit=0,chunk_id='7ad0ae',actual_wall_seconds=6.656,observed_utc=now,observation_source='unified exec completed process wait'))
    ids=[spec['guardian'],e['identity']]+[d['identity'] for d in e['descendants']];audit=[]
    for old in ids:
        try:current=b.identity(old['pid'])
        except psutil.NoSuchProcess:current=None
        assert current is None or not all(old[k]==current[k] for k in ('pid','create','cmd','exe'))
        audit.append(dict(recorded=old,current=current,original_core_live=False))
    assert b.base.inventory()==[]
    write(out/'TERMINAL_AUDIT.json',dict(observed_utc=now,identities=audit,all_original_core_absent=True,source_fixed=True,other_campaign_workloads=[]))
    normal,mirror=v['results']
    assert normal['actions']['1']['command_changed_ticks']==mirror['actions']['-1']['command_changed_ticks']==285
    assert normal['actions']['-1']['command_changed_ticks']==mirror['actions']['1']['command_changed_ticks']==0
    assert normal['actions']['1']['first_changed_command_tick']==mirror['actions']['-1']['first_changed_command_tick']==16
    finding=dict(status='verified_existing_bank_residual_control_authority_not_strength',verification=str(out/'VERIFICATION.json'),
        facts=['Neutral residual0 exactly reproduces residual=None and saved original commands on all600 packets.',
        'Normal negative-turn prefix: bank residual+1 reduces requested bank magnitude72to64 on all300 inputs and changes aileron285/300; residual-1 clips outward on all300 with no goal/command change.',
        'Mirrored positive-turn prefix: bank residual-1 reduces magnitude72to64 and changes aileron285/300; residual+1 clips outward on all300 with no goal/command change.',
        'Both first changed counterfactual command outputs occur at saved tick16. First15 goal changes are masked by output clipping;8 of these also have active slew, overlapping counts not additive.',
        'Other command channels and requested pitch/speed/rudder remain exact for all alternatives; original aileron clip/slew independently reconstructed with scalar math.',
        'Synthetic lowaltitude/lowCAS invoke original recover behavior and override bank to0; synthetic ownG8.6 retains original elevator-limiter behavior. guard=False there is not evidence the G limiter is absent.'],
        actual_worker_exit=0,actual_parent_exit=0,wall_seconds=6.656,unique_saved_packets=600,alternative_action_rows=1800,
        limitations=['Private one-step clones share identical neutral history; this does not test sustained closed-loop alternative dynamics.',
        'All sampled saved packets use the far8degree residual limit. Near2.5degree limit was read from frozen source, not newly established in near-range flight.',
        'Actual controller function output on saved packets is not a new simulator-sent action. No safety guarantee, victory or trained model produced.',
        'Existing3D tactical actors are incompatible with a new1D bank-action contract; no direct relabeling or exact resume.'],
        new_FDM_ticks=0,model_inference_calls=0,training_started=False,seed_claims=[],formal_deployment='repair_guide',deployment_allowed=False)
    write(out/'FINDINGS.json',finding)
    plan=dict(status='proposed_not_implemented',hypothesis='The verified original bank-residual API can be wired through real60Hz physics without command/residual confusion, duplicate acts or altered judge timing, with unchanged neutral behavior before action onset.',
        single_factor='Blue input contract only: exact original RepairController.act receives [bank_action,0,0,0], existing magnitude/final bound/safety unchanged. One scalar action held for20 physics ticks; no learned actor yet.',
        next_work='Isolate a bank-only wrapper/short FDM harness. Do not alter rule_family_v1/policy.py, frozen RepairController, M1, red adapter/models or XML. Actual runtime class/MRO/path/SHA receipt required.',
        existing_step_source='combat_v3.env.CombatEnvV3.step source124–135 verified: finite4 residual -> packet_controller.act once -> actualsend -> physics -> judge. RepairDuel.step can forward4 residuals; TacticalDuel.step expects3 tactics and calls set_tactical, so it must not be used for a pure-guide bank-only bridge.',
        proposed_probe=dict(new_unused_development_seed_count=1,seeds_not_selected_or_claimed=True,two_fresh_resets=True,physics_ticks_per_reset=300,total_new_FDM_ticks=600,
            resets=['neutral residual0 throughout','preset API exercise: completed_ticks0–99=0,100–199=-1,200–299=+1; changes align20tick decision cadence'],
            red='same independent frozen sac5000 object/model per reset, private controller/clock/cache/RNG restoration',
            same_both_initial_SHA=True,first100_blue_and_red_packet_command_prefix_must_match_exact=True,
            purpose='Interface timing/control authority/safety observations only; preset bank actions are not a tactical policy or combat evaluation.',
            hard_total_seconds=240,worker_seconds=90,verification_seconds_in_original_total=60,independent_watchdog=True),
        gates=['new isolated source contract and static mapping/reset tests before launch','unique output and seedregistry/resources/OSlock/STOP','original source_XML_model_SHA','new reserved/actual ledger time','independent original wall watchdog','actual parent/worker/verifier exits0 and precise owned descendants absent'],
        verification=['one act/command/send/physics/judge per60Hz tick','actual residual and actual emitted command linkage','completed_tick red timing/private attack/3Hz actor decisions','counterfactual and sustained replay from saved legal packet exact','initial/final/CSV/ACMI and judge event/score','zero residual baseline reproduction and prefix equality until first prescribed action','source and reset state independence'],
        safety='Any blue>9G rejects the new interface candidate; original limits/G logic cannot be loosened. Synthetic parity did not prove dynamic safety.',
        reward='No training. If later learning is proposed, explicitly define a new judge-based reward; do not silently use legacy RepairDuel shaping or claim old critic/optimizer/replay exact resume.',
        FDM_launch_allowed=False,reason='New wrapper/harness/tests/verifier/source contract/unused seed not yet implemented; software work can proceed autonomously to meet these technical gates.',training_allowed=False,
        no_repeat_completed_authority_check=True,no_speed_bank_parameter_sweep=True,no_training_or_promotion_claim=True,formal_deployment='repair_guide',deployment_allowed=False)
    write(out/'NEXT_RESEARCH_PLAN.json',plan)
    lp=ROOT/'compute_budgets'/f'{datetime.datetime.now().date().isoformat()}.json';ledger=read(lp)
    for item in ledger['items']:
        if item['id']==out.name:item.update(status='completed_verified_existing_bank_authority',actual_parent_exit=0,actual_worker_exit=0,actual_wall_seconds=6.656,unique_saved_packets=600,alternative_action_rows=1800)
    write(lp,ledger)
    next_action='原bank-only residual已在保存600packet確認有效：內向8deg目標改變、兩側各285次副翼差異、neutral精確回退。下一項先隔離實作真60Hz bank-only介面/測試，再新seed兩次reset共600tick短FDM，固定sac5000紅方；尚未實作/未訓練/不是戰力。'
    j=read(ROOT/'research_latest.json');j.update(updated_utc=now,active_workload=None,current_process_alert=None,current_live_workloads=dict(learners=[],loops=[],evaluations=[],observed_utc=now),latest_bank_authority=str(out),latest_saved_diagnostic=dict(run=str(out),verification=str(out/'VERIFICATION.json'),findings=str(out/'FINDINGS.json'),actual_parent_exit=0,actual_worker_exit=0,scope='real frozen controller outputs on600 saved packets, neutral-state independent one-step alternatives',new_FDM_ticks=0),next_action=next_action,next_session_plan=str(out/'NEXT_RESEARCH_PLAN.json'),next_factor_status='bank_authority_verified_short_FDM_interface_proposed_not_implemented',daily_compute_reserved_hours=ledger['reserved_hours'],latest_usage_observation=spec['usage_observation']);write(ROOT/'research_latest.json',j)
    p=read(ROOT/'pipeline_latest.json');p['updated_utc']=now;p['race_focus_update'].update(latest_saved_diagnostic=str(out/'FINDINGS.json'),next_research=str(out/'NEXT_RESEARCH_PLAN.json'),next_factor_status=j['next_factor_status'],formal_deployment='repair_guide',training_started=False);write(ROOT/'pipeline_latest.json',p)
    prep=read(ROOT/'experiments/opponent_pool/rule_family_v1/PREPARATION.json');prep.update(latest_bank_authority=str(out),next_plan=str(out/'NEXT_RESEARCH_PLAN.json'),FDM_launch_allowed=False);write(ROOT/'experiments/opponent_pool/rule_family_v1/PREPARATION.json',prep)
    note=f'''## {now} 原bank residual有效操控權驗證

- 新獨立120s/OSlock/STOP/資源/source/XML/model/保存artifact SHA閘門；兩保存前綴各300packet，共600唯一輸入、1800個±1/0 API替代列。每個替代由同一neutral歷史act前clone獨立settings/last/積分狀態，直接原RepairController.act與command；沒有改rule_family policy或正式來源。
- neutral0逐列精確等於None及保存原command。normal+1、mirror-1（朝減小bank幅度）使目標72→64，各300個目標變更、285個副翼輸出差異，首次差異皆保存tick16；相反方向各300次被原72界限裁掉。原動態限幅取自凍結source，未新增控制數字或掃角度；不是永久bank64飛行候選。
- 前15幀目標有變但輸出被既有aileron clipping遮住，其中8亦有slew，重疊不相加。原aileron clip/slew另以標量公式核對。其他三個命令通道與pitch/speed/rudder目標完全相同。4非法輸入與9合成安全替代核對通過；8.6G時guard布林false不代表原G elevator limiter沒作用，不能當閉環9G安全。
- worker/guardian實際0，6.656s（7ad0ae）；3原core身分已無，無新FDM、模型推論、訓練或seedclaim。far8degree分支有保存實例，near2.5僅source讀出不當近距飛行證據。
- 決策：有效操控權這個介面前提已成立，沒有新戰力/勝率。下一項新bank-only wrapper與實際60Hz接線短FDM：原RepairController，直接RepairDuel.step四維residual，不走要求3tactics/set_tactical的TacticalDuel.step；新unused seed、兩fresh reset各300tick、neutral/預定API序列，同initialSHA及前100幀一致，240s總/90s worker/60s核對。新runner/contract/test/verifier尚未實作，不能直接啟動。不是學習戰術/完整對戰，通過後才考慮新訓練契約，舊3tactic actor不轉名或帶critic/replay假續訓。
- 今日預留{ledger['reserved_hours']:.6f}h，原120s預留不退款；用量UTC2026-10-18 04:37:04較低96%，無credits/reset。正式repair_guide與兩模型保留，不部署。原家族前60s命令等價及四場比較暫緩狀態保留，不能擴稱全300s等價。

證據：{out/'VERIFICATION.json'}；{out/'AUTHORITY.csv'}；{out/'FINDINGS.json'}；{out/'NEXT_RESEARCH_PLAN.json'}。
'''
    for name in ('REVIEW_LOG.md','RACE_FOCUS_20261017.md'):
        with (ROOT/name).open('a',encoding='utf8') as stream:stream.write('\n\n'+note)
    (ROOT/'latest_result.md').write_text('# 最新進度（10/18）\n\n'+note+'\n最近完整對戰仍是far_speed_v1四場：原72為1勝1負，速度版0勝2負、全0命中，速度候選拒絕。本輪沒有新對戰或訓練結果。\n',encoding='utf8')
    event=out.name+'|verified_existing_bank_authority|'+sha(out/'FINDINGS.json')
    for name in ('monitor_notice.json','review_notice.json'):
        notices=read(ROOT/name);notices.setdefault('events',{})[event]=dict(status='verified_existing_bank_authority',report=str(out/'FINDINGS.json'),evidence_sha256=sha(out/'FINDINGS.json'),notified_utc=now,channel='ai heartbeat',requires_user_action=False);write(ROOT/name,notices)
    print(json.dumps(dict(verified_bank_authority=True,actual_parent_exit=0,actual_worker_exit=0,identities_absent=len(ids),daily_reserved_hours=ledger['reserved_hours'],new_FDM_ticks=0,next_plan=str(out/'NEXT_RESEARCH_PLAN.json')),ensure_ascii=False))
if __name__=='__main__':main(Path(sys.argv[1]))
