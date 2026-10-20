"""Four isolated known-fixture cases, reusing the mature smoke guardian/worker.

Only in-process helper bindings change; frozen source/XML/deployment stay intact.
No FDM until root explicitly uses start. No sweep, fresh-seed or holdout claim.
"""
from __future__ import annotations
import argparse,ast,copy,csv,importlib.util,json,math,os,subprocess,sys,time,uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import psutil

EXP=Path(__file__).resolve().parent;ROOT=EXP.parents[1]
SMOKE=ROOT/'experiments/g_latch_smoke'
KNOWN=ROOT/'experiments/g_latch_development/run_20261014_150515_b846'
PAIRS=('r000_rule_3000_mirrored_2026101400','r000_rl_9000_mirrored_2026101412')
ACTORS=('bank80_latch','bank75_latch');MANIFEST=EXP/'MANIFEST.json'
spec=importlib.util.spec_from_file_location('near75_mature_smoke',SMOKE/'launch_smoke.py')
engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
base=engine.base;bench=base.bench;PYTHON=base.PYTHON;REPAIR=base.REPAIR;COLUMNS=engine.COLUMNS
original_worker=engine.worker
original_runtime=bench.load_runtime;original_reset=bench.reset_initial_side
REAL_TIME=time;REAL_SUBPROCESS=subprocess
PROCESS_CACHE={};deadline_monotonic=None

def atomic_json(path,value):
    """Bounded WinError5/32 retry; never restarts the original job allowance."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp_'+uuid.uuid4().hex)
    try:
        temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        for attempt in range(6):
            try:os.replace(temporary,path);return
            except PermissionError as error:
                if getattr(error,'winerror',None) not in (None,5,32) or attempt==5:raise
                pause=min(.2,.025*2**attempt)
                if deadline_monotonic is not None and REAL_TIME.monotonic()+pause>=deadline_monotonic:raise
                REAL_TIME.sleep(pause)
    finally:
        if temporary.exists():
            try:temporary.unlink()
            except PermissionError:pass

def read(path):return base.read(path)
def ident(pid):
    try:
        p=psutil.Process(pid)
        return dict(pid=p.pid,create_time=p.create_time(),cmdline=p.cmdline(),parent_pid=p.ppid(),identity_observed=True)
    except psutil.NoSuchProcess:
        if pid in PROCESS_CACHE:return dict(PROCESS_CACHE[pid])
        return dict(pid=pid,create_time=None,cmdline=None,parent_pid=None,identity_observed=False,identity_error='NoSuchProcess')

def recorded_popen(command,*args,**kwargs):
    process=REAL_SUBPROCESS.Popen(command,*args,**kwargs)
    fallback=dict(pid=process.pid,create_time=None,cmdline=list(command),parent_pid=os.getpid(),
                  identity_observed=False,identity_error='NoSuchProcess_after_Popen')
    PROCESS_CACHE[process.pid]=fallback
    observed=ident(process.pid);PROCESS_CACHE[process.pid]=observed
    return process

def live(record):
    if not record or record.get('create_time') is None:return None
    try:
        p=psutil.Process(record['pid'])
        return p if abs(p.create_time()-record['create_time'])<.01 and p.cmdline()==record['cmdline'] else None
    except psutil.NoSuchProcess:return None

def occupied(exclude=()):
    for p in psutil.process_iter(['name','cmdline']):
        if p.pid in exclude:continue
        name=(p.info['name'] or '').lower()
        try:
            if 'jsb_host_gui_publish' in name:return ident(p.pid)
            if 'python' not in name:continue
            command=p.cmdline()
            for token in command:
                token=token.replace('\\','/').lower();file=token.rsplit('/',1)[-1]
                if token.startswith('e:/ai_pilot/') and file.endswith('.py') and (
                    file.startswith(('train','benchmark','calibrate','selfplay','self_play','portable')) or
                    (file.startswith(('launch','runner')) and any(a in command for a in ('run','worker','guard','start')))):
                    return ident(p.pid)
        except psutil.NoSuchProcess:continue
        except psutil.AccessDenied:return dict(pid=p.pid,status='unknown_access_denied')
    return None

def known_cases():
    rows=[]
    for pair in PAIRS:
        path=KNOWN/'cases'/(pair+'_candidate');raw=read(path/'result.json')
        if raw['status']!='completed' or not raw['score_eligible'] or raw['steps']!=18000:
            raise RuntimeError('Known fixture incomplete')
        if bench.json_hash(raw['initial'])!=raw['initial_sha256']:raise RuntimeError('Known fixture SHA differs')
        for actor in ACTORS:
            case={**raw['case'],'actor':actor}
            rows.append(dict(case=case,case_id=pair+'_'+actor,pair_key=pair,
                             initial_sha256=raw['initial_sha256'],fixture=str(path/'result.json')))
    return rows

def ast_check():
    def method(path,cls,name):
        node=next(n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n,ast.ClassDef) and n.name==cls)
        return next(n for n in node.body if isinstance(n,ast.FunctionDef) and n.name==name)
    old=method(base.FRESH/'candidate.py','Bank80Controller','act')
    new=method(EXP/'bank75_latch.py','Bank75LatchController','act')
    matches=[n for n in ast.walk(old) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='bank_limit' for t in n.targets)]
    if len(matches)!=1 or not isinstance(matches[0].value,ast.IfExp) or matches[0].value.body.value!=80:
        raise RuntimeError('Frozen bank ceiling structure changed')
    matches[0].value.body.value=75.
    if ast.dump(old,include_attributes=False)!=ast.dump(new,include_attributes=False):raise RuntimeError('More than bank_limit changed')
    if (EXP/'bank80_latch.py').read_bytes()!=(ROOT/'experiments/g_latch_development/safe_candidate.py').read_bytes():
        raise RuntimeError('Baseline latch source changed')
    tree=ast.parse((EXP/'bank75_latch.py').read_text(encoding='utf-8'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
    if [n.name for n in cls.body if isinstance(n,ast.FunctionDef)]!=['act'] or ast.unparse(cls.bases[0])!='GGuardLatchBank80':
        raise RuntimeError('Candidate command/init/safety must be inherited unchanged')
    return dict(act_only_constant_80_to75=True,command_latch_inherited_identically=True,unchanged_safety_thresholds=True)

def sources():
    result=bench.capture_sources(REPAIR)
    for label,path in {'new/launcher':Path(__file__),'new/bank80_latch.py':EXP/'bank80_latch.py',
        'new/bank75_latch.py':EXP/'bank75_latch.py','shared/smoke_guardian_worker':SMOKE/'launch_smoke.py',
        'shared/base_lifecycle':ROOT/'experiments/overload_60hz/launch_diagnostic.py'}.items():result[label]=bench.file_hash(path)
    for pair in PAIRS:
        for name in ('result.json','input.json'):
            result['known_fixture/'+pair+'/'+name]=bench.file_hash(KNOWN/'cases'/(pair+'_candidate')/name)
    return result

def preflight(remaining_percent=None):
    # Retain mature frozen149/XML/red checks. This constructs no simulator.
    ast_check();frozen=read(base.SNAPSHOT/'manifest.json')
    for label,expected in frozen['source_sha256'].items():
        if bench.file_hash(base.SNAPSHOT/label)!=expected:raise RuntimeError('Frozen149 changed: '+label)
    runtime=bench.capture_sources(REPAIR)
    for pair in PAIRS:
        inputs=read(KNOWN/'cases'/(pair+'_candidate')/'input.json')
        if runtime!=inputs['source_sha256']:raise RuntimeError('Known runtime/XML changed')
        if bench.bundle_hashes(bench.DEFAULT_RED_BUNDLE)!=inputs['red_bundle_sha256']:raise RuntimeError('Known frozen red changed')
    locked=read(MANIFEST)
    if locked['source_sha256']!=sources() or locked['planned_cases']!=known_cases():raise RuntimeError('New contract source/fixture drift')
    blocked=occupied((os.getpid(),));warnings=[]
    if (ROOT/'STOP').exists() or (EXP/'STOP').exists():blocked=dict(reason='STOP_exists')
    if psutil.virtual_memory().available<2*2**30 or psutil.disk_usage(str(ROOT)).free<10*2**30:blocked=dict(reason='resource_pressure')
    if remaining_percent is None:warnings.append('Live usage unverified; root must inspect before start')
    elif remaining_percent<35:warnings.append(f'Usage remaining {remaining_percent:g}%; bounded diagnostic only, not expansion')
    day=datetime.now(base.TAIPEI).strftime('%Y-%m-%d');ledger_path=ROOT/'compute_budgets'/(day+'.json')
    ledger=read(ledger_path) if ledger_path.exists() else {}
    reserved=ledger.get('reserved_hours',0.)
    if reserved+1/3>ledger.get('daily_limit_hours',ledger.get('limit_hours',6.)):warnings.append('Daily budget would exceed suggested cap; warning only, original hard deadline retained')
    return dict(check_only=True,simulator_started=False,ready_to_start=blocked is None,blocking_workload=blocked,
                trial_id=locked['trial_id'],research_contract=locked['research_contract'],source_sha256=locked['source_sha256'],
                planned_cases=[r['case'] for r in known_cases()],pairs=2,cases=4,seed_role='known_development_counterfactual',
                telemetry_hz=60,max_steps=18000,case_wall_seconds=360,hard_wall_seconds=1200,
                prior_reserved_hours=reserved,warnings=warnings,independent_guardian_required=True,
                dynamic_improvement_proven=False,deployment_allowed=False,ast_checks=ast_check())

def prepare():
    with base.JobLock(ROOT/'launch.lock'):
        ast_check();rows=known_cases();source=sources()
        contract=dict(format='near75_known_counterfactual_v1',actors=list(ACTORS),planned_cases=rows,
                      source_sha256=source,max_steps=18000,hz=60,case_wall_seconds=360,hard_wall_seconds=1200,
                      seed_role='known_development_counterfactual',baseline='new_complete_bank80_latch_only',
                      hypothesis='Near cap80→75 only; reduce rule altitude regression, RL attack>=166 accumulated ticks; reject any candidate absG>9',
                      deployment_allowed=False,original24_replay=False)
        trial='near75_known_cf_'+bench.json_hash(contract)[:16]
        manifest=dict(status='prepared_not_run',trial_id=trial,research_contract=contract,planned_cases=rows,source_sha256=source)
        if MANIFEST.exists() and read(MANIFEST).get('status')=='attempted':raise RuntimeError('Attempted contract cannot be reset')
        atomic_json(MANIFEST,manifest);atomic_json(EXP/'PREPARATION.json',preflight())
        print(json.dumps(dict(prepared_not_run=True,trial_id=trial,cases=4,simulator_started=False)))

def controls():
    sys.path.insert(0,str(REPAIR));sys.path.insert(0,str(base.FRESH));sys.path.insert(0,str(EXP))
    import bank80_latch,bank75_latch
    if bank75_latch.Bank75LatchController.command is not bank80_latch.GGuardLatchBank80.command:
        raise RuntimeError('Latch command identity changed')
    return dict(bank80_latch=bank80_latch.GGuardLatchBank80,bank75_latch=bank75_latch.Bank75LatchController)

def worker(input_file):
    specification=read(input_file);case=specification['case']
    expected=next((r for r in known_cases() if r['case']==case),None)
    if expected is None or specification['max_steps']!=18000 or specification['case_seconds']!=360:raise RuntimeError('Unexpected worker input')
    chosen=controls()[case['actor']]
    import candidate as original_bank80
    old_class=original_bank80.Bank80Controller;old_load=engine.load_candidate;old_reset=bench.reset_initial_side
    engine.load_candidate=lambda:SimpleNamespace(GGuardLatchBank80=chosen)
    original_bank80.Bank80Controller=chosen
    def checked_reset(environment,side,runtime):
        observation,initial=original_reset(environment,side,runtime)
        if bench.json_hash(initial)!=expected['initial_sha256']:raise RuntimeError('Known same-initial SHA did not reproduce')
        if type(environment.packet_controller) is not chosen:raise RuntimeError('Wrong actor controller')
        return observation,initial
    bench.reset_initial_side=checked_reset
    try:code=original_worker(input_file)
    finally:
        engine.load_candidate=old_load;original_bank80.Bank80Controller=old_class;bench.reset_initial_side=old_reset
    path=Path(input_file).parent/'result.json';raw=read(path)
    raw.update(smoke_control=case['actor'],controller_actor=case['actor'],paired_baseline_is_repair_guide=False,
               candidate_factor='near_bank_cap_80_to75_only' if case['actor']=='bank75_latch' else None,
               seed_role='known_development_counterfactual',expected_initial_sha256=expected['initial_sha256'],
               research_trial_id=read(MANIFEST)['trial_id'])
    atomic_json(path,raw);return code

def bind_deadline(folder):
    global deadline_monotonic
    launch=read(Path(folder)/'launch.json');deadline_monotonic=launch['deadline_monotonic']
    clock=SimpleNamespace(**vars(REAL_TIME))
    clock.time=lambda:launch['started_epoch']+(REAL_TIME.monotonic()-launch['started_monotonic'])
    base.time=clock;engine.time=clock

def run(folder):bind_deadline(folder);return engine.run(folder)
def guardian(folder):bind_deadline(folder);return engine.guardian(folder)

def start(remaining_percent=None):
    global deadline_monotonic
    with base.JobLock(ROOT/'launch.lock'):
        p=preflight(remaining_percent);manifest=read(MANIFEST)
        if not p['ready_to_start'] or manifest['status']!='prepared_not_run':raise RuntimeError('Contract already attempted or overlapping workload')
        folder=EXP/('run_'+datetime.now(base.TAIPEI).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:4]);folder.mkdir()
        now=REAL_TIME.time();monotonic=REAL_TIME.monotonic();deadline_monotonic=monotonic+1200
        launch=dict(source_sha256=p['source_sha256'],started_epoch=now,started_monotonic=monotonic,
                    deadline_epoch=now+1200,deadline_monotonic=deadline_monotonic,reserved_seconds=1200,
                    case_wall_seconds=360,planned_cases=p['planned_cases'],telemetry_hz=60,learner_started=False,
                    trial_id=p['trial_id'],seed_role=p['seed_role'],research_contract=p['research_contract'],warnings=p['warnings'])
        atomic_json(folder/'launch.json',launch);atomic_json(folder/'state.json',dict(status='preparing',supervisor=None,worker=None))
        manifest.update(status='attempted',output=str(folder));atomic_json(MANIFEST,manifest)
        day=datetime.now(base.TAIPEI).strftime('%Y-%m-%d');path=ROOT/'compute_budgets'/(day+'.json')
        ledger=read(path) if path.exists() else dict(date_taipei=day,reserved_hours=0.,daily_limit_hours=6.,items=[])
        ledger['reserved_hours']+=1/3;ledger['items'].append(dict(id=p['trial_id'],hours=1/3,status='reserved',output=str(folder),kind='known_development_counterfactual'))
        ledger['policy']='warning_only_original_monotonic_hard_deadline';atomic_json(path,ledger)
        with (folder/'guardian.log').open('w',encoding='utf-8') as out:
            parent=recorded_popen([str(PYTHON),'-B','-X','utf8',str(Path(__file__)),'guard','--job',str(folder)],
                                 stdout=out,stderr=subprocess.STDOUT,cwd=ROOT,creationflags=base.NO_WINDOW,
                                 env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','PYTHONUTF8':'1'})
        identity=ident(parent.pid);until=min(REAL_TIME.monotonic()+10,deadline_monotonic)
        atomic_json(folder/'guardian_spawn.json',dict(identity=identity,command=parent.args,
                    source_sha256=bench.file_hash(Path(__file__)),spawned_epoch=now,
                    popen_handle_owned_by_start=True,exit_not_yet_observed=True))
        while REAL_TIME.monotonic()<until:
            if (folder/'guard_status.json').exists():
                guarded=read(folder/'guard_status.json')
                if guarded['status']=='armed':
                    atomic_json(EXP/'latest.json',dict(run=str(folder),guardian=identity,supervisor=guarded['supervisor'],deadline_epoch=launch['deadline_epoch']))
                    print(str(folder));return
            if parent.poll() is not None:raise RuntimeError('Guardian exited before arm')
            REAL_TIME.sleep(.1)
        (folder/'STOP').write_text('launch_ack_timeout',encoding='utf-8')
        try:parent.wait(timeout=5)
        except subprocess.TimeoutExpired:base.cleanup([identity])
        raise RuntimeError('Guardian did not arm within original deadline')

def observe_guardian(folder):
    """Hold a real Windows process handle; a missing process never becomes exit0."""
    import ctypes
    from ctypes import wintypes
    if os.name!='nt':raise RuntimeError('This observer requires the Windows process handle API')
    folder=Path(folder).resolve();launch=read(folder/'launch.json');spawn=read(folder/'guardian_spawn.json')
    identity=spawn['identity'];expected=[str(PYTHON),'-B','-X','utf8',str(Path(__file__)),'guard','--job',str(folder)]
    if spawn['command']!=expected or identity['cmdline']!=expected or identity['create_time'] is None:
        raise RuntimeError('Guardian spawn identity is missing or differs')
    if spawn['source_sha256']!=launch['source_sha256']['new/launcher']:raise RuntimeError('Guardian source differs')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.GetProcessTimes.argtypes=[wintypes.HANDLE,*([ctypes.POINTER(wintypes.FILETIME)]*4)];kernel.GetProcessTimes.restype=wintypes.BOOL
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];kernel.WaitForSingleObject.restype=wintypes.DWORD
    kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)];kernel.GetExitCodeProcess.restype=wintypes.BOOL
    kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
    handle=kernel.OpenProcess(0x100000|0x1000,False,identity['pid'])
    if not handle:raise RuntimeError('Cannot open guardian handle; exit remains unknown')
    receipt=dict(identity=identity,actual_exit_code=None,wait_return_observed=False,
                 observer_scope='OpenProcess + GetProcessTimes + live PID/create/cmd + WaitForSingleObject + GetExitCodeProcess',
                 observer_source_sha256=bench.file_hash(Path(__file__)),opened_monotonic=REAL_TIME.monotonic())
    try:
        created,exited,kernel_time,user_time=(wintypes.FILETIME() for _ in range(4))
        if not kernel.GetProcessTimes(handle,ctypes.byref(created),ctypes.byref(exited),ctypes.byref(kernel_time),ctypes.byref(user_time)):
            raise RuntimeError('Cannot verify guardian handle creation time')
        epoch=(((created.dwHighDateTime<<32)|created.dwLowDateTime)-116444736000000000)/1e7
        if abs(epoch-identity['create_time'])>=.01 or live(identity) is None:raise RuntimeError('Guardian identity not live/matching when handle opened')
        receipt.update(handle_create_time=epoch,handle_identity_verified=True)
        atomic_json(folder/'guardian_observer_started.json',receipt)
        print('Holding verified guardian handle',identity['pid'],flush=True)
        limit=launch['deadline_monotonic']+30
        while REAL_TIME.monotonic()<limit:
            result=kernel.WaitForSingleObject(handle,500)
            if result==0:
                code=wintypes.DWORD()
                if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)):raise RuntimeError('GetExitCodeProcess failed')
                receipt.update(actual_exit_code=int(code.value),wait_return_observed=True,
                               finished_monotonic=REAL_TIME.monotonic(),observed_epoch=REAL_TIME.time())
                atomic_json(folder/'guardian_exit_observed.json',receipt)
                print('Actual guardian exit',code.value,flush=True)
                return 0 if code.value==0 else 1
            if result!=258:raise RuntimeError('WaitForSingleObject failed; exit unknown')
        receipt['error']='observer original deadline+30s exceeded; exit unknown'
        atomic_json(folder/'guardian_exit_observed.json',receipt);return 1
    finally:kernel.CloseHandle(handle)

def decision(results,pairs):
    safety=all(r['overload_ticks']==0 and r['peak_abs_g']<=9 and r['metrics']['deaths']==0 and r['metrics']['own_crashes']==0
               for r in results if r['case']['actor']=='bank75_latch')
    rule=next(p for p in pairs if '_rule_' in p['pair_key'])
    rl=next(r for r in results if r['case']['actor']=='bank75_latch' and r['case']['opponent']=='rl')
    supported=safety and rule['candidate_minus_baseline_common_min_hsl_m']>1e-6 and rl['attack_ticks']>=166
    return dict(safety_pass=safety,hypothesis_supported_on_known_cases=supported,
                rule_common_min_hsl_improvement_m=rule['candidate_minus_baseline_common_min_hsl_m'],rl_candidate_attack_ticks=rl['attack_ticks'],
                gate='reject_candidate' if not safety else 'known_hypothesis_pass_new_development_required' if supported else 'hypothesis_not_supported')

def verify(folder):
    folder=Path(folder);launch=read(folder/'launch.json');state=read(folder/'state.json')
    parent=read(folder/'supervisor_exit.json');guard=read(folder/'guard_status.json')
    guardian_exit=read(folder/'guardian_exit_observed.json');spawn=read(folder/'guardian_spawn.json')
    if (guardian_exit.get('wait_return_observed') is not True or guardian_exit.get('actual_exit_code')!=0
        or guardian_exit.get('handle_identity_verified') is not True or guardian_exit.get('identity')!=spawn['identity']
        or guardian_exit.get('observer_source_sha256')!=launch['source_sha256']['new/launcher']):
        raise RuntimeError('No verified guardian Windows handle exit0 receipt')
    if not parent['wait_return_observed'] or parent['actual_exit_code']!=0 or parent['wait_reason']!='exited':raise RuntimeError('No real successful Popen parent exit')
    if state['status']!='completed' or live(state.get('supervisor')) or guard['status']!='finished':raise RuntimeError('Run is not terminal')
    if sources()!=launch['source_sha256']:raise RuntimeError('Contract drift')
    results=[];matched={}
    for fixture in known_cases():
        path=folder/'cases'/fixture['case_id'];raw=read(path/'result.json');exit_record=read(path/'exit.json')
        if exit_record['exit_code']!=0 or exit_record['wait_reason']!='exited' or not raw['full_round_completed'] or not raw['score_eligible']:raise RuntimeError('Incomplete worker')
        if raw['case']!=fixture['case'] or raw['controller_actor']!=raw['case']['actor'] or raw['smoke_control']!=raw['case']['actor']:raise RuntimeError('Actor label/controller mismatch')
        if raw['initial_sha256']!=fixture['initial_sha256'] or bench.json_hash(raw['initial'])!=fixture['initial_sha256']:raise RuntimeError('Known initial drift')
        with (path/'telemetry_60hz.csv').open(encoding='utf-8',newline='') as stream:
            reader=csv.DictReader(stream)
            if tuple(reader.fieldnames)!=COLUMNS:raise RuntimeError('60Hz schema changed')
            rows=list(reader)
        overload=base.validate_rows(rows,raw['steps'],round(raw['metrics']['over_9g_seconds']*60))
        if any(not math.isclose(float(r['abs_g']),abs(float(r['signed_g'])),abs_tol=1e-12) for r in rows):raise RuntimeError('Absolute G mismatch')
        attack_ticks=sum(152.4<=float(r['distance_m'])<=914.4 and float(r['blue_angle_deg_judge_only'])<=1 for r in rows)
        if attack_ticks!=round(raw['metrics']['attack_seconds']*60):raise RuntimeError('Exact attack counter mismatch')
        with (path/'telemetry.csv').open(encoding='utf-8',newline='') as stream:counts=list(csv.DictReader(stream))
        if not counts or float(counts[-1]['attack_seconds'])!=raw['metrics']['attack_seconds']:raise RuntimeError('Sparse/exact attack final mismatch')
        if any(float(b['attack_seconds'])<float(a['attack_seconds']) for a,b in zip(counts,counts[1:])):raise RuntimeError('Attack accumulated time reset')
        times=[float(line[1:]) for line in (path/'duel.acmi').read_text(encoding='utf-8').splitlines() if line.startswith('#')]
        if not times or any(b<a for a,b in zip(times,times[1:])) or abs(times[-1]-raw['steps']/60)>.001:raise RuntimeError('ACMI incomplete')
        previous=raw['initial']['blue_own20_audit_only'][14];latched=False
        for row in rows:
            if abs(previous)>8.5:latched=True
            elif abs(previous)<8:latched=False
            if bool(int(row['g_guard_latched']))!=latched:raise RuntimeError('Latch counter mismatch')
            previous=float(row['signed_g'])
        item=dict(case=raw['case'],case_id=raw['case_id'],pair_key=raw['pair_key'],steps=raw['steps'],
                  initial_sha256=raw['initial_sha256'],metrics=raw['metrics'],attack_ticks=attack_ticks,
                  peak_abs_g=max(float(r['abs_g']) for r in rows),overload_ticks=len(overload),
                  min_hsl_altitude_m=min(float(r['altitude_m']) for r in rows),
                  actual_worker_exit=exit_record,
                  artifact_sha256={name:bench.file_hash(path/name) for name in ('result.json','telemetry_60hz.csv','telemetry.csv','duel.acmi','exit.json')})
        results.append(item);matched.setdefault(raw['pair_key'],{})[raw['case']['actor']]=(item,rows)
    pairs=[]
    for key,pair in matched.items():
        baseline,br=pair['bank80_latch'];candidate,cr=pair['bank75_latch'];exposure=min(len(br),len(cr))
        pairs.append(dict(pair_key=key,common_ticks=exposure,common_exposure_seconds=exposure/60,
                          baseline_common_min_hsl_m=min(float(r['altitude_m']) for r in br[:exposure]),
                          candidate_common_min_hsl_m=min(float(r['altitude_m']) for r in cr[:exposure]),
                          candidate_minus_baseline_common_min_hsl_m=min(float(r['altitude_m']) for r in cr[:exposure])-min(float(r['altitude_m']) for r in br[:exposure])))
    gates=decision(results,pairs)
    report=dict(format='near75_known_counterfactual_verified_v1',verified_comparison=True,trial_id=launch['trial_id'],
                seed_role='known_development_counterfactual',baseline='new_complete_bank80_latch',candidate='new_bank75_latch',
                actual_parent_exit_code=parent['actual_exit_code'],actual_guardian_exit_code=guardian_exit['actual_exit_code'],
                guardian_observation=guardian_exit,source_sha256=launch['source_sha256'],cases=results,pairs=pairs,
                **gates,
                dynamic_unknown=True,deployment_allowed=False,official_validation=False,
                next_action='Only if known hypothesis passes: register new development cases; retain original three rule kills before any promotion')
    atomic_json(folder/'VERIFIED_DIAGNOSTIC.json',report);return report

# Reuse mature guardian, supervisor, tick recorder, case worker and OS locks.
# Patch only process-local source bindings, atomic retries and two case time constants.
engine.EXP=EXP;engine.__file__=str(Path(__file__));engine.frozen_sources=sources
base.EXP=EXP;base.__file__=str(Path(__file__));base.reference_cases=known_cases;base.frozen_sources=sources
base.ident=ident;base.live=live;base.occupied=occupied
bench.atomic_json=atomic_json
proxy=SimpleNamespace(**vars(REAL_SUBPROCESS));proxy.Popen=recorded_popen
engine.subprocess=proxy;base.subprocess=proxy
tree=ast.parse((ROOT/'experiments/overload_60hz/launch_diagnostic.py').read_text(encoding='utf-8'))
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
class CaseWallPatch(ast.NodeTransformer):
    def visit_Dict(self,node):
        self.generic_visit(node)
        for key,value in zip(node.keys,node.values):
            if isinstance(key,ast.Constant) and key.value=='case_seconds':
                if not isinstance(value,ast.Constant) or value.value!=300:raise RuntimeError('Shared case wall structure changed')
                value.value=360.
        return node
    def visit_Call(self,node):
        self.generic_visit(node)
        if isinstance(node.func,ast.Name) and node.func.id=='min' and node.args and isinstance(node.args[0],ast.Constant) and node.args[0].value==310:node.args[0].value=360
        return node
node=CaseWallPatch().visit(node);module=ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[]))
exec(compile(module,str(Path(__file__))+'::shared_run_case360','exec'),base.__dict__)

def main():
    parser=argparse.ArgumentParser(description='Prepare/check four known-development bank80_latch vs bank75_latch cases')
    parser.add_argument('action',nargs='?',default='check',choices=['prepare','check','start','run','guard','worker','verify','observe-guardian'])
    parser.add_argument('--check-only',action='store_true');parser.add_argument('--job',type=Path);parser.add_argument('--input',type=Path)
    parser.add_argument('--remaining-percent',type=float);args=parser.parse_args()
    if args.action=='prepare':prepare();return 0
    if args.check_only or args.action=='check':print(json.dumps(preflight(args.remaining_percent),ensure_ascii=False,indent=2));return 0
    if args.action=='start':start(args.remaining_percent);return 0
    if args.action=='run':return run(args.job)
    if args.action=='guard':return guardian(args.job)
    if args.action=='worker':return worker(args.input)
    if args.action=='observe-guardian':return observe_guardian(args.job)
    print(json.dumps(verify(args.job),ensure_ascii=False,indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
