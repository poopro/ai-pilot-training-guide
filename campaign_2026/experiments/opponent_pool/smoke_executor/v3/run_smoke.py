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
    if Path(input_path).resolve()!=out/'cases'/case['case_id']/'input.json':raise RuntimeError('Worker path outside reservation')
    if psutil.Process().ppid()!=launch['supervisor']['pid'] or not matching(launch['supervisor']):raise RuntimeError('Worker ownership mismatch')
    guard=read(out/'guard.json')
    if guard['status']!='armed' or not matching(guard['guard']):raise RuntimeError('Worker lacks active guard')
    if spec['case'] not in launch['cases'] or spec['source_freeze']!=launch['source_freeze'] or spec['tools_sha256']!=tools():raise RuntimeError('Unreserved case/source/tools')
    registry=read(ROOT/'seed_registry.json');trial=registry['trials'][launch['trial_id']]
    if case['seed'] not in trial['seeds'] or trial['output']!=str(out):raise RuntimeError('Seed reservation missing')
    began=time.monotonic();env=None
    result={'case':case,'status':'initializing','steps':0,'score_eligible':False,'official_validation':False,'worker_identity':identity()}
    try:
        source_gate(spec['source_freeze']);resource_gate()
        runtime=bench.load_runtime(ROOT/'repair_v1');np=runtime.np
        red=runtime.artifacts.load_policy(runtime.env.DEFAULT_BUNDLE,device='cpu') if case['opponent_id']=='rl' else None
        env=runtime.env.RepairDuel(p2=case['opponent_id'] if case['opponent_id'] in ('rule','rl') else 'rule',policy=red,attack_angle=1.,max_steps=300,distance_ft=case['distance_ft'],controller='repair',stage='official')
        env.reset(seed=case['seed']);_,initial=bench.reset_initial_side(env,case['side'],runtime)
        import opponents
        if Path(opponents.__file__).resolve()!=POOL/'opponents.py':raise RuntimeError('Incorrect adapter module')
        red_rng=np.random.default_rng();red_rng.bit_generator.state=copy.deepcopy(env.np_random.bit_generator.state)
        blue_rng=np.random.default_rng(case['seed'] ^ 0x5A5A5A5A)
        env.np_random=red_rng
        opponents.configure_red(env,case['opponent_id'])
        if hasattr(env.red_fighter,'rng'):env.red_fighter.rng=red_rng
        red_controller=env.red_fighter.controller if case['opponent_id']!='rl' else env.red_packet_controller
        if env.packet_controller is red_controller:raise RuntimeError('Shared blue/red controller')
        # A recursive audit checks nested integrators/previous-state storage, not just outer identity.
        def mutable_ids(obj,seen=None):
            seen=set() if seen is None else seen
            if id(obj) in seen or isinstance(obj,(str,bytes,int,float,bool,type(None),type)):return set()
            seen.add(id(obj));result_ids=set()
            if isinstance(obj,(dict,list,set,np.ndarray)) or hasattr(obj,'__dict__'):result_ids.add(id(obj))
            if hasattr(obj,'__dict__'):
                for key,value in vars(obj).items():
                    if key not in ('settings','config'):result_ids.update(mutable_ids(value,seen))
            elif isinstance(obj,dict):
                for value in obj.values():result_ids.update(mutable_ids(value,seen))
            elif isinstance(obj,(list,tuple,set)):
                for value in obj:result_ids.update(mutable_ids(value,seen))
            return result_ids
        if mutable_ids(env.packet_controller)&mutable_ids(red_controller):raise RuntimeError('Shared nested controller state')
        import jsbsim
        data_root=Path(jsbsim.get_default_root_dir()).resolve()
        for aircraft in (env.fdm1,env.fdm2):
            if Path(aircraft.fdm.get_root_dir()).resolve()!=data_root or Path(aircraft.fdm.get_full_aircraft_path()).resolve()!=data_root/'aircraft'/'f16':raise RuntimeError('FDM XML path differs')
        commands={};counts={'blue':0,'red':0}
        for side,aircraft in (('blue',env.fdm1),('red',env.fdm2)):
            original=aircraft.sendAction
            def capture(command,side=side,original=original):
                commands[side]=legal_command(command);counts[side]+=1
                return original(command)
            aircraft.sendAction=capture
        result.update(initial=initial,initial_sha256=jsha(initial),red_rng_initial_sha256=jsha(red_rng.bit_generator.state),blue_rng_initial_sha256=jsha(blue_rng.bit_generator.state),independent_rng=blue_rng is not red_rng,independent_controller_state=True,policy_observation='OWN20+ENEMY6',source_freeze=spec['source_freeze'],tools_sha256=spec['tools_sha256'],status='running')
        write(folder/'result.json',result)
        fields=['tick','simulation_seconds','blue_observation_sha256','red_observation_sha256','blue_command','red_command','distance_m','blue_altitude_m','red_altitude_m','blue_g','red_g']
        reason='max_steps';terminated=False
        with (folder/'telemetry.csv').open('w',encoding='utf8',newline='') as telemetry,(folder/'duel.acmi').open('w',encoding='utf8') as acmi:
            writer=csv.DictWriter(telemetry,fieldnames=fields);writer.writeheader()
            acmi.write('FileType=text/acmi/tacview\nFileVersion=2.2\n0,ReferenceTime='+datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')+'\n1,Type=Air+FixedWing,Name=F16,Color=Blue\n2,Type=Air+FixedWing,Name=F16,Color=Red\n');env.write_frame(acmi)
            for tick in range(1,301):
                if stop(out):reason='STOP';break
                if time.monotonic()-began>=30:reason='case_deadline';break
                before=[]
                for own,enemy in ((env.fdm1,env.fdm2),(env.fdm2,env.fdm1)):
                    packet=runtime.simulator_observation(own,enemy)
                    if np.asarray(packet).shape!=(26,) or not np.isfinite(packet).all():raise RuntimeError('Nonfinite/illegal policy observation')
                    before.append(jsha(np.asarray(packet,dtype=float).tolist()))
                env.step(np.zeros(4,dtype=np.float32));result['steps']=tick
                if any(counts[s]!=tick for s in counts):raise RuntimeError('Command count differs from physics tick')
                packets=[runtime.simulator_observation(env.fdm1,env.fdm2),runtime.simulator_observation(env.fdm2,env.fdm1)]
                if not all(np.isfinite(p).all() for p in packets):raise RuntimeError('Nonfinite state after physics')
                row={'tick':tick,'simulation_seconds':tick/60.,'blue_observation_sha256':before[0],'red_observation_sha256':before[1],'blue_command':json.dumps(commands['blue']),'red_command':json.dumps(commands['red']),'distance_m':env.geometry['distance_m'],'blue_altitude_m':packets[0][2]*.3048,'red_altitude_m':packets[1][2]*.3048,'blue_g':packets[0][14],'red_g':packets[1][14]}
                writer.writerow(row);env.write_frame(acmi)
                if tick%30==0:telemetry.flush();acmi.flush();write(folder/'heartbeat.json',{'tick':tick,'identity':identity()})
                if env.outcome!='ongoing':reason='legal_termination';terminated=True;break
        source_gate(spec['source_freeze'])
        result.update(status='interface_pass' if reason in ('max_steps','legal_termination') else 'partial',stop_reason=reason,legal_termination=terminated,command_counts=counts,artifact_sha256={n:sha(folder/n) for n in ('telemetry.csv','duel.acmi')})
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
            ident=identity(p.pid);worker_deadline=min(launch['deadline_monotonic'],worker_start_monotonic+30)
            write(out/'active_worker.json',{'identity':ident,'deadline_epoch':worker_start_epoch+30,'deadline_monotonic':worker_deadline,'case_id':case['case_id']})
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
