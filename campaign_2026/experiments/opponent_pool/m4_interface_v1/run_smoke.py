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
    result={'status':'running','case':case,'episodes':[],'score_eligible':False,'official_validation':False,'deployment_allowed':False}
    try:
        sys.path.insert(0,str(ROOT/'experiments'/'m4_tactical_v2'))
        import m4_tactical_rl as m
        import numpy as np
        m.torch.set_num_threads(1)
        frozen=m.load_policy(m.DEFAULT_BUNDLE) if case['opponent_id']=='rl' else None
        env=m.TacticalDuel(opponent=case['opponent_id'],policy=frozen,distance_ft=6000,max_steps=300)
        fields=['episode','tick','act_calls','blue_send_calls','red_send_calls','judge_calls','attack_ticks','distance_m','blue_angle_deg','blue_g','actual_command','command_from_act','observation_sha256']
        with (folder/'telemetry.csv').open('w',newline='',encoding='utf8') as stream,(folder/'duel.acmi').open('w',encoding='utf8') as acmi:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
            acmi.write('FileType=text/acmi/tacview\nFileVersion=2.2\n0,ReferenceTime=2026-10-15T00:00:00Z\n1,Type=Air+FixedWing,Name=Blue\n2,Type=Air+FixedWing,Name=Red\n')
            for ep in range(2):
                if stop(out) or time.monotonic()>=launch['deadline_monotonic']:raise RuntimeError('STOP/deadline before reset')
                env.reset(seed=case['seed'])
                initial=m.simulator_observation(env.fdm1,env.fdm2).tolist()
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
                    writer.writerow({'episode':ep,'tick':tick,'act_calls':counts['act'],'blue_send_calls':counts['blue'],'red_send_calls':counts['red'],'judge_calls':tick,'attack_ticks':env.judge.attack[0],'distance_m':geo['distance_m'],'blue_angle_deg':geo['blue_angle_deg'],'blue_g':bg,'actual_command':json.dumps(state['actual']),'command_from_act':json.dumps(state['cmd']),'observation_sha256':jsha(obs.tolist())})
                env.fdm1.sendAction=blue;env.fdm2.sendAction=red;env.judge.update=judge
                decisions=0;reward=0.
                for _ in range(15):
                    if stop(out) or time.monotonic()>=launch['deadline_monotonic']:raise RuntimeError('STOP/deadline during physics')
                    _,rew,terminated,truncated,info=env.step(np.zeros(3,dtype=np.float32));decisions+=1;reward+=rew;env.write_frame(acmi)
                    if info['attack_ticks']!=env.blue_frames:raise RuntimeError('Tactical counter differs from parent judge')
                    if terminated or truncated:break
                if env.current_step!=300:raise RuntimeError('Short diagnostic ended early; not full300tick interface evidence')
                if state['fallbacks']:raise RuntimeError('Opponent fallback occurred')
                result['episodes'].append({'episode':ep,'initial_sha256':jsha(initial),'final_sha256':jsha(m.simulator_observation(env.fdm1,env.fdm2).tolist()),'ticks':env.current_step,'decisions':decisions,'counts':counts.copy(),'attack_ticks':int(env.blue_frames),'tactical_attack_ticks':int(info['attack_ticks']),'reward':reward,'max_command_error':state['max_command_error'],'fallbacks':state['fallbacks'],'opponent_actual':env.p2_type})
                stream.flush();acmi.flush()
        first,second=result['episodes']
        for key in ['initial_sha256','final_sha256','ticks','decisions','counts','attack_ticks','tactical_attack_ticks','reward','opponent_actual']:
            if first[key]!=second[key]:raise RuntimeError('Same-seed reset reproduction failed: '+key)
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
            ident=identity(p.pid);worker_deadline=min(launch['deadline_monotonic'],worker_start_monotonic+45)
            write(out/'active_worker.json',{'identity':ident,'deadline_epoch':worker_start_epoch+45,'deadline_monotonic':worker_deadline,'case_id':case['case_id']})
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
