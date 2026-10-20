"""Shared smoke gates. Importing this file never constructs an FDM."""
from pathlib import Path
import sys, os, json, time, math, copy
from datetime import datetime, timezone, timedelta
import psutil
HERE=Path(__file__).resolve().parent
POOL=next(parent for parent in HERE.parents if parent.name=='opponent_pool')
ROOT=POOL.parents[1]
sys.path.insert(0,str(POOL));sys.path.insert(0,str(ROOT))
import prepare_smoke as prep
import benchmark_pool as bench
from runner import JobLock
TAIPEI=timezone(timedelta(hours=8))
NO_WINDOW=getattr(__import__('subprocess'),'CREATE_NO_WINDOW',0)
read=prep.read
MODE_CONTRACT={
    'm4_aligned1':{'cases':1,'distinct_seeds':1,'total_wall_seconds':90,'case_wall_seconds':45,'max_ticks':300,'reset_repeats':2},
}

def write(path,value):
    """Windows readers may briefly deny ReplaceFile; retry the same temp bytes."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    import uuid
    temporary=path.with_name(path.name+'.tmp_'+uuid.uuid4().hex)
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
    try:
        for attempt in range(8):
            try:os.replace(temporary,path);return
            except PermissionError:
                if attempt==7:raise
                time.sleep(min(.01*(2**attempt),.08))
    finally:
        if temporary.exists():temporary.unlink()

sha=bench.file_hash
jsha=bench.json_hash

def identity(pid=None):
    p=psutil.Process(pid or os.getpid())
    return {'pid':p.pid,'creation_epoch':p.create_time(),'cmdline':p.cmdline(),'exe':p.exe(),'parent_pid':p.ppid()}

def matching(record):
    try:
        p=psutil.Process(record['pid'])
        return p if abs(p.create_time()-record['creation_epoch'])<.01 and p.cmdline()==record['cmdline'] and os.path.normcase(p.exe())==os.path.normcase(record['exe']) else None
    except psutil.NoSuchProcess:return None
    # AccessDenied deliberately propagates: unknown identity is never dead.

def stop(out):
    locations=[ROOT,POOL,HERE,Path(out),HERE.parent]
    return any((p/'STOP').exists() for p in locations)

def resource_gate():
    ram=psutil.virtual_memory().available;disk=psutil.disk_usage(str(ROOT)).free
    if ram<2*1024**3 or disk<10*1024**3:raise RuntimeError('Resource floor: RAM 2GiB, disk 10GiB')
    return {'available_ram_bytes':ram,'free_disk_bytes':disk}

def occupied(exclude=()):
    found=[]
    for p in psutil.process_iter(['name']):
        if p.pid in set(exclude)|{os.getpid()}:continue
        name=(p.info['name'] or '').lower()
        if not ('python' in name or name.startswith(('host','jsbsim'))):continue
        try:cmd=p.cmdline()
        except psutil.NoSuchProcess:continue
        except psutil.AccessDenied:raise RuntimeError('Workload identity unreadable; occupancy unknown')
        args=[s.replace('\\','/').lower() for s in cmd]
        if any('e:/ai_pilot/' in s for s in args):
            names=[s.rsplit('/',1)[-1] for s in args]
            if any(n.endswith(('.py','.exe')) and any(v in n for v in ('host','player','train','runner','benchmark','launch','smoke','calibrat','guard','watchdog','m4_tactical','win_loop')) for n in names):
                found.append(identity(p.pid))
    return found

def tools():
    files=list(HERE.glob('*.py'))+[HERE/'CONTRACT.json']
    return {p.name:sha(p) for p in sorted(files)}

def contract_gate():
    contract=read(HERE/'CONTRACT.json')
    actual={p.name:sha(p) for p in sorted(HERE.glob('*.py'))}
    if contract['executor_sha256']!=actual:raise RuntimeError('M4 diagnostic executor changed')
    if contract['readme_sha256']!=sha(HERE/'README.md'):raise RuntimeError('M4 protocol changed')
    if contract.get('mode_contract')!=MODE_CONTRACT:raise RuntimeError('M4 mode changed')
    for relative,digest in contract['m4_sources_sha256'].items():
        if sha(ROOT/relative)!=digest:raise RuntimeError('M4/rules source changed: '+relative)
    return contract

def source_gate(expected=None):
    contract=contract_gate()
    source=prep.frozen_status()
    if not source['verified']:raise RuntimeError('Frozen dependencies mismatch')
    source={**source,'m4_sources_sha256':contract['m4_sources_sha256']}
    if expected and source!=expected:raise RuntimeError('Source inventory changed')
    return source

def plan_cases_for_mode(seed,diagnostic_case_index=None):
    if diagnostic_case_index is not None:raise ValueError('Exactly1aligned counter fixture')
    if isinstance(seed,bool) or not isinstance(seed,int) or not 0<=seed<2**31:raise ValueError('Invalid seed')
    return [{'case_id':f'aligned_counter_{seed}','opponent_id':'rule','seed':seed,'distance_ft':6000,
             'max_steps':300,'reset_repeats':2,'stage':'rear','expect_nonzero':True,'coaxial_init':True,
             'opening':'nonofficial_rear_body_axis_aligned_before_first_physics_tick','score_eligible':False}]

def validate_execution_plan(cases,seed,diagnostic_case_index=None):
    if cases!=plan_cases_for_mode(seed,diagnostic_case_index):raise ValueError('Changed M4 diagnostic plan')
    return 'm4_aligned1'

def execution_mode_gate(launch):
    mode=validate_execution_plan(launch['cases'],launch['base_seed'],launch.get('diagnostic_case_index'))
    if launch.get('execution_mode')!=mode or launch.get('mode_contract')!=MODE_CONTRACT[mode]:raise ValueError('Changed diagnostic mode')
    if launch.get('total_wall_seconds')!=90 or launch.get('case_wall_seconds')!=45:raise ValueError('Changed original deadline')
    return mode

def check(seed,exclude=(),diagnostic_case_index=None):
    cases=plan_cases_for_mode(seed,diagnostic_case_index)
    mode=validate_execution_plan(cases,seed,diagnostic_case_index)
    seeds=prep.seed_status(read(ROOT/'seed_registry.json'),cases)
    if stop(HERE):raise RuntimeError('STOP exists')
    jobs=occupied(exclude)
    return {'cases':cases,'source_freeze':source_gate(),'tools_sha256':tools(),'resources':resource_gate(),
            'seeds':seeds,'occupied':jobs,'execution_allowed':not jobs and seeds['fresh_relative_to_registry'],
            'score_eligible':False,'official_validation':False,'new_fdm_ticks':0,'diagnostic_only':True,'diagnostic_case_index':diagnostic_case_index,
            'base_seed':seed,'execution_mode':mode,'mode_contract':copy.deepcopy(MODE_CONTRACT[mode]),'planned_case_count':len(cases)}

def reserve(seed,out,remaining,usage_epoch,diagnostic_case_index=None):
    if not math.isfinite(remaining) or not 0<=remaining<=100 or not 0<=time.time()-usage_epoch<=600:raise ValueError('Fresh quota observation required; quota only warns')
    state=check(seed,diagnostic_case_index=diagnostic_case_index)
    day_now=datetime.now(TAIPEI).date().isoformat()
    if not '2026-10-14'<=day_now<='2026-11-03':raise RuntimeError('Outside authorized research dates')
    if not state['execution_allowed']:raise RuntimeError('Occupied or seed previously attempted/reserved')
    trial='m4_aligned_counter_v1_'+str(seed)+('_diagnostic_'+str(diagnostic_case_index) if diagnostic_case_index is not None else '_single_aligned_counter')
    total_seconds=MODE_CONTRACT[state['execution_mode']]['total_wall_seconds']
    reservation_start_epoch=time.time();reservation_start_monotonic=time.monotonic()
    reservation_hours=total_seconds/3600
    registry=copy.deepcopy(read(ROOT/'seed_registry.json'))
    registry.setdefault('trials',{})[trial]={'seeds':state['seeds']['requested'],'status':'reserved','seed_role':'development_interface_smoke_not_holdout','output':str(out)}
    day=datetime.now(TAIPEI).date().isoformat();ledger_path=ROOT/'compute_budgets'/(day+'.json')
    ledger=read(ledger_path) if ledger_path.exists() else {'date_taipei':day,'daily_limit_hours':6.,'reserved_hours':0.,'items':[]}
    hours=[x['hours'] for x in ledger['items']]
    if any(isinstance(h,bool) or not isinstance(h,(int,float)) or not math.isfinite(h) or h<0 for h in hours):raise RuntimeError('Invalid ledger item hours')
    if not math.isfinite(float(ledger['reserved_hours'])):raise RuntimeError('Invalid ledger total')
    total=sum(hours)
    if ledger['date_taipei']!=day or abs(total-float(ledger['reserved_hours']))>1e-8:raise RuntimeError('Invalid daily ledger')
    if any(x['id']==trial for x in ledger['items']):raise RuntimeError('Trial budget already reserved')
    ledger['items'].append({'id':trial,'hours':reservation_hours,'status':'reserved','output':str(out),'warning_only_daily_policy':True})
    ledger['reserved_hours']=total+reservation_hours
    write(ledger_path,ledger);write(ROOT/'seed_registry.json',registry)
    state.update(trial_id=trial,ledger=str(ledger_path),remaining_percent=remaining,usage_epoch=usage_epoch,
        quota_warning=remaining<=10,daily_warning=ledger['reserved_hours']>6,total_wall_seconds=total_seconds,case_wall_seconds=45,launcher=identity(),
        reservation_start_epoch=reservation_start_epoch,reservation_start_monotonic=reservation_start_monotonic,
        deadline_epoch=reservation_start_epoch+total_seconds,deadline_monotonic=reservation_start_monotonic+total_seconds)
    return state

def legal_command(command):
    values=[float(x) for x in command]
    if len(values)!=4 or not all(math.isfinite(x) for x in values) or any(abs(x)>1 for x in values[:3]) or not 0<=values[3]<=1:raise ValueError('Invalid finite bounded command')
    return values
