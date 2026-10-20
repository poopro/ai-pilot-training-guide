"""One complete game, stream actual full packets/commands/CSV/ACMI."""
from pathlib import Path
import copy,csv,json,sys,time,traceback
import numpy as np
import common as c
FIELDS=['tick','distance_m','blue_angle_deg','red_angle_deg','blue_g','red_g','blue_agl_m','red_agl_m','blue_attack','red_attack','blue_overG','red_overG','blue_position','red_position','blue_advantage','red_advantage','event','winner','bank_action']
def run(folder):
    inp=c.read(folder/'INPUT.json');out=Path(inp['out']);case=inp['case'];phase=inp['phase'];spec=c.check(out,phase);c.gate(spec);limits=c.read(out/(phase+'_LIMITS.json'))
    import policy as p
    m=p.m;began=time.monotonic();model=p.model() if case['mode']=='learned' else None
    env=m.TacticalDuel(opponent='rule',distance_ft=case['distance_ft'],max_steps=18000);rows=0;peak=[0.,0.];minimum=[float('inf'),float('inf')];inband=0;front=0;red_attack=0;last=None
    try:
        env.reset(seed=case['seed']);side=c.b.initialize_side(env,case['side'],m)
        initial=[m.simulator_observation(env.fdm1,env.fdm2).tolist(),m.simulator_observation(env.fdm2,env.fdm1).tolist()];rng_state=copy.deepcopy(env.np_random.bit_generator.state)
        blue=p.BluePolicy(case['mode'],env.settings,model);env.packet_controller=blue.controller;env.controller_variant='repair'
        red=p.make_red(case['opponent'],env.settings,initial[1],rng_state)
        start=dict(case=case,initial=initial,initial_sha256=c.digest(initial),side_transform=side,blue=blue.receipt,command_source=blue.command_source,red=p.red_receipt(red,case['opponent']),red_rng_state=rng_state,
            candidate_model_sha256=c.MODEL_SHA,parent_step_path=m.RepairDuel.step.__code__.co_filename,opponent_fallback=False)
        c.write(folder/'START.json',start)
        counts={k:0 for k in ('act','command','blue_send','red_send','blue_physics','red_physics','judge')};state={}
        def act(packet,residual=None,started=True):
            n=env.current_step;assert started is True;np.testing.assert_array_equal(residual,blue.select(packet,n))
            state['blue_pre']=np.asarray(packet).tolist();state['residual']=np.asarray(residual).tolist();value=blue.next(packet,n);counts['act']+=1;counts['command']=blue.command_calls;state['blue_command']=value.tolist();return value,blue.guard
        env.packet_controller.act=act
        def red_action():
            n=env.current_step;assert counts['blue_physics']==counts['red_physics']==n
            packet=m.simulator_observation(env.fdm2,env.fdm1);value,guard,mode=p.fixed.opponent_command(red,case['opponent'],packet,n)
            if case['opponent']=='sac5000':assert red.attack_ticks==env.judge.attack[1]
            state['red_pre']=packet.tolist();state['red_command']=value.tolist();state['red_guard']=guard;state['red_mode']=mode;env.p2_mode=mode;env.p2_guard=guard;return value
        env._red_action=red_action
        for plane,key in ((env.fdm1,'blue_send'),(env.fdm2,'red_send')):
            original=plane.sendAction
            def send(value,key=key,original=original):
                counts[key]+=1;np.testing.assert_array_equal(p.fixed.legal_command(value),state['blue_command' if key=='blue_send' else 'red_command']);return original(value)
            plane.sendAction=send
        for plane,key in ((env.fdm1,'blue_physics'),(env.fdm2,'red_physics')):
            original=plane.step
            def step(plane=plane,key=key,original=original):
                before=plane.fdm.get_sim_time();value=original();assert abs(plane.fdm.get_sim_time()-before-1/60)<1e-9;counts[key]+=1;return value
            plane.step=step
        with (folder/'telemetry.jsonl').open('w',encoding='utf8') as js,(folder/'telemetry.csv').open('w',encoding='utf8',newline='') as cs,(folder/'duel.acmi').open('w',encoding='utf8') as acmi:
            writer=csv.DictWriter(cs,fieldnames=FIELDS);writer.writeheader();acmi.write('FileType=text/acmi/tacview\nFileVersion=2.2\n0,ReferenceTime=2026-10-18T00:00:00Z\n1,Type=Air+FixedWing,Name=Blue Bank Policy\n2,Type=Air+FixedWing,Name=Frozen Red\n');env.write_frame(acmi)
            original_judge=env.judge.update
            def judge(geo,bg,rg):
                nonlocal rows,red_attack,last,inband,front
                original_judge(geo,bg,rg);counts['judge']+=1;n=env.current_step;assert all(v==n for v in counts.values())
                post=[m.simulator_observation(env.fdm1,env.fdm2).tolist(),m.simulator_observation(env.fdm2,env.fdm1).tolist()];blue.observe(post[0],n)
                redgeo=p.features.geometry_from_observation(post[1]);red_attack+=int(152.4<=redgeo['distance_m']<=914.4 and redgeo['blue_angle_deg']<=1.)
                assert [blue.attack,red_attack]==env.judge.attack
                alt=[float(plane.fdm['position/h-agl-ft'])*.3048 for plane in (env.fdm1,env.fdm2)];snap=env.judge.core.snapshot()
                row=dict(tick=n,distance_m=float(geo['distance_m']),blue_angle_deg=float(geo['blue_angle_deg']),red_angle_deg=float(geo['red_angle_deg']),blue_g=float(bg),red_g=float(rg),blue_agl_m=alt[0],red_agl_m=alt[1],blue_attack=snap['attack_ticks'][0],red_attack=snap['attack_ticks'][1],blue_overG=snap['over_g_ticks'][0],red_overG=snap['over_g_ticks'][1],blue_position=snap['position_sum'][0],red_position=snap['position_sum'][1],blue_advantage=snap['advantage'][0],red_advantage=snap['advantage'][1],event=snap['event'],winner=snap['winner'],bank_action=blue.bank)
                row.update(blue_packet_pre=state['blue_pre'],red_packet_pre=state['red_pre'],blue_packet_post=post[0],red_packet_post=post[1],blue_command=state['blue_command'],red_command=state['red_command'],blue_residual=state['residual'],blue_goals=blue.goals,blue_guard=blue.guard,red_guard=state['red_guard'],red_mode=state['red_mode'],blue_private_attack=blue.attack,red_private_attack=red_attack,decision_features=blue.last_features.tolist() if (n-1)%20==0 else None,red_adapter=red.status() if case['opponent']=='sac5000' else None,counts=counts.copy(),sim_times=[env.fdm1.fdm.get_sim_time(),env.fdm2.fdm.get_sim_time()])
                js.write(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n');writer.writerow({k:row[k] for k in FIELDS});rows=n;last=row
                for k,g in enumerate((bg,rg)):peak[k]=max(peak[k],abs(float(g)));minimum[k]=min(minimum[k],alt[k])
                band=152.4<=row['distance_m']<=914.4;inband+=int(band);front+=int(band and row['blue_angle_deg']<=90)
                if abs(bg)>9:raise RuntimeError('Blue over9G; stop case and reject promotion')
            env.judge.update=judge
            for n in range(18000):
                if n%20==0:
                    if c.stop(out) or c.stop(folder) or c.b.expired(spec,limits) or not c.live(spec['guardian']):raise RuntimeError('Original deadline/STOP/parent')
                    packet=m.simulator_observation(env.fdm1,env.fdm2);residual=blue.select(packet,n)
                _,_,term,trunc,_=m.RepairDuel.step(env,c.bridge.residual(blue.bank))
                if env.current_step%20==0:env.write_frame(acmi)
                if n%1800==1799:c.gate(spec);c.write(folder/'progress.json',dict(ticks=env.current_step,phase=phase,peak_blue_G=peak[0]))
                if term or trunc:
                    if env.current_step%20:env.write_frame(acmi)
                    break
        final=env.judge.core.snapshot();assert final['event']!='ongoing' and final['winner'] in ('blue','red','draw')
        assert rows==blue.act_calls==blue.command_calls==env.current_step
        pending=None;red_final=None
        if case['opponent']=='sac5000':
            pending=red.command(last['red_packet_post'],completed_tick=rows).tolist();red_final=red.status();assert red.attack_ticks==final['attack_ticks'][1]
        c.gate(spec);c.check(out,phase)
        result=dict(status='complete_game_pending_verifier',case=case,initial_sha256=start['initial_sha256'],rows=rows,counts=counts,final=final,final_packets=[last['blue_packet_post'],last['red_packet_post']],peak_g=peak,min_AGL_m=minimum,in_range_ticks=inband,in_range_front_ticks=front,blue_predict_calls=blue.predict_calls,blue_actor_sha256=c.tc.actor_digest(model) if model is not None else None,pending_red_command_not_sent=pending,red_final_adapter=red_final,wall_seconds=time.monotonic()-began,artifacts={name:c.sha(folder/name) for name in ('START.json','telemetry.jsonl','telemetry.csv','duel.acmi')},deployment_allowed=False)
        c.write(folder/'RESULT.json',result);print(json.dumps(dict(case=case['id'],ticks=rows,event=final['event'],winner=final['winner'],wall_seconds=result['wall_seconds'])),flush=True);return 0
    except BaseException as exc:
        c.write(folder/'PARTIAL_FAILURE.json',dict(error=repr(exc),recorded_rows=rows,wall_seconds=time.monotonic()-began));raise
    finally:env.close()
if __name__=='__main__':
    try:raise SystemExit(run(Path(sys.argv[1])))
    except Exception:traceback.print_exc();raise SystemExit(2)
