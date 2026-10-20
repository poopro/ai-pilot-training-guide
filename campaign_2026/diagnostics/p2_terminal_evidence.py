"""Fresh, owned built-in P2 STOPPED evidence; never substitutes invented stdout."""
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import re
import time

VERSION = 1
STOP = b'[P2] Stopping: Host state changed to STOPPED'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def before_logs(paths):
    result = {}
    for path in paths:
        path = Path(path).resolve()
        if path.is_file():
            stat = path.stat(); data = path.read_bytes(); after = path.stat()
            if (stat.st_size, stat.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise RuntimeError('P2 log changed during prelaunch capture')
            result[str(path)] = dict(exists=True, size=stat.st_size,
                                    mtime_ns=stat.st_mtime_ns, sha256=sha(data))
        else:
            result[str(path)] = dict(exists=False)
    return result

def owned_p2(ledger, session, child_pid, stop_epoch):
    if ledger.get('token') != session.get('watchdog_token'):
        return False
    tracked = ledger.get('tracked', {})
    matches = [(key, item) for key, item in tracked.items()
               if item.get('identity', {}).get('pid') == child_pid]
    if len(matches) != 1:
        return False
    key, item = matches[0]; identity = item['identity']
    command = identity.get('command', [])
    if '--internal-player2' not in command or not command:
        return False
    if Path(command[0]).name.lower() != 'jsb_host_gui_publish.exe':
        return False
    root = session.get('host_launch_identity',session['host_processes'][0])
    if not root['create_time'] <= identity.get('create_time', 0) <= stop_epoch:
        return False
    seen = set()
    while key in tracked and key not in seen:
        seen.add(key); entry = tracked[key]
        if entry.get('role') == 'host_root':
            identity = entry['identity']
            return (identity['pid'] == root['pid'] and
                    identity['create_time'] == root['create_time'] and
                    identity['command'] == root['command'])
        key = entry.get('discovered_from')
    return False

def terminal_checks(session, data, source, rows, csv_sha256, ledger, captured_epoch):
    checks = dict(new_capture_version=False, fresh_log=False, owned_child=False,
                  stopped_then_exited=False, csv_adjudicated=False,
                  initial_positions_match=False)
    try:
        checks['new_capture_version'] = session.get('terminal_capture_version') == VERSION
        baseline = session['p2_logs_before_launch'][source['path']]
        allowed={str((Path(session[key])/'player2_runtime.log').resolve()) for key in ('host_dir','runtime_dir')}
        checks['fresh_log'] = (source['sha256'] == sha(data) and source['size'] == len(data)
            and source['path'] in allowed
            and session['start_clicked_epoch'] <= source['mtime_ns']/1e9 <= captured_epoch
            and (not baseline['exists'] or (source['mtime_ns'] > baseline['mtime_ns']
                 and source['sha256'] != baseline['sha256'])))
        text = data.decode('utf-8', errors='replace')
        if '[P2]' not in text:
            text = data.decode('cp950', errors='replace')
        children = re.findall(r'^\[P2\] Child PID=(\d+)\s*$', text, re.M)
        checks['owned_child'] = (len(children) == 1 and text.count('[P2] Built-in Player2 started') == 1
            and owned_p2(ledger, session, int(children[0]), source['mtime_ns']/1e9))
        checks['stopped_then_exited'] = re.search(
            r'\[P2\] Stopping: Host state changed to STOPPED\s*\n\[P2\] Process exited with code [01]\s*$', text) is not None
        last = rows[-1]; winner = float(last['system_Final_whoiswinner'])
        full = float(last['time']) >= 299.9 and len(rows) >= 17900
        early = winner in (1., 2.) and min(float(last['player1_Score_RemainingHP']),
                                                float(last['player2_Score_RemainingHP'])) <= 0
        checks['csv_adjudicated'] = winner in (1., 2.) and (full or early) and bool(csv_sha256)
        pattern = r'Pos:\s+Lat=([-\d.]+) deg, Lon=([-\d.]+) deg, Alt=([-\d.]+) ft'
        own = re.search(r'\[OWN STATE\]\s+'+pattern, text)
        enemy = re.search(r'\[ENEMY\]\s+'+pattern, text)
        first = rows[0]
        checks['initial_positions_match'] = bool(own and enemy) and all(
            abs(float(value)-float(first[f'player{side}_{field}'])) <= tolerance
            for match, side in [(own, 2), (enemy, 1)]
            for value, field, tolerance in zip(match.groups(), ('lat_deg','lon_deg','alt_ft'), (.0002,.0002,30.)))
    except (KeyError, ValueError, IndexError, TypeError):
        pass
    return checks

def _probe(session, ledger, *, stable_seconds=2.):
    """Cheap tail check until STOPPED, then bind fresh log to a new terminal CSV."""
    if session.get('terminal_capture_version') != VERSION or 'start_clicked_epoch' not in session:
        return None
    candidates = []
    now = time.time()
    for label in session.get('p2_logs_before_launch', {}):
        path = Path(label)
        if not path.is_file():
            continue
        stat = path.stat()
        if stat.st_mtime < session['start_clicked_epoch'] or now-stat.st_mtime < stable_seconds:
            continue
        with path.open('rb') as stream:
            stream.seek(max(0, stat.st_size-4096)); tail = stream.read()
        if STOP not in tail:
            continue
        data = path.read_bytes(); after = path.stat()
        if (stat.st_size,stat.st_mtime_ns) != (after.st_size,after.st_mtime_ns):
            continue
        source = dict(path=str(path.resolve()), size=stat.st_size, mtime_ns=stat.st_mtime_ns, sha256=sha(data))
        for directory in (Path(session['host_dir']),Path(session['runtime_dir'])):
            if not directory.is_dir():
                continue
            for csv_path in directory.glob('*.csv'):
                cs = csv_path.stat(); prior = session['preexisting_csv'].get(str(csv_path))
                if cs.st_mtime < session['start_clicked_epoch'] or now-cs.st_mtime < stable_seconds:
                    continue
                if prior and cs.st_mtime_ns == prior['mtime_ns']:
                    continue
                raw = csv_path.read_bytes(); ca = csv_path.stat()
                if (cs.st_size,cs.st_mtime_ns) != (ca.st_size,ca.st_mtime_ns):
                    continue
                with csv_path.open(encoding='utf-8-sig', newline='') as stream:
                    rows = list(csv.DictReader(stream))
                checks = terminal_checks(session,data,source,rows,sha(raw),ledger,now)
                if all(checks.values()):
                    acmi = csv_path.parent/'output_acmi'/(csv_path.stem+'.acmi')
                    if not acmi.is_file() or now-acmi.stat().st_mtime < stable_seconds:
                        continue
                    terminal_times = [float(line[1:]) for line in acmi.read_text(encoding='utf-8-sig').splitlines()
                                      if line.startswith('#')]
                    if not terminal_times or abs(terminal_times[-1]-float(rows[-1]['time'])) > .1:
                        continue
                    candidates.append(dict(source=source, csv=str(csv_path), csv_sha256=sha(raw), checks=checks,
                                           captured_epoch=now, data=data))
    return candidates[0] if len(candidates) == 1 else None

def probe(session, ledger, *, stable_seconds=2.):
    try:
        return _probe(session,ledger,stable_seconds=stable_seconds)
    except (OSError,ValueError,KeyError,TypeError):
        return None

def capture(session, folder, ledger):
    candidate = probe(session,ledger)
    if candidate is None:
        return None
    folder = Path(folder)
    log = folder/'p2_runtime_terminal.log'; log.write_bytes(candidate.pop('data'))
    ledger_path = folder/'p2_watchdog_observation.json'
    ledger_path.write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    receipt = dict(candidate, log_snapshot=str(log), ledger_snapshot=str(ledger_path),
                   ledger_sha256=sha(ledger_path.read_bytes()), terminal_capture_version=VERSION,
                   captured_utc=datetime.now(timezone.utc).isoformat())
    receipt_path = folder/'p2_terminal_receipt.json'
    receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return str(receipt_path)

def verify(folder, session, rows, csv_sha256):
    checks = dict(fresh_owned_p2_stop_verified=False, prelaunch_p2_receipt_matches=False,
                  p2_snapshots_match=False, p2_csv_hash_matches=False)
    try:
        folder = Path(folder).resolve()
        def local(value):
            path = Path(value).resolve()
            if not path.is_relative_to(folder):
                raise ValueError('P2 evidence outside round folder')
            return path
        receipt = read(local(session['p2_terminal_receipt']))
        pre = read(local(session['host_launch_record']))
        checks['prelaunch_p2_receipt_matches'] = (pre.get('terminal_capture_version') == VERSION
            and pre['p2_logs_before_launch'] == session['p2_logs_before_launch']
            and session.get('terminal_capture_version') == VERSION
            and {key:pre[key] for key in ('pid','create_time','command')} == session['host_launch_identity'])
        log = local(receipt['log_snapshot']); ledger_path = local(receipt['ledger_snapshot'])
        data = log.read_bytes(); ledger = read(ledger_path)
        checks['p2_snapshots_match'] = (sha(data) == receipt['source']['sha256']
            and sha(ledger_path.read_bytes()) == receipt['ledger_sha256'])
        checks['p2_csv_hash_matches'] = receipt['csv_sha256'] == csv_sha256
        checks['fresh_owned_p2_stop_verified'] = all(terminal_checks(
            session,data,receipt['source'],rows,csv_sha256,ledger,receipt['captured_epoch']).values())
    except (KeyError,TypeError,ValueError,IndexError,OSError):
        pass
    return checks
