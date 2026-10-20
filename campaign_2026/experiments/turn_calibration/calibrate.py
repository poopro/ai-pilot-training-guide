"""Isolated seven-case FDM calibration. No learner, controller edit or combat score."""
from pathlib import Path
import argparse,csv,hashlib,json,os,random,subprocess,sys,time,uuid
import psutil
import numpy as np
ROOT=Path(r'E:\ai_pilot\campaign_2026'); EXP=ROOT/'experiments'/'turn_calibration'
sys.path.insert(0,str(ROOT))
import benchmark as bench
from runner import JobLock

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):bench.atomic_json(p,v)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sources():
    v=bench.capture_sources(ROOT/'repair_v1')
    for name in ['calibrate.py','calibration_worker.py','calibration_adapter.py']:
        v['calibration/'+name]=sha(EXP/name)
    v['campaign/benchmark.py']=sha(ROOT/'benchmark.py')
    return v
def stopped(folder):return (ROOT/'STOP').exists() or (EXP/'STOP').exists() or (Path(folder)/'STOP').exists()
def planned():
    rows=[{'case_id':'bank00_path_alpha','bank_deg':0,'pitch_spec':'path_alpha','speed_kts':320}]
    for bank in [30,50,70]:
        for pitch in ['nose0','path_alpha']:
            rows.append({'case_id':f'bank{bank:02d}_{pitch}','bank_deg':bank,'pitch_spec':pitch,'speed_kts':320})
    return rows
def validate_case(folder,row,result):
    if result.get('complete') is not True or result.get('status')!='complete':return False
    if result.get('ticks_executed')!=2100 or result.get('csv_rows')!=2100:return False
    if result.get('official_validation') or result.get('combat_score_eligible'):return False
    with (folder/(row['case_id']+'.csv')).open(encoding='utf-8',newline='') as f:
        rows=list(csv.DictReader(f))
    if len(rows)!=2100:return False
    if sum(r['phase']=='warmup' for r in rows)!=900 or sum(r['phase']=='test' for r in rows)!=1200:return False
    for index,r in enumerate(rows,1):
        if int(r['tick'])!=index:return False
        if not abs(float(r['sim_time_s'])-index/60)<1e-9:return False
        numbers=[float(v) for k,v in r.items() if k not in ['phase','mode_before','mode_after']]
        if not np.isfinite(numbers).all():return False
    return True

def worker(input_file):
    spec=read(input_file);folder=Path(input_file).parent
    try:
        if sources()!=spec['source_sha256']:raise RuntimeError('Frozen sources changed before worker')
        random.seed(spec['seed']);np.random.seed(spec['seed'])
        runtime=bench.load_runtime(ROOT/'repair_v1')
        from calibration_adapter import make_pair
        from calibration_worker import run_case
        adapter,controller=make_pair(runtime)
        dt_own=adapter.own.fdm.get_delta_t();dt_red=adapter.reference.fdm.get_delta_t()
        result=run_case(adapter,controller,spec['case'],str(folder),time.monotonic,lambda:stopped(spec['out']))
        result.update(source_sha256=spec['source_sha256'],seed=spec['seed'],fdm_dt_s=[dt_own,dt_red])
        if sources()!=spec['source_sha256']:
            result.update(complete=False,status='incomplete',reason='Frozen sources changed during worker')
        write(folder/'result.json',result)
        return 0 if result['complete'] else 2
    except BaseException as e:
        import traceback;traceback.print_exc()
        write(folder/'result.json',{'status':'failed','complete':False,'error':repr(e),
            'official_validation':False,'combat_score_eligible':False})
        return 2

def identity(proc):
    p=psutil.Process(proc.pid)
    return {'pid':proc.pid,'creation_epoch':p.create_time(),'cmdline':p.cmdline()}
def occupied():
    for proc in psutil.process_iter(['name']):
        if 'python' not in (proc.info['name'] or '').lower():continue
        try:cmd=proc.cmdline()
        except psutil.NoSuchProcess:continue
        except psutil.AccessDenied:raise RuntimeError('Python process access denied; workload state unknown')
        paths=[s.replace('\\','/').lower() for s in cmd]
        if any(s.endswith(('/train.py','/train_opponents.py','/benchmark.py','/benchmark_gate.py','/benchmark_probe.py'))
            and s.startswith('e:/ai_pilot/') for s in paths):
            return {'pid':proc.pid,'command':cmd}
    return None

def main(args):
    with JobLock(EXP/'launch.lock'):
        if stopped(EXP):raise RuntimeError('STOP exists; no calibration started')
        if occupied():raise RuntimeError('An existing learner or evaluation is active; no duplicate compute started')
        if psutil.virtual_memory().available<2*1024**3:raise RuntimeError('Insufficient available RAM')
        folder=EXP/('run_'+time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:4]);folder.mkdir()
        began=time.monotonic();frozen=sources();rows=planned()
        report={'status':'running','kind':'command_channel_calibration_not_combat_score',
            'source_sha256':frozen,'cases':[],'planned_cases':7,'case_wall_seconds':150,'total_wall_seconds':600,
            'initial_altitude_msl_ft':12000,'speed_cas_kts':320,'seed':2026101200,
            'physics_hz':60,'warmup_ticks':900,'test_ticks':1200,'supervisor':identity_subprocess_self(),
            'usage_verified_remaining_percent':args.remaining_percent,'usage_observed_epoch':args.usage_epoch,
            'daily_compute_reserved_hours':4.916666666666667,'daily_limit_hours':6,
            'official_validation':False,'combat_score_eligible':False,'complete':False}
        def save():
            report['wall_seconds']=time.monotonic()-began;write(folder/'report.json',report)
            latest={'run':str(folder),'report':str(folder/'report.json'),'status':report['status'],
                'complete':report['complete'],'supervisor':report['supervisor'],'current':report.get('current'),
                'completed_cases':len(report['cases']),'planned_cases':7,'official_validation':False,
                'combat_score_eligible':False,'daily_compute_reserved_hours':report['daily_compute_reserved_hours']}
            write(EXP/'latest.json',latest)
        save()
        try:
            for row in rows:
                remaining=600-(time.monotonic()-began)
                if remaining<=0 or stopped(folder):break
                if sources()!=frozen:raise RuntimeError('Source mismatch before case')
                case_folder=folder/'cases'/row['case_id'];case_folder.mkdir(parents=True)
                spec={'case':row,'seed':2026101200,'out':str(folder),'source_sha256':frozen}
                write(case_folder/'input.json',spec)
                limit=min(150.,remaining)
                with (case_folder/'worker.log').open('w',encoding='utf-8') as log:
                    proc=subprocess.Popen([sys.executable,'-B','-X','utf8',str(EXP/'calibrate.py'),
                        '--_worker',str(case_folder/'input.json')],cwd=EXP,stdout=log,stderr=subprocess.STDOUT,
                        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    report['current']={'case_id':row['case_id'],'process':identity(proc),'case_limit_seconds':limit}
                    save()
                    reason=bench.wait_process(proc,timeout_s=limit,stop_check=lambda:stopped(folder))
                result=read(case_folder/'result.json') if (case_folder/'result.json').exists() else {'complete':False,'status':'missing_result'}
                eligible=reason=='exited' and proc.returncode==0 and validate_case(case_folder,row,result)
                report['cases'].append({'case':row,'worker_exit_code':proc.returncode,'wait_reason':reason,
                    'valid_calibration':eligible,'result':result,'folder':str(case_folder)})
                report.pop('current',None);save()
                print(f"{len(report['cases'])}/7 {row['case_id']} valid={eligible}",flush=True)
                if not eligible:break
            valid=len(report['cases'])==7 and all(c['valid_calibration'] for c in report['cases'])
            initial={c['result'].get('initial_state_sha') for c in report['cases']}
            boundary={c['result'].get('warmup_boundary_sha') for c in report['cases']}
            valid=valid and len(initial)==len(boundary)==1 and None not in initial|boundary
            if sources()!=frozen:raise RuntimeError('Source mismatch after calibration')
            report.update(complete=bool(valid),initials_identical=len(initial)==1,
                warmup_boundaries_identical=len(boundary)==1,status='completed' if valid else 'incomplete')
        except BaseException as e:
            report.update(status='failed',complete=False,error=repr(e))
        finally:
            report.pop('current',None);save()
        print(json.dumps({'run':str(folder),'status':report['status'],'complete':report['complete']},ensure_ascii=False),flush=True)
        return 0 if report['complete'] else 2
def identity_subprocess_self():
    p=psutil.Process(os.getpid());return {'pid':p.pid,'creation_epoch':p.create_time(),'cmdline':p.cmdline()}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--_worker',type=Path)
    p.add_argument('--remaining-percent',type=float);p.add_argument('--usage-epoch',type=float)
    args=p.parse_args()
    if args._worker:raise SystemExit(worker(args._worker))
    if args.remaining_percent is None or not 35<=args.remaining_percent<=100 or args.usage_epoch is None:
        p.error('Fresh observed usage >=35% required')
    if not 0<=time.time()-args.usage_epoch<=600:p.error('Usage observation is stale')
    raise SystemExit(main(args))
