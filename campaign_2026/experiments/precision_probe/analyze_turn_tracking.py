"""Time-aligned, read-only analysis of one previously observed development case."""
from pathlib import Path
import csv,hashlib,json,math,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(r'E:\ai_pilot\campaign_2026')
sys.path.insert(0,str(ROOT/'diagnostics'))
from observation_diagnostics import analyze_observation

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def wrap(x):return (x+180)%360-180
def stats(rows):
    if not rows:return {'samples':0}
    names=['nose_deg','heading_error_deg','bank_error_deg','roll_deg','roll_rate_deg_s',
        'load_abs','alpha_deg','yaw_rate_deg_s','los_rate_deg_s','rate_error_deg_s']
    return {'samples':len(rows),'absolute_medians':{k:float(np.median([abs(r[k]) for r in rows])) for k in names},
        'load_below_one_fraction':float(np.mean([r['load_abs']<1 for r in rows])),
        'opposite_yaw_to_los_fraction':float(np.mean([r['yaw_rate_deg_s']*r['los_rate_deg_s']<0 for r in rows]))}

case=ROOT/'experiments'/'precision_probe'/'case'
result=read(case/'result.json');meta=read(case.parent/'PROBE.json');original=read(Path(meta['original_result']))
assert result['score_eligible'] and result['full_round_completed'] and result['steps']==18000
assert original['initial_sha256']==result['initial_sha256'] and original['metrics']==result['metrics']
paths=[case/'telemetry.csv',case/'result.json',Path(meta['original_result'])]
hashes={str(p):sha(p) for p in paths}
parsed=[]
with paths[0].open(encoding='utf-8',newline='') as f:
    for r in csv.DictReader(f):
        o=np.array(json.loads(r['legal_obs26']),dtype=float)
        assert o.shape==(26,) and np.isfinite(o).all()
        g=analyze_observation(o)
        phi,theta=np.radians(o[3:5]);p,q,b=o[9:12]
        yaw=math.degrees((q*math.sin(phi)+b*math.cos(phi))/math.cos(theta))
        rollrate=math.degrees(p+math.tan(theta)*(q*math.sin(phi)+b*math.cos(phi)))
        lat,lat2=np.radians([o[0],o[20]])
        n=(lat2-lat)*6378137;e=math.radians(wrap(o[21]-o[1]))*6378137*math.cos((lat+lat2)/2)
        vn,ve=(o[23:25]-o[6:8])*.3048
        los=math.degrees((n*ve-e*vn)/max(n*n+e*e,1e-9))
        parsed.append({'time_s':float(r['simulation_seconds']),'distance_m':g['range_m'],
            'nose_deg':g['nose_error_deg'],'heading_error_deg':float(r['heading_error_deg_legal']),
            'heading_deg':o[5],'bank_target_deg':float(r['command_bank_target_before_tick']),
            'bank_error_deg':wrap(float(r['command_bank_target_before_tick'])-o[3]),
            'roll_deg':o[3],'roll_rate_deg_s':rollrate,'alpha_deg':o[18],
            'load_signed':o[14],'load_abs':abs(o[14]),'yaw_rate_deg_s':yaw,'los_rate_deg_s':los,
            'rate_error_deg_s':los-yaw,'mode':r['controller_mode']})
assert len(parsed)==3000 and all(abs(b['time_s']-a['time_s']-.1)<1e-9 for a,b in zip(parsed,parsed[1:]))
firing=[r for r in parsed if 500*.3048<=r['distance_m']<=3000*.3048]
aim=[r for r in firing if r['nose_deg']<=10]
highbank=[r for r in aim if abs(r['roll_deg'])>=45]
tracking=[r for r in highbank if abs(r['bank_error_deg'])<=5]
lowload=[r for r in highbank if r['load_abs']<1]
loaded=[r for r in highbank if r['load_abs']>=1]
fd_errors=[]
for a,b in zip(parsed,parsed[1:]):
    fd=wrap(b['heading_deg']-a['heading_deg'])/(b['time_s']-a['time_s'])
    fd_errors.append(abs(fd-.5*(a['yaw_rate_deg_s']+b['yaw_rate_deg_s'])))
best=min(firing,key=lambda r:r['nose_deg']);window=[r for r in parsed if abs(r['time_s']-best['time_s'])<=8]
report={'case_id':result['case_id'],'input_sha256':hashes,'source_sha256':sha(Path(__file__)),
    'full_original_round_reproduced':True,'sample_hz':10,'sample_count':len(parsed),'no_new_simulator_ticks':True,
    'firing_range':stats(firing),'aiming_within10':stats(aim),'aiming_high_bank':stats(highbank),
    'aiming_high_bank_error_within5':stats(tracking),'aiming_high_bank_load_below1':stats(lowload),
    'aiming_high_bank_load_at_least1':stats(loaded),
    'finite_difference_vs_euler_yaw_abs_error_p50_p95_deg_s':np.percentile(fd_errors,[50,95]).tolist(),
    'best_sample':best,'window_start_s':window[0]['time_s'],'window_end_s':window[-1]['time_s'],
    'official_validation':False,
    'limits':['One selected observed development case; descriptive association, not causal proof or win rate.',
        'Bank command precedes recorded observation by one physics tick; samples are 0.1s apart.',
        'No command/actuator history or integral states were logged; cannot infer zero aileron equilibrium.',
        'Absolute pilot load is used without asserting force decomposition or calibration of lift.',
        'Finite differences check sampled yaw kinematics, not empirical rudder/elevator signs or roll-step response.']}
out=case.parent/'tracking_analysis';out.mkdir(exist_ok=False)
with (out/'aligned_samples.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(parsed[0]));w.writeheader();w.writerows(parsed)
t=[r['time_s'] for r in window]
fig,axes=plt.subplots(4,1,figsize=(11,9),sharex=True,layout='constrained')
for axis,fields,label in [
    (axes[0],[('nose_deg','Nose error'),('heading_error_deg','Signed heading error')],'Error (deg)'),
    (axes[1],[('bank_target_deg','Bank target (before tick)'),('roll_deg','Actual bank')],'Bank (deg)'),
    (axes[2],[('load_abs','Absolute pilot load')],'Load (norm)'),
    (axes[3],[('los_rate_deg_s','LOS bearing rate'),('yaw_rate_deg_s','Actual heading rate')],'Rate (deg/s)')]:
    for key,label_line in fields:axis.plot(t,[r[key] for r in window],label=label_line,lw=1.6)
    axis.set_ylabel(label);axis.grid(alpha=.25);axis.legend(loc='best',fontsize=8)
    axis.axvline(best['time_s'],color='black',ls=':',lw=.8)
axes[0].axhline(1,color='gray',ls='--',lw=.8);axes[2].axhline(1,color='gray',ls='--',lw=.8)
axes[-1].set_xlabel('Simulation time (s)')
fig.suptitle('One selected development case: simultaneous aiming / bank / load / heading rate\nDescriptive evidence only; no controller changes; vertical line = best sampled aim',fontsize=11)
fig.savefig(out/'turn_tracking.png',dpi=160);plt.close(fig)
assert all(sha(Path(p))==v for p,v in hashes.items())
(out/'ANALYSIS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:report[k] for k in ['aiming_high_bank','aiming_high_bank_error_within5','aiming_high_bank_load_below1','aiming_high_bank_load_at_least1','finite_difference_vs_euler_yaw_abs_error_p50_p95_deg_s']},ensure_ascii=False))
