"""Private supervisor/worker. A recorded launcher and independent guard are mandatory."""
import argparse,csv,subprocess,time,copy,traceback
from common import *

def await_guard(out,launch):
    end=time.monotonic()+10
    while time.monotonic()<end:
        if (out/'guard.json').exists():
            try:guard=read(out/'guard.json')
            except (OSError,ValueError):
                time.sleep(.1);continue
            if guard['status']=='armed' and guard['target']==launch['supervisor'] and matching(guard['guard']):return guard
        if stop(out):raise RuntimeError('STOP before guard armed')
        time.sleep(.1)
    raise RuntimeError('Independent guard not armed')

def write_frame_with_offset(stream,env,offset):
    stream.write(f"#{(offset+env.current_step)/60.:.3f}\n")
    for oid,plane in ((1,env.fdm1),(2,env.fdm2)):
        pose=plane.getProperty('pose')
        stream.write(f"{oid},T={pose[1]}|{pose[7]}|{pose[2]}|{pose[5]}|{pose[4]}|{pose[3]}\n")

def worker(input_path):
    spec=read(input_path);out=Path(spec['out']);folder=Path(input_path).parent;case=spec['case'];launch=read(out/'launch.json')
    if Path(input_path).resolve()!=out/'cases'/case['case_id']/'input.json':raise RuntimeError('Worker outside reserved folder')
    if psutil.Process().ppid()!=launch['supervisor']['pid'] or not matching(launch['supervisor']):raise RuntimeError('Worker parent identity mismatch')
    execution_mode_gate(launch)
    guard=read(out/'guard.json')
    if guard['status']!='armed' or not matching(guard['guard']):raise RuntimeError('No independent live guard')
    if case not in launch['cases'] or spec['tools_sha256']!=launch['tools_sha256']:raise RuntimeError('Unreserved input')
    source_gate(spec['source_freeze'])
    began=time.monotonic();env=None
    result={'status':'running','case':case,'episodes':[],'tactical_decisions':[],'score_eligible':False,'official_validation':False,'deployment_allowed':False}
    try:
        sys.path.insert(0,str(ROOT/'experiments'/case['actor_source']))
        import m4_tactical_rl as m
        import m1_station as station_module
        if Path(m.__file__).resolve().parent.name!=case['actor_source'] or Path(station_module.__file__).resolve().parent.name!=case['actor_source']:raise RuntimeError('Actor import path mixed')
        import numpy as np
        m.torch.set_num_threads(1)
        actor_policy=m.SAC.load(model_for_actor(case['actor_id']),device='cpu')
        if actor_policy is not None and (actor_policy.observation_space.shape!=(13,) or actor_policy.action_space.shape!=(3,)):raise RuntimeError('Frozen model dimension mismatch')
        frozen=m.load_policy(m.DEFAULT_BUNDLE) if case['opponent_id']=='rl' else None
        env=m.TacticalDuel(opponent=case['opponent_id'],policy=frozen,distance_ft=case['distance_ft'],max_steps=case['max_steps'],stage=case['stage'])
        fields=['episode','tick','act_calls','blue_send_calls','red_send_calls','judge_calls','attack_ticks','distance_m','blue_angle_deg','blue_g','actual_command','command_from_act','observation_sha256','red_angle_deg','red_g','blue_agl_m','red_agl_m','blue_hsl_m','red_hsl_m','red_attack_ticks','blue_over_g_ticks','red_over_g_ticks','position_blue','position_red','advantage_blue','advantage_red','event','winner']
        with (folder/'telemetry.csv').open('w',newline='',encoding='utf8') as stream,(folder/'duel.acmi').open('w',encoding='utf8') as acmi:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
            acmi.write('FileType=text/acmi/tacview\nFileVersion=2.2\n0,ReferenceTime=2026-10-15T00:00:00Z\n1,Type=Air+FixedWing,Name=Blue\n2,Type=Air+FixedWing,Name=Red\n')
            for ep in range(1):
                actual_heading_error=None
                if stop(out) or time.monotonic()>=launch['deadline_monotonic']:raise RuntimeError('STOP/deadline before reset')
                env.reset(seed=case['seed'])
                #Purpose-built counter fixture, not a candidate performance opening.
                #Remove only the measured heading jitter before the first physics
                #step; do not set attack counters, rewards, or later flight states.
                if case.get('coaxial_init'):
                    from env import JsbsimFdm
                    from combat_v3.controller import relative_geometry
                    initial_pose=m.simulator_observation(env.fdm1,env.fdm2)
                    target=m.geometry_from_observation(initial_pose)['bearing_deg']
                    env.fdm1=JsbsimFdm(fdm_id=1,fdm_ic_lat=float(initial_pose[0]),fdm_ic_long=float(initial_pose[1]),
                                      fdm_ic_h=float(initial_pose[2]),fdm_ic_v=340.,fdm_ic_psi=float(target-case['heading_error_deg'])%360.)
                    env.geometry=relative_geometry(env.fdm1,env.fdm2)
                    env.prev_potential=env._potential(env.geometry)
                    new_packet=m.simulator_observation(env.fdm1,env.fdm2)
                    actual_heading_error=(m.geometry_from_observation(new_packet)['bearing_deg']-new_packet[5]+180)%360-180
                    if abs(actual_heading_error-case['heading_error_deg'])>.01:raise RuntimeError('Physical yaw error differs from reserved fixture')
                    if env.judge.attack!=[0,0] or env.current_step!=0:raise RuntimeError('No preloaded counter or physics allowed')
                initial=m.simulator_observation(env.fdm1,env.fdm2).tolist()
                initial_red=m.simulator_observation(env.fdm2,env.fdm1).tolist()
                counts={'act':0,'blue':0,'red':0,'judge':0};state={'cmd':None,'actual':None,'expected_attack':0,'max_command_error':0.0,'fallbacks':0}
                pc=env.packet_controller;original_act=pc.act
                def act(*args,**kwargs):
                    counts['act']+=1
                    cmd,active=original_act(*args,**kwargs);state['cmd']=legal_command(cmd)
                    return cmd,active
                pc.act=act
                old_blue=env.fdm1.sendAction;old_red=env.fdm2.sendAction;old_judge=env.judge.update
                def blue(cmd):
                    counts['blue']+=1;state['actual']=legal_command(cmd)
                    err=max(abs(x-y) for x,y in zip(state['actual'],state['cmd']));state['max_command_error']=max(err,state['max_command_error'])
                    if err>1e-12:raise RuntimeError('Actual sent action differs from sole controller output')
                    return old_blue(cmd)
                def red(cmd):
                    counts['red']+=1;legal_command(cmd)
                    if 'fallback' in env.p2_mode:state['fallbacks']+=1
                    return old_red(cmd)
                def judge(geo,bg,rg):
                    old_judge(geo,bg,rg);counts['judge']+=1;tick=counts['judge']
                    if any(counts[k]!=tick for k in ('act','blue','red')):raise RuntimeError('Not one controller/send/physics tick')
                    state['expected_attack']+=int(env.judge.window(geo['distance_m'],geo['blue_angle_deg']))
                    if env.judge.attack[0]!=state['expected_attack']:raise RuntimeError('Post-step judge counter mismatch')
                    obs=m.simulator_observation(env.fdm1,env.fdm2)
                    if len(obs)!=26 or not np.isfinite(obs).all():raise RuntimeError('Illegal policy observation')
                    redobs=m.simulator_observation(env.fdm2,env.fdm1)
                    if len(redobs)!=26 or not np.isfinite(redobs).all():raise RuntimeError('Illegal red policy observation')
                    writer.writerow({'episode':ep,'tick':tick,'act_calls':counts['act'],'blue_send_calls':counts['blue'],'red_send_calls':counts['red'],'judge_calls':tick,'attack_ticks':env.judge.attack[0],'distance_m':geo['distance_m'],'blue_angle_deg':geo['blue_angle_deg'],'blue_g':bg,'actual_command':json.dumps(state['actual']),'command_from_act':json.dumps(state['cmd']),'observation_sha256':jsha(obs.tolist()),'red_angle_deg':geo['red_angle_deg'],'red_g':rg,
                        'blue_agl_m':float(env.fdm1.fdm['position/h-agl-ft'])*.3048,'red_agl_m':float(env.fdm2.fdm['position/h-agl-ft'])*.3048,
                        'blue_hsl_m':float(env.fdm1.fdm['position/h-sl-ft'])*.3048,'red_hsl_m':float(env.fdm2.fdm['position/h-sl-ft'])*.3048,
                        'red_attack_ticks':env.judge.attack[1],'blue_over_g_ticks':env.judge.over_g[0],'red_over_g_ticks':env.judge.over_g[1],
                        'position_blue':env.judge.position[0],'position_red':env.judge.position[1],
                        'advantage_blue':env.judge.advantages()[0],'advantage_red':env.judge.advantages()[1],
                        'event':env.judge.core.event,'winner':env.judge.core.winner})
                env.fdm1.sendAction=blue;env.fdm2.sendAction=red;env.judge.update=judge
                decisions=0;reward=0.
                for _ in range((case['max_steps']+19)//20):
                    if stop(out) or time.monotonic()>=launch['deadline_monotonic']:raise RuntimeError('STOP/deadline during physics')
                    before=env.tactical_obs_only()
                    action=actor_policy.predict(before,deterministic=True)[0]
                    if action.shape!=(3,) or not np.isfinite(action).all() or np.max(np.abs(action))>1:raise RuntimeError('Invalid tactical action')
                    result['tactical_decisions'].append({'start_tick':env.current_step,'observation':before.tolist(),'action':action.tolist()})
                    tactical_observation,rew,terminated,truncated,info=env.step(action);decisions+=1;reward+=rew;write_frame_with_offset(acmi,env,ep*case['max_steps'])
                    if info['attack_ticks']!=env.blue_frames:raise RuntimeError('Tactical counter differs from parent judge')
                    if tactical_observation.shape!=(13,) or not np.isfinite(tactical_observation).all():raise RuntimeError('Incorrect13value legal tactical observation')
                    if terminated or truncated:break
                if env.current_step!=case['max_steps'] and env.judge.core.event=='ongoing':raise RuntimeError('Incomplete diagnostic cutoff')
                if case['expect_nonzero'] and env.blue_frames<=0:raise RuntimeError('Rear fixture did not exercise nonzero attack counter')
                if state['fallbacks']:raise RuntimeError('Opponent fallback occurred')
                result['episodes'].append({'episode':ep,'initial_sha256':jsha(initial),'initial_heading_error_deg':actual_heading_error,'initial_legal_blue':initial,'initial_legal_red':initial_red,'final_sha256':jsha(m.simulator_observation(env.fdm1,env.fdm2).tolist()),'final_legal_blue':m.simulator_observation(env.fdm1,env.fdm2).tolist(),'final_legal_red':m.simulator_observation(env.fdm2,env.fdm1).tolist(),'ticks':env.current_step,'decisions':decisions,'counts':counts.copy(),'attack_ticks':int(env.blue_frames),'tactical_attack_ticks':int(info['attack_ticks']),'reward':reward,'max_command_error':state['max_command_error'],'fallbacks':state['fallbacks'],'opponent_actual':env.p2_type,'actual_spawn_distance_ft':env.spawn_distance_ft,'rules_profile':vars(env.judge.profile),'judge_event':env.judge.core.event,'judge_winner':env.judge.core.winner,'reported_won':bool(info.get('won',False)),'terminated':terminated,'truncated':truncated,'tactical_observation_shape':list(tactical_observation.shape),'true_round_complete':env.judge.core.event!='ongoing'})
                stream.flush();acmi.flush()
        if env.judge.core.event=='ongoing':raise RuntimeError('Incomplete full game')
        source_gate(spec['source_freeze'])
        result.update(status='interface_pass',artifact_sha256={n:sha(folder/n) for n in ('telemetry.csv','duel.acmi')})
    except BaseException as error:
        traceback.print_exc();result.update(status='failed',error=repr(error))
    finally:
        if env is not None:
            try:env.close()
            except BaseException as error:result.update(status='failed',close_error=repr(error))
        result['wall_seconds']=time.monotonic()-began;write(folder/'result.json',result)
    return 0 if result['status']=='interface_pass' else 2

def supervisor(out):
    out=Path(out);began=time.monotonic()
    end=time.monotonic()+10
    while not (out/'launch.json').exists() and time.monotonic()<end:time.sleep(.1)
    launch=read(out/'launch.json')
    if identity()!=launch['supervisor'] or psutil.Process().ppid()!=launch['launcher']['pid'] or not matching(launch['launcher']):raise RuntimeError('Supervisor ownership mismatch')
    execution_mode_gate(launch)
    await_guard(out,launch)
    report={'status':'running','cases':[],'score_eligible':False,'official_validation':False,'plan_sha256':jsha(launch['cases'])}
    code=0
    for case in launch['cases']:
        if stop(out) or time.monotonic()>=launch['deadline_monotonic']:code=2;break
        resource_gate();source_gate(launch['source_freeze'])
        folder=out/'cases'/case['case_id'];folder.mkdir(parents=True)
        write(folder/'input.json',{'out':str(out),'case':case,'source_freeze':launch['source_freeze'],'tools_sha256':launch['tools_sha256']})
        with (folder/'worker.log').open('w',encoding='utf8') as log:
            worker_start_monotonic=time.monotonic();worker_start_epoch=time.time()
            p=subprocess.Popen([sys.executable,'-B','-X','utf8',str(HERE/'run_smoke.py'),'--worker',str(folder/'input.json')],stdout=log,stderr=subprocess.STDOUT,creationflags=NO_WINDOW)
            ident=identity(p.pid);worker_deadline=min(launch['deadline_monotonic'],worker_start_monotonic+90)
            write(out/'active_worker.json',{'identity':ident,'deadline_epoch':worker_start_epoch+90,'deadline_monotonic':worker_deadline,'case_id':case['case_id']})
            try:wcode=p.wait(timeout=max(0,worker_deadline-time.monotonic())+3)
            except subprocess.TimeoutExpired:
                # Independent guard owns termination; never restart timed-out cases.
                write(out/'abort.json',{'reason':'worker_guard_did_not_finish'});wcode=p.wait(timeout=5)
            receipt={'identity':ident,'actual_worker_exit_code':wcode,'case_id':case['case_id'],'input_sha256':sha(folder/'input.json'),'result_sha256':sha(folder/'result.json') if (folder/'result.json').exists() else None}
            write(folder/'worker_exit.json',receipt)
        report['cases'].append(receipt);write(out/'report.json',report)
        if wcode!=0:code=2;break
    report.update(status='completed' if len(report['cases'])==len(launch['cases']) and code==0 else 'partial',wall_seconds=time.monotonic()-began)
    write(out/'report.json',report)
    return code if len(report['cases'])==len(launch['cases']) else 2

def guarded_worker(input_path):
    # Ownership/guard failures occur before the FDM try/finally. Preserve them too.
    try:return worker(input_path)
    except BaseException as error:
        traceback.print_exc()
        spec=read(input_path);folder=Path(input_path).parent
        write(folder/'result.json',{'case':spec['case'],'worker_identity':identity(),'status':'failed','steps':0,'score_eligible':False,'official_validation':False,'failure_phase':'pre_fdm_gate','error':repr(error)})
        return 2

if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--out',type=Path);g.add_argument('--worker',type=Path);a=p.parse_args()
    raise SystemExit(guarded_worker(a.worker) if a.worker else supervisor(a.out))
