"""Locked 24-case fresh development: true repair guide vs fixed Bank80/G latch.

No learner, original-diagnostic rerun, holdout use or automatic deployment.
The validated smoke guardian owns the supervisor's actual Popen wait handle.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time
import uuid

EXP=Path(__file__).resolve().parent; ROOT=EXP.parents[1]
SMOKE=ROOT/'experiments'/'g_latch_smoke'
SMOKE_RUN=SMOKE/'run_20261014_145019_d9db'
MANIFEST=EXP/'MANIFEST.json'; SEED_BASE=2026101400
spec=importlib.util.spec_from_file_location('validated_g_latch_smoke',SMOKE/'launch_smoke.py')
engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
base=engine.base;bench=engine.bench;REPAIR=engine.REPAIR;PYTHON=engine.PYTHON
original_worker=engine.worker
sys.path.insert(0,str(base.FRESH))
from budget import used_seeds


def planned_cases():
    return [{'case':asdict(c),'case_id':c.case_id,'pair_key':c.pair_key}
        for c in bench.plan_cases(1,SEED_BASE,'both',True)]


def requested_seeds():
    return sorted({c['case']['seed'] for c in planned_cases()})


def trial_id():
    return 'g_latch_development_'+str(SEED_BASE)+'_'+bench.file_hash(EXP/'safe_candidate.py')[:12]


def source_hashes():
    hashes=bench.capture_sources(REPAIR)
    for key,path in {'development/launcher':Path(__file__),'development/candidate':EXP/'safe_candidate.py',
        'helpers/frozen_smoke_launcher':SMOKE/'launch_smoke.py',
        'helpers/frozen_diagnostic_launcher':base.P1/'launch_diagnostic.py' if hasattr(base,'P1') else ROOT/'experiments'/'overload_60hz'/'launch_diagnostic.py',
        'evidence/verified_smoke':SMOKE_RUN/'VERIFIED_SMOKE.json',
        'evidence/smoke_comparison':SMOKE_RUN/'COMPARISON.json',
        'evidence/original_reproduction':engine.REPRO,'evidence/original_analysis':engine.ANALYSIS}.items():
        hashes[key]=bench.file_hash(path)
    return hashes


def check_seed_ownership(registry,allow_prepared=False):
    name=trial_id(); owned=registry.get('trials',{}).get(name)
    others={**registry,'trials':{k:v for k,v in registry.get('trials',{}).items() if k!=name}}
    observed,holdout=used_seeds(others)
    if set(requested_seeds())&(observed|holdout): raise RuntimeError('New development seed collides with observed/trial/holdout')
    if owned:
        if not allow_prepared or owned['status']!='prepared_not_run' or owned['seeds']!=requested_seeds():
            raise RuntimeError('Prepared seeds have already been attempted or changed')
    elif allow_prepared:
        raise RuntimeError('Seed preparation ownership missing')
    return True


def pure_controls():
    """No simulator is constructed; return the two explicit frozen classes."""
    candidate=engine.load_candidate()
    from controller import RepairController
    return RepairController,candidate.GGuardLatchBank80


def frozen_sources():
    manifest=base.read(MANIFEST)
    current=source_hashes()
    if current!=manifest['source_sha256']: raise RuntimeError('Prepared development sources changed')
    return current


def readiness():
    blocked=base.occupied((os.getpid(),))
    if blocked is None and (EXP/'latest.json').is_file():
        previous=base.read(EXP/'latest.json')
        if base.live(previous.get('guardian')):blocked=previous['guardian']
    return blocked


def preflight(remaining_percent=None):
    manifest=base.read(MANIFEST);frozen_sources();engine.single_factor_check()
    check_seed_ownership(base.read(ROOT/'seed_registry.json'),True)
    if (ROOT/'STOP').exists() or (EXP/'STOP').exists():raise RuntimeError('STOP exists')
    import psutil
    if psutil.virtual_memory().available<2*2**30 or psutil.disk_usage(str(ROOT)).free<10*2**30:
        raise RuntimeError('Needs available RAM>=2GiB and disk>=10GiB')
    if bench.bundle_hashes(bench.DEFAULT_RED_BUNDLE)!=manifest['red_bundle_sha256']:raise RuntimeError('Frozen red model changed')
    blocked=readiness();warnings=[]
    if remaining_percent is not None and remaining_percent<=10:warnings.append('Codex usage remaining <=10%; warning only')
    day=datetime.now(base.TAIPEI).strftime('%Y-%m-%d');ledger_path=ROOT/'compute_budgets'/(day+'.json')
    prior=base.read(ledger_path)['reserved_hours'] if ledger_path.exists() else 0.
    if prior+40/60>6:warnings.append('Daily reservations exceed6h; warning only; this run remains bounded40min')
    return {'check_only':True,'simulator_started':False,'learner_started':False,'ready_to_start':blocked is None,
        'blocking_workload':blocked,'planned_cases':24,'pairs':12,'fresh_development_seed_base':SEED_BASE,
        'seeds':requested_seeds(),'seed_registry_verified':True,'holdout_used':False,
        'baseline':'pure repair_guide, no Bank80 alias','candidate':'fixed Bank80 with G latch >8.5 on/<8.0 off',
        'controller_change_from_smoke':False,'source_sha_verified':True,'source_sha256':manifest['source_sha256'],
        'initial_fairness':'same full initial SHA required for every pair after simulation; not claimed before run',
        'telemetry_hz':60,'max_wall_seconds':2400,'case_seconds':300,'warnings':warnings,
        'parent_worker_exit_receipts_required':True,'gate_policy':manifest['gate_policy'],
        'hypothesis_limit':manifest['hypothesis_limit']}


def prepare():
    with base.JobLock(ROOT/'launch.lock'):
        if MANIFEST.exists():raise RuntimeError('Preparation already frozen; use check-only')
        registry=base.read(ROOT/'seed_registry.json');check_seed_ownership(registry)
        if bench.file_hash(EXP/'safe_candidate.py')!=bench.file_hash(SMOKE/'safe_candidate.py'):
            raise RuntimeError('Candidate differs from validated smoke bytes')
        proven=base.read(SMOKE_RUN/'VERIFIED_SMOKE.json')
        if not proven['verified_two_case_smoke'] or proven['actual_parent_exit_code']!=0:
            raise RuntimeError('Smoke actual exits/evidence not verified')
        for key,value in bench.capture_sources(REPAIR).items():
            if proven['source_sha256'].get(key)!=value:
                raise RuntimeError('Runtime/controller/XML differs from verified smoke: '+key)
        if bench.bundle_hashes(bench.DEFAULT_RED_BUNDLE)!=base.read(base.REFERENCE)['red_bundle_sha256']:
            raise RuntimeError('Red bundle differs from original verified reference')
        engine.single_factor_check()
        gate_policy={'required_complete_cases':24,'required_matched_pairs':12,'case_horizon_ticks':18000,
            'complete_or_legal_terminal_only':True,'real_parent_and_worker_exit0':True,
            'same_source_red_and_initial_sha':True,'candidate_over9g_ticks_required':0,
            'per_opponent_kills_no_regression':True,'per_opponent_deaths_crashes_overg_no_regression':True,
            'performance':'kills increase, or equal kills with mean attack>=1.2x and improvement>=0.25s',
            'altitude':'Every paired minimum-altitude regression over1e-6m is explicit safety-review pending',
            'automatic_deployment':False,'official_win_probability':False}
        manifest={'format':'g_latch_fresh_development_preparation_v1','status':'prepared_not_run',
            'source_sha256':source_hashes(),'red_bundle_sha256':bench.bundle_hashes(bench.DEFAULT_RED_BUNDLE),
            'seed_base':SEED_BASE,'seeds':requested_seeds(),'seed_role':'prepared_fresh_development_not_holdout',
            'trial_id':trial_id(),'planned_cases':planned_cases(),'max_wall_seconds':2400,
            'baseline_class':'repair_v1.controller.RepairController','candidate_class':'GGuardLatchBank80',
            'guide_alias':False,'candidate_actor_policy_used':False,'gate_policy':gate_policy,
            'hypothesis_limit':'Smoke first command divergence tick9505/158.4167s in recover, before244s event. Same-initial whole-round zero overG only; attack fell26.44% and min altitude fell0.6002m vs unmodified Bank80. New24 compares fixed combined candidate to pure repair_guide; no claim of a local one-tick fix or tournament strength.'}
        registry.setdefault('trials',{})[trial_id()]={'seeds':requested_seeds(),'status':'prepared_not_run',
            'seed_role':'prepared_fresh_development_not_holdout','preparation':str(MANIFEST)}
        bench.atomic_json(MANIFEST,manifest);bench.atomic_json(ROOT/'seed_registry.json',registry)
        print(json.dumps({'prepared_not_run':True,'manifest':str(MANIFEST),'seed_base':SEED_BASE,'seeds':requested_seeds(),'planned_cases':24},ensure_ascii=False))


def worker(input_file):
    # Keep the tested 60Hz recorder, but explicitly select pure guide as baseline.
    # Preload the candidate while its true Bank80 parent is still registered.
    candidate_module=engine.load_candidate();guide,candidate_class=pure_controls()
    import candidate as frozen_bank80
    OriginalBank80=frozen_bank80.Bank80Controller;original_load=engine.load_candidate
    engine.load_candidate=lambda:candidate_module
    frozen_bank80.Bank80Controller=guide
    try:code=original_worker(input_file)
    finally:
        engine.load_candidate=original_load;frozen_bank80.Bank80Controller=OriginalBank80
    path=Path(input_file).parent/'result.json';raw=base.read(path)
    raw.update(smoke_control='pure_repair_guide' if raw['case']['actor']=='guide' else 'fixed_bank80_G_latch',
        paired_baseline_is_repair_guide=True,candidate_factor='fixed_bank80_G_latch' if raw['case']['actor']=='candidate' else None,
        seed_role='fresh_development_not_holdout')
    bench.atomic_json(path,raw);return code


def gates(rows,summary):
    totals=summary['totals'];guide=totals['guide'];candidate=totals['candidate']
    per_opponent={};altitude=[]
    for opponent in ('rule','rl'):
        selected=[r for r in rows if r['case']['opponent']==opponent]
        group={}
        for arm in ('guide','candidate'):
            arm_rows=[r for r in selected if r['case']['actor']==arm]
            group[arm]={k:sum(r['metrics'][k] for r in arm_rows) for k in bench.METRIC_DIRECTIONS if k!='min_altitude_m'}
            group[arm].update(cases=len(arm_rows),min_altitude_m=min(r['metrics']['min_altitude_m'] for r in arm_rows),
                mean_attack_seconds=sum(r['metrics']['attack_seconds'] for r in arm_rows)/len(arm_rows))
        per_opponent[opponent]=group
    matched={}
    for row in rows:matched.setdefault(row['pair_key'],{})[row['case']['actor']]=row
    for key,pair in matched.items():
        delta=pair['candidate']['metrics']['min_altitude_m']-pair['guide']['metrics']['min_altitude_m']
        if delta < -1e-6:altitude.append({'pair_key':key,'delta_min_altitude_m':delta})
    safety=candidate['over_9g_seconds']==0 and all(
        group['candidate']['kills']>=group['guide']['kills'] and
        all(group['candidate'][k]<=group['guide'][k] for k in ('deaths','own_crashes','over_9g_seconds'))
        for group in per_opponent.values())
    gain=candidate['kills']>guide['kills'] or (candidate['kills']==guide['kills'] and
        candidate['mean_attack_seconds']>=guide['mean_attack_seconds']*1.2 and
        candidate['mean_attack_seconds']-guide['mean_attack_seconds']>=.25)
    return {'gate':'reject_candidate' if not safety or not gain else 'metric_pass_safety_review_pending' if altitude else 'development_pass_review_pending',
        'safety_pass':safety,'performance_pass':gain,'by_opponent':per_opponent,
        'paired_altitude_regressions':altitude,'deployment_allowed':False,'official_win_probability':False}


def verify(folder):
    import csv
    folder=Path(folder);launch=base.read(folder/'launch.json');state=base.read(folder/'state.json')
    receipt=base.read(folder/'supervisor_exit.json');guardian=base.read(folder/'guard_status.json')
    if receipt.get('actual_exit_code')!=0 or not receipt.get('wait_return_observed') or receipt.get('wait_reason')!='exited':raise RuntimeError('Actual parent exit0 required')
    if state['status']!='completed' or guardian['status']!='finished' or base.live(state.get('supervisor')):raise RuntimeError('Not terminal')
    if frozen_sources()!=launch['source_sha256']:raise RuntimeError('Source drift')
    results=[]
    for case in planned_cases():
        path=folder/'cases'/case['case_id'];raw=base.read(path/'result.json');actual_exit=base.read(path/'exit.json');specification=base.read(path/'input.json')
        if actual_exit['exit_code']!=0 or actual_exit['wait_reason']!='exited' or raw['status']!='completed' or not raw['score_eligible']:raise RuntimeError('Worker partial/failure')
        if raw['case']!=case['case'] or raw['case_id']!=case['case_id'] or raw['steps']!=18000 and raw['stop_reason']!='legal_termination':raise RuntimeError('Case plan/horizon differs')
        if raw['initial_sha256']!=bench.json_hash(raw['initial']):raise RuntimeError('Initial evidence hash mismatch')
        if specification['source_sha256']!=base.read(base.REFERENCE)['source_sha256'] or specification['diagnostic_source_sha256']!=launch['source_sha256']:raise RuntimeError('Worker source differs')
        if specification['red_bundle_sha256']!=base.read(MANIFEST)['red_bundle_sha256'] or raw['actor_policy_used']:raise RuntimeError('Opponent or hidden actor differs')
        with (path/'telemetry_60hz.csv').open(encoding='utf-8',newline='') as stream:
            reader=csv.DictReader(stream)
            if tuple(reader.fieldnames)!=engine.COLUMNS:raise RuntimeError('60Hz schema differs')
            telemetry=list(reader)
        base.validate_rows(telemetry,raw['steps'],round(raw['metrics']['over_9g_seconds']*60))
        if not (path/'duel.acmi').is_file() or (path/'duel.acmi').stat().st_size<100:raise RuntimeError('ACMI missing')
        if not all(math.isfinite(float(v)) for v in raw['metrics'].values()):raise RuntimeError('Nonfinite metric')
        expected='pure_repair_guide' if raw['case']['actor']=='guide' else 'fixed_bank80_G_latch'
        if raw['smoke_control']!=expected or not raw['paired_baseline_is_repair_guide']:raise RuntimeError('Hidden guide alias')
        raw.update(worker_exit_code=actual_exit['exit_code'],artifact_sha256={name:bench.file_hash(path/name) for name in ('result.json','telemetry_60hz.csv','telemetry.csv','duel.acmi','exit.json')})
        results.append(raw)
    summary=bench.summarize(results,bench.plan_cases(1,SEED_BASE,'both',True),True)
    if not summary['complete'] or summary['paired_completed']!=12:raise RuntimeError('Not24 complete cases/12 matched initial SHA pairs')
    decision=gates(results,summary)
    report={'format':'g_latch_fresh_development_verified_v1','verified_comparison':True,'seed_role':'fresh_development_not_holdout',
        'actual_parent_exit_code':0,'eligible_cases':24,'matched_pairs':12,'source_sha256':launch['source_sha256'],
        'baseline':'pure_repair_guide','candidate':'fixed_bank80_G_latch','guide_alias':False,
        'summary':summary,'cases':results,**decision,'hypothesis_limit':base.read(MANIFEST)['hypothesis_limit']}
    bench.atomic_json(folder/'VERIFIED_DEVELOPMENT.json',report);return report


def start(remaining_percent=None):
    with base.JobLock(ROOT/'launch.lock'):
        prepared=preflight(remaining_percent)
        if not prepared['ready_to_start']:raise RuntimeError('Wait for Host/other workload terminal; no parallel FDM')
        folder=EXP/('run_'+datetime.now(base.TAIPEI).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:4]);folder.mkdir()
        now=time.time();launch={'source_sha256':prepared['source_sha256'],'started_epoch':now,'deadline_epoch':now+2400,
            'planned_cases':[c['case'] for c in planned_cases()],'reserved_seconds':2400,'learner_started':False,
            'telemetry_hz':60,'trial_id':trial_id(),'warnings':prepared['warnings'],'baseline':'pure_repair_guide','candidate':'fixed_bank80_G_latch'}
        bench.atomic_json(folder/'launch.json',launch);bench.atomic_json(folder/'state.json',{'status':'preparing','supervisor':None,'worker':None})
        registry=base.read(ROOT/'seed_registry.json');registry['trials'][trial_id()].update(status='attempted',output=str(folder),seed_role='fresh_development_attempted_not_holdout')
        bench.atomic_json(ROOT/'seed_registry.json',registry)
        day=datetime.now(base.TAIPEI).strftime('%Y-%m-%d');ledger_path=ROOT/'compute_budgets'/(day+'.json')
        ledger=base.read(ledger_path) if ledger_path.exists() else {'date_taipei':day,'reserved_hours':0.,'daily_limit_hours':6.,'items':[]}
        ledger['reserved_hours']+=40/60;ledger['items'].append({'id':trial_id(),'hours':40/60,'status':'reserved','output':str(folder)})
        ledger['policy']='warning_only_hard_run_deadline_required';bench.atomic_json(ledger_path,ledger)
        with (folder/'guardian.log').open('w',encoding='utf-8') as output:
            guardian=engine.subprocess.Popen([str(PYTHON),'-B','-X','utf8',str(Path(__file__)),'guard','--job',str(folder)],
                stdout=output,stderr=engine.subprocess.STDOUT,cwd=ROOT,creationflags=base.NO_WINDOW,
                env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','PYTHONUTF8':'1'})
        identity=base.ident(guardian.pid);until=time.monotonic()+10
        while time.monotonic()<until:
            if (folder/'guard_status.json').is_file():
                guarded=base.read(folder/'guard_status.json')
                if guarded['status']=='armed':
                    bench.atomic_json(EXP/'latest.json',{'run':str(folder),'guardian':identity,'supervisor':guarded['supervisor'],'deadline_epoch':launch['deadline_epoch']});print(str(folder));return
            if guardian.poll() is not None:raise RuntimeError('Independent guardian failed')
            time.sleep(.1)
        (folder/'STOP').write_text('launch_ack_timeout',encoding='utf-8')
        try:guardian.wait(timeout=5)
        except engine.subprocess.TimeoutExpired:base.cleanup([identity])
        raise RuntimeError('Guardian acknowledgement timeout')


# Bind only process-local helpers. All original files remain frozen on disk.
engine.EXP=EXP;engine.__file__=str(Path(__file__));engine.frozen_sources=frozen_sources
base.EXP=EXP;base.__file__=str(Path(__file__));base.reference_cases=planned_cases;base.frozen_sources=frozen_sources


def main():
    parser=argparse.ArgumentParser(description='24 fresh development cases; true guide vs fixed G-latch candidate')
    parser.add_argument('action',nargs='?',default='check',choices=['prepare','check','start','run','guard','worker','verify'])
    parser.add_argument('--check-only',action='store_true');parser.add_argument('--job',type=Path);parser.add_argument('--input',type=Path);parser.add_argument('--remaining-percent',type=float)
    args=parser.parse_args()
    if args.action=='prepare':prepare();return 0
    if args.check_only or args.action=='check':print(json.dumps(preflight(args.remaining_percent),ensure_ascii=False,indent=2));return 0
    if args.action=='start':start(args.remaining_percent);return 0
    if args.action=='run':return engine.run(args.job)
    if args.action=='guard':return engine.guardian(args.job)
    if args.action=='worker':return worker(args.input)
    print(json.dumps(verify(args.job),ensure_ascii=False,indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
