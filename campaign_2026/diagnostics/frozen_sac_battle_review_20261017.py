"""Read saved completed games only; never invoke a controller, model or FDM."""
import csv
import datetime
import hashlib
import json
import sys
from pathlib import Path

import psutil


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def audit_identity(i):
    try:
        p = psutil.Process(i['pid'])
        same_time = abs(p.create_time() - i['create']) < .01
        same = same_time and p.cmdline() == i['cmd'] and p.exe().lower() == i['exe'].lower() and p.ppid() == i['parent']
        return dict(identity=i, state='same_identity_live' if same else 'pid_reused_or_identity_mismatch')
    except psutil.NoSuchProcess:
        return dict(identity=i, state='absent_no_exit_inferred')
    except psutil.AccessDenied:
        return dict(identity=i, state='unknown_access_denied')


def main(out):
    audit = Path(read(out/'OFFLINE_REAUDIT_POINTER.json')['audit'])
    c = read(audit/'COMPARISON.json')
    v = read(audit/'AUDIT_EXIT.json')
    p = read(out/'PARENT_EXIT_OBSERVED.json')
    if not (c['verified_comparison'] and v['actual_worker_exit'] == 0 and p['actual_exit'] == 0
            and read(audit/'GUARDIAN_EXIT_OBSERVED.json')['actual_exit'] == 0):
        raise RuntimeError('Requires actual successful parent and independent verifier')
    records = [read(out/'CONTRACT.json')['guardian'], v['identity'],
               read(out/'VERIFIER_EXIT.json')['identity'], read(audit/'CONTRACT.json')['guardian']]
    records.extend(d['identity'] for d in v['owned_descendants'])
    data = []
    for result in c['results']:
        folder = out/'cases'/result['case']['id']
        receipt = read(folder/'WORKER_EXIT.json')
        records.append(receipt['identity'])
        records.extend(d['identity'] for d in receipt['descendants'])
        r = read(folder/'RESULT.json')
        ranges = []
        angles = []
        in_band_angles = []
        with (folder/'telemetry.csv').open(encoding='utf8', newline='') as stream:
            for row in csv.DictReader(stream):
                distance, angle = float(row['distance_m']), float(row['blue_angle_deg'])
                ranges.append(distance)
                angles.append(angle)
                if 152.4 <= distance <= 914.4:
                    in_band_angles.append(angle)
        command_hash = hashlib.sha256()
        first = last = None
        with (folder/'telemetry.jsonl').open(encoding='utf8') as stream:
            for line in stream:
                row = json.loads(line)
                cmd = row['blue_command']
                command_hash.update(json.dumps(cmd, separators=(',', ':')).encode())
                first = cmd if first is None else first
                last = cmd
        tactics = [d['action'] for d in r['tactical_decisions']]
        data.append(dict(**result, csv_sha256=sha(folder/'telemetry.csv'),
                         actual_blue_commands_sha256=command_hash.hexdigest(),
                         first_command=first, last_command=last,
                         range_min_m=min(ranges), range_max_m=max(ranges),
                         in_attack_range_ticks=len(in_band_angles),
                         in_attack_range_percent=100*len(in_band_angles)/len(ranges),
                         best_nose_angle_deg=min(angles),
                         best_nose_angle_inside_range_deg=min(in_band_angles) if in_band_angles else None,
                         unique_tactical_actions=len({tuple(a) for a in tactics}),
                         tactical_min=[min(a[k] for a in tactics) for k in range(3)],
                         tactical_max=[max(a[k] for a in tactics) for k in range(3)]))
    equivalence = []
    for opening in (0, 1):
        group = [r for r in data if r['case']['opening'] == opening]
        equivalence.append(dict(opening=opening, side=group[0]['case']['side'],
                                same_initial_sha=len({r['initial_sha256'] for r in group}) == 1,
                                identical_all_numeric_telemetry=len({r['csv_sha256'] for r in group}) == 1,
                                identical_all_actual_blue_commands=len({r['actual_blue_commands_sha256'] for r in group}) == 1))
    identities = { (r['pid'], r['create']):r for r in records }
    process_audit = [audit_identity(i) for i in identities.values()]
    if any(a['state'] in ('same_identity_live', 'unknown_access_denied') for a in process_audit):
        raise RuntimeError('Terminal original identity still live or unknown; preserve evidence')
    review = dict(status='completed_development_review', created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  comparison_sha256=sha(audit/'COMPARISON.json'), independent_audit=str(audit), results=data,
                  within_opening_equivalence=equivalence,
                  actual_parent_exit=0, actual_saved_data_audit_exit=0,
                  original_60s_verifier_exit=read(out/'VERIFIER_EXIT.json')['actual_exit'],
                  terminal_process_audit=process_audit,
                  gate='no_model_advantage_in_this_development_batch_no_promotion',
                  decision='不晉級、不盲續訓練；先確認戰術輸出經控制器後的實際影響與進入攻擊距離的能力。',
                  causal_limit='相同實際命令可證明本批未產生控制差異；bank/速度裁切是待逐支路驗證的假設，尚非根因定論。',
                  opening_limit='兩個開發開局各使用不同seed，不能把開局間差異單獨歸因左右側。',
                  not_pure_repair_guide=True, holdout=False, official_validation=False,
                  training_started=False, deployment_allowed=False,
                  retained_deployment='repair_guide')
    (out/'SAFETY_REVIEW.json').write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(dict(results=[{k:r[k] for k in ('case','event','winner','attack_ticks','over9G','score_margin','range_min_m','in_attack_range_ticks')} for r in data], equivalence=equivalence, original_identities_absent=len(process_audit)), ensure_ascii=False))


if __name__ == '__main__':
    main(Path(sys.argv[1]))
