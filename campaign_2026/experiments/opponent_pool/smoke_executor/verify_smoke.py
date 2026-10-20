"""Audit interface smoke only; never report wins, league scores, or promotion."""
import argparse,csv,math
from common import *

def verify(out):
    out=Path(out);errors=[];pairs={};counts={}
    try:
        launch=read(out/'launch.json');report=read(out/'report.json');receipt=read(out/'launcher_receipt.json');exit_record=read(out/'supervisor_exit.json');guard=read(out/'guard.json')
    except (OSError,ValueError) as error:
        result={'format':'guide_pool_smoke_verification_v1','verified_interface_smoke':False,'errors':['Missing/incomplete mandatory exit evidence: '+repr(error)],'score_eligible':False,'win_rate_evidence':False,'official_validation':False,'deployment_allowed':False}
        write(out/'VERIFICATION.json',result);return result
    try:
        prep.assert_plan(launch['cases'])
        if launch['tools_sha256']!=tools():raise ValueError('Executor source changed')
        source_gate(launch['source_freeze'])
        if receipt['actual_parent_exit_code']!=0 or exit_record['actual_parent_exit_code']!=0 or exit_record['identity']!=launch['supervisor']:raise ValueError('No successful actual supervisor exit')
        if receipt['actual_guard_exit_code']!=0 or guard['status']!='finished' or guard['unknown'] or guard['reason'] not in ('observed_supervisor_exit','supervisor_missing'):raise ValueError('Guard cleanup incomplete')
        if receipt['launch_sha256']!=sha(out/'launch.json') or receipt['reservation_sha256']!=sha(out/'reservation.json'):raise ValueError('Launcher receipt SHA changed')
        if receipt.get('report_sha256')!=sha(out/'report.json') or receipt.get('guard_sha256')!=sha(out/'guard.json'):raise ValueError('Final report/guard receipt changed')
        if report['status']!='completed' or len(report['cases'])!=24 or report['wall_seconds']>900 or report['plan_sha256']!=jsha(launch['cases']):raise ValueError('Incomplete planned smoke')
        if report.get('score_eligible') is not False or report.get('official_validation') is not False:raise ValueError('Smoke cannot be promoted to score/official validation')
        for case,item in zip(launch['cases'],report['cases']):
            folder=out/'cases'/case['case_id'];record=read(folder/'result.json');wexit=read(folder/'worker_exit.json');spec=read(folder/'input.json')
            if item!=wexit or wexit['actual_worker_exit_code']!=0 or wexit['case_id']!=case['case_id'] or wexit['input_sha256']!=sha(folder/'input.json') or wexit['result_sha256']!=sha(folder/'result.json'):raise ValueError('Worker exit/artifact changed: '+case['case_id'])
            if record['worker_identity']!=wexit['identity'] or spec['case']!=case or record['case']!=case:raise ValueError('Case/worker identity differs')
            if spec['tools_sha256']!=launch['tools_sha256'] or spec['source_freeze']!=launch['source_freeze'] or record['source_freeze']!=launch['source_freeze']:raise ValueError('Case source mismatch')
            if record['status']!='interface_pass' or record['score_eligible'] is not False or record['official_validation'] is not False or record['wall_seconds']>30:raise ValueError('Partial/invalid case')
            steps=record['steps']
            if not 1<=steps<=300 or (steps<300 and not record['legal_termination']):raise ValueError('Incomplete nonterminal ticks')
            if record['command_counts']!={'blue':steps,'red':steps} or not record['independent_rng'] or not record['independent_controller_state'] or record['policy_observation']!='OWN20+ENEMY6':raise ValueError('Command/state contract differs')
            if record['initial_sha256']!=jsha(record['initial']):raise ValueError('Initial SHA differs')
            for name in ('telemetry.csv','duel.acmi'):
                if record['artifact_sha256'][name]!=sha(folder/name):raise ValueError('Trajectory SHA differs')
            with (folder/'telemetry.csv').open(encoding='utf8',newline='') as f:rows=list(csv.DictReader(f))
            if len(rows)!=steps or [int(r['tick']) for r in rows]!=list(range(1,steps+1)):raise ValueError('CSV tick coverage differs')
            for row in rows:
                for side in ('blue','red'):
                    legal_command(json.loads(row[side+'_command']))
                    token=row[side+'_observation_sha256']
                    if len(token)!=64 or any(ch not in '0123456789abcdef' for ch in token):raise ValueError('Observation SHA invalid')
                for key in ('simulation_seconds','distance_m','blue_altitude_m','red_altitude_m','blue_g','red_g'):
                    if not math.isfinite(float(row[key])):raise ValueError('Nonfinite telemetry')
                if abs(float(row['simulation_seconds'])-int(row['tick'])/60)>1e-8:raise ValueError('CSV clock differs')
            lines=(folder/'duel.acmi').read_text(encoding='utf8').splitlines()
            times=[float(s[1:]) for s in lines if s.startswith('#')]
            if len(times)!=steps+1 or any(abs(t-i/60)>.00051 for i,t in enumerate(times)):raise ValueError('ACMI missing physics frames')
            trajectory={1:0,2:0}
            for line in lines:
                if line.startswith(('1,T=','2,T=')):
                    oid=int(line[0]);pose=[float(x) for x in line.split('T=',1)[1].split('|')]
                    if len(pose)!=6 or not all(math.isfinite(x) for x in pose):raise ValueError('ACMI pose invalid')
                    trajectory[oid]+=1
            if trajectory!={1:steps+1,2:steps+1}:raise ValueError('ACMI aircraft frames incomplete')
            pairs.setdefault(case['pair_key'],{})[case['side']]=record
            counts[case['opponent_id']]=counts.get(case['opponent_id'],0)+1
        for pair in pairs.values():
            normal,mirror=pair['normal'],pair['mirrored'];a,b=normal['initial'],mirror['initial']
            if normal['red_rng_initial_sha256']!=mirror['red_rng_initial_sha256'] or normal['blue_rng_initial_sha256']!=mirror['blue_rng_initial_sha256']:raise ValueError('Pair initial RNG differs')
            if a['red_own20_audit_only']!=b['red_own20_audit_only']:raise ValueError('Mirror changed red state')
            if a['cross_track_m']*b['cross_track_m']>=0 or abs(a['distance_m']-b['distance_m'])>max(1,a['distance_m']*.01):raise ValueError('Mirror side/distance invalid')
            for i in (2,3,4,5,12):
                if abs(a['blue_own20_audit_only'][i]-b['blue_own20_audit_only'][i])>1e-5:raise ValueError('Mirror changed blue invariant')
    except (ValueError,RuntimeError,KeyError,OSError,TypeError) as e:errors.append(repr(e))
    result={'format':'guide_pool_smoke_verification_v1','verified_interface_smoke':not errors,'errors':errors,'case_count':len(report['cases']),'geometry_pair_count':len(pairs),'per_opponent_case_count':counts,'self_play_cases':6 if not errors else None,'new_fdm_ticks':sum(read(out/'cases'/x['case_id']/'result.json').get('steps',0) for x in report['cases'] if (out/'cases'/x['case_id']/'result.json').exists()),'score_eligible':False,'win_rate_evidence':False,'official_validation':False,'deployment_allowed':False,'report_sha256':sha(out/'report.json')}
    write(out/'VERIFICATION.json',result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=verify(a.out);print(json.dumps(r,ensure_ascii=False));raise SystemExit(0 if r['verified_interface_smoke'] else 2)
