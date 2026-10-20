"""Tiny local job runner.  Runs ONLY python scripts that sit directly in this folder.

Job file (jobs/pending/<id>.json): {"script": "rollout.py", "args": ["smoke"], "max_minutes": 180}
Stop everything: create jobs/STOP (or double-click STOP_WORKER.cmd). Logs: logs/<id>.log
Children run at BELOW_NORMAL priority; new jobs wait while free RAM < 2.5 GiB.
"""
import json, os, subprocess, sys, time, traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
JOBS = HERE / 'jobs'; PENDING = JOBS / 'pending'; RUNNING = JOBS / 'running'; DONE = JOBS / 'done'; LOGS = HERE / 'logs'
STOP = JOBS / 'STOP'; STATUS = JOBS / 'worker_status.json'
for d in (PENDING, RUNNING, DONE, LOGS):
    d.mkdir(parents=True, exist_ok=True)


def kill_tree(pid):
    subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True)


def ram_ok():
    try:
        import psutil
        return psutil.virtual_memory().available > 2.5 * 1024 ** 3
    except Exception:
        return True


def status(**kw):
    kw['time'] = time.strftime('%Y-%m-%d %H:%M:%S'); kw['pid'] = os.getpid()
    STATUS.write_text(json.dumps(kw, ensure_ascii=False), encoding='utf-8')


def run_job(path):
    job = json.loads(path.read_text(encoding='utf-8'))
    jid = path.stem
    script = str(job['script'])
    if os.sep in script or '/' in script or script == 'worker.py' or not (HERE / script).is_file() or not script.endswith('.py'):
        return dict(id=jid, error='script not allowed: ' + script)
    running = RUNNING / path.name
    path.replace(running)
    log = (LOGS / (jid + '.log')).open('w', encoding='utf-8')
    cmd = [sys.executable, '-X', 'utf8', '-u', script] + [str(x) for x in job.get('args', [])]
    flags = getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=str(HERE), stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
    limit = float(job.get('max_minutes', 180)) * 60
    reason = None
    while proc.poll() is None:
        if STOP.exists(): reason = 'stopped'; break
        if time.time() - t0 > limit: reason = 'timeout'; break
        status(state='running', job=jid, script=script, args=job.get('args', []), elapsed_s=round(time.time() - t0))
        time.sleep(3)
    if reason:
        kill_tree(proc.pid)
    log.close()
    rc = proc.poll()
    out = dict(id=jid, script=script, args=job.get('args', []), exit_code=rc, reason=reason, seconds=round(time.time() - t0, 1))
    (DONE / (jid + '.result.json')).write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    running.replace(DONE / path.name)
    return out


def main():
    print('worker pid', os.getpid(), 'folder', HERE, flush=True)
    while not STOP.exists():
        status(state='idle')
        jobs = sorted(PENDING.glob('*.json'))
        if jobs and ram_ok():
            try:
                print(run_job(jobs[0]), flush=True)
            except Exception:
                traceback.print_exc()
                try: jobs[0].replace(DONE / (jobs[0].stem + '.error.json'))
                except Exception: pass
        time.sleep(3)
    status(state='stopped')
    print('STOP file found; worker exiting', flush=True)


if __name__ == '__main__':
    main()
