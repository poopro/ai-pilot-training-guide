"""Two-case bank80 vs G-latch development smoke; no automatic deployment.

The independent guardian is the actual parent of the supervisor, and records
Popen.wait() exit codes even while the conversation is idle. Check is read only.
"""
from __future__ import annotations
import argparse
import ast
import copy
import csv
from datetime import datetime
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

EXP=Path(__file__).resolve().parent; ROOT=EXP.parents[1]
P1=ROOT/'experiments'/'overload_60hz'
REPRO=P1/'run_20261014_004750_fdbe'/'VERIFIED_REPRODUCTION.json'
ANALYSIS=REPRO.with_name('ANALYSIS.json')
spec=importlib.util.spec_from_file_location('frozen_p1_diagnostic',P1/'launch_diagnostic.py')
base=importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
bench=base.bench; PYTHON=base.PYTHON; REPAIR=base.REPAIR
original_preflight=base.preflight; original_cases=base.reference_cases
COLUMNS=base.COLUMNS+('g_guard_latched',)


def single_factor_check():
    original=(REPAIR/'controller.py').read_text(encoding='utf-8')
    candidate=(EXP/'safe_candidate.py').read_text(encoding='utf-8')
    def method(text,cls):
        node=next(n for n in ast.parse(text).body if isinstance(n,ast.ClassDef) and n.name==cls)
        return next(n for n in node.body if isinstance(n,ast.FunctionDef) and n.name=='command')
    old=method(original,'RepairController'); new=method(candidate,'GGuardLatchBank80')
    replacement=ast.parse('''if safety:
    if abs(o[14]) > 8.5:
        self.g_guard_latched = True
    elif abs(o[14]) < 8.0:
        self.g_guard_latched = False
if safety and self.g_guard_latched:
    elevator = max(elevator, -.08)
''').body
    matches=[i for i,n in enumerate(old.body) if isinstance(n,ast.If) and
        ast.unparse(n.test)=='safety and abs(o[14]) > 8.5']
    if len(matches)!=1: raise RuntimeError('Frozen G limiter structure differs')
    i=matches[0]; old.body[i:i+1]=replacement
    if ast.dump(old,include_attributes=False)!=ast.dump(new,include_attributes=False):
        raise RuntimeError('Candidate changed more than G-latch condition')
    return True


def planned_cases():
    original=next(c for c in original_cases() if c['case']['actor']=='candidate')
    result=[]
    for actor in ('guide','candidate'):
        row=copy.deepcopy(original); row['case']['actor']=actor
        row['case_id']=row['pair_key']+'_'+actor
        result.append(row)
    return result


def frozen_sources():
    result=bench.capture_sources(REPAIR)
    for label,path in {'smoke/safe_candidate.py':EXP/'safe_candidate.py','smoke/launch_smoke.py':Path(__file__),
        'diagnostic/frozen_launcher':P1/'launch_diagnostic.py','diagnostic/verified_reproduction':REPRO,
        'diagnostic/analysis':ANALYSIS,'diagnostic/reference_report':base.REFERENCE}.items():
        result[label]=bench.file_hash(path)
    return result


def preflight():
    # Source/record checks remain useful during a Host run. Only start is gated.
    original_occupied=base.occupied
    try:
        base.occupied=lambda exclude=():None
        prepared=original_preflight()
    finally: base.occupied=original_occupied
    reproduced=base.read(REPRO); analysis=base.read(ANALYSIS)
    if not reproduced['verified_reproduction'] or not analysis['verified_worker_reproduction']:
        raise RuntimeError('Original two-case reproduction has not been verified')
    single_factor_check()
    blocked=original_occupied((os.getpid(),))
    if blocked is None and (EXP/'latest.json').is_file():
        prior=base.read(EXP/'latest.json')
        if base.live(prior.get('guardian')):
            blocked=prior['guardian']
    prepared.update(planned_cases=[c['case'] for c in planned_cases()],
        baseline_control='frozen bank80, actor label guide is only a paired-slot alias',
        candidate_control='bank80 + G guard latch: >8.5 on; <8.0 off',
        original_guide_role='description only; no new fair guide comparison',
        original_overload_ticks={'unmodified_bank80':1,'new_candidate':'not measured'},
        same_saved_initial_sha256=planned_cases()[0]['initial_sha256'],
        only_control_factor_verified_by_ast=True,columns=list(COLUMNS),
        source_sha256=frozen_sources(),ready_to_start=blocked is None,blocking_workload=blocked,
        parent_exit_receipt='guardian Popen.wait, not inferred from state',
        actual_60hz_reproduction='original complete; no original diagnostic rerun; new candidate not run')
    return prepared


def load_candidate():
    sys.path.insert(0,str(REPAIR)); sys.path.insert(0,str(base.FRESH))
    path=EXP/'safe_candidate.py'; spec=importlib.util.spec_from_file_location('g_latch_candidate',path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def worker(input_file):
    specification=base.read(input_file); folder=Path(input_file).parent
    if frozen_sources()!=specification['diagnostic_source_sha256']: raise RuntimeError('Source drift')
    original_loader=bench.load_runtime
    candidate_module=load_candidate()
    import candidate as frozen_candidate
    OriginalBank80=frozen_candidate.Bank80Controller
    frozen_candidate.Bank80Controller=candidate_module.GGuardLatchBank80
    with (folder/'telemetry_60hz.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=COLUMNS); writer.writeheader()
        def logged_runtime(repair_root):
            runtime=original_loader(repair_root); Original=runtime.env.RepairDuel
            runtime.RepairController=OriginalBank80  # paired baseline is Bank80, not repair guide
            class TickLoggedDuel(Original):
                def step(self,action):
                    result=super().step(action); info=result[4]
                    obs=runtime.simulator_observation(self.fdm1,self.fdm2); command=info['actual_action']; control=self.packet_controller
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
                        'speed_target':float(control.speed_target),'g_guard_latched':int(getattr(control,'g_guard_latched',False))}
                    writer.writerow(row)
                    if self.current_step%60==0: stream.flush()
                    return result
            runtime.env=SimpleNamespace(**{**vars(runtime.env),'RepairDuel':TickLoggedDuel})
            return runtime
        bench.load_runtime=logged_runtime
        try: code=bench.run_worker(input_file)
        finally:
            bench.load_runtime=original_loader; frozen_candidate.Bank80Controller=OriginalBank80
    raw=base.read(folder/'result.json')
    raw.update(smoke_control='frozen_bank80' if raw['case']['actor']=='guide' else 'bank80_g_guard_latch_8_5_8_0',
        candidate_factor='g_guard_release_hysteresis_only' if raw['case']['actor']=='candidate' else None,
        paired_baseline_is_repair_guide=False)
    bench.atomic_json(folder/'result.json',raw)
    return code


def run(folder):
    # Reuse the frozen process lifecycle, not its old guide-v-bank80 case plan.
    folder=Path(folder); until=time.monotonic()+5
    while not (folder/'guard_status.json').is_file() and time.monotonic()<until:
        time.sleep(.05)
    guarded=base.read(folder/'guard_status.json')
    if guarded['status']!='armed' or base.live(guarded.get('identity')) is None:
        raise RuntimeError('No live independent guardian; refusing simulator launch')
    if base.occupied((os.getpid(),guarded['identity']['pid'])):
        raise RuntimeError('Host/other workload started during launch; refusing parallel FDM')
    return base.run(folder)


def guardian(folder):
    folder=Path(folder); launch=base.read(folder/'launch.json'); tracked=[]; supervisor=None; supervisor_id=None
    receipt={'actual_exit_code':None,'wait_return_observed':False}
    try:
        if frozen_sources()!=launch['source_sha256']: raise RuntimeError('Source drift before supervisor launch')
        command=[str(PYTHON),'-B','-X','utf8',str(Path(__file__)),'run','--job',str(folder)]
        with (folder/'supervisor.log').open('w',encoding='utf-8') as out:
            supervisor=subprocess.Popen(command,stdout=out,stderr=subprocess.STDOUT,cwd=ROOT,creationflags=base.NO_WINDOW,
                env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','PYTHONUTF8':'1'})
        supervisor_id=base.ident(supervisor.pid); tracked.append(supervisor_id)
        state=base.read(folder/'state.json')
        if not state.get('supervisor'): state['supervisor']=supervisor_id; bench.atomic_json(folder/'state.json',state)
        bench.atomic_json(folder/'guard_status.json',{'status':'armed','identity':base.ident(os.getpid()),'supervisor':supervisor_id})
        reason='exited'
        while supervisor.poll() is None:
            state=base.read(folder/'state.json')
            if state.get('worker') and state['worker'] not in tracked: tracked.append(state['worker'])
            pressure=psutil.virtual_memory().available<.5*2**30 or psutil.disk_usage(str(ROOT)).free<10*2**30
            excludes=(os.getpid(),supervisor.pid)+tuple(r['pid'] for r in tracked)
            overlapping=base.occupied(excludes)
            if (folder/'STOP').exists() or (ROOT/'STOP').exists() or time.time()>=launch['deadline_epoch'] or pressure or overlapping:
                reason='workload_overlap' if overlapping else 'resource_pressure' if pressure else 'stopped' if (folder/'STOP').exists() or (ROOT/'STOP').exists() else 'deadline'
                (folder/'STOP').write_text(reason,encoding='utf-8')
                try: supervisor.wait(timeout=3)
                except subprocess.TimeoutExpired: base.cleanup(tracked)
                break
            time.sleep(.2)
        code=supervisor.wait(timeout=10)
        receipt.update(actual_exit_code=code,wait_return_observed=True,identity=supervisor_id,wait_reason=reason)
    except BaseException as error:
        receipt['error']=repr(error)
        base.cleanup(tracked)
        if supervisor is not None:
            try: receipt.update(actual_exit_code=supervisor.wait(timeout=10),wait_return_observed=True,identity=supervisor_id,wait_reason='guardian_error')
            except BaseException as wait_error: receipt['wait_error']=repr(wait_error)
    finally:
        cleaned=base.cleanup(tracked)
        bench.atomic_json(folder/'supervisor_exit.json',receipt)
        bench.atomic_json(folder/'guard_status.json',{'status':'finished','identity':base.ident(os.getpid()),
            'cleanup':cleaned,'parent_receipt':receipt,'deadline_epoch':launch['deadline_epoch']})
    return 0 if receipt.get('actual_exit_code')==0 else 1


def start():
    with base.JobLock(ROOT/'launch.lock'):
        prepared=preflight()
        if not prepared['ready_to_start']: raise RuntimeError('Wait for Host/other workload terminal; no parallel FDM')
        folder=EXP/('run_'+datetime.now(base.TAIPEI).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:4]); folder.mkdir()
        now=time.time(); launch={'source_sha256':prepared['source_sha256'],'started_epoch':now,'deadline_epoch':now+1200,
            'planned_cases':prepared['planned_cases'],'distance_ft':6000,'approximate_distance_m':1828.8,
            'learner_started':False,'telemetry_hz':60,'reserved_seconds':1200,'purpose':'one-factor safety smoke'}
        bench.atomic_json(folder/'launch.json',launch); bench.atomic_json(folder/'state.json',{'status':'preparing','supervisor':None,'worker':None})
        day=datetime.now(base.TAIPEI).strftime('%Y-%m-%d'); ledger_path=ROOT/'compute_budgets'/(day+'.json')
        ledger=base.read(ledger_path) if ledger_path.exists() else {'date_taipei':day,'reserved_hours':0.,'limit_hours':6.,'items':[]}
        ledger['reserved_hours']+=1/3; ledger['items'].append({'id':folder.name,'hours':1/3,'status':'reserved','kind':'g_latch_two_case_smoke','output':str(folder)})
        ledger['policy']='warning_only_hard_run_deadline_required'; bench.atomic_json(ledger_path,ledger)
        with (folder/'guardian.log').open('w',encoding='utf-8') as out:
            parent=subprocess.Popen([str(PYTHON),'-B','-X','utf8',str(Path(__file__)),'guard','--job',str(folder)],
                stdout=out,stderr=subprocess.STDOUT,cwd=ROOT,creationflags=base.NO_WINDOW,
                env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','PYTHONUTF8':'1'})
        parent_id=base.ident(parent.pid); until=time.monotonic()+10
        while time.monotonic()<until:
            if (folder/'guard_status.json').exists():
                guarded=base.read(folder/'guard_status.json')
                if guarded['status']=='armed':
                    bench.atomic_json(EXP/'latest.json',{'run':str(folder),'guardian':parent_id,'supervisor':guarded['supervisor'],'deadline_epoch':launch['deadline_epoch']})
                    print(str(folder)); return
            if parent.poll() is not None: raise RuntimeError('Independent guardian launch failed')
            time.sleep(.1)
        (folder/'STOP').write_text('launch_ack_timeout',encoding='utf-8')
        try: parent.wait(timeout=5)
        except subprocess.TimeoutExpired: base.cleanup([parent_id])
        raise RuntimeError('Independent guardian did not acknowledge; launch stopped')


def verify(folder):
    folder=Path(folder); launch=base.read(folder/'launch.json'); state=base.read(folder/'state.json')
    receipt=base.read(folder/'supervisor_exit.json'); guarded=base.read(folder/'guard_status.json')
    if not receipt['wait_return_observed'] or receipt['actual_exit_code']!=0 or receipt['wait_reason']!='exited':
        raise RuntimeError('No actual successful parent exit receipt')
    if state['status']!='completed' or base.live(state.get('supervisor')) or guarded['status']!='finished':
        raise RuntimeError('Smoke not terminal')
    if frozen_sources()!=launch['source_sha256']: raise RuntimeError('Source drift')
    comparison=[]
    for case in planned_cases():
        path=folder/'cases'/case['case_id']; raw=base.read(path/'result.json'); exit_receipt=base.read(path/'exit.json')
        if exit_receipt['exit_code']!=0 or exit_receipt['wait_reason']!='exited' or not raw['score_eligible']:
            raise RuntimeError('No actual successful complete worker exit')
        if raw['initial_sha256']!=case['initial_sha256'] or bench.json_hash(raw['initial'])!=case['initial_sha256']:
            raise RuntimeError('Pair initial SHA mismatch')
        with (path/'telemetry_60hz.csv').open(encoding='utf-8',newline='') as stream:
            reader=csv.DictReader(stream)
            if tuple(reader.fieldnames)!=COLUMNS: raise RuntimeError('Telemetry columns changed')
            rows=list(reader)
        events=base.validate_rows(rows,raw['steps'],round(raw['metrics']['over_9g_seconds']*60))
        if raw['case']['actor']=='guide':
            if raw['outcome']!=case['outcome'] or raw['steps']!=case['steps']: raise RuntimeError('Frozen bank80 did not reproduce')
            for key,value in case['metrics'].items():
                if not math.isclose(raw['metrics'][key],value,rel_tol=0,abs_tol=1e-9): raise RuntimeError('Frozen bank80 metric changed: '+key)
        else:
            previous_g=raw['initial']['blue_own20_audit_only'][14]; latched=False
            for row in rows:
                if abs(previous_g)>8.5: latched=True
                elif abs(previous_g)<8.: latched=False
                if int(row['g_guard_latched'])!=int(latched): raise RuntimeError('G-latch state differs from previous-tick G')
                previous_g=float(row['signed_g'])
        comparison.append({'actor':raw['case']['actor'],'control':raw['smoke_control'],'initial_sha256':raw['initial_sha256'],
            'metrics':raw['metrics'],'peak_abs_g':max(float(r['abs_g']) for r in rows),'overload_events':events,
            'latched_ticks':sum(int(r['g_guard_latched']) for r in rows),'telemetry_sha256':bench.file_hash(path/'telemetry_60hz.csv')})
    report={'verified_two_case_smoke':True,'actual_parent_exit_code':receipt['actual_exit_code'],'candidate_factor':'g_guard_latch_only',
        'baseline':'frozen_bank80','original_guide':'description only, not a new pair','cases':comparison,
        'source_sha256':launch['source_sha256'],'deployment_allowed':False,'official_validation':False,
        'next_action':'Review one-case safety evidence before any expanded new-seed testing; never infer tournament win rate'}
    bench.atomic_json(folder/'VERIFIED_SMOKE.json',report); return report


# The frozen lifecycle is called with this new plan/tool; frozen source files
# themselves remain byte-for-byte unchanged.
base.EXP=EXP; base.__file__=str(Path(__file__)); base.reference_cases=planned_cases; base.frozen_sources=frozen_sources


def main():
    parser=argparse.ArgumentParser(description='Two-case frozen bank80 vs G-latch smoke; no learner')
    parser.add_argument('action',nargs='?',default='check',choices=['check','start','run','guard','worker','verify'])
    parser.add_argument('--check-only',action='store_true'); parser.add_argument('--job',type=Path); parser.add_argument('--input',type=Path)
    args=parser.parse_args()
    if args.check_only or args.action=='check': print(json.dumps(preflight(),ensure_ascii=False,indent=2)); return 0
    if args.action=='start': start(); return 0
    if args.action=='run': return run(args.job)
    if args.action=='guard': return guardian(args.job)
    if args.action=='worker': return worker(args.input)
    print(json.dumps(verify(args.job),ensure_ascii=False,indent=2)); return 0


if __name__=='__main__': raise SystemExit(main())
