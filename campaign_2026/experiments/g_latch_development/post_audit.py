"""Independent terminal-only evidence audit. Never starts JSBSim or a learner.

This file is outside the running source freeze. Preserve the original verifier
and its output; this audit adds stronger checks and an independent result.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime,timezone
import importlib.util
import json
import math
from pathlib import Path
import sys

EXP=Path(__file__).resolve().parent
sys.path.insert(0,str(EXP))
import launch_development as dev
EARLY={'kill','shot_down','own_crash','enemy_crash','mutual_crash','simultaneous_hit'}


def need(value,message):
    if not value:raise RuntimeError(message)


def integer(value,label):
    need(type(value) is int,label+' must be a JSON integer')
    return value


def legal_terminal(raw):
    steps=integer(raw['steps'],'steps')
    need(1<=steps<=18000,'steps outside1..18000')
    need(raw.get('status')=='completed' and raw.get('score_eligible') is True and
         raw.get('full_round_completed') is True,'partial/ineligible round')
    outcome=raw['outcome'];reason=raw['stop_reason']
    if outcome in EARLY:need(reason=='legal_termination','early outcome missing legal termination')
    else:need(outcome=='timeout' and reason=='round_horizon' and steps==18000,'invalid full horizon/outcome')
    metrics=raw['metrics']
    expected={'kills':int(outcome=='kill'),'deaths':int(outcome in ('shot_down','simultaneous_hit')),
        'own_crashes':int(outcome in ('own_crash','mutual_crash')),
        'enemy_crashes':int(outcome in ('enemy_crash','mutual_crash')),
        'survival':int(outcome not in ('own_crash','mutual_crash','shot_down','simultaneous_hit'))}
    for key,value in expected.items():need(metrics[key]==value,'outcome/count contradiction: '+key)
    for key in ('attack_seconds','enemy_attack_seconds','over_9g_seconds'):
        number=float(metrics[key]);need(math.isfinite(number) and 0<=number<=steps/60+1e-9,'invalid elapsed metric: '+key)
    need(math.isfinite(float(metrics['min_altitude_m'])),'nonfinite minimum AGL')


def check_ticks(rows,raw,candidate):
    previous_g=float(raw['initial']['blue_own20_audit_only'][14]);latched=False;overloads=0;count=0;peak=0.;min_hsl=math.inf;latched_ticks=0
    for row in rows:
        count+=1
        need(float(row['tick'])==count,'missing/duplicate/noninteger tick')
        need(math.isclose(float(row['simulation_seconds']),count/60,rel_tol=0,abs_tol=1e-9),'tick clock differs')
        need(all(math.isfinite(float(v)) for k,v in row.items() if k!='controller_mode'),'nonfinite CSV')
        current_g=float(row['signed_g']);abs_g=abs(current_g)
        need(math.isclose(float(row['abs_g']),abs_g,rel_tol=0,abs_tol=1e-12),'abs_g differs from signed_g')
        overloads+=int(abs_g>9.)
        need(float(row['overload_ticks'])==overloads,'exact overload counter differs')
        need(all(-1<=float(row[k])<=1 for k in ('aileron','elevator','rudder')) and 0<=float(row['throttle'])<=1,'illegal controls')
        flag=float(row['g_guard_latched']);need(flag in (0.,1.),'invalid latch flag')
        if candidate:
            if abs(previous_g)>8.5:latched=True
            elif abs(previous_g)<8.:latched=False
            need(flag==int(latched),'previous-tick G latch contradiction at tick'+str(count))
        else:need(flag==0,'baseline unexpectedly has G latch')
        previous_g=current_g;peak=max(peak,abs_g);min_hsl=min(min_hsl,float(row['altitude_m']));latched_ticks+=int(flag)
    need(count==raw['steps'],'CSV row count differs from actual steps')
    need(math.isclose(float(raw['metrics']['over_9g_seconds'])*60,overloads,rel_tol=0,abs_tol=1e-8),'raw overG seconds are not exact CSV tick count')
    return {'rows':count,'overload_ticks':overloads,'latched_ticks':latched_ticks,'peak_abs_g':peak,
        'minimum_hsl_from_csv_m':min_hsl,'minimum_agl_from_judge_m':raw['metrics']['min_altitude_m'],
        'altitude_reference_note':'CSV is HSL; judge minimum is AGL. Preserve original AGL metric; do not replace it with HSL.'}


def case_audit(case_folder,planned,supervisor,engine,source_sha,red_sha):
    raw=engine.base.read(case_folder/'result.json');specification=engine.base.read(case_folder/'input.json');receipt=engine.base.read(case_folder/'exit.json')
    need(type(receipt.get('exit_code')) is int and receipt['exit_code']==0 and receipt['wait_reason']=='exited','worker exit0 receipt missing')
    identity=receipt['identity'];need(identity['parent_pid']==supervisor['pid'],'worker receipt parent differs')
    expected=supervisor['cmdline'][:5]+['worker','--input',str(case_folder/'input.json')]
    need(identity['cmdline']==expected,'worker exact command differs')
    need(identity['create_time']>=supervisor['create_time'],'worker predates supervisor')
    need(raw['case']==planned['case'] and raw['case_id']==planned['case_id'] and raw['pair_key']==planned['pair_key'],'case plan identity differs')
    need(specification['case']==planned['case'] and specification['max_steps']==18000 and specification['bundle'] is None and specification['candidate_bundle_sha256'] is None,'input plan/hidden actor differs')
    need(specification['diagnostic_source_sha256']==source_sha,'worker diagnostic source differs')
    need(specification['source_sha256']==engine.base.read(engine.base.REFERENCE)['source_sha256'],'worker base source differs')
    need(specification['red_bundle_sha256']==red_sha,'worker red hash differs')
    need(raw['actor_policy_used'] is False,'unexpected learned blue actor')
    need(raw['initial_sha256']==engine.bench.json_hash(raw['initial']),'raw initial SHA differs')
    legal_terminal(raw)
    with (case_folder/'telemetry_60hz.csv').open(encoding='utf-8',newline='') as stream:
        reader=csv.DictReader(stream);need(tuple(reader.fieldnames)==engine.COLUMNS,'60Hz schema differs')
        tick_audit=check_ticks(reader,raw,raw['case']['actor']=='candidate')
    with (case_folder/'telemetry.csv').open(encoding='utf-8',newline='') as stream:
        rows=list(csv.DictReader(stream))
    expected_samples=raw['steps']//60+int(raw['steps']%60!=0)
    need(len(rows)==expected_samples and int(rows[-1]['tick'])==raw['steps'],'1Hz final sample/row count differs')
    need(all(all(math.isfinite(float(v)) for k,v in r.items() if k!='controller_mode') for r in rows),'nonfinite1Hz CSV')
    for key in ('attack_seconds','enemy_attack_seconds','over_9g_seconds'):
        need(math.isclose(float(rows[-1][key]),float(raw['metrics'][key]),rel_tol=0,abs_tol=1e-9),'CSV final metric differs: '+key)
    acmi=(case_folder/'duel.acmi').read_text(encoding='utf-8');frames=[line for line in acmi.splitlines() if line.startswith('#')]
    need(acmi.startswith('FileType=text/acmi/tacview') and frames and math.isclose(float(frames[-1][1:]),raw['steps']/60,rel_tol=0,abs_tol=.00051),'ACMI missing final frame')
    need(not engine.base.live(identity),'worker still alive')
    return raw,{'case_id':raw['case_id'],**tick_audit,'actual_worker_exit_code':0,
        'artifact_sha256':{name:engine.bench.file_hash(case_folder/name) for name in ('input.json','result.json','exit.json','telemetry_60hz.csv','telemetry.csv','duel.acmi')}}


def terminal_audit(folder,smoke=False):
    folder=Path(folder).resolve()
    if smoke:
        location=dev.SMOKE/'launch_smoke.py';spec=importlib.util.spec_from_file_location('post_audit_frozen_smoke',location)
        engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
        planned=engine.planned_cases();current=engine.frozen_sources();red=engine.bench.bundle_hashes(engine.bench.DEFAULT_RED_BUNDLE)
        expected_red=engine.base.read(engine.base.REFERENCE)['red_bundle_sha256']
    else:
        engine=dev.engine;planned=dev.planned_cases();current=dev.frozen_sources();red=dev.bench.bundle_hashes(dev.bench.DEFAULT_RED_BUNDLE)
        expected_red=dev.base.read(dev.MANIFEST)['red_bundle_sha256']
    launch=engine.base.read(folder/'launch.json');state=engine.base.read(folder/'state.json')
    need(state['status']=='completed','run partial/live: terminal audit refused')
    need(not engine.base.live(state.get('supervisor')),'supervisor still alive')
    receipt=engine.base.read(folder/'supervisor_exit.json');guardian=engine.base.read(folder/'guard_status.json')
    need(type(receipt.get('actual_exit_code')) is int and receipt['actual_exit_code']==0 and receipt.get('wait_return_observed') is True and receipt['wait_reason']=='exited','actual parent exit0 missing')
    need(receipt['identity']==state['supervisor'],'parent receipt identity differs from state')
    need(guardian['status']=='finished' and guardian['parent_receipt']==receipt,'guardian final receipt differs')
    need(not engine.base.live(guardian['identity']),'guardian still alive')
    need(current==launch['source_sha256'],'frozen sources differ from launch')
    need(red==expected_red,'actual current red bundle differs from frozen hash')
    need(launch['planned_cases']==[p['case'] for p in planned],'launch plan differs')
    results=[];evidence=[];pairs={}
    for case in planned:
        raw,audit=case_audit(folder/'cases'/case['case_id'],case,receipt['identity'],engine,current,red)
        results.append(raw);evidence.append(audit);pairs.setdefault(raw['pair_key'],{})[raw['case']['actor']]=raw['initial_sha256']
    need(len(pairs)==len(planned)//2 and all(set(p)=={'guide','candidate'} and p['guide']==p['candidate'] for p in pairs.values()),'pair initial SHA mismatch')
    report={'passed':True,'mode':'smoke' if smoke else 'fresh_development','simulator_started':False,'learner_started':False,
        'actual_parent_exit_code':0,'complete_cases':len(results),'matched_pairs':len(pairs),'source_sha256':current,
        'actual_red_bundle_sha256':red,'cases':evidence,'audit_source_sha256':engine.bench.file_hash(__file__),
        'deployment_allowed':False,'timestamp_utc':datetime.now(timezone.utc).isoformat()}
    if not smoke:
        for row in results:
            expected='pure_repair_guide' if row['case']['actor']=='guide' else 'fixed_bank80_G_latch'
            need(row['smoke_control']==expected and row['paired_baseline_is_repair_guide'] is True,'guide/candidate role metadata differs')
        summary=dev.bench.summarize(results,dev.bench.plan_cases(1,dev.SEED_BASE,'both',True),True)
        need(summary['complete'] and summary['paired_completed']==12,'not24 full cases/12 pairs')
        report.update(summary=summary,**dev.gates(results,summary))
    return report


def main():
    parser=argparse.ArgumentParser(description='Independent terminal-only CSV/receipt/hash audit; no FDM')
    parser.add_argument('--job',type=Path,required=True);parser.add_argument('--smoke',action='store_true');parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    try:
        report=terminal_audit(args.job,args.smoke);code=0
    except BaseException as error:
        report={'passed':False,'error':repr(error),'simulator_started':False,'learner_started':False,'deployment_allowed':False,
            'audit_source_sha256':dev.bench.file_hash(__file__),'timestamp_utc':datetime.now(timezone.utc).isoformat()};code=1
    dev.bench.atomic_json(args.out,report)
    print(json.dumps({k:report[k] for k in ('passed','simulator_started','learner_started','complete_cases','matched_pairs','gate','error') if k in report},ensure_ascii=False))
    return code


if __name__=='__main__':raise SystemExit(main())
