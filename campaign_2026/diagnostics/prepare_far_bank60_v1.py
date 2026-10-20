"""Create an isolated, single-factor experiment from frozen battle v2."""
from pathlib import Path
import hashlib,json
ROOT=Path(r'E:\ai_pilot\campaign_2026')
OLD=ROOT/'experiments/opponent_pool/frozen_sac_battle_v2'
NEW=ROOT/'experiments/opponent_pool/far_bank60_v1'
NEW.mkdir(exist_ok=False)
def replace(s,a,b):
    if s.count(a)!=1:raise RuntimeError('Expected unique replacement: '+a[:100])
    return s.replace(a,b)
b=(OLD/'battle.py').read_text(encoding='utf8')
b=replace(b,"ACTORS=('station_zero','sac5000','transfer10000');SEEDS=(2026310200,2026310201)","ACTORS=('station_zero','far_bank60');SEEDS=(2026310300,2026310301)")
b=replace(b,"TRIAL='frozen_sac_battle_v2_2026310200_two_openings_three_actors'","TRIAL='far_bank60_v1_2026310300_two_openings_two_doctrines'")
b=replace(b,"HERE/'test_static.py')","HERE/'test_static.py',HERE/'candidate.py')")
b=replace(b,"blue_actor=None if case['actor']=='station_zero' else frozen_actor(case['actor'])","blue_actor=None  # This experiment compares two zero-tactical rule controllers only.")
b=replace(b,"decisions=[];peak=[0.,0.];minimum=[float('inf'),float('inf')]",'''decisions=[];peak=[0.,0.];minimum=[float('inf'),float('inf')]
        from candidate import project_goal
        original_command=env.packet_controller.command
        def logged_command(packet,roll,pitch,speed,rudder=0.,safety=True):
            distance=geometry_from_observation(packet)['distance_m']
            requested=[float(roll),float(pitch),float(speed),float(rudder)]
            applied=project_goal(distance,requested,enabled=case['actor']=='far_bank60')
            state['blue_guidance']=dict(distance_m=distance,requested=requested,applied=applied,far_cap_enabled=case['actor']=='far_bank60',safety=safety)
            return original_command(packet,*applied,safety=safety)
        env.packet_controller.command=logged_command''')
b=replace(b,"blue_private_guard=state['blue_guard'],sim_times=", "blue_private_guard=state['blue_guard'],blue_guidance=state['blue_guidance'],sim_times=")
b=b.replace("experiment='frozen_sac_battle_v2'","experiment='far_bank60_v1'")
b=b.replace("profile='frozen_sac_six_battle_v2'","profile='far_bank60_four_game_development_v1'")
b=b.replace("hypothesis='Frozen learned blue policies may improve or regress versus zero-tactical StationController against a fixed learned SAC red; evaluate complete paired games'","hypothesis='Changing only the blue far requested bank cap72 to60 may break persistent symmetric saturated turn geometry and enter firing range; may regress'")
b=b.replace("single_factor='Blue actor choice only within each exact initial opening'","single_factor='Blue requested roll cap60 only at distance>914.4m before unchanged command; baseline72, zero tactical both'")
b=replace(b,"planned_cases=6,matched_pairs_planned=2","planned_cases=4,matched_pairs_planned=2,actual_parent_exit_code=None")
b=replace(b,"blue_policy_candidates", "blue_policy_candidates") if 'blue_policy_candidates' in b else b
b=replace(b,"Read full-frame", "Read full-frame") if 'Read full-frame' in b else b
(NEW/'battle.py').write_text(b,encoding='utf8')
v=(OLD/'verify.py').read_text(encoding='utf8')
v=v.replace("len(report['cases'])==6,'complete six batch'","len(report['cases'])==4,'complete four batch'")
v=v.replace("for name in ('sac5000','transfer10000')","for name in ('sac5000',)")
v=replace(v,"if c['actor']=='station_zero':check(d['action']==[0.,0.,0.],tag+' zero baseline')\n                        else:check(np.array_equal(replay_actors[c['actor']].predict(features,deterministic=True)[0],np.asarray(d['action'],dtype=np.float32)),tag+' exact blue frozen-model decision')", "check(d['action']==[0.,0.,0.],tag+' zero tactical rule controller')")
v=replace(v,"if (n-1)%20==0:",'''g=row['blue_guidance'];pregeo=geometry_from_observation(row['blue_packet_pre'])
                check(abs(g['distance_m']-pregeo['distance_m'])<1e-5,tag+' command uses legal own geometry')
                requested=g['requested'];applied=g['applied']
                expected_roll=max(-60.,min(60.,requested[0])) if c['actor']=='far_bank60' and g['distance_m']>914.4 else requested[0]
                check(g['far_cap_enabled']==(c['actor']=='far_bank60') and g['safety'] is True and applied==[expected_roll,*requested[1:]],tag+' unique cap mapping, other goals and safety unchanged')
                if (n-1)%20==0:''')
v=v.replace("len(group)==3","len(group)==2").replace("if len(group)!=3:","if len(group)!=2:")
v=replace(v,"valid=not errors and len(results)==6","valid=not errors and len(results)==4")
v=replace(v,"remaining=min(60.,spec['deadline_monotonic']","remaining=min(120.,spec['deadline_monotonic']")
v=v.replace("original_deadline_or_60s_verifier_cap","original_deadline_or_120s_verifier_cap")
v=replace(v,"all_frozen_policy_decisions_independently_recomputed=True", "all_frozen_red_policy_decisions_independently_recomputed=True,all_blue_zero_tactical_decisions_verified=True,all_goal_mappings_verified=True")
(NEW/'verify.py').write_text(v,encoding='utf8')
(NEW/'PREPARATION.json').write_text(json.dumps(dict(status='prepared_not_launched',old_runner_source=str(OLD),old_runner_sha256=hashlib.sha256((OLD/'battle.py').read_bytes()).hexdigest(),single_factor='Far blue roll target cap72→60 at distance>914.4m only; no model learning',original_worker_seconds=90,original_whole_seconds=600,verifier_seconds=120,source_plan='Both original frozen validated interface and new batch files locked; no edits to old sources/models',seed_plan=[2026310300,2026310301],seed_claimed=False,not_holdout=True),ensure_ascii=False,indent=2),encoding='utf8')
print(str(NEW))
