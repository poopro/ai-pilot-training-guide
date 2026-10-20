from pathlib import Path
import csv, json, math, sys
import numpy as np
ROOT=Path(r'E:\ai_pilot\campaign_2026')
sys.path.insert(0,str(ROOT/'diagnostics'))
from observation_diagnostics import analyze_observation

folder=ROOT/'experiments'/'precision_probe'/'case'
result=json.loads((folder/'result.json').read_text(encoding='utf-8'))
if not result.get('score_eligible') or not result.get('full_round_completed'):
    raise ValueError('Probe is not a completed round')
meta=json.loads((folder.parent/'PROBE.json').read_text(encoding='utf-8'))
original=json.loads(Path(meta['original_result']).read_text(encoding='utf-8'))
if original['initial_sha256']!=result['initial_sha256'] or any(not math.isclose(float(v),float(result['metrics'][k]),rel_tol=0,abs_tol=1e-6) for k,v in original['metrics'].items()):
    raise ValueError('Read-only replay did not reproduce the original case')
with (folder/'telemetry.csv').open(encoding='utf-8',newline='') as stream: rows=list(csv.DictReader(stream))
parsed=[]; errors=[]
for row in rows:
    obs=json.loads(row['legal_obs26']); diag=analyze_observation(obs)
    for key,csv_key in [('nose_error_deg','blue_angle_deg_judge_only'),('body_azimuth_deg','body_az_deg_legal'),('body_elevation_deg','body_el_deg_legal')]:
        if diag[key] is not None: errors.append(abs(diag[key]-float(row[csv_key])))
    phi,theta=map(math.radians,obs[3:5])
    yaw_rate=math.degrees((obs[10]*math.sin(phi)+obs[11]*math.cos(phi))/math.cos(theta))
    lat,lat2=map(math.radians,[obs[0],obs[20]])
    north=(lat2-lat)*6378137;east=math.radians(obs[21]-obs[1])*6378137*math.cos((lat+lat2)/2)
    vn,ve=(np.asarray(obs[23:25])-np.asarray(obs[6:8]))*.3048
    los_rate=math.degrees((north*ve-east*vn)/max(north*north+east*east,1e-9))
    parsed.append({'time_s':float(row['simulation_seconds']),'distance_m':diag['range_m'],
        'nose_deg':diag['nose_error_deg'],'body_az_deg':diag['body_azimuth_deg'],'body_el_deg':diag['body_elevation_deg'],
        'heading_error_deg':float(row['heading_error_deg_legal']),
        'world_pitch_error_deg':float(row['world_elevation_deg_legal'])-obs[4],
        'command_pitch_error_deg':float(row['command_pitch_target_before_tick'])-obs[4],
        'command_bank_error_deg':(float(row['command_bank_target_before_tick'])-obs[3]+180)%360-180,
        'roll_deg':obs[3],'pitch_deg':obs[4],'alpha_deg':obs[18],
        'yaw_rate_deg_s':yaw_rate,'los_rate_deg_s':los_rate,'los_minus_yaw_rate_deg_s':los_rate-yaw_rate,
        'load_factor':obs[14],
        'closing_mps':diag['closing_mps'],'mode':row['controller_mode']})
if max(errors)>1e-5: raise ValueError('Legal diagnostics disagree with the existing geometry')
close=[r for r in parsed if r['distance_m']<1100]
firing_range=[r for r in close if 500*.3048<=r['distance_m']<=3000*.3048]
aiming=[r for r in firing_range if r['nose_deg']<=10]
def describe(rows):
    if not rows:return {'samples':0}
    fields=['nose_deg','body_az_deg','body_el_deg','heading_error_deg','world_pitch_error_deg','command_pitch_error_deg','command_bank_error_deg','roll_deg','alpha_deg','closing_mps','yaw_rate_deg_s','los_rate_deg_s','los_minus_yaw_rate_deg_s','load_factor']
    return {'samples':len(rows),'absolute_p10_p50_p90':{k:np.percentile([abs(r[k]) for r in rows if r[k] is not None],[10,50,90]).tolist() for k in fields},
        'in_cone_fractions':{str(c):sum(r['nose_deg']<=c for r in rows)/len(rows) for c in [10,3,1]},
        'horizontal_body_within1_vertical_outside1_fraction':sum(abs(r['body_az_deg'] or 0)<=1 and abs(r['body_el_deg'])>1 for r in rows)/len(rows),
        'vertical_body_within1_horizontal_outside1_fraction':sum(abs(r['body_el_deg'])<=1 and abs(r['body_az_deg'] or 0)>1 for r in rows)/len(rows)}
report={'case_id':result['case_id'],'full_round_completed':True,'reproduced_original_metrics':True,
    'exact_metrics':result['metrics'],'sample_count':len(rows),'sample_hz':10,
    'max_geometry_error_deg':max(errors),'close':describe(close),'firing_range':describe(firing_range),
    'aiming_within10':describe(aiming),'best_10_close_samples':sorted(firing_range,key=lambda r:r['nose_deg'])[:10],
    'official_validation':False,'interpretation':'This is one selected development case; sample proportions are not exact tick durations or win rates. Commands precede the recorded observations by one physics tick.'}
out=folder.parent/'ANALYSIS.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ['best_10_close_samples','interpretation']},ensure_ascii=False))
