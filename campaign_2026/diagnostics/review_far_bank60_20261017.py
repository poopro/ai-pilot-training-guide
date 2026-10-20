"""Read-only saved-battle analysis and project record publication."""
import csv,datetime,hashlib,json,sys
from pathlib import Path
import psutil
ROOT=Path(r'E:\ai_pilot\campaign_2026')
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def absent(i):
    try:
        p=psutil.Process(i['pid']);same=abs(p.create_time()-i['create'])<.01 and p.cmdline()==i['cmd'] and p.exe().lower()==i['exe'].lower() and p.ppid()==i['parent']
        if same:raise RuntimeError('Original process identity still live')
        return 'reused_or_identity_mismatch'
    except psutil.NoSuchProcess:return 'absent_no_exit_inferred'

def main(out):
    c=read(out/'COMPARISON.json');v=read(out/'VERIFIER_EXIT.json');e=read(out/'PARENT_EXIT_OBSERVED.json');vg=read(out/'VERIFIER_PARENT_EXIT_OBSERVED.json')
    assert c['verified_comparison'] and c['complete_games']==4 and e['actual_exit']==vg['actual_exit']==v['actual_exit']==0
    ids=[read(out/'CONTRACT.json')['guardian'],v['identity']];results=[];commands={};rates={}
    for r in c['results']:
        folder=out/'cases'/r['case']['id'];exit=read(folder/'WORKER_EXIT.json');assert exit['actual_worker_exit']==0 and exit['worker_and_descendants_absent']
        ids.append(exit['identity']);ids.extend(d['identity'] for d in exit['descendants'])
        distance=[];band=cone=0
        with (folder/'telemetry.csv').open(encoding='utf8',newline='') as stream:
            for row in csv.DictReader(stream):
                d=float(row['distance_m']);angle=float(row['blue_angle_deg']);distance.append(d)
                band+=int(152.4<=d<=914.4);cone+=int(152.4<=d<=914.4 and angle<=1.)
        assert cone==r['attack_ticks'][0]
        cap=0;case_commands=[];case_rates=[];bank_sum=0.;previous_heading=None;windows=[]
        with (folder/'telemetry.jsonl').open(encoding='utf8') as stream:
            for line in stream:
                row=json.loads(line);g=row['blue_guidance'];cap+=int(g['applied'][0]!=g['requested'][0]);packet=row['blue_packet_post']
                case_commands.append(row['blue_command']);bank_sum+=abs(packet[3])
                case_rates.append(0. if previous_heading is None else abs((packet[5]-previous_heading+180)%360-180)*60)
                previous_heading=packet[5]
                if row['tick'] in (60,3600,7200,10800,14400,18000):windows.append(dict(tick=row['tick'],range_m=row['distance_m'],blue_angle_deg=row['blue_angle_deg'],red_angle_deg=row['red_angle_deg'],bank_deg=packet[3],heading_deg=packet[5],cas_kts=packet[12]/1.6878098571011957,score_margin=row['blue_advantage']-row['red_advantage']))
        commands[r['case']['id']]=case_commands;rates[r['case']['id']]=case_rates
        result=dict(**r,minimum_distance_m=min(distance),inside_attack_range_ticks=band,inside_attack_cone_ticks=cone,actual_goal_changed_ticks=cap,
                    blue_kill=int(r['event']=='blue_kill'),blue_death=int(r['event']=='red_kill'),blue_crash=int(r['event'] in ('blue_crash','mutual_crash')),collision=int(r['event']=='collision'),mean_absolute_bank_deg=bank_sum/len(case_commands),mean_absolute_heading_rate_deg_s=sum(case_rates)/len(case_rates),saved_windows=windows)
        results.append(result)
    pairs=[]
    for opening in (0,1):
        base=next(r for r in results if r['case']['opening']==opening and r['case']['actor']=='station_zero')
        cand=next(r for r in results if r['case']['opening']==opening and r['case']['actor']=='far_bank60')
        common=next(r for r in c['paired_tradeoffs'] if r['opening']==opening)
        pairs.append(dict(opening=opening,side=base['case']['side'],baseline_event=base['event'],candidate_event=cand['event'],baseline_winner=base['winner'],candidate_winner=cand['winner'],baseline_attacks=base['attack_ticks'],candidate_attacks=cand['attack_ticks'],baseline_over9G=base['over9G'],candidate_over9G=cand['over9G'],baseline_margin=base['score_margin'],candidate_margin=cand['score_margin'],baseline_range_min_m=base['minimum_distance_m'],candidate_range_min_m=cand['minimum_distance_m'],baseline_in_range_ticks=base['inside_attack_range_ticks'],candidate_in_range_ticks=cand['inside_attack_range_ticks'],common_minimum_AGL_delta_m=common['common_minimum_AGL_delta_m'],common_score_margin_delta=common['common_score_margin_delta'],common_ticks=common['common_ticks']))
        bcmd=commands[base['case']['id']];ccmd=commands[cand['case']['id']];n=common['common_ticks']
        pairs[-1].update(first_actual_command_difference_tick=next((i+1 for i,(x,y) in enumerate(zip(bcmd,ccmd)) if x!=y),None),baseline_common_heading_rate_deg_s=sum(rates[base['case']['id']][:n])/n,candidate_common_heading_rate_deg_s=sum(rates[cand['case']['id']][:n])/n)
    candidate=[r for r in results if r['case']['actor']=='far_bank60']
    unsafe=any(r['over9G'][0] or r['blue_crash'] or r['collision'] for r in candidate)
    improvement=any(p['candidate_winner']=='blue' and p['baseline_winner']!='blue' or p['candidate_attacks'][0]>p['baseline_attacks'][0] or p['candidate_in_range_ticks']>p['baseline_in_range_ticks'] for p in pairs)
    regress=any(p['candidate_winner']=='red' and p['baseline_winner']!='red' or p['candidate_margin']<p['baseline_margin'] or p['common_minimum_AGL_delta_m']<0 for p in pairs)
    gate='reject_safety_regression' if unsafe else ('mixed_development_signal_no_promotion' if improvement and regress else 'promising_development_requires_expansion_no_promotion' if improvement else 'reject_no_combat_improvement')
    audit=[dict(identity=i,state=absent(i)) for i in ids]
    failed=ROOT/'experiments/opponent_pool/far_bank60_v1/run_20261017_152917_6fba7c'
    oldids=[read(failed/'CONTRACT.json')['guardian']]
    olde=read(failed/'cases/normal_station_zero_2026310300/WORKER_EXIT.json');oldids.append(olde['identity']);oldids.extend(d['identity'] for d in olde['descendants'])
    oldaudit=[dict(identity=i,state=absent(i)) for i in oldids]
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    review=dict(status='completed_verified_development_review',updated_utc=now,comparison_sha256=sha(out/'COMPARISON.json'),results=results,pairs=pairs,gate=gate,unsafe=unsafe,improvement_signal=improvement,regression_present=regress,actual_parent_exit=0,actual_verifier_exit=0,terminal_identity_audit=audit,prior_failed_identity_audit=oldaudit,training_started=False,deployment_allowed=False,retained_deployment='repair_guide',holdout=False,official_validation=False,opening_confounded_with_seed=True)
    write(out/'SAFETY_REVIEW.json',review)
    next_action=('保存退步case並分析原因，否決本候選，不盲續訓練。' if unsafe or not improvement else '先分析逐開局輸贏/高度取捨與命中視窗，凍結此開發候選；再依最差case決定一個因素或擴凍結對手/未見開局，不能直接部署。')
    write(out/'NEXT_REVIEW.json',dict(status='planned_saved_data_review_not_new_run',next_action=next_action,source=str(out/'SAFETY_REVIEW.json'),focus='用已保存的首次真command差異、共同曝光轉向率、角度/射程/積分時窗定位退步或改善；避免把幾何變化等同有效瞄準。此批與兩seed均已用，不重跑。',no_new_training=True,no_automatic_parameter_sweep=True))
    rp=ROOT/'research_latest.json';r=read(rp)
    r.update(updated_utc=now,status='completed_verified_development',experiment='far_bank60_v2',run=str(out),comparison=str(out/'COMPARISON.json'),safety_review=str(out/'SAFETY_REVIEW.json'),verified_comparison=True,complete_games=4,new_FDM_ticks=c['new_FDM_ticks'],gate=gate,candidate_gate=gate,actual_parent_exit_code=0,actual_parent_exit_observation=str(out/'PARENT_EXIT_OBSERVED.json'),actual_verifier_exit_code=0,source_manifest=str(out/'CONTRACT.json'),hard_deadline_epoch=read(out/'CONTRACT.json')['deadline_epoch'],max_wall_seconds=600,planned_cases=4,matched_pairs_planned=2,completed_pairs=2,next_action=next_action,active_workload=None,supervisor=None,guardian=None,worker=None,current_live_workloads=dict(learners=[],loops=[],evaluations=[],observed_utc=now),deployment_allowed=False,retained_deployment='repair_guide',training_started=False,next_factor_status='completed_development_not_deployed',nonzero_attack_counter_exercised=c['nonzero_attack_counter_exercised'])
    write(rp,r)
    r['next_session_plan']=str(out/'NEXT_REVIEW.json');write(rp,r)
    lp=ROOT/'compute_budgets/2026-10-17.json';ledger=read(lp)
    for item in ledger['items']:
        if item['id']==out.name:item.update(status='completed_verified_development',actual_parent_exit=0,actual_verifier_exit=0,original_reservation_retained=True)
        elif item['id']==failed.name:item.update(status='failed_import_collision_before_recorded_combat',actual_shell_exit=1,actual_worker_exit=2,original_reservation_retained=True)
    write(lp,ledger)
    r['daily_compute_reserved_hours']=ledger['reserved_hours'];r['daily_compute_reserved_date']='2026-10-17';write(rp,r)
    regp=ROOT/'seed_registry.json';reg=read(regp)
    for trial in reg.get('trials',{}).values():
        if trial.get('output')==str(out):trial.update(status='completed_verified_development',comparison=str(out/'COMPARISON.json'),reusable=False)
        elif trial.get('output')==str(failed):trial.update(status='failed_import_collision',reusable=False)
    write(regp,reg)
    pp=ROOT/'pipeline_latest.json';pipe=read(pp);pipe['campaign_latest_20261017'].update(status=r['status'],latest_full_battle_review=str(out/'SAFETY_REVIEW.json'),latest_comparison=str(out/'COMPARISON.json'),next_research=next_action,formal_deployment='repair_guide',next_factor_status='completed_development_not_deployed');write(pp,pipe)
    lines=['# 最新進度：遠距轉彎上限60度的四場比較已完成','',f"- 完整4場、{c['new_FDM_ticks']}模擬步、2個相同initial SHA配對；worker／父程序／獨立核對器實際0，來源/XML/模型/逐幀規則/紅方決策/目標裁切/CSV/ACMI核對通過。",'- 唯一變更：藍方距離>914.4m時轉彎目標上限72→60，其餘目標、安全控制與對手不變；基準是零戰術StationController，非pure repair_guide。']
    for p in pairs:lines.append(f"- {p['side']}：基準{p['baseline_event']}/{p['baseline_winner']}、命中{p['baseline_attacks'][0]}；候選{p['candidate_event']}/{p['candidate_winner']}、命中{p['candidate_attacks'][0]}；進入射程{p['baseline_in_range_ticks']}→{p['candidate_in_range_ticks']} tick，最近{p['baseline_range_min_m']:.2f}→{p['candidate_range_min_m']:.2f}m，共同最低AGL差{p['common_minimum_AGL_delta_m']:+.2f}m，候選過9G {p['candidate_over9G'][0]}tick。")
    lines += [f'- 決策：{gate}。{next_action}','- 沒有新訓練，不自動部署；正式repair_guide及原兩模型保留。這是兩個開發開局，非未知隊伍勝率。','- v1初始化誤載同名candidate.py失敗已保留；v2以絕對路徑預先綁定唯一檔，cold import碰撞測試通過，使用全新種子，沒有重跑原失敗種子。',f'- 今日預留{ledger["reserved_hours"]:.6f}h，失敗預留不退款。',f'','證據：'+str(out/'SAFETY_REVIEW.json')]
    text='\n'.join(lines)+'\n';(ROOT/'latest_result.md').write_text(text,encoding='utf8')
    for path,title in ((ROOT/'REVIEW_LOG.md','四場遠距bank60單因素開發結果'),(ROOT/'RACE_FOCUS_20261017.md','最新開發比較')):
        with path.open('a',encoding='utf8') as f:f.write('\n\n## '+now+' '+title+'\n\n'+text.split('\n',1)[1])
    with (ROOT/'REVIEW_LOG.md').open('a',encoding='utf8') as f:
        f.write('\n- 來源manifest：'+str(out/'CONTRACT.json')+'；comparison SHA '+sha(out/'COMPARISON.json')+'。原600秒含4worker與預先規劃120秒核對cap，未增加時限。原v1 shell真1、worker2、guardian intended2不可混作精確觀察；無完整場次，2seed/600秒預留保留。v2唯一修正為絕對路徑提前綁定投影檔，原物理/reset/control AST及cold import碰撞測試通過；新種子2026310400/1，不拼批。\n')
    np=ROOT/'review_notice.json';notice=read(np);notice.setdefault('events',{})[out.name+'|'+gate+'|'+sha(out/'SAFETY_REVIEW.json')]=dict(status=gate,report=str(out/'SAFETY_REVIEW.json'),report_sha256=sha(out/'SAFETY_REVIEW.json'),notified_utc=now,channel='ai heartbeat final');write(np,notice)
    print(json.dumps(dict(gate=gate,pairs=pairs,reserved_hours=ledger['reserved_hours'],retained_deployment='repair_guide'),ensure_ascii=False))

if __name__=='__main__':main(Path(sys.argv[1]))
