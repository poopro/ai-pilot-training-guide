"""One fresh development trial; reserve its budget before any simulator worker."""
from pathlib import Path
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
import argparse,json,os,sys,time,uuid
import psutil
ROOT=Path(__file__).resolve().parents[2];EXP=Path(__file__).resolve().parent
SNAPSHOT=ROOT/'candidates'/'near_bank80_20261012'
sys.path.insert(0,str(ROOT))
import benchmark_fresh as bench
from budget import date_taipei,checked,reserve,claim_seeds,TAIPEI
from runner import JobLock

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def self_identity():
    p=psutil.Process(os.getpid())
    return {'pid':p.pid,'creation_epoch':p.create_time(),'cmdline':p.cmdline()}

def occupied():
    for p in psutil.process_iter(['name']):
        if p.pid==os.getpid() or 'python' not in (p.info['name'] or '').lower():continue
        try:cmd=p.cmdline()
        except psutil.NoSuchProcess:continue
        except psutil.AccessDenied:raise RuntimeError('Python process unreadable; workload unknown')
        for arg in cmd:
            path=arg.replace('\\','/').lower();name=path.rsplit('/',1)[-1]
            if path.startswith('e:/ai_pilot/') and ((name.startswith(('train','benchmark','calibrate','launch_fresh')) and name.endswith('.py')) or (name=='runner.py' and 'run' in cmd)):
                return {'pid':p.pid,'creation_epoch':p.create_time(),'cmdline':cmd}
    return None

def preflight(seed,now):
    if not 0<=seed<=2**31-20:raise ValueError('Seed outside supported range')
    if (ROOT/'STOP').exists() or (EXP/'STOP').exists():raise RuntimeError('STOP exists')
    other=occupied()
    if other:raise RuntimeError('Another project compute workload is active: '+str(other))
    if psutil.virtual_memory().available<2*1024**3:raise RuntimeError('Available RAM below 2GiB')
    if psutil.disk_usage(str(ROOT)).free<10*1024**3:raise RuntimeError('Free disk below 10GiB')
    manifest=read(SNAPSHOT/'manifest.json')
    for relative,expected in manifest['source_sha256'].items():
        if bench.file_hash(SNAPSHOT/relative)!=expected:raise RuntimeError('Frozen snapshot changed: '+relative)
    original=read(SNAPSHOT/'COMPARISON.json')
    actual=bench.capture_sources(ROOT/'repair_v1')
    for key,expected in original['source_sha256'].items():
        if key=='candidate/benchmark_bank80.py':continue
        if actual.get(key)!=expected:raise RuntimeError('Original runtime/candidate/XML changed: '+key)
    original_report=read(SNAPSHOT/'report.json')
    if bench.bundle_hashes(bench.DEFAULT_RED_BUNDLE)!=original_report['red_bundle_sha256']:
        raise RuntimeError('Frozen red bundle changed')
    cases=bench.plan_cases(1,seed,'both',True)
    seeds=sorted({c.seed for c in cases})
    trial='bank80_fresh_dev_'+str(seed)+'_'+actual['candidate/near_bank80.py'][:12]
    registry=claim_seeds(read(ROOT/'seed_registry.json'),trial,seeds)
    day=date_taipei(now);ledger_path=ROOT/'compute_budgets'/(day+'.json')
    prior=read(ledger_path) if ledger_path.exists() else None
    prior=checked(prior,day)
    ledger=None;budget_error=None
    try:ledger=reserve(prior,day,trial,40/60)
    except ValueError as e:budget_error=str(e)
    local=now.astimezone(TAIPEI)
    midnight=(local+timedelta(days=1)).replace(hour=0,minute=0,second=0,microsecond=0)
    same_day_time=(midnight-local).total_seconds()>=2410
    within_dates='2026-10-13'<=day<='2026-11-03'
    return {'trial':trial,'seed':seed,'seeds':seeds,'source_sha256':actual,'registry':registry,
            'day':day,'ledger_path':ledger_path,'ledger':ledger,'budget_error':budget_error,
            'same_day_time':same_day_time,'within_dates':within_dates,
            'prior_reserved_hours':prior['reserved_hours'],'red_bundle_sha256':original_report['red_bundle_sha256']}

def main(args):
    now=datetime.now(timezone.utc)
    if args.check_only:
        p=preflight(args.seed,now)
        print(json.dumps({'check_only':True,'simulator_started':False,'candidate_and_runtime_hashes_verified':True,
            'seed_role':'fresh relative to recorded campaign case inputs; development, not holdout',
            'trial':p['trial'],'seeds':p['seeds'],'planned_cases':24,'compute_budget_date':p['day'],
            'prior_reserved_hours':p['prior_reserved_hours'],'reservation_hours':40/60,
            'budget_fits':p['ledger'] is not None,'budget_error':p['budget_error'],
            'same_day_wall_time_available':p['same_day_time'],'within_research_dates':p['within_dates'],
            'ready_on_current_date_without_usage_check':p['ledger'] is not None and p['same_day_time'] and p['within_dates']},ensure_ascii=False))
        return 0
    if args.remaining_percent is None or not 35<=args.remaining_percent<=100 or args.usage_epoch is None:
        raise ValueError('Fresh observed minimum remaining usage >=35% required')
    if not 0<=time.time()-args.usage_epoch<=600:raise ValueError('Usage observation stale')
    with JobLock(ROOT/'launch.lock'):
        p=preflight(args.seed,datetime.now(timezone.utc))
        if not p['within_dates']:raise RuntimeError('Fresh validation is scheduled for 10/13 through 11/3')
        if not p['same_day_time']:raise RuntimeError('Not enough wall time before midnight; wait for the next calendar-day budget')
        if p['ledger'] is None:raise RuntimeError(p['budget_error'])
        out=EXP/('run_'+datetime.now(TAIPEI).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:4])
        out.mkdir(exist_ok=False)
        p['registry']['trials'][p['trial']].update(output=str(out),reserved_utc=bench.utc_now())
        bench.atomic_json(p['ledger_path'],p['ledger'])
        bench.atomic_json(ROOT/'seed_registry.json',p['registry'])
        ident=self_identity()
        launch={'kind':'frozen_bank80_fresh_development','reservation_id':p['trial'],
            'seed':args.seed,'seeds':p['seeds'],'seed_role':'development_from_reservation_not_holdout',
            'supervisor':ident,'compute_budget_date':p['day'],'source_sha256':p['source_sha256'],
            'candidate_snapshot':str(SNAPSHOT),'reserved_hours':40/60,'planned_cases':24,
            'case_wall_seconds':150,'total_wall_seconds':2400,'official_validation':False,'actor_policy_used':False}
        bench.atomic_json(out/'launch.json',launch)
        previous=read(ROOT/'research_latest.json')
        pointer={'updated_utc':bench.utc_now(),'status':'running','experiment':'fresh_bank80',
            'run':str(out),'supervisor':ident,'report':str(out/'report.json'),
            'candidate_snapshot':str(SNAPSHOT),'planned_cases':24,'actor_policy_used':False,
            'official_validation':False,'retained_deployment':'repair_guide','seed_role':'fresh_development_not_holdout',
            'reservation_id':p['trial'],'compute_budget_date':p['day'],'daily_compute_reserved_hours':p['ledger']['reserved_hours'],
            'previous_research_pointer':previous,'next_action':'Wait for actual exit; verify all pairs and safety before promotion'}
        bench.atomic_json(EXP/'latest.json',pointer);bench.atomic_json(ROOT/'research_latest.json',pointer)
        run_args=SimpleNamespace(out=out,repair_root=ROOT/'repair_v1',rounds=1,seed=args.seed,
            mirror='both',max_steps=18000,case_seconds=150.,max_minutes=40.,
            remaining_percent=args.remaining_percent,usage_epoch=args.usage_epoch,
            daily_reserved_hours=p['ledger']['reserved_hours'],compute_budget_date=p['day'])
        began=time.monotonic();code=1
        try:code=bench.run_benchmark(run_args)
        except BaseException as e:
            pointer['error']=repr(e)
            if isinstance(e,KeyboardInterrupt):code=130
        finally:
            pointer.update(status='completed' if code==0 else 'incomplete',benchmark_return_code=code,
                updated_utc=bench.utc_now(),wall_seconds=time.monotonic()-began,
                actual_parent_exit_code=None,next_action='Observe the actual process exit, then run verify_fresh.py only for a full report; partial cases are excluded')
            bench.atomic_json(EXP/'latest.json',pointer);bench.atomic_json(ROOT/'research_latest.json',pointer)
            registry=read(ROOT/'seed_registry.json');registry['trials'][p['trial']].update(status=pointer['status'],benchmark_return_code=code)
            bench.atomic_json(ROOT/'seed_registry.json',registry)
            ledger=read(p['ledger_path'])
            for item in ledger['items']:
                if item['id']==p['trial']:item.update(status=pointer['status'],actual_elapsed_seconds=pointer['wall_seconds'],output=str(out))
            bench.atomic_json(p['ledger_path'],ledger)
        return code

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='New-day budget and fresh seed guarded paired development validation')
    parser.add_argument('--check-only',action='store_true')
    parser.add_argument('--seed',type=int,default=2026101300)
    parser.add_argument('--remaining-percent',type=float)
    parser.add_argument('--usage-epoch',type=float)
    raise SystemExit(main(parser.parse_args()))
