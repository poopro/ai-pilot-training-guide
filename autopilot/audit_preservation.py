"""Confirm original snapshots and v2 files without modifying training sources."""
from common import *
job=read(ROOT/'最新狀態.json');folder=Path(job['job_dir']);snap=folder/'baseline_source'
hashes=read(snap/'hashes.json');checks=[]
for name,expected in hashes.items():
    backup=snap/name
    checks.append({'path':str(backup),'matches_recorded_sha256':digest(backup)==expected})
v2=[{'path':str(BASE/name),'unchanged':digest(BASE/name)==value}
    for name,value in hashes.items() if name.startswith('combat_v2') or name.startswith('envs')]
result={'snapshot_checks':checks,'preserved_baseline_sources':v2,
        'all_preserved':all(c['matches_recorded_sha256'] for c in checks) and all(c['unchanged'] for c in v2),
        'note':'Original v2 model bundles are untouched; source and FDM checks above compare first snapshot.',
        'utc':stamp()}
baseline=BASE/'combat_v2/outputs/run_20261003_195337_befc/final_0000200000'
m=read(baseline/'manifest.json')
bundle_checks={name:digest(baseline/(name+ext))==m[name+'_sha256'] for name,ext in (('model','.zip'),('replay','.pkl'))}
result['v2_bundle']={'path':str(baseline),'timesteps':m['timesteps'],'checks':bundle_checks}
result['all_preserved']=result['all_preserved'] and all(bundle_checks.values())
atomic(folder/'baseline_preservation_audit.json',result)
print(json.dumps({'all_preserved':result['all_preserved'],'sources_checked':len(checks),'old_sources_unchanged':len(v2)}))
if not result['all_preserved']:raise SystemExit(1)
