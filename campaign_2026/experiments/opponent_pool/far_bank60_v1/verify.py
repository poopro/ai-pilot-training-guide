"""Saved full-frame judge replay and fair-opening verification; no new FDM."""
import sys,csv,json,math,time,subprocess,os
from pathlib import Path
from battle import read,write,sha,digest,ROOT,plan,sources,identity,live

def verify(out,parent_exit):
    spec=read(out/'CONTRACT.json');report=read(out/'report.json');guard=read(out/'GUARD_EXIT.json');errors=[];results=[]
    def check(ok,label):
        if not ok and len(errors)<100:errors.append(label)
    check(parent_exit==0,'actual parent/guardian exit');check(report['status']=='completed_pending_verifier' and len(report['cases'])==4,'complete four batch')
    check(spec['cases']==plan() and guard['source_unchanged'] and spec['sources']==sources(),'fixed plan/source/XML/models')
    sys.path.insert(0,str(ROOT/'experiments/rules_v20261014'));from judge import Judge,Frame,RuleProfile
    sys.path.insert(0,str(ROOT/'experiments/opponent_pool/frozen_sac_opponent_v2'));from packet_features import geometry_from_observation,tactical_obs
    from factory import frozen_actor,source_gate as actor_source_gate
    import numpy as np
    import torch
    torch.set_num_threads(1);actor_source_gate()
    replay_actors={name:frozen_actor(name) for name in ('sac5000',)}
    for c in spec['cases']:
        folder=out/'cases'/c['id'];tag=c['id']
        if not (folder/'RESULT.json').is_file() or not (folder/'WORKER_EXIT.json').is_file():check(False,tag+' missing result');continue
        r=read(folder/'RESULT.json');exit=read(folder/'WORKER_EXIT.json');check(exit['actual_worker_exit']==0 and exit['reason'] is None and exit['worker_and_descendants_absent'],tag+' real exit/cleanup')
        check(exit['result_sha256']==sha(folder/'RESULT.json') and exit['input_sha256']==sha(folder/'INPUT.json'),tag+' receipt links')
        if r['status']!='complete_game':check(False,tag+' incomplete');continue
        check(r['case']==c and r['initial_sha256']==digest(r['initial']) and r['own_packet_policy_only'] and r['all_actual_send_commands_equal_single_act_output'],tag+' actor contract')
        check(all(sha(folder/n)==h for n,h in r['artifacts'].items()),tag+' raw artifact hashes')
        j=Judge(RuleProfile(**r['final']['profile']));decisions={d['tick']:d for d in r['tactical_decisions']};last=None;heights=[];margins=[];expected_blue=0;expected_red=0;previous_guard=False;red_previous_guard=False;expected_red_action=None
        with (folder/'telemetry.jsonl').open(encoding='utf8') as stream,(folder/'telemetry.csv').open(encoding='utf8',newline='') as csvstream:
            csvrows=csv.DictReader(csvstream)
            for n,line in enumerate(stream,1):
                row=json.loads(line);csvrow=next(csvrows,None);check(csvrow is not None and int(csvrow['tick'])==n,tag+' CSV continuity')
                check(row['tick']==n and all(v==n for v in row['counts'].values()),tag+' one step'+str(n))
                check(row['red_adapter']['completed_tick']==n-1 and row['red_adapter']['act_calls']==n and row['red_adapter']['predict_calls']==(n-1)//20+1,tag+' red timing'+str(n))
                for side in ('blue','red'):
                    pre=row[side+'_packet_pre'];post=row[side+'_packet_post'];cmd=row[side+'_command']
                    check(len(pre)==len(post)==26 and all(math.isfinite(v) for v in pre+post),tag+' legal packet')
                    check(len(cmd)==4 and all(math.isfinite(v) for v in cmd) and all(abs(v)<=1 for v in cmd[:3]) and 0<=cmd[3]<=1,tag+' commands')
                    check(pre==(last[side+'_packet_post'] if last else r['initial'][0 if side=='blue' else 1]),tag+' packet linkage'+str(n))
                    geo=geometry_from_observation(post)
                    check(abs(geo['distance_m']-row['distance_m'])<1e-5 and abs(geo['blue_angle_deg']-row[side+'_angle_deg'])<1e-5,tag+' packet/judge geometry')
                g=row['blue_guidance'];pregeo=geometry_from_observation(row['blue_packet_pre'])
                check(abs(g['distance_m']-pregeo['distance_m'])<1e-5,tag+' command uses legal own geometry')
                requested=g['requested'];applied=g['applied']
                expected_roll=max(-60.,min(60.,requested[0])) if c['actor']=='far_bank60' and g['distance_m']>914.4 else requested[0]
                check(g['far_cap_enabled']==(c['actor']=='far_bank60') and g['safety'] is True and applied==[expected_roll,*requested[1:]],tag+' unique cap mapping, other goals and safety unchanged')
                if (n-1)%20==0:
                    d=decisions.get(n-1);check(d is not None,tag+' missing policy decision')
                    if d:
                        o=np.asarray(row['blue_packet_pre']);features=tactical_obs(o,geometry_from_observation(o),expected_blue,previous_guard,elapsed_ticks=n-1)
                        check(np.array_equal(features,np.asarray(d['features'],dtype=np.float32)),tag+' blue legal features')
                        check(d['action']==[0.,0.,0.],tag+' zero tactical rule controller')
                    ro=np.asarray(row['red_packet_pre']);rf=tactical_obs(ro,geometry_from_observation(ro),expected_red,red_previous_guard,elapsed_ticks=n-1)
                    expected_red_action=replay_actors['sac5000'].predict(rf,deterministic=True)[0]
                check(np.array_equal(expected_red_action,np.asarray(row['red_adapter']['tactical'],dtype=np.float32)),tag+' exact red frozen-model decision/hold')
                check(row['red_adapter']['attack_ticks']==expected_red,tag+' red private counter')
                frame=Frame(row['distance_m'],row['blue_angle_deg'],row['red_angle_deg'],row['blue_g'],row['red_g'],row['blue_agl_m'],row['red_agl_m']);s=j.advance(frame,started=True)
                expected_blue=s['attack_ticks'][0];expected_red=s['attack_ticks'][1]
                check(row['blue_private_attack']==expected_blue and row['blue_attack']==expected_blue and row['red_attack']==expected_red,tag+' counters')
                check(row['blue_overG']==s['over_g_ticks'][0] and row['red_overG']==s['over_g_ticks'][1],tag+' G count')
                for key,expected in (('blue_position',s['position_sum'][0]),('red_position',s['position_sum'][1]),('blue_advantage',s['advantage'][0]),('red_advantage',s['advantage'][1])):check(abs(row[key]-expected)<=1e-8,tag+' score '+key)
                check(row['event']==s['event'] and row['winner']==s['winner'],tag+' event priority/winner')
                if last:check(all(abs(a-b-1/60)<1e-9 for a,b in zip(row['sim_times'],last['sim_times'])),tag+' 60Hz time')
                heights.append(row['blue_agl_m']);margins.append(row['blue_advantage']-row['red_advantage']);previous_guard=row['blue_private_guard'];red_previous_guard=row['red_adapter']['guard_active'];last=row
            check(next(csvrows,None) is None,tag+' no extra CSV rows')
        check(last is not None and n==r['final']['ticks'] and j.snapshot()==r['final'],tag+' exact terminal judge replay')
        check(r['final']['event']!='ongoing' and r['final']['winner'] is not None and r['final']['ticks']<=18000,tag+' complete resolved round')
        check(r['red_final_adapter']['attack_ticks']==expected_red and r['red_final_adapter']['completed_tick']==n and r['red_final_adapter']['act_calls']==n+1 and r['pending_red_commands_not_sent']==1,tag+' terminal pending command')
        results.append(dict(case=c,initial_sha256=r['initial_sha256'],event=r['final']['event'],winner=r['final']['winner'],ticks=r['final']['ticks'],attack_ticks=r['final']['attack_ticks'],over9G=r['final']['over_g_ticks'],total_score=r['final']['total_score'],score_margin=r['final']['total_score'][0]-r['final']['total_score'][1],peak_abs_g=r['peak_abs_g'],min_agl_m=r['min_agl_m'],side_transform=r['side_transform'],heights=heights,margins=margins))
    comparisons=[]
    for opening in (0,1):
        group=[r for r in results if r['case']['opening']==opening]
        check(len(group)==2 and len({r['initial_sha256'] for r in group})==1,'same full blue/red initial SHA opening '+str(opening))
        if len(group)!=2:continue
        baseline=next(r for r in group if r['case']['actor']=='station_zero')
        for candidate in group:
            if candidate is baseline:continue
            common=min(len(candidate['heights']),len(baseline['heights']))
            comparisons.append(dict(opening=opening,side=candidate['case']['side'],candidate=candidate['case']['actor'],baseline='station_zero',candidate_event=candidate['event'],baseline_event=baseline['event'],candidate_winner=candidate['winner'],baseline_winner=baseline['winner'],attack_delta=candidate['attack_ticks'][0]-baseline['attack_ticks'][0],full_score_margin_delta=candidate['score_margin']-baseline['score_margin'],common_ticks=common,common_minimum_AGL_delta_m=min(candidate['heights'][:common])-min(baseline['heights'][:common]),common_score_margin_delta=candidate['margins'][common-1]-baseline['margins'][common-1]))
    for r in results:r.pop('heights');r.pop('margins')
    valid=not errors and len(results)==4
    verification=dict(verified_comparison=valid,errors=errors,complete_games=len(results),new_FDM_ticks=sum(r['ticks'] for r in results),actual_parent_exit=parent_exit,actual_worker_exits=guard['actual_all_worker_exits'],source_contract_sha256=sha(out/'CONTRACT.json'),results=results,paired_tradeoffs=comparisons,all_frozen_red_policy_decisions_independently_recomputed=True,all_blue_zero_tactical_decisions_verified=True,all_goal_mappings_verified=True,full_60Hz_controller_replay_performed=False,nonzero_attack_counter_exercised=any(sum(r['attack_ticks'])>0 for r in results),deployment_allowed=False,official_validation=False)
    write(out/'COMPARISON.json',verification);print(json.dumps({k:verification[k] for k in ('verified_comparison','errors','complete_games','new_FDM_ticks','nonzero_attack_counter_exercised')}));return 0 if valid else 2

def guarded(out,parent_exit):
    spec=read(out/'CONTRACT.json');remaining=min(120.,spec['deadline_monotonic']-time.monotonic(),spec['deadline_epoch']-time.time())
    if remaining<=0:raise RuntimeError('Original batch deadline reached; no late verification launch')
    command=[sys.executable,'-B','-X','utf8',str(Path(__file__)),'--internal',str(out),str(parent_exit)]
    with (out/'verifier.log').open('w',encoding='utf8') as log:
        p=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW);ident=identity(p.pid)
        try:code=p.wait(timeout=remaining);reason='normal_exit'
        except subprocess.TimeoutExpired:
            if not live(ident):raise RuntimeError('Verifier identity unknown at original deadline')
            p.terminate()
            try:code=p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                if not live(ident):raise RuntimeError('Verifier identity unknown before kill')
                p.kill();code=p.wait(timeout=2)
            reason='original_deadline_or_120s_verifier_cap'
    write(out/'VERIFIER_EXIT.json',dict(command=command,identity=ident,actual_exit=code,reason=reason,used_original_batch_deadline=True,identity_absent=not live(ident)))
    print(json.dumps(dict(verifier_actual_exit=code,reason=reason,comparison=str(out/'COMPARISON.json'))));return 0 if code==0 and reason=='normal_exit' else 2

if __name__=='__main__':
    if len(sys.argv)==4 and sys.argv[1]=='--guarded':raise SystemExit(guarded(Path(sys.argv[2]),int(sys.argv[3])))
    if len(sys.argv)==4 and sys.argv[1]=='--internal':raise SystemExit(verify(Path(sys.argv[2]),int(sys.argv[3])))
    raise SystemExit('Use --guarded OUT observed_parent_exit')
