"""One reserved, independently bounded FDM timing diagnostic. Never trains."""
from pathlib import Path
import os, sys, json, time, hashlib, subprocess, uuid, traceback, datetime, csv
import psutil

ROOT = Path(r'E:\ai_pilot\campaign_2026')
HERE = Path(__file__).resolve().parent
ADAPTER = ROOT/'experiments/opponent_pool/frozen_sac_opponent_v2'
MODELS = ('sac5000', 'transfer10000')
SEEDS = (2026310000, 2026310001)
TICKS = 300
SECONDS = 240

def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(v): return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
def write(p, v):
    p=Path(p); tmp=p.with_name(p.name+'.tmp_'+uuid.uuid4().hex)
    try:
        tmp.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
        for attempt in range(7):
            try: os.replace(tmp,p); return
            except PermissionError:
                if attempt==6: raise
                time.sleep(.025)
    finally:
        if tmp.exists(): tmp.unlink()
def identity(pid=None):
    p=psutil.Process(pid or os.getpid())
    return dict(pid=p.pid,create=p.create_time(),cmd=p.cmdline(),exe=p.exe(),parent=p.ppid())
def live(i):
    try: return identity(i['pid'])==i
    except psutil.NoSuchProcess: return False
def stopped(out):
    return any((p/'STOP').exists() for p in (ROOT,HERE,out,ADAPTER,ROOT/'experiments/opponent_pool'))
def dependencies():
    sys.path.insert(0,str(ROOT/'experiments/opponent_pool'))
    import benchmark_pool as b
    source=b.capture_sources(ROOT/'repair_v1')
    c=read(ROOT/'experiments/opponent_pool/m4_grid_eval_v1/CONTRACT.json')
    paths=[HERE/'probe.py',HERE/'verify.py',HERE/'USAGE_OBSERVATION.json',ADAPTER/'CONTRACT.json']
    paths += [ADAPTER/n for n in read(ADAPTER/'CONTRACT.json')['executor_sha256']]
    paths += [ROOT/n for n in c['m4_sources_sha256']]
    paths += [Path(v['model_path']) for v in read(ADAPTER/'CONTRACT.json')['models'].values()]
    return dict(physics_sources=source,files={str(p):sha(p) for p in paths})
def gate(spec):
    if dependencies()!=spec['sources']: raise RuntimeError('Frozen source/XML/model changed')
def expired(spec): return time.time()>=spec['deadline_epoch'] or time.monotonic()>=spec['deadline_monotonic']
def resources():
    v=dict(ram_bytes=psutil.virtual_memory().available,disk_bytes=psutil.disk_usage(str(ROOT)).free,cpu_percent=psutil.cpu_percent(.1),GPU_used=False)
    if v['ram_bytes']<2*2**30 or v['disk_bytes']<10*2**30 or v['cpu_percent']>=95: raise RuntimeError('Resource gate')
    return v
def inventory():
    found=[]
    for p in psutil.process_iter(['name']):
        if p.pid==os.getpid():continue
        name=(p.info['name'] or '').lower()
        if name=='jsb_host_gui_publish.exe': found.append(identity(p.pid));continue
        if name not in ('python.exe','pythonw.exe'):continue
        try: cmd=p.cmdline()
        except psutil.NoSuchProcess:continue
        # AccessDenied propagates: unknown is not idle.
        if any('e:/ai_pilot/' in x.replace('\\','/').lower() and x.lower().endswith('.py') for x in cmd):found.append(identity(p.pid))
    return found

def worker(out):
    spec=read(out/'CONTRACT.json')
    if os.getppid()!=spec['watchdog']['pid'] or not live(spec['watchdog']):raise RuntimeError('Worker parent identity')
    if expired(spec) or stopped(out):raise RuntimeError('STOP/deadline')
    gate(spec)
    sys.path.insert(0,str(ROOT/'experiments/m4_tactical_v4'))
    import m4_tactical_rl as m
    import numpy as np
    if Path(m.__file__).resolve()!=ROOT/'experiments/m4_tactical_v4/m4_tactical_rl.py':raise RuntimeError('Mixed tactical module')
    m.torch.set_num_threads(1)
    sys.path.insert(0,str(ADAPTER))
    from factory import build_frozen_opponent, source_gate
    from adapter import legal_command
    source_gate()
    summary=dict(status='running',scope='short FDM interface, not combat strength or training',episodes=[],new_FDM_ticks=0,training_started=False,official_validation=False,deployment_allowed=False)
    write(out/'state.json',dict(status='worker_running',worker=identity()))
    for model_id,seed in zip(MODELS,SEEDS):
        env=m.TacticalDuel(opponent='rule',distance_ft=6000,max_steps=TICKS)
        try:
            for episode in range(2):
                if expired(spec) or stopped(out):raise RuntimeError('STOP/deadline before reset')
                env.reset(seed=seed)
                initial=[m.simulator_observation(env.fdm1,env.fdm2).tolist(),m.simulator_observation(env.fdm2,env.fdm1).tolist()]
                red=build_frozen_opponent(model_id,env.settings)
                if red.controller is env.packet_controller:raise RuntimeError('Shared controller')
                env.p2_type='frozen_sac_'+model_id
                counts=dict(blue_act=0,blue_send=0,red_send=0,blue_physics=0,red_physics=0,judge=0)
                state=dict(blue_cmd=None,red_cmd=None,red_packet=None,command_latency_ms=[],expected_red=0,peak_g=[0.,0.],min_agl=[float('inf'),float('inf')])
                prefix=f'{model_id}_repeat{episode}'
                rows=[]
                old_act=env.packet_controller.act
                def blue_act(*args,**kwargs):
                    cmd,guard=old_act(*args,**kwargs);counts['blue_act']+=1;state['blue_cmd']=legal_command(cmd).tolist();return cmd,guard
                env.packet_controller.act=blue_act
                def red_action():
                    n=counts['red_physics']
                    if env.current_step!=n or counts['blue_physics']!=n:raise RuntimeError('Pre-step completed-state mismatch')
                    packet=m.simulator_observation(env.fdm2,env.fdm1)
                    t=time.perf_counter();cmd=red.command(packet,completed_tick=n);state['command_latency_ms'].append((time.perf_counter()-t)*1000)
                    before=red.status();np.testing.assert_array_equal(red.command(packet.copy(),completed_tick=n),cmd)
                    if red.status()!=before or red.attack_ticks!=env.judge.attack[1]:raise RuntimeError('Duplicate/cache or completed red counter')
                    state['red_packet']=packet.tolist();state['red_cmd']=cmd.tolist()
                    env.p2_mode='frozen_sac_'+model_id;env.p2_guard=bool(before['guard_active']);return cmd
                env._red_action=red_action
                old_blue_send=env.fdm1.sendAction;old_red_send=env.fdm2.sendAction
                def blue_send(cmd):
                    counts['blue_send']+=1;np.testing.assert_array_equal(legal_command(cmd),state['blue_cmd']);return old_blue_send(cmd)
                def red_send(cmd):
                    counts['red_send']+=1;np.testing.assert_array_equal(legal_command(cmd),state['red_cmd']);return old_red_send(cmd)
                env.fdm1.sendAction=blue_send;env.fdm2.sendAction=red_send
                for plane,key in ((env.fdm1,'blue_physics'),(env.fdm2,'red_physics')):
                    original=plane.step
                    def physics(original=original,plane=plane,key=key):
                        before=plane.fdm.get_sim_time();value=original();after=plane.fdm.get_sim_time()
                        if abs((after-before)-1/60)>1e-9:raise RuntimeError('Physical step was not one 60Hz tick')
                        counts[key]+=1;return value
                    plane.step=physics
                old_judge=env.judge.update
                def judge(geo,bg,rg):
                    old_judge(geo,bg,rg);counts['judge']+=1;n=counts['judge']
                    if env.current_step!=n or any(x!=n for x in counts.values()):raise RuntimeError('Not exactly one act/send/physics/judge per tick')
                    packet=m.simulator_observation(env.fdm2,env.fdm1)
                    state['expected_red']+=int(500*.3048<=geo['distance_m']<=3000*.3048 and geo['red_angle_deg']<=1.)
                    if env.judge.attack[1]!=state['expected_red']:raise RuntimeError('Post-step judge red window mismatch')
                    for k,plane in enumerate((env.fdm1,env.fdm2)):
                        state['peak_g'][k]=max(state['peak_g'][k],abs((bg,rg)[k]))
                        state['min_agl'][k]=min(state['min_agl'][k],plane.fdm['position/h-agl-ft']*.3048)
                    rows.append(dict(tick=n,completed_command_tick=red.completed_tick,red_packet_pre=state['red_packet'],red_packet_post=packet.tolist(),blue_command=state['blue_cmd'],red_command=state['red_cmd'],counts=counts.copy(),adapter_status=red.status(),judge_red_attack=env.judge.attack[1],red_angle=geo['red_angle_deg'],distance_m=geo['distance_m'],blue_g=bg,red_g=rg,sim_times=[env.fdm1.fdm.get_sim_time(),env.fdm2.fdm.get_sim_time()]))
                env.judge.update=judge
                acmi=out/(prefix+'.acmi')
                with acmi.open('w',encoding='utf8') as stream:
                    stream.write('FileType=text/acmi/tacview\nFileVersion=2.2\n0,ReferenceTime=2026-10-17T00:00:00Z\n1,Type=Air+FixedWing,Name=Blue\n2,Type=Air+FixedWing,Name=Frozen SAC Red\n')
                    env.write_frame(stream)
                    for _ in range(TICKS//20):
                        if expired(spec) or stopped(out):raise RuntimeError('STOP/deadline during FDM')
                        _,_,term,trunc,info=env.step(np.zeros(3,dtype=np.float32));env.write_frame(stream)
                        if term or trunc:break
                if env.current_step!=TICKS or len(rows)!=TICKS:raise RuntimeError('Incomplete short diagnostic')
                final_packet=m.simulator_observation(env.fdm2,env.fdm1)
                pending=red.command(final_packet,completed_tick=TICKS)
                if red.attack_ticks!=env.judge.attack[1] or red.act_calls!=TICKS+1 or red.predict_calls!=16:raise RuntimeError('Final completed-state accounting')
                # The 301st command only closes the final packet/counter contract; never sent.
                telemetry=out/(prefix+'.jsonl')
                telemetry.write_text(''.join(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n' for row in rows),encoding='utf8')
                replay=build_frozen_opponent(model_id,env.settings)
                for row in rows:np.testing.assert_array_equal(replay.command(row['red_packet_pre'],completed_tick=row['completed_command_tick']),row['red_command'])
                np.testing.assert_array_equal(replay.command(final_packet,completed_tick=TICKS),pending)
                record=dict(model=model_id,seed=seed,repeat=episode,initial=initial,initial_sha256=digest(initial),final_sha256=digest([m.simulator_observation(env.fdm1,env.fdm2).tolist(),final_packet.tolist()]),ticks=TICKS,counts=counts,final_adapter=red.status(),pending_commands_not_sent=1,attack_ticks=list(env.judge.attack),over9G=list(env.judge.over_g),peak_g=state['peak_g'],min_agl_m=state['min_agl'],max_full_command_ms=max(state['command_latency_ms']),max_warm_command_ms=max(state['command_latency_ms'][1:]),telemetry=str(telemetry),telemetry_sha256=sha(telemetry),acmi=str(acmi),acmi_sha256=sha(acmi),saved_packet_actor_replay_exact=True)
                summary['episodes'].append(record);summary['new_FDM_ticks']+=TICKS
                write(out/'RESULT.json',summary);write(out/'state.json',dict(status='worker_running',model=model_id,repeat=episode,completed_ticks=summary['new_FDM_ticks']))
        finally:env.close()
    for model in MODELS:
        a,b=[e for e in summary['episodes'] if e['model']==model]
        for key in ('initial_sha256','final_sha256','attack_ticks','counts','final_adapter','telemetry_sha256'):
            if a[key]!=b[key]:raise RuntimeError('Same-seed fresh-reset reproduction: '+key)
    gate(spec);source_gate();summary.update(status='verified_short_FDM_timing',source_unchanged=True,strength_verified=False)
    write(out/'RESULT.json',summary);return 0

def main():
    if len(sys.argv)==3 and sys.argv[1]=='--worker':return worker(Path(sys.argv[2]))
    if len(sys.argv)!=2 or sys.argv[1] not in ('--launch','--check-only'):raise RuntimeError('Explicit --launch or --check-only required')
    sys.path.insert(0,str(ROOT));from runner import JobLock
    with JobLock(ROOT/'launch.lock'):
        busy=inventory()
        if busy:raise RuntimeError('Existing or unknown work: '+repr(busy))
        r=resources()
        if stopped(HERE):raise RuntimeError('STOP')
        registry=read(ROOT/'seed_registry.json');seen={int(s) for s in registry.get('observed_seeds',{})}
        for trial in registry.get('trials',{}).values():seen.update(trial['seeds'])
        seen.update(registry.get('reserved_holdout_seeds',[]))
        if seen.intersection(SEEDS):raise RuntimeError('Seed already used/reserved')
        sources=dependencies()
        if sys.argv[1]=='--check-only':
            print(json.dumps(dict(check_only=True,resources=r,busy=busy,seeds=list(SEEDS),seed_collisions=[],frozen_files=len(sources['files']),physics_sources=len(sources['physics_sources']),hard_deadline_seconds=SECONDS,new_FDM_ticks=0)))
            return 0
        out=HERE/('run_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_')+uuid.uuid4().hex[:6]);out.mkdir()
        started=time.time();mono=time.monotonic()
        spec=dict(hypothesis='The frozen SAC red bridge consumes state n before physical n+1, emits once, and counts completed post-step windows once',single_change='Replace red rule action with existing immutable packet-only frozen SAC adapter; blue zero tactical and physics/judge unchanged',sources=sources,watchdog=identity(),deadline_epoch=started+SECONDS,deadline_monotonic=mono+SECONDS,resources=r,models=list(MODELS),seeds=list(SEEDS),ticks_per_repeat=TICKS,repeats=2,training_started=False,seed_role='new development interface test, not holdout',usage_observation=read(HERE/'USAGE_OBSERVATION.json'))
        write(out/'CONTRACT.json',spec)
        day=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat();lp=ROOT/'compute_budgets'/f'{day}.json';ledger=read(lp)
        ledger['items'].append(dict(id=out.name,hours=SECONDS/3600,status='reserved_fdm_interface',output=str(out),warning_only=True));ledger['reserved_hours']=sum(i['hours'] for i in ledger['items']);write(lp,ledger)
        registry.setdefault('trials',{})[out.name]=dict(seeds=list(SEEDS),status='attempted',seed_role='development_fdm_interface_not_holdout',output=str(out));write(ROOT/'seed_registry.json',registry)
        child=None;code=None;reason=None;tracked={};cleanup=[]
        try:
            with (out/'worker.log').open('w',encoding='utf8') as log:
                p=subprocess.Popen([sys.executable,'-B','-X','utf8',str(Path(__file__)),'--worker',str(out)],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                child=identity(p.pid);write(out/'worker_identity.json',child)
                while p.poll() is None:
                    root=psutil.Process(child['pid'])
                    for descendant in root.children(recursive=True):
                        try:
                            ident=identity(descendant.pid)
                            chain=[];node=descendant
                            while node.pid!=root.pid:
                                chain.append(identity(node.pid));node=node.parent()
                                if node is None:raise RuntimeError('Owned descendant chain lost')
                            if not live(child):raise RuntimeError('Worker changed while observing descendant')
                            tracked[(ident['pid'],ident['create'])]=dict(identity=ident,chain_to_worker=chain,worker_identity=child)
                        except psutil.NoSuchProcess:continue
                    if expired(spec) or stopped(out):
                        reason='STOP_or_original_deadline'
                        if not live(child):raise RuntimeError('Refuse to stop unknown identity')
                        for item in sorted(tracked.values(),key=lambda x:len(x['chain_to_worker']),reverse=True):
                            ident=item['identity']
                            if live(ident):
                                target=psutil.Process(ident['pid']);target.terminate();cleanup.append(item)
                        p.terminate();break
                    time.sleep(.1)
                try:code=p.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    if not live(child):raise RuntimeError('Unknown worker identity before forced deadline cleanup')
                    p.kill();code=p.wait(timeout=3)
        finally:
            receipt=dict(actual_worker_exit=code,watchdog_identity=spec['watchdog'],worker_identity=child,worker_identity_absent=(not live(child)) if child else None,reason=reason,wall_seconds=time.monotonic()-mono,source_unchanged=(dependencies()==sources),observed_owned_descendants=list(tracked.values()),deadline_cleanup=cleanup)
            write(out/'EXIT_RECEIPT.json',receipt)
            ledger=read(lp)
            for item in ledger['items']:
                if item['id']==out.name:item.update(status='completed' if code==0 else 'failed',actual_worker_exit=code,actual_wall_seconds=receipt['wall_seconds'])
            write(lp,ledger);print(json.dumps(dict(out=str(out),**receipt),ensure_ascii=False),flush=True)
        return 0 if code==0 and reason is None and receipt['source_unchanged'] else 2

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception:traceback.print_exc();raise SystemExit(1)
