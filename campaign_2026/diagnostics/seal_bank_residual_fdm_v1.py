"""Actual exit/audit and research handoff; no training or simulator launch."""
from pathlib import Path
import datetime,json,sys,psutil
ROOT=Path(r'E:\ai_pilot\campaign_2026');HERE=ROOT/'experiments/opponent_pool/bank_residual_fdm_v1'
sys.path.insert(0,str(HERE));import common as c
def main(out):
    spec=c.read(out/'CONTRACT.json');v=c.read(out/'VERIFICATION.json');result=c.read(out/'RESULT.json');g=c.read(out/'GUARD_EXIT.json')
    assert v['verified_bank_residual_60Hz_interface'] and v['errors']==[] and v['new_FDM_ticks']==600 and v['complete_combat_rounds']==0
    assert g['phase_exits']==dict(PRECHECK=0,WORKER=0,VERIFIER=0) and g['error'] is None and g['source_fixed'] and g['seed_claimed'];c.gate(spec)
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    c.write(out/'PARENT_EXIT_OBSERVED.json',dict(actual_exit=0,session_id=39687,chunk_id='d3e15a',actual_wall_seconds=42.125,observed_utc=now,observation_source='unified exec completed process wait'))
    ids=[spec['guardian']];phase_receipts={}
    for name in ('PRECHECK','WORKER','VERIFIER'):
        e=c.read(out/(name+'_EXIT.json'));assert e['actual_exit']==0 and e['reason'] is None and e['absent']
        phase_receipts[name]=dict(actual_exit=0,wall_seconds=e['wall_seconds'],receipt=str(out/(name+'_EXIT.json')))
        ids.append(e['identity']);ids.extend(d['identity'] for d in e['descendants'])
    ids=list({(i['pid'],i['create']):i for i in ids}.values());audit=[]
    for old in ids:
        try:current=c.identity(old['pid'])
        except psutil.NoSuchProcess:current=None
        assert current is None or not all(old[k]==current[k] for k in ('pid','create','cmd','exe'))
        audit.append(dict(recorded=old,current=current,original_core_live=False))
    assert c.b.base.inventory()==[]
    c.write(out/'TERMINAL_AUDIT.json',dict(observed_utc=now,identities=audit,all_original_core_absent=True,source_XML_models_fixed=True,other_campaign_workloads=[]))
    review=dict(status='verified_short_bank_FDM_interface_not_combat',gate='interface_pass_no_strength_or_promotion',
        seed=spec['seed'],initial_sha256=result['episodes'][0]['initial_sha256'],new_FDM_ticks=600,episode_count=2,seconds_each=5,complete_combat_rounds=0,
        facts=['Original pure RepairController through unchanged RepairDuel.step four-residual path, no3-tactic set_tactical/command-as-residual confusion.',
        'Two fresh resets have identical full both-aircraft initialSHA and first100 pre/post packet+actual command frames.',
        'Exercise schedule is an API test:0 for completed0..99,-1 for100..199,+1 for200..299 at20tick holds. Not a learned tactical policy.',
        'First actual sent blue command differs at201, first physics-packet difference202. Both exact full blue-controller and frozen-red-model/controller replays pass.',
        'Each600 physical tick has one act/command/send/physics/judge; CSV allfields, post-step judge/counters/score, WGS84 ACMI and source/XML/model verified.',
        'Both5s cutoffs remain judge ongoing/no winner. Both have0 attack/over9G. Blue peakG2.736380/2.493242; this is limited safety observation, not long-flight safety or advantage.'],
        episodes=v['episodes'],phase_receipts=phase_receipts,actual_parent_exit=0,actual_wall_seconds=42.125,
        source_freeze=str(HERE/'BRANCH_FREEZE.json'),limitations=['One development opening only; no full battle, league, holdout, trained blue policy or professional win rate.',
        'The bridge has operational authority; this does not establish that choosing a bank residual improves fighting.',
        'Old3D tactical models are incompatible with a fresh1D bank output and any changed observation space.'],
        training_started=False,formal_deployment='repair_guide',deployment_allowed=False)
    c.write(out/'SAFETY_REVIEW.json',review)
    plan=dict(status='proposed_fresh_bounded_training_not_implemented',hypothesis='A new policy with verified effective bank-residual authority may learn when to adjust bank; prior3-tactic policies were often clipped away. Test a small fresh learner, not a continuation or proof that more steps win.',
        single_research_change='New policy/control contract: one bank-only residual on exact pure RepairController, frozen existing residual limits and safety. Compare learned actor against zero residual in the same contract after training.',
        action=dict(dimensions=1,range=[-1,1],map='[bank,0,0,0] existing RepairController residual input',decision_every_physics_ticks=20,frequency_hz=3,neutral=0.,safety='Original72 bank bound/G/recovery/trim/slew untouched; any blue>9G prevents promotion and stops pilot for review'),
        observation=dict(dimensions=17,proposal='Original legal packet-only13 tactical features plus ownCAS/TAS and sin/cos of direct legal LOS bearing minus ownheading; explicit deterministic normalization to be frozen and tested before use.',
            allowed='OWN20+ENEMY6 plus own clock/private attack/guard only',forbidden='Judge truth/score, hidden enemy attitude/G, future observations'),
        reward=dict(proposed='After each20tick decision: delta of published-profile (blue advantage minus red advantage)/(10000/60), plus true resolved terminal winner bonus+180/-180/0. Not legacy parent reward.',
            cutoff='Short diagnostic/time cap is truncation, never fabricated victory. Actual300s event is terminal. Profile publication90/LINE1deg/AGL/right_bin; retain known Host divergence.'),
        model=dict(algorithm='fresh CPU SAC',network=[128,128],gamma=.9995,planned_decisions=3000,max_blue_FDM_ticks=60000,
            fresh_actor=True,fresh_critic_optimizer_replay=True,old5k10k_transfer_allowed=False,reason='Observation17/action1 differs from old13/action3 tactical meaning; no compatible direct actor transfer asserted.'),
        opponents=dict(proposed_rotation=['frozen sac5000 packet-only independent adapter','actual maneuvering RuleFighter','perturbed MirrorP2Controller'],
            implementation='Private red controller/RNG/clock/reset per episode, exact runtime type/file/model evidence. Detect mirror_fallback and stop for review instead of silently training on a broken mirror.',
            coverage='Cycle opponent/distance3000/6000/9000 and explicit side in a preregistered schedule with newseed registry. Report actual reached cells and partial last episode;3000 decisions cannot be called a complete league.'),
        hard_limits=dict(total_seconds=900,training_worker_seconds=780,verification_seconds=90,reserve_hours=.25,scope='single isolated learner, CPUthreads1, RAM/disk/CPU gates, source/XML/models freeze, new output/seedregistry/OSlock/STOP, independent watchdog before launch'),
        required_before_training=['Implement isolated new env/trainer/guardian/verifier/source contract; keep frozen original files untouched','Test17-feature shape/finite/legalown-only/no future inputs, action neutrality and exact mapping, per-tick clock/reset/private counters','Test scalar reward against independent judge snapshots and terminal/truncation cases; no legacy shaping leakage','Preregister fixed opponent schedule and new seedpool; actual source and resource gates','Predefined save/reload/provenance and full actor update/source/model artifacts, actual exits0; independent original watchdog'],
        pilot_verification=['actor weights actually changed','actual1D action reaches inherited act/send path with recorded attribution','final model/replay reload and source/modelSHA','exact complete/partial training episodes and safety per opponent/cell','training losses/updates do not establish combat strength'],
        after_pilot='Freeze final actor, then separately preregister6 complete development games/3 matched neutral-vs-learned pairs against three frozen opponent kinds with new initial seeds, full judge/event/score/commonAGL/CSV/ACMI and actual exits; only then decide further work. No automatic promotion.',
        training_launch_allowed=False,reason='New17x1 trainer/reward/opponent schedule and verification not implemented; only600tick input interface now verified.',
        no_repeat_completed_600tick_probe=True,no_bank_speed_sweep=True,no_old_futility_stop_resume=True,formal_deployment='repair_guide',deployment_allowed=False)
    c.write(out/'NEXT_RESEARCH_PLAN.json',plan)
    lp=ROOT/'compute_budgets'/f'{datetime.datetime.now().date().isoformat()}.json';ledger=c.read(lp)
    for item in ledger['items']:
        if item['id']==out.name:item.update(status='verified_short_bank_residual_FDM_interface',actual_parent_exit=0,actual_wall_seconds=42.125,actual_phase_exits=g['phase_exits'],new_FDM_ticks=600,seed_claimed=True)
    c.write(lp,ledger)
    reg=c.read(ROOT/'seed_registry.json');reg['trials'][out.name].update(status='verified_short_bank_FDM_interface',verification=str(out/'VERIFICATION.json'),new_FDM_ticks=600,reusable=False);c.write(ROOT/'seed_registry.json',reg)
    prep=c.read(HERE/'PREPARATION.json');prep.update(status='consumed_verified_short_FDM_interface',run=str(out),verification=str(out/'VERIFICATION.json'),seed_claimed=True,FDM_launch_allowed=False,reason='Completed600tick interface; do not rerun this seed/probe',actual_parent_exit=0,new_FDM_ticks=600);c.write(HERE/'PREPARATION.json',prep)
    next_action='bank-only真60Hz介面600tick已全核對，neutral前100幀一致、真command201/physics202差異；下一項隔離實作fresh17觀測×1bank action的小型SAC契約/語意與reward/opponent測試，再通過單例/資源/新seed/獨立900s才3000decision pilot；舊3tactic模型不接續，不當新戰力。'
    j=c.read(ROOT/'research_latest.json');j.update(updated_utc=now,active_workload=None,current_process_alert=None,current_live_workloads=dict(learners=[],loops=[],evaluations=[],observed_utc=now),latest_bank_FDM_interface=str(out),latest_verified_interface=dict(run=str(out),verification=str(out/'VERIFICATION.json'),review=str(out/'SAFETY_REVIEW.json'),new_FDM_ticks=600,actual_parent_exit=0,actual_worker_exit=0,actual_verifier_exit=0,complete_combat_rounds=0),next_action=next_action,next_session_plan=str(out/'NEXT_RESEARCH_PLAN.json'),next_factor_status='bank60Hz_interface_verified_fresh_training_contract_proposed',daily_compute_reserved_hours=ledger['reserved_hours'],latest_usage_observation=spec['usage_observation']);c.write(ROOT/'research_latest.json',j)
    p=c.read(ROOT/'pipeline_latest.json');p['updated_utc']=now;p['race_focus_update'].update(latest_verified_interface=str(out/'VERIFICATION.json'),next_research=str(out/'NEXT_RESEARCH_PLAN.json'),next_factor_status=j['next_factor_status'],formal_deployment='repair_guide',training_started=False);c.write(ROOT/'pipeline_latest.json',p)
    note=f'''## {now} bank-only真60Hz介面：600步完整驗證

- 全新獨立branch bank_residual_fdm_v1，原RepairController/紅方adapter/model/XML未改。7組前置mapping/時鐘/neutral回退/實際source檢查0後才claim新開局seed{spec['seed']}，兩fresh reset各300tick共600真FDM。不是兩場完整戰鬥，兩個5s cutoff皆ongoing/無勝方。
- 使用原RepairDuel.step四維residual，一維bank映射[bank,0,0,0]，每20tick持有；不走3tactics/set_tactical。neutral全0與預定API序列0→-1→+1（100/200completed ticks切換）。同雙方initialSHA、前100個pre/post packet與實際藍紅command完全一致；首次真sent blue command差異201、首次physics packet差異202，非保存反事實結果。
- 每tick一act/command/send/physics/judge、紅completed_tick/privatecounter/3Hz模型、完整藍act-command與紅actor-controller回放、事件/分數、CSV全欄/ACMI WGS84/來源XML/model均嚴格通過，VERIFICATION true/errors[]。
- 藍峰G neutral2.736380／exercise2.493242，紅2.748547／2.750228；兩次皆零命中/過9G。此為5s接線及有限動態安全觀察，不是戰力/長時安全/勝率，預定±1不是bank64戰術成功。
- precheck/worker/verifier與實際parent真0；各phase {g['phase_exits']}，原30s/90s/60s均受獨立240s總限約束，實際42.125s（39687/d3e15a）。{len(ids)}原core身份已無或重用，source固定，不碰重用PID。240s預留保留，今日合計{ledger['reserved_hours']:.6f}h，seed已consumed不重跑。
- 下一項：新fresh CPU128x128 SAC、17合法觀測×1bank action，最多3000decision/60000tick，規劃單獨900s含780s learner/90s核對；先實作及測試features/neutral/action/時鐘/reset/私counter/明確judge reward與三對手輪替，再新source/seedpool/OSlock/STOP/資源/watchdog才可啟動。新模型/契約尚未實作，不當已訓練；舊13×3 actor不相容，actor/critic/optimizer/replay全部fresh，不能假續訓。訓練後另凍結完整配對才能判戰力。
- 正式repair_guide及兩原模型保留，不部署、不放寬9G、不盲續舊SAC。真用量UTC2026-10-18 07:29:14較低89%，未用credits/reset。ASUS/LAN不作前置，本輪無需本人操作。

證據：{out/'VERIFICATION.json'}；{out/'SAFETY_REVIEW.json'}；{out/'TERMINAL_AUDIT.json'}；{out/'NEXT_RESEARCH_PLAN.json'}。
'''
    for name in ('REVIEW_LOG.md','RACE_FOCUS_20261017.md'):
        with (ROOT/name).open('a',encoding='utf8') as stream:stream.write('\n\n'+note)
    (ROOT/'latest_result.md').write_text('# 最新進度（10/18）\n\n'+note+'\n最近完整對戰仍為far_speed_v1原72 1勝1負、速度0勝2負/全0命中，速度候選拒絕。本輪是接線600步，未新增完整對戰或訓練成果。\n',encoding='utf8')
    event=out.name+'|verified_short_bank_FDM_interface|'+c.sha(out/'SAFETY_REVIEW.json')
    for name in ('monitor_notice.json','review_notice.json'):
        notices=c.read(ROOT/name);notices.setdefault('events',{})[event]=dict(status='verified_short_bank_FDM_interface',report=str(out/'SAFETY_REVIEW.json'),evidence_sha256=c.sha(out/'SAFETY_REVIEW.json'),notified_utc=now,channel='ai heartbeat',requires_user_action=False);c.write(ROOT/name,notices)
    print(json.dumps(dict(verified_interface=True,new_FDM_ticks=600,phase_exits=g['phase_exits'],actual_parent_exit=0,original_identities_absent=len(ids),daily_reserved_hours=ledger['reserved_hours'],next_plan=str(out/'NEXT_RESEARCH_PLAN.json')),ensure_ascii=False))
if __name__=='__main__':main(Path(sys.argv[1]))
