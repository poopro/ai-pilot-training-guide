"""Add only a freshly reaudited round with real collector/watchdog exits."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

from audit_host_evidence import audit

ROOT = Path(__file__).resolve().parents[1]
DIAG = ROOT / 'diagnostics'
LEGACY = Path(r'E:\ai_pilot\autopilot\combat_fix')

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def write(path, data):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)

def record(folder):
    folder = Path(folder).resolve()
    if not folder.is_relative_to((LEGACY / 'official_validation').resolve()):
        raise RuntimeError('Round folder outside recorded validation root')
    session = read(folder / 'session.json')
    token = session['watchdog_token']
    watchdog = read(DIAG / ('host_watchdog_' + token + '.json'))
    observed = read(DIAG / ('watchdog_exit_' + token + '.json'))
    auto = read(folder / 'auto_collector_exit.json')
    if (watchdog['token'] != token or observed['identity']['token'] != token
        or observed['actual_watchdog_exit_code'] != 0 or auto['actual_exit_code'] != 0
        or auto['token'] != token or auto['timed_out']
        or not watchdog['all_known_live_processes_stopped']):
        raise RuntimeError('Actual collector/watchdog exits or cleanup not verified')
    current = audit(folder / 'host_result.json')
    if not current['eligible_for_six_round_fixed_source_gate']:
        raise RuntimeError('Fresh Host audit rejected')
    path = DIAG / 'host_gate_latest.json'
    gate = read(path)
    if current['fixed_profile_hash'] != gate['fixed_profile_hash']:
        raise RuntimeError('Fixed Host profile differs from accepted baseline')
    result = read(folder / 'host_result.json')
    row = {'folder': str(folder), 'round_identity': current['round_identity'],
           'winner_raw': result['host_winner_raw'], 'sim_seconds': result['sim_seconds'],
           'p1_hp': result['players']['1']['hp'], 'p2_hp': result['players']['2']['hp'],
           'p1_overload': result['players']['1']['gforce_overload'], 'eligible': True,
           'actual_auto_collector_exit': auto['actual_exit_code'],
           'actual_watchdog_exit': observed['actual_watchdog_exit_code']}
    added = not any(v['round_identity'] == row['round_identity'] for v in gate['rounds'])
    if added:
        gate['rounds'].append(row)
    for existing in gate['rounds']:
        saved = audit(Path(existing['folder']) / 'host_result.json')
        if (not saved['eligible_for_six_round_fixed_source_gate']
            or saved['fixed_profile_hash'] != gate['fixed_profile_hash']
            or saved['round_identity'] != existing['round_identity']):
            raise RuntimeError('Previously counted round no longer passes')
    if len({v['round_identity'] for v in gate['rounds']}) != len(gate['rounds']):
        raise RuntimeError('Duplicate raw round identity')
    gate.update(eligible_rounds=len(gate['rounds']), verified_utc=datetime.now(timezone.utc).isoformat(),
                remaining=f"{max(0, 6-len(gate['rounds']))} additional fixed-profile rounds; LAN and clean-start rehearsal still pending")
    write(path, gate)
    research = read(ROOT / 'research_latest.json')
    research.update(updated_utc=gate['verified_utc'], host_last_round=str(folder),
                    host_last_gate=f"eligible_{len(gate['rounds'])}_of_6", host_gate=str(path),
                    host_execution_status='completed_and_eligible_auto_capture',
                    host_last_result={k: row[k] for k in ('winner_raw','sim_seconds','p1_hp','p2_hp','p1_overload')})
    research['operational_gate']['new_completed_host_rounds'] = len(gate['rounds'])
    write(ROOT / 'research_latest.json', research)
    budget_path = DIAG / 'active_host_budget.json'
    if budget_path.exists():
        reservation = read(budget_path)
        budget = read(reservation['ledger'])
        for item in budget['items']:
            if item['id'] == reservation['id']:
                if item.get('run') and item['run'] != str(folder):
                    raise RuntimeError('Budget reservation already belongs to another round')
                item.update(status='completed', run=str(folder),
                            actual_wall_seconds=observed['observed_epoch']-watchdog['create_time'],
                            auto_collector_exit_code=0, watchdog_exit_code=0)
        write(reservation['ledger'], budget)
    if added:
        with (ROOT / 'REVIEW_LOG.md').open('a', encoding='utf-8') as stream:
            stream.write(f"\n## {gate['verified_utc']}：固定來源 Host {len(gate['rounds'])}/6\n\n")
            stream.write(f"- winner={row['winner_raw']}、HP {row['p1_hp']}:{row['p2_hp']}、{row['sim_seconds']}秒、overload={row['p1_overload']}；自動collector/watchdog真實退出0、全部精確自建程序已清理。\n")
            stream.write(f"- 所有已計回合重新稽核，固定profile与raw round身份核對；證據 {folder}。\n")
    print(json.dumps({'added': added, 'gate': str(path), 'eligible_rounds': gate['eligible_rounds'],
                      'round': row}, ensure_ascii=False))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', type=Path, required=True)
    record(parser.parse_args().folder)
