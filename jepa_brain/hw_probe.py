"""Hardware probe + brain planner latency benchmark (read-only, writes runs/hw_probe.json)."""
import os, sys, json, time, platform, subprocess
import numpy as np
out = {'time': time.strftime('%F %T'), 'platform': platform.platform(), 'machine': platform.machine(),
       'python': sys.version.split()[0], 'logical_cpus': os.cpu_count()}
try:
    import psutil
    vm = psutil.virtual_memory()
    out['ram_total_gib'] = round(vm.total / 2**30, 2); out['ram_avail_gib'] = round(vm.available / 2**30, 2)
    out['physical_cores'] = psutil.cpu_count(logical=False)
    f = psutil.cpu_freq(); out['cpu_mhz'] = f.max if f else None
except Exception as e:
    out['psutil_err'] = repr(e)
def ps(cmd):
    try:
        return subprocess.run(['powershell', '-NoProfile', '-Command', cmd], capture_output=True, text=True, timeout=40).stdout.strip()
    except Exception as e:
        return repr(e)
out['cpu_name'] = ps('(Get-CimInstance Win32_Processor).Name')
out['gpu'] = ps('(Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name + " | " + [math]::Round($_.AdapterRAM/1GB,1) + "GB" }) -join "; "')
out['model'] = ps('(Get-CimInstance Win32_ComputerSystem | ForEach-Object { $_.Manufacturer + " " + $_.Model })')
out['nic'] = ps('(Get-NetAdapter | Where-Object Status -eq "Up" | ForEach-Object { $_.Name + " [" + $_.InterfaceDescription + "] " + $_.LinkSpeed }) -join "; "')
try:
    import torch
    torch.set_num_threads(1)
    out['torch'] = torch.__version__; out['cuda'] = torch.cuda.is_available()
    from common import *  # noqa
    from brain import Brain
    from feats import WINDOW, TOKEN_DIM
    b = Brain().eval()
    win = torch.randn(1, WINDOW, TOKEN_DIM)
    mask = torch.ones(8, dtype=torch.bool)
    import inspect
    res = {}
    for H in (2, 3):
        ts = []
        for i in range(60):
            t0 = time.perf_counter()
            with torch.no_grad():
                try:
                    b.plan(win, mask, 0, horizon=H)
                except Exception:
                    b.plan(win[0].numpy(), mask.numpy(), 0, horizon=H)
            ts.append((time.perf_counter() - t0) * 1000)
        ts = ts[5:]
        res[f'H{H}'] = {'mean_ms': round(float(np.mean(ts)), 2), 'p99_ms': round(float(np.percentile(ts, 99)), 2), 'max_ms': round(max(ts), 2)}
    out['plan_latency'] = res
    out['n_params'] = sum(p.numel() for p in b.parameters())
except Exception as e:
    import traceback; out['bench_err'] = traceback.format_exc()
os.makedirs('runs', exist_ok=True)
json.dump(out, open('runs/hw_probe.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
