"""New bank-only input through actual60Hz parent physics; no training."""
from pathlib import Path
import csv,json,sys
import numpy as np
import common as c
import bridge
FIELDS=['tick','distance_m','blue_angle_deg','red_angle_deg','blue_g','red_g','blue_agl_m','red_agl_m','blue_attack','red_attack','blue_overG','red_overG','blue_position','red_position','blue_advantage','red_advantage','event','winner']
def run(out):
    spec=c.check(out,'WORKER');c.gate(spec)
    sys.path.insert(0,str(c.ROOT/'experiments/m4_tactical_v4'));import m4_tactical_rl as m
    sys.path.insert(0,str(c.b.base.ADAPTER));from factory import build_frozen_opponent,source_gate as actor_gate
    from adapter import legal_command
    from packet_features import geometry_from_observation
    m.torch.set_num_threads(1);records=[];initials=[];prefix=[];blue_refs=[];red_refs=[]
    env=m.TacticalDuel(opponent='rule',distance_ft=6000,max_steps=300)
    try:
        for mode in ('neutral','exercise'):
            c.check(out,'WORKER');env.reset(seed=spec['seed'])
            blue=bridge.controller(env.settings);env.packet_controller=blue;env.controller_variant='repair';red=build_frozen_opponent('sac5000',env.settings);env.p2_type='frozen_sac5000'
            assert blue is not red.controller and blue.settings is not red.controller.settings
            assert all(blue is not old for old in blue_refs) and all(red is not old for old in red_refs);blue_refs.append(blue);red_refs.append(red)
            initial=[m.simulator_observation(env.fdm1,env.fdm2).tolist(),m.simulator_observation(env.fdm2,env.fdm1).tolist()];initials.append(c.digest(initial))
            if len(initials)>1:assert initials[-1]==initials[0]
            folder=out/mode;folder.mkdir();receipt=bridge.receipt(blue)
            counts={k:0 for k in ('act','command','blue_send','red_send','blue_physics','red_physics','judge')}
            state=dict(bank=0.,blue_pre=None,red_pre=None,blue_command=None,red_command=None,received=None,goals=None,guard=False,blue_attack=0)
            rows=[];peak=[0.,0.];minimum=[float('inf'),float('inf')]
            original_command=blue.command
            def command(packet,roll,pitch,speed,rudder=0.,safety=True):
                counts['command']+=1;assert safety is True
                state['goals']=[float(roll),float(pitch),float(speed),float(rudder)]
                return original_command(packet,roll,pitch,speed,rudder,safety=True)
            blue.command=command;original_act=blue.act
            def act(packet,residual=None,started=True):
                assert started is True;np.testing.assert_array_equal(residual,bridge.residual(state['bank']))
                counts['act']+=1;state['blue_pre']=np.asarray(packet).tolist();state['received']=np.asarray(residual).tolist()
                value,guard=original_act(packet,residual=residual,started=True);state['blue_command']=legal_command(value).tolist();state['guard']=bool(guard);return value,guard
            blue.act=act
            def red_action():
                n=counts['red_physics'];assert env.current_step==n==counts['blue_physics']
                packet=m.simulator_observation(env.fdm2,env.fdm1);value=red.command(packet,completed_tick=n)
                assert red.attack_ticks==env.judge.attack[1];state['red_pre']=packet.tolist();state['red_command']=value.tolist();env.p2_guard=red.status()['guard_active'];env.p2_mode='frozen_sac5000';return value
            env._red_action=red_action
            for plane,key in ((env.fdm1,'blue_send'),(env.fdm2,'red_send')):
                original=plane.sendAction
                def send(value,original=original,key=key):
                    counts[key]+=1;np.testing.assert_array_equal(legal_command(value),state['blue_command' if key=='blue_send' else 'red_command']);return original(value)
                plane.sendAction=send
            for plane,key in ((env.fdm1,'blue_physics'),(env.fdm2,'red_physics')):
                original=plane.step
                def step(original=original,plane=plane,key=key):
                    before=plane.fdm.get_sim_time();value=original();assert abs(plane.fdm.get_sim_time()-before-1/60)<1e-9;counts[key]+=1;return value
                plane.step=step
            original_judge=env.judge.update
            def judge(geo,bg,rg):
                original_judge(geo,bg,rg);counts['judge']+=1;n=counts['judge'];assert env.current_step==n and all(v==n for v in counts.values())
                post=[m.simulator_observation(env.fdm1,env.fdm2).tolist(),m.simulator_observation(env.fdm2,env.fdm1).tolist()]
                legal=geometry_from_observation(post[0]);state['blue_attack']+=int(152.4<=legal['distance_m']<=914.4 and legal['blue_angle_deg']<=1)
                assert state['blue_attack']==env.judge.attack[0]
                alt=[float(p.fdm['position/h-agl-ft'])*.3048 for p in (env.fdm1,env.fdm2)]
                for k,g in enumerate((bg,rg)):peak[k]=max(peak[k],abs(float(g)));minimum[k]=min(minimum[k],alt[k])
                snap=env.judge.core.snapshot()
                row=dict(tick=n,distance_m=float(geo['distance_m']),blue_angle_deg=float(geo['blue_angle_deg']),red_angle_deg=float(geo['red_angle_deg']),blue_g=float(bg),red_g=float(rg),blue_agl_m=alt[0],red_agl_m=alt[1],blue_attack=snap['attack_ticks'][0],red_attack=snap['attack_ticks'][1],blue_overG=snap['over_g_ticks'][0],red_overG=snap['over_g_ticks'][1],blue_position=snap['position_sum'][0],red_position=snap['position_sum'][1],blue_advantage=snap['advantage'][0],red_advantage=snap['advantage'][1],event=snap['event'],winner=snap['winner'])
                row.update(blue_packet_pre=state['blue_pre'],red_packet_pre=state['red_pre'],blue_packet_post=post[0],red_packet_post=post[1],blue_command=state['blue_command'],red_command=state['red_command'],blue_residual_received=state['received'],bank_action=state['bank'],blue_requested_goals=state['goals'],blue_guard=state['guard'],blue_private_attack=state['blue_attack'],red_adapter=red.status(),counts=counts.copy(),sim_times=[env.fdm1.fdm.get_sim_time(),env.fdm2.fdm.get_sim_time()]);rows.append(row)
            env.judge.update=judge
            with (folder/'duel.acmi').open('w',encoding='utf8') as stream:
                stream.write('FileType=text/acmi/tacview\nFileVersion=2.2\n0,ReferenceTime=2026-10-18T00:00:00Z\n1,Type=Air+FixedWing,Name=Blue Bank API\n2,Type=Air+FixedWing,Name=Frozen SAC Red\n');env.write_frame(stream)
                for completed in range(300):
                    c.check(out,'WORKER');assert env.current_step==completed
                    if completed%20==0:state['bank']=bridge.scheduled(mode,completed)
                    assert state['bank']==bridge.scheduled(mode,completed)
                    # Direct frozen4-residual parent path, no3-tactic step or learning reward.
                    _,_,term,trunc,_=m.RepairDuel.step(env,bridge.residual(state['bank']))
                    if env.current_step%20==0:env.write_frame(stream)
                    if term or (trunc and env.current_step!=300):raise RuntimeError('Unexpected short interface termination')
            assert env.current_step==len(rows)==300
            final_red=m.simulator_observation(env.fdm2,env.fdm1).tolist();pending=red.command(final_red,completed_tick=300)
            assert red.attack_ticks==env.judge.attack[1] and red.act_calls==301 and red.predict_calls==16
            (folder/'telemetry.jsonl').write_text(''.join(json.dumps(r,separators=(',',':'),allow_nan=False)+'\n' for r in rows),encoding='utf8')
            with (folder/'telemetry.csv').open('w',encoding='utf8',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=FIELDS);writer.writeheader();writer.writerows({k:r[k] for k in FIELDS} for r in rows)
            key=lambda r:[r[k] for k in ('blue_packet_pre','red_packet_pre','blue_packet_post','red_packet_post','blue_command','red_command')]
            prefix.append([key(r) for r in rows[:100]])
            record=dict(mode=mode,seed=spec['seed'],initial=initial,initial_sha256=c.digest(initial),runtime_blue=receipt,parent_step_path=str(Path(m.RepairDuel.step.__code__.co_filename).resolve()),
                final=env.judge.core.snapshot(),final_packets=[m.simulator_observation(env.fdm1,env.fdm2).tolist(),final_red],red_final_adapter=red.status(),pending_red_command=pending.tolist(),pending_red_commands_not_sent=1,
                counts=counts,peak_g=peak,min_AGL_m=minimum,first100_packet_command_sha256=c.digest(prefix[-1]),rows=300,artifacts={n:c.sha(folder/n) for n in ('telemetry.jsonl','telemetry.csv','duel.acmi')})
            c.write(folder/'RESULT.json',record);records.append(record)
        assert prefix[0]==prefix[1];assert all(r['final']['over_g_ticks'][0]==0 for r in records)
    finally:env.close()
    c.gate(spec);actor_gate()
    c.write(out/'RESULT.json',dict(status='short_FDM_complete_pending_independent_verifier',episodes=records,new_FDM_ticks=600,source_fixed=True,training_started=False,formal_deployment='repair_guide',deployment_allowed=False,strength_verified=False))
    print(json.dumps(dict(new_FDM_ticks=600,episodes=2,first100_exact=True,blue_peak_g=[r['peak_g'][0] for r in records])),flush=True);return 0
if __name__=='__main__':raise SystemExit(run(Path(sys.argv[1])))
