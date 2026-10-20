"""Read terminal v4 evidence; never launch or stop a process."""
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import psutil

ROOT = Path(__file__).resolve().parents[1]
BRANCH = ROOT / 'diagnostics/portable_host_v4'

def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

def identity_state(record):
    try:
        p = psutil.Process(record['pid'])
        creation = record.get('create_time', record.get('creation_epoch'))
        command = record.get('command', record.get('cmdline'))
        same = abs(p.create_time() - creation) < .01 and p.cmdline() == command and p.exe().lower() == record['exe'].lower()
        return {'pid': p.pid, 'state': 'identity_verified_live' if same else 'reused_or_mismatch'}
    except psutil.NoSuchProcess:
        return {'pid': record['pid'], 'state': 'absent'}
    except psutil.AccessDenied:
        return {'pid': record['pid'], 'state': 'unknown_access_denied'}

def audit(folder):
    result = read(folder / 'portable_result.json')
    guard = read(folder / 'watchdog_receipt.json')
    wait = read(folder / 'watchdog_exit_observed.json')
    collector = read(folder / 'collector_exit.json')
    assert result['portable_rehearsal_complete'] is True
    assert all(result['checks'].values())
    assert collector['actual_exit_code'] == wait['actual_exit_code'] == 0
    assert guard['cleanup']['all_known_processes_stopped'] is True
    live = read(folder / 'live.json')
    identities = [entry['identity'] for entry in live['tracked'].values()]
    identities.append(read(folder / 'guard_spawn.json')['identity'])
    states = [identity_state(r) for r in identities]
    assert all(s['state'] in ('absent', 'reused_or_mismatch') for s in states), states
    csv_path = folder / Path(result['source_csv']).name
    assert hashlib.sha256(csv_path.read_bytes()).hexdigest() == result['csv_sha256']
    with csv_path.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    gkeys = ['player1_g_acc', 'player2_g_acc']
    assert all(k in rows[0] for k in gkeys)
    summary = {
        'observed_utc': datetime.now(timezone.utc).isoformat(),
        'verified_new_portable_round': True,
        'actual_collector_exit_code': collector['actual_exit_code'],
        'actual_watchdog_exit_code': wait['actual_exit_code'],
        'rows': len(rows), 'sim_seconds': float(rows[-1]['time']),
        'raw_host_winner': result['host_winner_raw'],
        'final_HP': [float(rows[-1][f'player{i}_Score_RemainingHP']) for i in (1, 2)],
        'physical_G_columns': gkeys,
        'over9G_ticks': [sum(abs(float(r[k])) > 9 for r in rows) for k in gkeys],
        'max_abs_G': [max(abs(float(r[k])) for r in rows) for k in gkeys],
        'same_fixed_profile_hash': result['fixed_profile_hash'],
        'original_identity_audit': states,
        'competition_certification': False,
    }
    (folder / 'TERMINAL_AUDIT_20261016.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary

if __name__ == '__main__':
    import sys
    for name in sys.argv[1:]:
        folder = (BRANCH / 'runs' / name).resolve()
        assert folder.is_relative_to((BRANCH / 'runs').resolve())
        print(json.dumps({'run': name, 'audit': audit(folder)}, ensure_ascii=False))
