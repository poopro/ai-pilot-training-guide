"""Independent owned process watchdog; never starts any simulator."""
import argparse,time,os
from pathlib import Path
from common import *

def run_guard(out):
    out=Path(out);launch=read(out/'launch.json');target=launch['supervisor'];known={target['pid']:target}
    began=time.monotonic();limit=launch['total_wall_seconds']
    if not 30<=limit<=900:raise ValueError('Invalid reserved guard deadline')
    deadline=time.time()+limit
    receipt={'status':'armed','guard':identity(),'target':target,'deadline_epoch':deadline,'stopped':[],'unknown':[],'observed_descendants':[]}
    publication_failed=False
    def publish():
        nonlocal publication_failed
        try:
            write(out/'guard.json',receipt);publication_failed=False;return True
        except OSError as error:
            publication_failed=True
            receipt.setdefault('publication_errors',[]).append({'epoch':time.time(),'error':repr(error)})
            print('Guard receipt publication failed; deadline and cleanup remain active: '+repr(error),file=sys.stderr,flush=True)
            return False
    armed=publish()
    reason=None if armed else 'initial_receipt_unavailable' 
    while not reason:
        try:
            parent=matching(target)
            if parent:
                for child in parent.children(recursive=True):
                    try:
                        if child.pid not in known:
                            ident=identity(child.pid);known[child.pid]=ident
                            receipt['observed_descendants'].append({'identity':ident,'observed_parent_pid':child.ppid(),'observed_under_supervisor':target['pid'],'observed_epoch':time.time()})
                    except psutil.NoSuchProcess:pass
            else:reason='supervisor_missing'
        except psutil.AccessDenied:
            receipt['unknown'].append({'phase':'observe','time':time.time()});reason='identity_unknown'
        if stop(out):reason='STOP'
        if time.time()>=deadline:reason='deadline'
        if (out/'supervisor_exit.json').exists():reason='observed_supervisor_exit'
        if (out/'abort.json').exists():reason='launch_abort'
        # Individual worker hard deadline remains independent of supervisor polling.
        publish()
        try:active=read(out/'active_worker.json') if (out/'active_worker.json').exists() else None
        except (OSError,ValueError) as error:
            receipt['unknown'].append({'phase':'read_active_worker','error':repr(error)});reason='worker_receipt_unreadable';active=None
        if active and time.time()>=active['deadline_epoch']:
            rec=active['identity']
            try:
                p=matching(rec)
                if p:p.terminate();receipt['stopped'].append({'identity':rec,'reason':'case_deadline'})
            except psutil.AccessDenied:receipt['unknown'].append({'phase':'worker_deadline','identity':rec})
        if not reason:time.sleep(.2)
    for rec in reversed(list(known.values())):
        try:
            p=matching(rec)
            if p:
                p.terminate()
                try:p.wait(timeout=2)
                except psutil.TimeoutExpired:
                    p=matching(rec)
                    if p:p.kill();p.wait(timeout=2)
                receipt['stopped'].append({'identity':rec,'reason':reason})
        except psutil.NoSuchProcess:pass
        except (psutil.AccessDenied,psutil.TimeoutExpired) as e:receipt['unknown'].append({'identity':rec,'error':repr(e)})
    receipt.update(status='finished',reason=reason,wall_seconds=time.monotonic()-began)
    publish()
    return 3 if publication_failed else (0 if not receipt['unknown'] else 2)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    raise SystemExit(run_guard(p.parse_args().out))
