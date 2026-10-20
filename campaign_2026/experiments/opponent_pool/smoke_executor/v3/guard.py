"""Independent watchdog: receipt I/O cannot cancel STOP or owned cleanup."""
import argparse
import time
from pathlib import Path
from common import *


def run_guard(out):
    out = Path(out)
    launch = read(out / 'launch.json')
    target = launch['supervisor']
    limit = launch['total_wall_seconds']
    if isinstance(limit, bool) or not isinstance(limit, (int, float)) or not math.isfinite(limit) or not 30 <= limit <= 900:
        raise ValueError('Invalid reserved guard deadline')
    began = time.monotonic()
    deadline = launch['deadline_monotonic']
    if not math.isfinite(deadline) or abs(deadline-launch['reservation_start_monotonic']-limit)>1e-6 or abs(launch['deadline_epoch']-launch['reservation_start_epoch']-limit)>1e-6:
        raise ValueError('Guard requires the original reserved deadline')
    known = {target['pid']: target}
    ancestry = {target['pid']: []}
    case_deadlines = {}
    receipt = {'status': 'armed', 'guard': identity(), 'target': target,
               'deadline_epoch': launch['deadline_epoch'], 'deadline_monotonic': deadline, 'total_wall_seconds': limit,
               'stopped': [], 'unknown': [], 'observed_descendants': [],
               'publication_error_count': 0, 'publication_errors': []}
    publication_failed = False

    def publish():
        nonlocal publication_failed
        try:
            write(out / 'guard.json', receipt)
            publication_failed = False
            return True
        except OSError as error:
            publication_failed = True
            receipt['publication_error_count'] += 1
            if len(receipt['publication_errors']) < 32:
                receipt['publication_errors'].append({'epoch': time.time(), 'error': repr(error)})
            print('Guard receipt unavailable; watchdog still active: ' + repr(error), file=sys.stderr, flush=True)
            return False

    def discover(parent):
        # A disk receipt alone cannot prove ancestry or ownership.
        for child in parent.children(recursive=True):
            try:
                rec = identity(child.pid)
                parents = [identity(p.pid) for p in child.parents()]
                if target not in parents or not matching(rec) or not matching(target):
                    continue
                known[rec['pid']] = rec
                ancestry[rec['pid']] = parents[:parents.index(target) + 1]
                if not any(x['identity'] == rec for x in receipt['observed_descendants']):
                    receipt['observed_descendants'].append({'identity': rec, 'ancestors': ancestry[rec['pid']], 'observed_epoch': time.time()})
            except psutil.NoSuchProcess:
                continue

    def terminate(rec, reason):
        try:
            process = matching(rec)
            if process:
                process.terminate()
                try:
                    process.wait(timeout=1)
                except psutil.TimeoutExpired:
                    process = matching(rec)
                    if process:
                        process.kill()
                        process.wait(timeout=1)
                receipt['stopped'].append({'identity': rec, 'reason': reason})
        except psutil.NoSuchProcess:
            pass
        except (psutil.AccessDenied, psutil.TimeoutExpired) as error:
            receipt['unknown'].append({'phase': 'cleanup', 'identity': rec, 'error': repr(error)})

    armed = publish()
    reason = None if armed else 'initial_receipt_unavailable'
    while reason is None:
        try:
            parent = matching(target)
            if parent:
                discover(parent)
            else:
                reason = 'supervisor_missing'
        except psutil.NoSuchProcess:
            # Parent can exit between identity verification and enumeration.
            reason = 'supervisor_missing'
        except psutil.AccessDenied as error:
            receipt['unknown'].append({'phase': 'observe', 'error': repr(error)})
            reason = 'identity_unknown'
        if stop(out):
            reason = 'STOP'
        if time.monotonic() >= deadline:
            reason = 'deadline'
        if (out / 'supervisor_exit.json').exists() and reason is None:
            reason = 'observed_supervisor_exit'
        if (out / 'abort.json').exists() and reason is None:
            reason = 'launch_abort'
        try:
            active = read(out / 'active_worker.json') if (out / 'active_worker.json').exists() else None
            if active:
                rec = active['identity']
                if known.get(rec['pid']) != rec or target not in ancestry.get(rec['pid'], []):
                    process = matching(rec)
                    parent = matching(target)
                    if process and parent:
                        discover(parent)
                    if known.get(rec['pid']) != rec or target not in ancestry.get(rec['pid'], []):
                        if process:
                            receipt['unknown'].append({'phase': 'unowned_worker_receipt', 'identity': rec})
                            reason = 'worker_identity_unknown'
                        active = None
                if active:
                    key = json.dumps(rec, sort_keys=True)
                    worker_deadline = active['deadline_monotonic']
                    if not isinstance(worker_deadline, (int, float)) or isinstance(worker_deadline, bool) or not math.isfinite(worker_deadline):
                        raise ValueError('Invalid worker deadline')
                    if key not in case_deadlines:
                        case_deadlines[key] = min(deadline, worker_deadline)
                    if time.monotonic() >= case_deadlines[key]:
                        for owned in reversed(list(known.values())):
                            if owned == rec or rec in ancestry.get(owned['pid'], []):
                                terminate(owned, 'case_deadline')
        except psutil.NoSuchProcess:
            pass
        except (OSError, ValueError, KeyError, TypeError, psutil.AccessDenied) as error:
            receipt['unknown'].append({'phase': 'active_worker', 'error': repr(error)})
            reason = 'worker_receipt_unreadable'
        publish()
        if reason is None:
            time.sleep(.2)
    try:
        parent = matching(target)
        if parent:
            discover(parent)
    except psutil.NoSuchProcess:
        pass
    except psutil.AccessDenied as error:
        receipt['unknown'].append({'phase': 'final_observe', 'error': repr(error)})
    for rec in reversed(list(known.values())):
        terminate(rec, reason)
    receipt.update(status='finished', reason=reason, wall_seconds=time.monotonic() - began)
    saved = publish()
    print(json.dumps({'guard_final_receipt': receipt, 'receipt_saved': saved}, ensure_ascii=False), flush=True)
    return 3 if publication_failed else (0 if not receipt['unknown'] else 2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    raise SystemExit(run_guard(parser.parse_args().out))
