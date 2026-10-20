"""Read saved telemetry only; never imports models, controllers or FDM."""
import csv,json,hashlib,datetime,time
from pathlib import Path
import psutil
ROOT=Path(r'E:\ai_pilot\campaign_2026')
RUN=ROOT/'experiments/opponent_pool/m4_grid_eval_v1/run_20261016_104729_96f65a'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(name):
    p=RUN/'cases'/name/'telemetry.csv'
    with p.open(encoding='utf8',newline='') as f: rows=list(csv.DictReader(f))
    return p,rows
def stats(rows):
    inrange=lambda r:500*.3048<=float(r['distance_m'])<=3000*.3048
    hit=lambda r:inrange(r) and float(r['blue_angle_deg'])<=1
    segments=[];start=None
    for r in rows:
        if hit(r) and start is None:start=int(r['tick'])
        if not hit(r) and start is not None:
            segments.append([start,int(r['tick'])-1]);start=None
    if start is not None:segments.append([start,int(rows[-1]['tick'])])
    return {'ticks':len(rows),'end_event':rows[-1]['event'],'end_attack_ticks':int(rows[-1]['attack_ticks']),
      'recomputed_hit_ticks':sum(hit(r) for r in rows),'range_window_ticks':sum(inrange(r) for r in rows),
      'angle_within_1deg_ticks':sum(float(r['blue_angle_deg'])<=1 for r in rows),
      'range_ok_angle_out_ticks':sum(inrange(r) and float(r['blue_angle_deg'])>1 for r in rows),
      'angle_ok_range_out_ticks':sum(float(r['blue_angle_deg'])<=1 and not inrange(r) for r in rows),
      'attack_segments_tick_inclusive':segments,'min_AGL_m':min(float(r['blue_agl_m']) for r in rows)}
started=time.time(); verification=RUN/'VERIFICATION.json'
assert json.loads(verification.read_text(encoding='utf8'))['verified_paired_final_policy'] is True
report={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'saved development telemetry only; no new FDM/model inference or training','source_verification_sha256':sha(verification),'cases':{},'usage_observation':{'observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'five_hour_remaining':85,'weekly_remaining':55,'primary_reset':1792169034,'weekly_reset':1792654206},'process_inventory':[]}
for p in psutil.process_iter(['pid','create_time','cmdline','exe','ppid']):
    try:
        text=' '.join(p.info['cmdline'] or [])
        if str(ROOT).lower() in text.lower() and any(x in text for x in ('run_smoke.py','win_loop.py','m4_tactical_rl.py','portable_host.py')):report['process_inventory'].append(p.info)
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
for opponent,seed in [('rule',2026300302),('mirror',2026300303)]:
    pa,a=load(f'final_{opponent}_sac5000_{seed}');pb,b=load(f'final_{opponent}_transfer10000_{seed}')
    sa,sb=stats(a),stats(b)
    assert sa['end_attack_ticks']==sa['recomputed_hit_ticks'] and sb['end_attack_ticks']==sb['recomputed_hit_ticks']
    dif=next(((ra,rb) for ra,rb in zip(a,b) if json.loads(ra['actual_command'])!=json.loads(rb['actual_command'])),None)
    report['cases'][opponent]={'old':sa,'new':sb,'csv_sha256':{'old':sha(pa),'new':sha(pb)},'common_exposure_ticks':min(len(a),len(b)),
      'common_exposure':{'old':stats(a[:min(len(a),len(b))]),'new':stats(b[:min(len(a),len(b))])},
      'first_command_divergence':None if dif is None else {'tick':int(dif[0]['tick']),'old_command':json.loads(dif[0]['actual_command']),'new_command':json.loads(dif[1]['actual_command']),'same_recorded_observation_hash':dif[0]['observation_sha256']==dif[1]['observation_sha256']},
      'hypothesis':'Both earliest differing commands change throttle only at equal recorded observation hashes. Later loss of angle-window retention may involve tactical speed/energy modulation; this is an association, not a demonstrated cause. A later one-factor throttle-channel ablation requires a new isolated contract and paired diagnostics before training.',
      'next_single_factor':'First validate frozen learned-red adapter with true model and private controller timing; do not retrain or change gains based on this descriptive analysis.'}
report['elapsed_seconds']=time.time()-started
out=ROOT/'diagnostics/GRID_REGRESSION_WINDOW_REVIEW_20261016.json'
out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False,indent=2))
