"""Publish saved results and updated human priorities; no FDM or training."""
import datetime,json
from pathlib import Path
from probe import ROOT,HERE,read,write,sha

out=HERE/'run_20261017_063110_af2e25'
v=read(out/'VERIFICATION.json');exit_audit=read(out/'ACTUAL_EXITS_AND_TERMINAL_AUDIT.json');result=read(out/'RESULT.json');spec=read(out/'CONTRACT.json');receipt=read(out/'EXIT_RECEIPT.json')
assert v['verified_FDM_packet_timing'] and not v['errors'] and exit_audit['actual_parent_exit']==exit_audit['actual_worker_exit']==exit_audit['actual_verifier_exit']==0
assert all(a['state']=='absent_exit_not_inferred' for a in exit_audit['audit'])
utc=datetime.datetime.now(datetime.timezone.utc).isoformat()
next_action='Implement a new independently guarded six-full-game development comparison: blue zero-tactical StationController / frozen sac5000 / transfer10000 against fixed frozen sac5000 red, two new openings including left/right, same full initial SHA per opening. Planned only, not implemented or launched. Retain baseline; no blind training or replay reuse.'
review=dict(completed_utc=utc,hypothesis=spec['hypothesis'],unique_change=spec['single_change'],verified_FDM_packet_timing=True,actual_parent_exit=0,actual_worker_exit=0,actual_verifier_exit=0,new_FDM_ticks=1200,distinct_development_seeds=spec['seeds'],same_seed_repeats=2,source_xml_model_fixed=True,source_freeze_sha256=sha(out/'CONTRACT.json'),verification_sha256=sha(out/'VERIFICATION.json'),parent_wall_seconds=receipt['wall_seconds'],verifier_wall_seconds=1.0723828,reserved_seconds=240,attack_counter_nonzero_exercised=False,over9G_ticks=sum(sum(e['over9G']) for e in result['episodes']),max_cold_command_ms=max(e['max_full_command_ms'] for e in result['episodes']),max_observed_warm_command_ms=max(e['max_warm_command_ms'] for e in result['episodes']),decision='interface_pass_prepare_full_battle_not_promotion',next_action=next_action,full_battle_verified=False,training_started=False,formal_deployment='repair_guide')
write(out/'FINAL_REVIEW.json',review)
write(out/'state.json',dict(status='terminal_verified_interface',actual_parent_exit=0,actual_worker_exit=0,actual_verifier_exit=0,completed_ticks=1200,completed_utc=utc))
j=read(ROOT/'research_latest.json')
j['last_complete_combat_comparison']=dict(run=j['run'],report=j['report'],safety_review=j.get('safety_review'),gate=j['gate'],verified_comparison=j['verified_comparison'])
ident=receipt['watchdog_identity'];parent=dict(pid=ident['pid'],creation_epoch=ident['create'],cmdline=ident['cmd'],exe=ident['exe'],parent_pid=ident['parent'])
j.update(updated_utc=utc,status='completed_verified_fdm_interface',experiment='frozen_sac_fdm_v1',run=str(out),report=str(out/'VERIFICATION.json'),comparison=None,verified_comparison=False,verified_interface=True,gate='interface_pass_prepare_full_battle_not_promotion',next_action=next_action,source_manifest=str(out/'CONTRACT.json'),source_hashes_verified=True,supervisor=parent,guardian=parent,actual_parent_exit_code=0,benchmark_return_code=0,actor_policy_used=True,planned_cases=4,matched_pairs_planned=0,hard_deadline_epoch=spec['deadline_epoch'],max_wall_seconds=240,reservation_id=out.name,compute_budget_date='2026-10-17',retained_deployment='repair_guide',deployment_allowed=False,seed_role='development_FDM_interface_not_holdout',safety_review=str(out/'FINAL_REVIEW.json'),post_audit=str(out/'ACTUAL_EXITS_AND_TERMINAL_AUDIT.json'),post_audit_passed=True)
j['active_workload']=dict(status='terminal_verified_interface',run=str(out),actual_parent_exit_code=0)
j['current_live_workloads']=dict(learners=[],loops=[],evaluations=[],observed_utc=utc,evidence=str(out/'ACTUAL_EXITS_AND_TERMINAL_AUDIT.json'))
j['current_process_alert']=None
j['race_focus']=dict(user_confirmed_tatajia_not_accepted=True,trip_schedule_conflict=False,priority='model_or_rule_program_combat_performance',ASUS_LAN_status='deferred_not_research_prerequisite',model_progress_review='2026-10-19',candidate_delivery_target='2026-10-20',document=str(ROOT/'RACE_FOCUS_20261017.md'))
j['frozen_sac_FDM_timing']=review
j['decision_checkpoint_taipei']='2026-10-19 model/combat evidence review; no Tatajia decision'
write(ROOT/'research_latest.json',j)
pipeline=read(ROOT/'pipeline_latest.json');pipeline['campaign_latest_20261017']=dict(status=j['status'],research_pointer=str(ROOT/'research_latest.json'),latest_interface=str(out/'VERIFICATION.json'),latest_full_battle_review=j['last_complete_combat_comparison']['safety_review'],model_focus=True,ASUS_LAN_deferred=True,formal_deployment='repair_guide',old_pipeline_record_preserved=True);write(ROOT/'pipeline_latest.json',pipeline)
ledgerpath=ROOT/'compute_budgets/2026-10-17.json';ledger=read(ledgerpath)
for item in ledger['items']:
    if item['id']==out.name:item.update(actual_parent_exit=0,actual_verifier_exit=0,actual_verifier_seconds=1.0723828,actual_parent_plus_verifier_seconds=receipt['wall_seconds']+1.0723828,original_reservation_retained=True)
ledger['reserved_hours']=sum(i['hours'] for i in ledger['items']);write(ledgerpath,ledger)
j['daily_compute_reserved_hours']=ledger['reserved_hours'];write(ROOT/'research_latest.json',j)
latest='''# 最新狀態：聚焦模型與對戰，學習紅方已接通真實模擬

- 使用者已確認塔塔加未錄取，行程無衝突；ASUS/LAN改為備存，下一步集中模型／規則對戰實力。
- 兩個凍結模型均已接入真FDM紅方：每模型2次同種子reset、每次300步，共1200步；父／worker／verifier實際退出0。首幀、60Hz單次act/send/physics/judge、3Hz策略、合法packet、cache/reset、確定推論重播及來源/XML/模型SHA通過。
- 這是四段5秒接線短測，命中0、過9G0；沒有新訓練或完整勝率證據。冷首次command36.53ms、此批暖command最大約2.26ms，尚非網路60Hz最壞延遲保證。
- 最新完整18場比較仍是mixed：新10k對部分鏡像變強但rule掉擊落、mirror近距命中131→2，不晉級。正式repair_guide，兩模型保留。
- 下一步規劃新6場完整比較：藍方零戰術StationController／5k／10k對同一凍結5k紅方，兩個新開發開局含左右，配對初始SHA一致。runner與新seed尚未建立／啟動，不能宣稱完成；先比較再決定單因素修正與有上限訓練。
- 尚無競賽報名完成證據；原紀錄截止10/21，10/17／10/20各提醒一次。

依據：`RACE_FOCUS_20261017.md`、`research_latest.json`、`diagnostics/frozen_sac_fdm_v1/run_20261017_063110_af2e25/VERIFICATION.json`與`FINAL_REVIEW.json`。
'''
(ROOT/'latest_result.md').write_text(latest,encoding='utf8')
road=ROOT/'WIN_BY_1020.md';body=road.read_text(encoding='utf-8-sig');prefix='> 10/17 最新人類指示：塔塔加未錄取，已無行程衝突；主力集中模型／規則對戰表現。ASUS/LAN暫存，不是本地研究前置。10/19改為模型進度檢視，10/20整理可執行候選。以 `RACE_FOCUS_20261017.md` 與最新research pointer為準；以下舊塔塔加決策與ASUS優先順序只作歷史，不再執行。\n\n'
if not body.startswith('> 10/17 最新人類指示'):road.write_text(prefix+body,encoding='utf8')
with (ROOT/'REVIEW_LOG.md').open('a',encoding='utf8') as log:
    log.write('\n\n## 10/17 06:33 模型優先與凍結SAC紅方FDM接通\n')
    log.write('- 人類已確認塔塔加未錄取、無行程衝突，要求主力模型／規則對戰程式；ai/ai-2保持原UTC時刻，移除塔塔加選擇與ASUS前置，讀新RACE_FOCUS。\n')
    log.write('- 新獨立frozen_sac_fdm_v1，source23files+physics/XML144項凍結；新seed2026310000/1已attempted；OSlock/STOP/CPU/RAM2GiB/disk10GiB/獨立240s guardian。preflight真0，無其他活研究。\n')
    log.write('- run_20261017_063110_af2e25兩模型各2×300tick共1200，worker0、parent實際0(eb2570/session74217)、verifier0(d708f9)，25.594s parent，1.072383s verifier，240s預留保留；今日總預留'+str(ledger['reserved_hours'])+'h。\n')
    log.write('- 命令來自完成n步後的own26packet，下一步一次act/send/physics；judge poststep；0/20/...3Hz，duplicate無變動，final state300有一個未送出的第301命令以關閉最後counter。實際命令／sim時間／controller獨立／reset相同SHA與新actor savedpacket重播精確相符。四份JSONL與ACMI保存，0過G、0命中，非零FDM攻擊路徑仍未觸發，不能稱戰力或自我對戰訓練。冷首36.5313ms、暖最大2.2587ms非最壞實時保證。\n')
    log.write('- 精確guardian/worker/owned conhost原identity均已不在，不補子程序退出碼、不停止無關程序。保持原模型與repair_guide。\n')
    log.write('- 下一項：新六場完整公平開發比較，三種藍方對固定學習紅方，兩新開局含左右；未實作／未claim，原18場與本1200tick不重跑。\n')
notices=read(ROOT/'email_notice.json')
for key,item in notices.get('events',{}).items():
    if 'vivobook' in key.lower() or 'portable_second_PC_needed' in key:
        item.setdefault('historical_status',item.get('status'));item['status']='deferred_by_user_race_model_focus_20261017';item['current_user_action_required']=False
write(ROOT/'email_notice.json',notices)
print(json.dumps(dict(run=str(out),verified=True,reserved_hours=ledger['reserved_hours'],published_utc=utc)))
