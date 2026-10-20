"""Independent owned process watchdog; never starts any simulator."""
import argparse,time,os
from pathlib import Path
from common import *

def run_guard(out):
    out=Path(out);launch=read(out/'launch.json');target=launch['supervisor'];known={target['pid']:target}
    began=time.monotonic();deadline=time.time()+900
    receipt={'status':'armed','guard':identity(),'target':target,'deadline_epoch':deadline,'stopped':[],'unknown':[],'observed_descendants':[]}
    write(out/'guard.json',receipt)
    reason=None
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
        write(out/'guard.json',receipt)
        active=read(out/'active_worker.json') if (out/'active_worker.json').exists() else None
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
    write(out/'guard.json',receipt)
    return 0 if not receipt['unknown'] else 2

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    raise SystemExit(run_guard(p.parse_args().out))
