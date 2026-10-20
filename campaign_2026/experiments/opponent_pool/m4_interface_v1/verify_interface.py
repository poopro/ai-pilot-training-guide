"""Validate complete real FDM interface receipts; never a combat promotion."""
import argparse
import csv
from common import *


def verify(out, parent_exit):
    out = Path(out).resolve()
    if out.parent != HERE or parent_exit != 0:
        raise ValueError('Need this branch job and observed launcher exit0')
    launch = read(out/'launch.json')
    execution_mode_gate(launch)
    source_gate(launch['source_freeze'])
    if launch['tools_sha256'] != tools(): raise ValueError('Executor source changed')
    receipt = read(out/'launcher_receipt.json')
    supervisor = read(out/'supervisor_exit.json')
    guard = read(out/'guard.json')
    report = read(out/'report.json')
    errors = []
    def require(ok, message):
        if not ok: errors.append(message)
    require(receipt['actual_parent_exit_code'] == 0, 'supervisor wait not0')
    require(receipt['actual_guard_exit_code'] == 0, 'guard wait not0')
    require(supervisor['actual_parent_exit_code'] == 0, 'supervisor receipt not0')
    require(receipt['report_sha256'] == sha(out/'report.json'), 'report hash')
    require(receipt['guard_sha256'] == sha(out/'guard.json'), 'guard hash')
    require(receipt['reservation_sha256'] == sha(out/'reservation.json'), 'reservation hash')
    require(receipt['launch_sha256'] == sha(out/'launch.json'), 'launch hash')
    require(guard['target'] == launch['supervisor'], 'guard target identity')
    require(not guard.get('unknown'), 'unknown guard identity')
    require(not guard.get('stopped'), 'guard had to stop a process')
    require(report['status'] == 'completed' and len(report['cases']) == 3, 'incomplete3 workers')
    total = 0
    summaries = []
    for case, worker in zip(launch['cases'], report['cases']):
        folder = out/'cases'/case['case_id']
        result = read(folder/'result.json')
        require(worker['case_id'] == case['case_id'], 'case order')
        require(worker['actual_worker_exit_code'] == 0, 'worker exit not0')
        require(worker['input_sha256'] == sha(folder/'input.json'), 'worker input hash')
        require(worker['result_sha256'] == sha(folder/'result.json'), 'worker result hash')
        require(result['status'] == 'interface_pass', 'worker interface failure')
        require(result['case'] == case, 'worker case changed')
        require(len(result['episodes']) == 2, 'missing reset repeat')
        for name, digest in result.get('artifact_sha256', {}).items():
            require(name in ('telemetry.csv','duel.acmi') and sha(folder/name) == digest, 'artifact hash')
        require(set(result.get('artifact_sha256',{})) == {'telemetry.csv','duel.acmi'}, 'missing artifact')
        with (folder/'telemetry.csv').open(encoding='utf-8',newline='') as stream:
            rows = list(csv.DictReader(stream))
        require(len(rows) == 600, 'not600 rows per worker')
        for ep in range(2):
            selected = [row for row in rows if int(row['episode']) == ep]
            require(len(selected) == 300, 'not300 rows per reset')
            counter = 0
            for tick, row in enumerate(selected, 1):
                require(all(int(row[name]) == tick for name in ('tick','act_calls','blue_send_calls','red_send_calls','judge_calls')), 'per-tick call mismatch')
                actual = legal_command(json.loads(row['actual_command']))
                calculated = legal_command(json.loads(row['command_from_act']))
                require(actual == calculated, 'actual action changed')
                distance, angle = float(row['distance_m']), float(row['blue_angle_deg'])
                counter += int(500*.3048 <= distance <= 3000*.3048 and angle <= 1.)
                require(int(row['attack_ticks']) == counter, 'CSV post-step counter')
            summary = result['episodes'][ep]
            require(summary['counts'] == {'act':300,'blue':300,'red':300,'judge':300}, 'summary counts')
            require(summary['attack_ticks'] == summary['tactical_attack_ticks'] == counter, 'summary attack count')
            require(summary['max_command_error'] == 0 and summary['fallbacks'] == 0, 'command error/fallback')
            require(summary['opponent_actual'] == case['opponent_id'], 'wrong opponent')
            total += len(selected)
        first, second = result['episodes']
        require(first['initial_sha256'] == second['initial_sha256'] and first['final_sha256'] == second['final_sha256'], 'same-seed reset not reproducible')
        summaries.append({'opponent':case['opponent_id'],'ticks':600,'initial_sha256':first['initial_sha256'],'same_seed_reset_reproduced':True,'attack_ticks_per_reset':first['attack_ticks']})
    require(total == 1800, 'not1800 ticks')
    result = {'verified_real_FDM_interface':not errors,'errors':errors,'new_FDM_ticks':total,
              'case_summaries':summaries,'actual_observed_launcher_exit_code':parent_exit,
              'score_eligible':False,'combat_win_rate_evidence':False,'official_validation':False,
              'deployment_allowed':False,'source_contract':'legacy_diagnostic_not_official',
              'report_sha256':sha(out/'report.json')}
    write(out/'VERIFICATION.json',result)
    if errors: raise RuntimeError(repr(errors))
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--parent-exit-code',required=True,type=int)
    args=parser.parse_args()
    print(json.dumps(verify(args.out,args.parent_exit_code),ensure_ascii=False))
