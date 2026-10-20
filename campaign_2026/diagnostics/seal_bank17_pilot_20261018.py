"""Post-run evidence/record updates only, no training, inference or simulation."""
from pathlib import Path
import sys,json,datetime
root=Path(r'E:\ai_pilot\campaign_2026');here=root/'experiments/opponent_pool/bank_residual_train_v4';sys.path.insert(0,str(here));import common as c
def main():
    actual_exit=int(sys.argv[1]);chunk=sys.argv[2];assert actual_exit==0
    out=Path(c.read(here/'LATEST.json')['out']);result=c.read(out/'RESULT.json');verification=c.read(out/'VERIFICATION.json');spec=c.read(out/'CONTRACT.json');guard=c.read(out/'GUARD_EXIT.json');now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    assert verification['verified_fresh_bank_residual_pilot'] and guard['phase_exits']==dict(PRECHECK=0,WORKER=0,VERIFIER=0) and result['actual_decisions']==3000
    c.gate(spec)
    c.write(out/'PARENT_EXIT_OBSERVED.json',dict(actual_exit=actual_exit,session_id=40509,chunk_id=chunk,observed_utc=now,observation_source='Unified exec completed actual wait; not inferred from guardian intended return'))
    identities=[spec['guardian']]
    for name in ('PRECHECK','WORKER','VERIFIER'):
        receipt=c.read(out/(name+'_EXIT.json'));identities.append(receipt['identity']);identities.extend(d['identity'] for d in receipt['descendants'])
    audit=[]
    import psutil
    for identity in identities:
        try:
            current=c.identity(identity['pid']);same=all(current[key]==identity[key] for key in ('pid','create','cmd','exe'));entry=dict(original=identity,current=current,original_core_identity_alive=same,parent_equal=current['parent']==identity['parent'],status='same_core_alive' if same else 'pid_reused')
        except psutil.NoSuchProcess:entry=dict(original=identity,original_core_identity_alive=False,status='absent')
        audit.append(entry)
    assert not any(x['original_core_identity_alive'] for x in audit)
    c.write(out/'TERMINAL_AUDIT.json',dict(observed_utc=now,core_identity_fields=['pid','create','cmd','exe'],identities=audit,unrelated_processes_stopped=False))
    episodes=[]
    for item in result['completed_episodes']:
        f=item['final'];episodes.append(dict(case=item['case'],ticks=item['ticks'],event=f['event'],winner=f['winner'],blue_red_attack=f['attack_ticks'],blue_red_over9G=f['over_g_ticks'],blue_minus_red_advantage=f['advantage'][0]-f['advantage'][1],training_episode_not_fair_eval=True))
    prior_failures=[]
    for branch in ('bank_residual_train_v1','bank_residual_train_v2','bank_residual_train_v3'):
        previous=root/'experiments/opponent_pool'/branch;pout=Path(c.read(previous/'LATEST.json')['out']);failure=c.read(pout/'TERMINAL_FAILURE.json');prior_failures.append(dict(run=str(pout),terminal_failure=str(pout/'TERMINAL_FAILURE.json'),sha256=c.sha(pout/'TERMINAL_FAILURE.json'),parent_actual_exit=1,precheck_actual_exit=failure['actual_precheck_exit'],worker_actual_exit=failure.get('actual_worker_exit'),new_recorded_FDM_ticks=failure.get('new_recorded_FDM_ticks',failure.get('new_FDM_ticks',0)),actual_decisions=failure.get('actual_decisions',0)))
        prep=c.read(previous/'PREPARATION.json');prep.update(status='failed_preserved_not_relaunchable',training_launch_allowed=False,terminal_failure=str(pout/'TERMINAL_FAILURE.json'));c.write(previous/'PREPARATION.json',prep)
    review=dict(gate='learning_mechanics_verified_strength_unmeasured_no_promotion',hypothesis=spec['hypothesis'],actual_decisions=3000,new_FDM_ticks=result['new_FDM_ticks'],gradient_updates=result['gradient_updates'],replay_size=3000,
        initial_actor_sha256=result['initial_actor_sha256'],final_actor_sha256=result['final_actor_sha256'],model_sha256=c.sha(out/'model.zip'),complete_training_episodes=episodes,last_episode=result['last_episode'],actual_reached_cells=result['actual_reached_cells'],
        sample_controller_action_effect=verification['sampled_nonzero_action_command_effect'],peak_abs_blue_G=result['peak_abs_blue_G'],min_AGL_m=result['min_AGL_m'],blue_over9G=0,
        verification_scope=dict(full_tick_counts_and_judge_math=True,all3000_decision_features_and_reward=True,all3000_first_tick_blue_command_replay=True,full_frame_packet_geometry=False,full_frame_red_controller=False,ACMI=False),
        actual_phase_exits=guard['phase_exits'],actual_parent_exit=0,total_wall_seconds=guard['wall_seconds'],original_wall_seconds=900,old_failed_attempts_preserved=prior_failures,
        strength_verified=False,matched_evaluation=False,unknown_team_win_rate=None,formal_deployment='repair_guide',deployment_allowed=False,decision='Freeze new fresh17x1 bundle; do not add training before neutral-vs-learned matched complete development games',observed_utc=now)
    c.write(out/'FINAL_REVIEW.json',review)
    nextplan=dict(status='proposed_not_implemented_not_launched',purpose='Test whether newly trained bank model improves full combat over exact neutral original RepairController',candidate_model=str(out/'model.zip'),candidate_sha256=c.sha(out/'model.zip'),candidate_actor_sha256=result['final_actor_sha256'],
        actors=['neutral_original_RepairController_bank0','deterministic_fresh17x1_bank_model'],opponents=['frozen_sac5000','true_maneuvering_RuleFighter','perturbed_MirrorP2Controller'],planned_cases=6,planned_matched_pairs=3,new_seed_claimed=False,initials='Each opponent/seed: both sides initialSHA identical neutral/candidate; explicit side saved; no shared controller/RNG/clock/cache',
        total_wall_seconds=900,case_wall_seconds=90,precheck_seconds=30,verifier_seconds=180,reserved_hours=.25,original_wall_not_extended=True,
        necessary_gates=['Unique unused seeds/output, fixed candidate/red/source/XML SHA and runtime MRO/act-command receipts','OS lock STOP resources independent guardian total900s including verification','Neutral deterministic reset/own private counter/3Hz feature-action mapping; all opponents actual APIs failclosed','Full per-frame legal packets both sides, actual sent commands,60Hz counts, complete CSV/ACMI and true initial/terminal','Full sample source/model/initial equality, actor/controller/judge score/event replay and true parent/worker/verifier exits0'],
        review_metrics=['Per-opponent winner/scoremargin/attack/kill/death/crash/collision/over9G','In-range and in-front ticks, common-exposure minimum AGL and worst case','Any candidate blue>9G rejects; do not average away a regression'],
        deployment_allowed=False,no_new_training_before_comparison=True,scope='Development comparison only; sixgames do not establish unknown-team win rate')
    c.write(out/'NEXT_EVALUATION_PLAN.json',nextplan)
    ledgerpath=root/'compute_budgets/2026-10-18.json';ledger=c.read(ledgerpath)
    for item in ledger['items']:
        if item['id']==out.name:item.update(status='verified_fresh_training_pilot_not_strength',actual_parent_exit=0,actual_decisions=3000,new_FDM_ticks=result['new_FDM_ticks'],gradient_updates=result['gradient_updates'],actual_wall_seconds=guard['wall_seconds'])
    c.write(ledgerpath,ledger)
    reg=c.read(root/'seed_registry.json');reg['trials'][out.name].update(status='verified_pilot_model_frozen_no_promotion',used_episode_seeds=[x['seed'] for x in result['actual_reached_cells']],unused_reserved_episode_seeds=[x['seed'] for x in spec['episodes'] if x['seed'] not in {v['seed'] for v in result['actual_reached_cells']}],reusable=False,actual_decisions=3000,model_sha256=c.sha(out/'model.zip'));c.write(root/'seed_registry.json',reg)
    prep=c.read(here/'PREPARATION.json');prep.update(status='consumed_verified_pilot_no_relaunch',training_launch_allowed=False,verified_pilot=str(out/'VERIFICATION.json'),model=str(out/'model.zip'),next_plan=str(out/'NEXT_EVALUATION_PLAN.json'));c.write(here/'PREPARATION.json',prep)
    j=c.read(root/'research_latest.json');j.update(updated_utc=now,active_workload=None,current_process_alert=None,current_live_workloads=dict(learners=[],loops=[],evaluations=[],observed_utc=now))
    j['latest_training']=dict(run=str(out),verification=str(out/'VERIFICATION.json'),review=str(out/'FINAL_REVIEW.json'),manifest=str(out/'BUNDLE_MANIFEST.json'),model=str(out/'model.zip'),model_sha256=c.sha(out/'model.zip'),actual_decisions=3000,gradient_updates=result['gradient_updates'],new_FDM_ticks=result['new_FDM_ticks'],actual_parent_exit=0,actual_worker_exit=0,actual_verifier_exit=0,strength_verified=False,deployment_allowed=False)
    j['next_action']='新fresh17×1 bank模型已完成3000decision並驗證存讀/真命令作用；先讀FINAL_REVIEW及NEXT_EVALUATION_PLAN，另立新契約/seed/source900s做neutral-vs-learned三對手6完整配對，未對戰前不追加訓練或部署。舊三失敗收據與預留保留。'
    j['latest_training_gate']=review['gate'];j['latest_training_next_plan']=str(out/'NEXT_EVALUATION_PLAN.json');j['latest_usage_observation']=spec['usage_observation'];j['current_day_reserved_hours']=ledger['reserved_hours'];c.write(root/'research_latest.json',j)
    pipeline=c.read(root/'pipeline_latest.json');pipeline['updated_utc']=now;u=pipeline.setdefault('race_focus_update',{});u.update(latest_training=j['latest_training'],training_started=True,next_research=str(out/'NEXT_EVALUATION_PLAN.json'),next_factor_status='fresh_bank17_pilot_verified_matched_strength_eval_proposed',formal_deployment='repair_guide');c.write(root/'pipeline_latest.json',pipeline)
    block=f"""## {now} 新17觀測×1bank小模型：3000decision完整訓練，尚未量測戰力

- 全fresh CPU SAC128×128，原13×3模型不相容，未帶舊actor/critic/optimizer/replay。原RepairController殘差API、72度/G/recover/trim/slew維持；每20個60Hz tick只更新一維bank，17特徵僅合法packet/私有自機counter/guard/clock。新reward為公告profile雙方advantage差增量/(10000/60)+真終局winner±180，cutoff不編勝方。
- 新模型完整3000decision/{result['new_FDM_ticks']}真FDM步/{result['gradient_updates']}梯度更新；actor SHA改變、model與replay3000重載精確，10組前置檢查及worker/verifier/實際parent均真0，phase {guard['phase_exits']}。原900s總限、30s前測/780s learner/90s核對，實際{guard['wall_seconds']:.3f}s；{len(audit)}原core身份已無或重用，來源XML/紅方模型不變。
- 實際到達{len(result['actual_reached_cells'])}個排程cell、完整訓練回合{len(episodes)}，最後partial見FINAL_REVIEW；不是完整聯賽/公平勝率。每tick計數及裁判、每decision特徵/reward、3000個decision首tick真blue act-command回放核對；其中{verification['sampled_nonzero_action_command_effect']}個抽樣與同狀態neutral命令不同。訓練紀錄沒有全幀packet/紅controller回放或ACMI，不冒稱完整對戰審查。
- 藍峰值G {result['peak_abs_blue_G']:.6f}，零過9G；最低AGL {result['min_AGL_m']:.3f}m為本訓練樣本，沒有公平基準高度比較。訓練回合事件/得分不能當模型勝率。gate={review['gate']}，未部署、尚無模型優勢證據。
- v1動態class來源反射失敗：precheck0/worker2/parent shell1、0decision/0記錄步（已FDM初始化）。v2修反射後900decision/18000步/75updates，在切換RuleFighter時因command-only API解包失敗，worker2/parent1；partial模型不晉級。v3只前測import package名錯誤真1、無learner/FDM/seedclaim。v4只修正該前測import，生產沿用v3已修正三對手API；實際三對手CPU接線測試通過才新fresh訓練。全部舊來源/失敗收據/原預留保留，不重跑原seed。
- 本日預留累計{ledger['reserved_hours']:.6f}h（含上述四次各900s及既有0.4h，不退款），用量只讀一次UTC2026-10-18 10:31:11，較低93%，未用credits/reset。正式repair_guide與兩原模型保留；ASUS/LAN不是前置，無需本人操作。
- 下一項：依NEXT_EVALUATION_PLAN新立900s總/90s每worker/180s嚴格核對的6完整開發場，三對手各neutral-vs-learned同雙方initialSHA配對；新seed/來源模型凍結/獨立deadline/lock/STOP/資源。先看逐對score/event/命中/射程/前半球/共同AGL/最差case，再決定有無理由追加訓練。尚未實作/啟動該比較，不預設較強，不自動部署。

證據：{out/'VERIFICATION.json'}；{out/'FINAL_REVIEW.json'}；{out/'BUNDLE_MANIFEST.json'}；{out/'TERMINAL_AUDIT.json'}；{out/'NEXT_EVALUATION_PLAN.json'}。
"""
    (root/'latest_result.md').write_text('# 最新進度（10/18）\n\n'+block+'\n最近完整公平對戰仍是far_speed原72 1勝1負、速度候選0勝2負/全0命中；本輪完成新訓練，尚未新增公平對戰結果。\n',encoding='utf8')
    for path in (root/'REVIEW_LOG.md',root/'RACE_FOCUS_20261017.md'):
        with path.open('a',encoding='utf8') as stream:stream.write('\n\n'+block)
    for path in (root/'monitor_notice.json',root/'review_notice.json'):
        value=c.read(path);value.setdefault('notices',{})[out.name+'|verified_fresh_bank_training|'+c.sha(out/'FINAL_REVIEW.json')]=dict(status='verified_fresh_bank_training',report=str(out/'FINAL_REVIEW.json'),evidence_sha256=c.sha(out/'FINAL_REVIEW.json'),notified_utc=now,channel='ai heartbeat',requires_user_action=False);c.write(path,value)
    print(json.dumps(dict(out=str(out),decisions=3000,ticks=result['new_FDM_ticks'],updates=result['gradient_updates'],model_sha256=c.sha(out/'model.zip'),actual_cells=len(result['actual_reached_cells']),complete_training_episodes=len(episodes),last_ticks=result['last_episode']['ticks'],sample_effect=verification['sampled_nonzero_action_command_effect'],peak_G=result['peak_abs_blue_G'],reserved_hours=ledger['reserved_hours'],review_sha256=c.sha(out/'FINAL_REVIEW.json'),terminal_identity_count=len(audit),strength_verified=False)),flush=True)
if __name__=='__main__':main()
