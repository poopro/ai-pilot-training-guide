"""Replay exactly two observed RL/6000-ft mirrored cases, logging every tick.

No controller changes, learner, parameter sweep, holdout or deployment. Imports
of the simulator runtime occur only in the explicitly launched worker.
"""
from __future__ import annotations
import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
import uuid
import psutil

EXP = Path(__file__).resolve().parent
ROOT = EXP.parents[1]
REPAIR = ROOT / 'repair_v1'
PYTHON = Path(r'C:\Users\USER\anaconda3\envs\F16_ai\python.exe')
FRESH = ROOT / 'experiments' / 'fresh_bank80'
REFERENCE = FRESH / 'run_20261013_013609_5218' / 'report.json'
SNAPSHOT = ROOT / 'candidates' / 'near_bank80_20261012'
TAIPEI = timezone(timedelta(hours=8))
TERMINAL = {'completed', 'failed', 'stopped', 'deadline', 'resource_pressure'}
COLUMNS = ('tick','simulation_seconds','controller_mode','guard_active','aileron','elevator',
    'rudder','throttle','signed_g','abs_g','overload_ticks','altitude_m','cas_kts','tas_mps',
    'roll_deg','pitch_deg','alpha_deg','p_rad_s','q_rad_s','r_rad_s','closing_mps','distance_m',
    'blue_angle_deg_judge_only','bank_target','pitch_target','speed_target')
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
sys.path.insert(0, str(ROOT))
from runner import JobLock
sys.path.insert(0, str(FRESH))
import benchmark_fresh as bench


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def ident(pid):
    p = psutil.Process(pid)
    return {'pid':p.pid,'create_time':p.create_time(),'cmdline':p.cmdline(),'parent_pid':p.ppid()}


def live(record):
    if not record:
        return None
    try:
        p = psutil.Process(record['pid'])
        return p if abs(p.create_time()-record['create_time']) < .01 and p.cmdline()==record['cmdline'] else None
    except psutil.NoSuchProcess:
        return None


def cleanup(records):
    """Children first; recheck creation time and exact command before each signal."""
    tracked = {r['pid']:dict(r) for r in records if r}
    for r in list(tracked.values()):
        p = live(r)
        if p:
            for c in p.children(recursive=True):
                try: tracked[c.pid] = ident(c.pid)
                except psutil.NoSuchProcess: pass
    def depth(r):
        seen=set(); result=0
        while r['parent_pid'] in tracked and r['parent_pid'] not in seen:
            seen.add(r['parent_pid']); result+=1; r=tracked[r['parent_pid']]
        return result
    events=[]
    for r in sorted(tracked.values(),key=depth,reverse=True):
        p=live(r)
        if p is None: continue
        p.terminate()
        _, alive=psutil.wait_procs([p],timeout=3)
        if alive and live(r): p.kill(); psutil.wait_procs([p],timeout=3)
        events.append({'identity':r,'after':'absent' if live(r) is None else 'still_alive'})
    return events


def occupied(exclude=()):
    for p in psutil.process_iter(['name','cmdline']):
        if p.pid in exclude: continue
        name=(p.info['name'] or '').lower()
        if 'jsb_host_gui_publish' in name: return ident(p.pid)
        if 'python' not in name: continue
        try:
            cmd=p.cmdline()
            for token in cmd:
                path=token.replace('\\','/').lower(); base=path.rsplit('/',1)[-1]
                if path.startswith('e:/ai_pilot/') and base.endswith('.py') and (
                    base.startswith(('train','benchmark','calibrate','launch_fresh','launch_pool')) or
                    (base in ('runner.py','launch_diagnostic.py') and any(v in cmd for v in ('run','worker','guard')))):
                    return ident(p.pid)
        except psutil.NoSuchProcess: pass
    return None


def frozen_sources():
    sources=bench.capture_sources(REPAIR)
    sources['diagnostic/launch_diagnostic.py']=bench.file_hash(__file__)
    sources['diagnostic/reference_report']=bench.file_hash(REFERENCE)
    sources['diagnostic/frozen_manifest']=bench.file_hash(SNAPSHOT/'manifest.json')
    return sources


def reference_cases():
    report=read(REFERENCE)
    if report['status']!='completed' or not report['benchmark_complete']:
        raise RuntimeError('Reference is not a completed comparison')
    cases=[c for c in report['cases'] if c['case']['opponent']=='rl' and
        c['case']['distance_ft']==6000 and c['case']['side']=='mirrored']
    if len(cases)!=2 or {c['case']['actor'] for c in cases}!={'guide','candidate'}:
        raise RuntimeError('Expected precisely one guide and one bank80 case')
    if len({c['initial_sha256'] for c in cases})!=1:
        raise RuntimeError('Original pair initial SHA differs')
    for case in cases:
        raw=read(REFERENCE.parent/'cases'/case['case_id']/'result.json')
        if bench.json_hash(raw['initial'])!=case['initial_sha256'] or raw['metrics']!=case['metrics']:
            raise RuntimeError('Original raw initial/final evidence differs')
    return cases


def preflight():
    if (ROOT/'STOP').exists() or (EXP/'STOP').exists(): raise RuntimeError('STOP exists')
    other=occupied((os.getpid(),))
    if other: raise RuntimeError('Another compute/Host workload is active: '+str(other))
    if psutil.virtual_memory().available<2*2**30 or psutil.disk_usage(str(ROOT)).free<10*2**30:
        raise RuntimeError('Requires at least 2GiB available RAM and 10GiB disk')
    manifest=read(SNAPSHOT/'manifest.json')
    for name,expected in manifest['source_sha256'].items():
        if bench.file_hash(SNAPSHOT/name)!=expected: raise RuntimeError('Frozen snapshot changed: '+name)
    report=read(REFERENCE); current=bench.capture_sources(REPAIR)
    if current!=report['source_sha256']: raise RuntimeError('Original runtime/controller/candidate/XML bytes changed')
    if bench.bundle_hashes(bench.DEFAULT_RED_BUNDLE)!=report['red_bundle_sha256']:
        raise RuntimeError('Frozen RL opponent changed')
    cases=reference_cases()
    return {'check_only':True,'simulator_started':False,'learner_started':False,'controller_change':False,
        'distance_ft':6000,'approximate_distance_m':1828.8,'side':'mirrored','seed':2026101311,
        'planned_cases':[c['case'] for c in cases],'same_saved_initial_sha256':cases[0]['initial_sha256'],
        'original_outcomes':{c['case']['actor']:c['outcome'] for c in cases},
        'original_overload_ticks':{c['case']['actor']:round(c['metrics']['over_9g_seconds']*60) for c in cases},
        'all_original_source_bytes_verified':True,'telemetry_hz':60,'columns':list(COLUMNS),
        'hard_wall_seconds':1200,'case_wall_seconds':300,'independent_guard_required':True,
        'quota_and_daily_budget_policy':'warnings only; explicit bounded replay, no new seeds',
        'actual_60hz_reproduction':'not run; validator must compare initial SHA, final metrics and exact counters',
        'source_sha256':frozen_sources()}


def worker(input_path):
    spec=read(input_path); folder=Path(input_path).parent
    if frozen_sources()!=spec['diagnostic_source_sha256']: raise RuntimeError('Diagnostic source drift')
    original_loader=bench.load_runtime
    with (folder/'telemetry_60hz.csv').open('w',encoding='utf-8',newline='') as output:
        writer=csv.DictWriter(output,fieldnames=COLUMNS); writer.writeheader()
        def logged_runtime(repair_root):
            runtime=original_loader(repair_root); Original=runtime.env.RepairDuel
            class TickLoggedDuel(Original):
                def step(self,action):
                    result=super().step(action); info=result[4]
                    obs=runtime.simulator_observation(self.fdm1,self.fdm2)
                    command=info['actual_action']; control=self.packet_controller
                    row={'tick':self.current_step,'simulation_seconds':self.current_step/60,
                        'controller_mode':info['controller_mode'],'guard_active':int(info['guard_active']),
                        'aileron':command[0],'elevator':command[1],'rudder':command[2],'throttle':command[3],
                        'signed_g':float(obs[14]),'abs_g':abs(float(obs[14])),
                        'overload_ticks':int(self.judge.over_g[0]),'altitude_m':float(obs[2])*.3048,
                        'cas_kts':float(obs[12])/1.6878098571011957,'tas_mps':float(obs[13])*.3048,
                        'roll_deg':float(obs[3]),'pitch_deg':float(obs[4]),'alpha_deg':float(obs[18]),
                        'p_rad_s':float(obs[9]),'q_rad_s':float(obs[10]),'r_rad_s':float(obs[11]),
                        'closing_mps':float(info['closing_mps']),'distance_m':float(info['distance']),
                        'blue_angle_deg_judge_only':float(info['blue_angle_deg']),
                        'bank_target':float(control.bank_target),'pitch_target':float(control.pitch_target),
                        'speed_target':float(control.speed_target)}
                    writer.writerow(row)
                    if self.current_step%60==0: output.flush()
                    return result
            runtime.env=SimpleNamespace(**{**vars(runtime.env),'RepairDuel':TickLoggedDuel})
            return runtime
        bench.load_runtime=logged_runtime
        try: return bench.run_worker(input_path)
        finally: bench.load_runtime=original_loader


def validate_rows(rows,steps,expected_overload):
    if len(rows)!=steps: raise RuntimeError('Missing 60Hz tick rows')
    count=0; events=[]
    for tick,row in enumerate(rows,1):
        if int(row['tick'])!=tick: raise RuntimeError('Missing/duplicate tick')
        if not all(math.isfinite(float(value)) for key,value in row.items() if key!='controller_mode'):
            raise RuntimeError('Nonfinite telemetry')
        if not math.isclose(float(row['simulation_seconds']),tick/60,abs_tol=1e-9): raise RuntimeError('Tick time mismatch')
        if abs(float(row['signed_g']))>9:
            count+=1; events.append(row)
        if int(row['overload_ticks'])!=count: raise RuntimeError('Exact overload counter mismatch')
        if any(not -1<=float(row[k])<=1 for k in ('aileron','elevator','rudder')) or not 0<=float(row['throttle'])<=1:
            raise RuntimeError('Illegal controls')
    if count!=expected_overload: raise RuntimeError('Overload count did not reproduce original')
    return events


def verify(folder):
    folder=Path(folder); launch=read(folder/'launch.json'); state=read(folder/'state.json')
    if state['status']!='completed' or live(state.get('supervisor')): raise RuntimeError('Replay not terminal')
    if frozen_sources()!=launch['source_sha256']: raise RuntimeError('Source bytes changed')
    results=[]
    for reference in reference_cases():
        case_folder=folder/'cases'/reference['case_id']; raw=read(case_folder/'result.json'); exit_record=read(case_folder/'exit.json')
        if exit_record['exit_code']!=0 or exit_record['wait_reason']!='exited': raise RuntimeError('Worker did not exit normally')
        if not raw['score_eligible'] or raw['status']!='completed' or raw['steps']!=reference['steps']:
            raise RuntimeError('Incomplete reproduction')
        if raw['initial_sha256']!=reference['initial_sha256'] or bench.json_hash(raw['initial'])!=reference['initial_sha256']:
            raise RuntimeError('Initial SHA did not reproduce original')
        if raw['outcome']!=reference['outcome']: raise RuntimeError('Final outcome did not reproduce')
        for key,value in reference['metrics'].items():
            if not math.isclose(raw['metrics'][key],value,rel_tol=0,abs_tol=1e-9): raise RuntimeError('Final metric differs: '+key)
        with (case_folder/'telemetry_60hz.csv').open(encoding='utf-8',newline='') as stream:
            reader=csv.DictReader(stream)
            if tuple(reader.fieldnames)!=COLUMNS: raise RuntimeError('60Hz schema differs')
            rows=list(reader)
        events=validate_rows(rows,raw['steps'],round(reference['metrics']['over_9g_seconds']*60))
        results.append({'actor':reference['case']['actor'],'initial_sha256':raw['initial_sha256'],
            'steps':raw['steps'],'overload_ticks':len(events),'overload_events':events,
            'peak_abs_g':max(float(r['abs_g']) for r in rows),
            'window_244_245_seconds':[r for r in rows if 244<=float(r['simulation_seconds'])<=245],
            'telemetry_sha256':bench.file_hash(case_folder/'telemetry_60hz.csv'),
            'acmi_sha256':bench.file_hash(case_folder/'duel.acmi')})
    report={'verified_reproduction':True,'distance_ft':6000,'approximate_distance_m':1828.8,
        'same_control_laws':True,'learner_started':False,'official_validation':False,'deployment_allowed':False,
        'source_sha256':launch['source_sha256'],'cases':results,'purpose':'locate original one-tick overload; not a new candidate'}
    bench.atomic_json(folder/'VERIFIED_REPRODUCTION.json',report)
    return report


def guard(folder):
    folder=Path(folder); launch=read(folder/'launch.json'); tracked={}
    bench.atomic_json(folder/'guard_status.json',{'status':'armed','identity':ident(os.getpid()),'deadline_epoch':launch['deadline_epoch']})
    while True:
        state=read(folder/'state.json')
        for name in ('supervisor','worker'):
            r=state.get(name)
            if r: tracked[r['pid']]=r
        for r in list(tracked.values()):
            p=live(r)
            if p:
                for c in p.children(recursive=True):
                    try: tracked[c.pid]=ident(c.pid)
                    except psutil.NoSuchProcess: pass
        reason=None
        if (folder/'STOP').exists() or (ROOT/'STOP').exists(): reason='stopped'
        elif time.time()>=launch['deadline_epoch']: reason='deadline'
        elif state['status'] in TERMINAL and live(state.get('supervisor')) is None: reason='terminal'
        elif state.get('supervisor') and live(state['supervisor']) is None: reason='supervisor_lost'
        if reason:
            events=cleanup(list(tracked.values()))
            bench.atomic_json(folder/'guard_status.json',{'status':'finished','reason':reason,'cleanup':events,
                'identity':ident(os.getpid()),'deadline_epoch':launch['deadline_epoch']})
            return
        time.sleep(.2)


def run(folder):
    folder=Path(folder); launch=read(folder/'launch.json'); state=read(folder/'state.json')
    state.update(status='running',supervisor=ident(os.getpid()))
    bench.atomic_json(folder/'state.json',state); child=None; owned=None; power=False
    try:
        with JobLock(ROOT/'learner.lock'):
            if os.name=='nt':
                import ctypes
                power=bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000001))
                if not power: raise RuntimeError('Cannot request temporary wake lock')
            for ref in reference_cases():
                if frozen_sources()!=launch['source_sha256']: raise RuntimeError('Source drift')
                if time.time()>=launch['deadline_epoch'] or (folder/'STOP').exists(): raise RuntimeError('Deadline/STOP')
                if psutil.virtual_memory().available<.5*2**30 or psutil.disk_usage(str(ROOT)).free<10*2**30: raise RuntimeError('Resource pressure')
                case_folder=folder/'cases'/ref['case_id']; case_folder.mkdir(parents=True,exist_ok=False)
                spec={'case':ref['case'],'out':str(folder),'repair_root':str(REPAIR),'max_steps':18000,
                    'case_seconds':300.,'bundle':None,'candidate_bundle_sha256':None,
                    'source_sha256':read(REFERENCE)['source_sha256'],
                    'red_bundle_sha256':read(REFERENCE)['red_bundle_sha256'],
                    'diagnostic_source_sha256':launch['source_sha256']}
                bench.atomic_json(case_folder/'input.json',spec)
                command=[str(PYTHON),'-B','-X','utf8',str(Path(__file__)),'worker','--input',str(case_folder/'input.json')]
                with (case_folder/'stdout.log').open('w',encoding='utf-8') as out,(case_folder/'stderr.log').open('w',encoding='utf-8') as err:
                    child=subprocess.Popen(command,stdout=out,stderr=err,cwd=ROOT,creationflags=NO_WINDOW,
                        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','PYTHONUTF8':'1'})
                    owned=ident(child.pid); state['worker']=owned; state['case_id']=ref['case_id']; bench.atomic_json(folder/'state.json',state)
                    reason=bench.wait_process(child,timeout_s=min(310,max(.01,launch['deadline_epoch']-time.time())),
                        stop_check=lambda:(folder/'STOP').exists() or (ROOT/'STOP').exists())
                    code=child.wait(timeout=5)
                bench.atomic_json(case_folder/'exit.json',{'exit_code':code,'wait_reason':reason,'identity':owned})
                child=None; state['worker']=None
                if code!=0 or reason!='exited': raise RuntimeError('Case incomplete: '+ref['case_id'])
            state['status']='completed'
    except BaseException as e:
        state.update(status='failed',error=repr(e))
    finally:
        if child is not None and child.poll() is None: cleanup([owned])
        if power:
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        state.update(worker=None,finished_epoch=time.time()); bench.atomic_json(folder/'state.json',state)
    return 0 if state['status']=='completed' else 1


def start():
    with JobLock(ROOT/'launch.lock'):
        preparation=preflight(); folder=EXP/('run_'+datetime.now(TAIPEI).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:4])
        folder.mkdir(parents=True,exist_ok=False); now=time.time()
        launch={'source_sha256':preparation['source_sha256'],'started_epoch':now,'deadline_epoch':now+1200,
            'planned_cases':preparation['planned_cases'],'telemetry_hz':60,'learner_started':False,
            'distance_ft':6000,'approximate_distance_m':1828.8,'reserved_seconds':1200}
        bench.atomic_json(folder/'launch.json',launch); bench.atomic_json(folder/'state.json',{'status':'preparing','supervisor':None,'worker':None})
        day=datetime.now(TAIPEI).strftime('%Y-%m-%d'); ledger_path=ROOT/'compute_budgets'/(day+'.json')
        ledger=read(ledger_path) if ledger_path.exists() else {'date_taipei':day,'reserved_hours':0.,'limit_hours':6.,'items':[]}
        ledger['reserved_hours']+=1/3; ledger['items'].append({'id':folder.name,'hours':1/3,'status':'reserved','kind':'observed_overload_60hz_replay','output':str(folder)})
        ledger['policy']='warning_only_hard_run_deadline_required'; bench.atomic_json(ledger_path,ledger)
        command=[str(PYTHON),'-B','-X','utf8',str(Path(__file__))]
        with (folder/'guard.log').open('w',encoding='utf-8') as out:
            watchdog=subprocess.Popen(command+['guard','--job',str(folder)],stdout=out,stderr=subprocess.STDOUT,cwd=ROOT,creationflags=NO_WINDOW)
        watchdog_id=ident(watchdog.pid); until=time.monotonic()+10
        while time.monotonic()<until:
            if (folder/'guard_status.json').exists() and read(folder/'guard_status.json')['status']=='armed': break
            if watchdog.poll() is not None: raise RuntimeError('Independent guard failed to arm')
            time.sleep(.1)
        else: cleanup([watchdog_id]); raise RuntimeError('Independent guard did not acknowledge')
        try:
            with (folder/'supervisor.log').open('w',encoding='utf-8') as out:
                supervisor=subprocess.Popen(command+['run','--job',str(folder)],stdout=out,stderr=subprocess.STDOUT,cwd=ROOT,creationflags=NO_WINDOW)
            supervisor_id=ident(supervisor.pid); state=read(folder/'state.json')
            if not state.get('supervisor'): state['supervisor']=supervisor_id; bench.atomic_json(folder/'state.json',state)
            bench.atomic_json(EXP/'latest.json',{'run':str(folder),'supervisor':supervisor_id,'guard':watchdog_id,'deadline_epoch':launch['deadline_epoch']})
            print(str(folder))
        except BaseException:
            (folder/'STOP').write_text('launch_failed',encoding='utf-8'); cleanup([watchdog_id]); raise


def main():
    parser=argparse.ArgumentParser(description='Exactly two 6000-ft mirrored cases; 60Hz telemetry only')
    parser.add_argument('action',nargs='?',default='check',choices=['check','start','run','guard','worker','verify'])
    parser.add_argument('--check-only',action='store_true'); parser.add_argument('--job',type=Path); parser.add_argument('--input',type=Path)
    args=parser.parse_args()
    if args.check_only or args.action=='check': print(json.dumps(preflight(),ensure_ascii=False,indent=2)); return 0
    if args.action=='start': start(); return 0
    if args.action=='worker': return worker(args.input)
    if args.action=='run': return run(args.job)
    if args.action=='guard': guard(args.job); return 0
    print(json.dumps(verify(args.job),ensure_ascii=False,indent=2)); return 0


if __name__=='__main__': raise SystemExit(main())
