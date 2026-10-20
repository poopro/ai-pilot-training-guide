"""Reserve one bounded Host round after authoritative workload/resource checks."""
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import sys
import time
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner import JobLock

with JobLock(ROOT / 'launch.lock'):
    if (ROOT / 'STOP').exists():
        raise RuntimeError('STOP exists')
    if psutil.virtual_memory().available < 2*2**30 or psutil.disk_usage(str(ROOT)).free < 10*2**30:
        raise RuntimeError('Insufficient RAM or disk')
    for process in psutil.process_iter(['name','cmdline']):
        if process.pid == os.getpid():
            continue
        if 'jsb_host_gui_publish' in (process.info['name'] or '').lower():
            raise RuntimeError('Host already active')
        if 'python' not in (process.info['name'] or '').lower():
            continue
        command = process.cmdline()
        for token in command:
            normalized = token.replace('\\','/').lower()
            base = normalized.rsplit('/',1)[-1]
            if not normalized.startswith('e:/ai_pilot/') or not base.endswith('.py'):
                continue
            if (base.startswith(('benchmark','train_','calibrate'))
                or (base in ('runner.py','launch_diagnostic.py','launch_smoke.py')
                    and any(v in command for v in ('run','worker','guard')))
                or base == 'host_watchdog.py'):
                raise RuntimeError(f'Existing compute/watchdog PID {process.pid}')
    day = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
    path = ROOT / 'compute_budgets' / (day+'.json')
    budget = json.loads(path.read_text(encoding='utf-8'))
    gate = json.loads((ROOT/'diagnostics/host_gate_latest.json').read_text(encoding='utf-8'))
    if gate['eligible_rounds'] >= gate['required_rounds']:
        raise RuntimeError('Six-round gate already fulfilled; avoid unnecessary round')
    ident = 'host_fixed_round'+str(gate['eligible_rounds']+1)+'_'+str(time.time_ns())
    budget['reserved_hours'] += .2
    budget['items'].append({'id':ident,'hours':.2,'status':'reserved',
                            'kind':'official_host_fixed_round','deadline_seconds':720})
    path.write_text(json.dumps(budget,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'diagnostics/active_host_budget.json').write_text(
        json.dumps({'ledger':str(path),'id':ident},indent=2),encoding='utf-8')
    print(json.dumps({'reservation_id':ident,'reserved_hours':budget['reserved_hours'],
                      'next_round':gate['eligible_rounds']+1},ensure_ascii=False))
