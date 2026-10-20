from pathlib import Path
import json,datetime,hashlib,sys
ROOT=Path(r'E:\ai_pilot\campaign_2026');SOURCE=ROOT/'experiments/opponent_pool/rear_latch60_v2';RUN=SOURCE/'run_20261017_203915_d840e7'
sys.path.insert(0,str(SOURCE));import battle as b
read,write,sha=b.read,b.write,b.sha
review=read(RUN/'SAFETY_REVIEW.json');comparison_path=Path(review['comparison_path']);comparison=read(comparison_path);spec=read(RUN/'CONTRACT.json');report=read(RUN/'report.json')
assert comparison['verified_comparison'] and not comparison['errors'] and read(RUN/'PARENT_EXIT_OBSERVED.json')['actual_exit']==0 and read(RUN/'VERIFIER_WRAPPER_EXIT_OBSERVED.json')['actual_exit']==1
guard_review=Path(read(ROOT/'research_latest.json')['latest_rear_latch_review'])
assert read(guard_review/'WORKER_EXIT.json')['actual_worker_exit']==0 and read(guard_review/'PARENT_EXIT_OBSERVED.json')['actual_exit']==0
b.source_gate(spec)
identities=[spec['guardian']]
for receipt in report['cases']:
    identities.append(receipt['identity']);identities.extend(x['identity'] for x in receipt['descendants'])
identities.append(read(RUN/'VERIFIER_EXIT.json')['identity'])
identities.extend(read(RUN/'VERIFIER_PROCESS_OBSERVATION.json')['identities'])
identities.extend([read(guard_review/'CONTRACT.json')['guardian'],read(guard_review/'WORKER_EXIT.json')['identity']])
identities.extend(x['identity'] for x in read(guard_review/'WORKER_EXIT.json')['descendants'])
identities=list({(i['pid'],i['create']):i for i in identities}.values())
import psutil
audit=[]
for i in identities:
    try:current=b.identity(i['pid'])
    except psutil.NoSuchProcess:current=None
    same_core=current is not None and all(current[k]==i[k] for k in ('pid','create','cmd','exe'))
    audit.append(dict(identity=i,current=current,status='absent' if current is None else 'reused_or_different_identity',original_core_still_live=same_core))
assert not any(x['original_core_still_live'] for x in audit)
assert b.base.inventory()==[]
now=datetime.datetime.now(datetime.timezone.utc).isoformat();day=datetime.datetime.now().date().isoformat();ledger=read(ROOT/'compute_budgets'/f'{day}.json')
write(RUN/'TERMINAL_AUDIT.json',dict(observed_utc=now,identities=audit,exact_recorded_identity_count=len(audit),all_original_identities_absent=True,other_campaign_workloads=[],source_unchanged=True,formal_deployment='repair_guide'))
summary_lines=[]
for p in review['paired_review']:
    base=next(x for x in review['results'] if x['case']['opening']==p['opening'] and x['case']['actor']=='bank60');cand=next(x for x in review['results'] if x['case']['opening']==p['opening'] and x['case']['actor']=='latch60')
    summary_lines.append(f"- {p['side']}：unlatched60／latch60勝方 {p['baseline_winner']}／{p['candidate_winner']}，藍方分差 {p['baseline_score_margin']:.3f}→{p['candidate_score_margin']:.3f}；命中 {p['baseline_attack'][0]}→{p['candidate_attack'][0]} tick，射程內敵在前半球 {p['baseline_front_inband_ticks']}→{p['candidate_front_inband_ticks']} tick，共同最低AGL差 {p['common_minimum_agl_delta_m']:+.3f}m。候選latch觸發{len(cand['latch_trigger_ticks'])}次／啟用{cand['latch_active_ticks']}tick，過9G {cand['over9G_ticks'][0]}tick。")
if review['gate']=='promising_mechanism_only_original72_reference_required':next_action='此latch只顯示勝過已否決bank60的機制訊號。下一研究先設新開局同雙方initial SHA的原72參考與latch60比較，再決定擴對手；不能直接晉級或盲續訓練。'
else:next_action='先用本批保存packet分析首次latch前後與其後5/10/20/40秒的LOS/heading角速度、實際bank對目標、CAS/TAS與高度，分辨持續追不上、能量或內層限制造成；僅分析必要視窗，不重投影全72k或重跑四場，不再掃角度/盲續SAC。'
text='\n'.join(summary_lines)
body=f'''## {now} 後半球方向保持：四場完整機制比較

- 假設與唯一改動：目標從正後方跨越±180度時保持原轉向方向，回到前半球解除；只改方向，原far60/near72幅度、速度/俯仰/rudder與內層安全/G/trim不改。零戰術StationController，不是pure repair_guide。
- 新種子2026310600/1，4/4完整、2個相同雙方initial SHA配對、{comparison['new_FDM_ticks']}真FDM步。四worker／模擬parent實際0；原verifier2／wrapper工具1，錯把ACMI地理緯度與packet地心緯度直接相等，原失敗與COMPARISON=false保留。另立180秒保存資料嚴格審查，按原wrapper與JSBSim WGS84座標轉換修正此檢查，沒有重跑FDM、沒有延長原600秒。新審查worker／guardian實際0，全部紅方模型決策、合法packet、逐幀裁判、CSV所有欄位及ACMI 0/20/terminal姿態核對通過。沒有新訓練。
{text}
- 決策：{review['gate']}。這只比較已否決bank60與latch60，不能說勝過原72、正式repair_guide或專業隊伍。正式部署與兩凍結模型保留。
- 前置17項測試及3590/3973幀保存packet的真inner-command逐命令完全一致已通過。v1首case因NumPy bool_日誌序列化失敗，父工具退出1、worker2、CSV已有2物理tick，0完整場；原600秒及2026310500/1保留不重用。v2只把heading/body角度正規化Python float，控制AST除型別轉換相同；另外嚴格CSV verifier正確核對None寫成空欄的格式，不放寬任何數值/事件條件。
- 所有{len(audit)}個記錄身分已無，source144+23及本批檔/模型SHA固定。今日預留{ledger['reserved_hours']:.6f}h，失敗與離線檢討均計入不退款。
- 下一步：{next_action}

證據：{RUN/'SAFETY_REVIEW.json'}；新獨立審查 {comparison_path}；原失敗 {RUN/'COMPARISON.json'}。
'''
for name in ('REVIEW_LOG.md','RACE_FOCUS_20261017.md'):
    f=ROOT/name
    with f.open('a',encoding='utf8') as stream:stream.write('\n\n'+body)
(ROOT/'latest_result.md').write_text('# 最新對戰研究結果（10/17）\n\n'+body+'\n報名完成仍未有證據；10/17提醒已寄，不重寄。ASUS/LAN不作研究前置。\n',encoding='utf8')
j=read(ROOT/'research_latest.json');j.update(updated_utc=now,status='completed_verified_development',experiment='rear_latch60_v2',run=str(RUN),report=str(RUN/'report.json'),comparison=str(comparison_path),original_failed_comparison=str(RUN/'COMPARISON.json'),verified_comparison=True,gate=review['gate'],actual_parent_exit_code=0,parent_exit_receipt=str(RUN/'PARENT_EXIT_OBSERVED.json'),original_verifier_exit_receipt=str(RUN/'VERIFIER_EXIT.json'),saved_data_audit=str(guard_review),safety_review=str(RUN/'SAFETY_REVIEW.json'),next_session_plan=str(RUN/'NEXT_RESEARCH_PLAN.json'),next_action=next_action,active_workload=None,current_live_workloads=dict(learners=[],loops=[],evaluations=[],observed_utc=now),current_process_alert=None,deployment_allowed=False,retained_deployment='repair_guide',training_started=False,source_hashes_verified=True,terminal_process_audit=str(RUN/'TERMINAL_AUDIT.json'),latest_usage_observation=spec['usage_observation'],latest_rear_latch_precheck=str(ROOT/'diagnostics/rear_latch_precheck_v1_20261017_203552_9a320f'))
write(ROOT/'research_latest.json',j)
lp=ROOT/'compute_budgets'/f'{day}.json';ledger=read(lp)
for item in ledger['items']:
    if item['id']==RUN.name:item.update(status='completed_physics_original_verifier_failed_saved_audit_verified',actual_guard_wall_seconds=read(RUN/'GUARD_EXIT.json')['wall_seconds'],original_verifier_exit=2,original_verifier_cap_seconds=120,independent_saved_audit=str(guard_review),actual_saved_audit_wall_seconds=read(guard_review/'WORKER_EXIT.json')['wall_seconds'],no_reservation_refund=True)
write(lp,ledger)
registry=read(ROOT/'seed_registry.json');registry['trials'][b.TRIAL].update(status='completed_verified_saved_data_audit',comparison=str(comparison_path),gate=review['gate']);write(ROOT/'seed_registry.json',registry)
p=read(ROOT/'pipeline_latest.json');p['updated_utc']=now;p.setdefault('race_focus_update',{}).update(latest_comparison=str(comparison_path),original_failed_comparison=str(RUN/'COMPARISON.json'),latest_safety_review=str(RUN/'SAFETY_REVIEW.json'),candidate_gate=review['gate'],next_research=str(RUN/'NEXT_RESEARCH_PLAN.json'),next_factor_status='rear_latch60_four_game_verified_mechanism_only',formal_deployment='repair_guide',training_started=False);write(ROOT/'pipeline_latest.json',p)
event=RUN.name+'|'+review['gate']+'|'+sha(RUN/'SAFETY_REVIEW.json')
notice=read(ROOT/'monitor_notice.json');notice.setdefault('events',{})[event]=dict(status=review['gate'],evidence_sha256=sha(RUN/'SAFETY_REVIEW.json'),notified_utc=now,channel='ai-2 heartbeat',requires_user_action=False,summary='4 complete rear direction latch mechanism games; baseline already rejected60; no deployment or training');write(ROOT/'monitor_notice.json',notice)
rn=read(ROOT/'review_notice.json');rn.setdefault('events',{})[event]=dict(status='reviewed',evidence_sha256=sha(RUN/'SAFETY_REVIEW.json'),reviewed_utc=now);write(ROOT/'review_notice.json',rn)
print(json.dumps(dict(gate=review['gate'],pairs=review['paired_review'],reserved_hours=ledger['reserved_hours'],original_identities_absent=len(audit),next_action=next_action),ensure_ascii=False))
