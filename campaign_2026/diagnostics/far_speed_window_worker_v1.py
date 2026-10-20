"""Selected saved packets only; scalar extraction plus independent NumPy audit.

No controller, simulator, actor or training calls. Stream scans select windows;
only selected packets receive new numerical calculations.
"""
from pathlib import Path
import csv,json,math,os,sys,statistics
ROOT=Path(r'E:\ai_pilot\campaign_2026')
SOURCE=ROOT/'experiments/opponent_pool/far_speed_v1'
RUN=SOURCE/'run_20261018_033053_98bc0f'
sys.path.insert(0,str(SOURCE));import battle as b
read,write,sha=b.read,b.write,b.sha
def wrap(x):return (x+180.)%360.-180.
def clip(x,a,z):return max(a,min(z,x))
def bearing(p):
    n=math.radians(p[20]-p[0])*6378137.
    e=math.radians(p[21]-p[1])*6378137.*math.cos(math.radians((p[20]+p[0])/2))
    return math.degrees(math.atan2(e,n))%360.
def course(n,e):return math.degrees(math.atan2(e,n))%360.
def metrics(row,prev):
    p=row['blue_packet_pre'];old=prev['blue_packet_pre'] if prev else p
    n=math.radians(p[20]-p[0])*6378137.;e=math.radians(p[21]-p[1])*6378137.*math.cos(math.radians((p[20]+p[0])/2));down=-(p[22]-p[2])*.3048
    d=math.sqrt(n*n+e*e+down*down);rv=[(p[23+k]-p[6+k])*.3048 for k in range(3)]
    ratio=clip(p[12]/max(p[13],1.),.4,1.2)
    enemy_speed=math.sqrt(sum((v*.3048)**2 for v in p[23:26]))
    eq=enemy_speed*1.9438444924*ratio
    close=clip((d-600.)*.07,-30.,65.) if not 152.4<=d<=914.4 else 0.
    close_cas=close*1.9438444924*ratio;raw=eq+close_cas
    los=bearing(p);lead_seconds=min(10.,d/max(max(p[13]*.3048,100.),150.))
    lead=math.degrees(math.atan2(e+p[24]*.3048*lead_seconds,n+p[23]*.3048*lead_seconds))%360.
    adjusted=los+(clip(wrap(lead-los),-20.,20.)*.35 if not 152.4<=d<=914.4 else 0.)
    he=wrap(adjusted-p[5]);eligible=d>914.4 and abs(he)>45.
    original=clip(min(raw,290.) if abs(he)>45. and not 152.4<=d<=914.4 else raw,260.,450.)
    g=row['blue_guidance'];t=g['speed_trace']
    for key,value in [('distance_m',d),('heading_error_deg',he),('raw_speed_kts',raw),('original_speed_kts',original)]:
        assert abs(t[key]-value)<1e-7,(key,t[key],value)
    assert t['eligible']==eligible and t['enabled']==g['far_speed_enabled']
    assert abs(g['requested'][2]-original)<1e-7
    assert abs(g['applied'][2]-(clip(raw,260.,450.) if eligible and t['enabled'] else original))<1e-7
    assert all(g['requested'][k]==g['applied'][k] for k in (0,1,3))
    dt=60. if prev else 0.
    return dict(tick=int(row['tick']),pre_time_s=(row['tick']-1)/60.,distance_pre_m=d,distance_post_m=float(row['distance_m']),heading_error_deg=he,
        raw_speed_kts=raw,enemy_equivalent_cas_proxy_kts=eq,desired_close_mps=close,desired_close_cas_term_kts=close_cas,cas_ratio=ratio,
        raw_at450=bool(raw>=450.),eligible=bool(eligible),requested_speed_kts=float(g['requested'][2]),applied_speed_kts=float(g['applied'][2]),
        actual_CAS_kts=p[12]/1.6878098571011957,actual_TAS_kts=p[13]/1.6878098571011957,
        actual_ground_speed_kts=math.sqrt(sum(v*v for v in p[6:9]))*.3048*3600/1852,
        actual_bank_deg=float(p[3]),requested_bank_deg=float(g['applied'][0]),abs_roll_tracking_error_deg=abs(wrap(g['applied'][0]-p[3])),
        actual_throttle=float(row['blue_command'][3]),guard_active=bool(row['blue_private_guard']),G_guard_input=bool(abs(p[14])>8.5),
        own_HSL_pre_m=p[2]*.3048,own_AGL_post_m=float(row['blue_agl_m']),
        closure_mps=-(n*rv[0]+e*rv[1]+down*rv[2])/d,
        LOS_rate_deg_s=wrap(los-bearing(old))*dt,own_heading_rate_deg_s=wrap(p[5]-old[5])*dt,
        own_ground_course_rate_deg_s=wrap(course(p[6],p[7])-course(old[6],old[7]))*dt,
        enemy_velocity_course_proxy_rate_deg_s=wrap(course(p[23],p[24])-course(old[23],old[24]))*dt)

def summary(rows):
    med=lambda k:float(statistics.median(r[k] for r in rows))
    return dict(rows=len(rows),first_tick=rows[0]['tick'],last_tick=rows[-1]['tick'],raw_at450_ticks=sum(r['raw_at450'] for r in rows),
        eligible_ticks=sum(r['eligible'] for r in rows),desired_close_at65_ticks=sum(r['desired_close_mps']>=65 for r in rows),
        median_raw_speed_kts=med('raw_speed_kts'),median_enemy_equivalent_cas_proxy_kts=med('enemy_equivalent_cas_proxy_kts'),median_desired_close_cas_term_kts=med('desired_close_cas_term_kts'),
        median_requested_speed_kts=med('requested_speed_kts'),median_applied_speed_kts=med('applied_speed_kts'),median_actual_CAS_kts=med('actual_CAS_kts'),median_actual_TAS_kts=med('actual_TAS_kts'),
        median_abs_speed_error_kts=float(statistics.median(abs(r['applied_speed_kts']-r['actual_CAS_kts']) for r in rows)),
        median_abs_heading_error_deg=float(statistics.median(abs(r['heading_error_deg']) for r in rows)),
        median_abs_actual_bank_deg=float(statistics.median(abs(r['actual_bank_deg']) for r in rows)),median_abs_roll_tracking_error_deg=med('abs_roll_tracking_error_deg'),
        median_abs_LOS_rate_deg_s=float(statistics.median(abs(r['LOS_rate_deg_s']) for r in rows)),
        median_abs_own_heading_rate_deg_s=float(statistics.median(abs(r['own_heading_rate_deg_s']) for r in rows)),
        median_abs_own_ground_course_rate_deg_s=float(statistics.median(abs(r['own_ground_course_rate_deg_s']) for r in rows)),
        median_closure_mps=med('closure_mps'),minimum_distance_pre_m=min(r['distance_pre_m'] for r in rows),distance_pre_change_m=rows[-1]['distance_pre_m']-rows[0]['distance_pre_m'],
        throttle_at_max_ticks=sum(r['actual_throttle']>=.999 for r in rows),guard_ticks=sum(r['guard_active'] for r in rows),G_guard_input_ticks=sum(r['G_guard_input'] for r in rows),
        HSL_pre_change_m=rows[-1]['own_HSL_pre_m']-rows[0]['own_HSL_pre_m'],minimum_AGL_post_m=min(r['own_AGL_post_m'] for r in rows))

def independent_audit(rawrows,computed):
    # Independent implementation: vector array operations, distinct conversion
    # expressions and explicit coordinate reconstruction, no scalar helper use.
    import numpy as np
    p=np.asarray([r['row']['blue_packet_pre'] for r in rawrows],dtype=float)
    prev=np.asarray([r['previous']['blue_packet_pre'] if r['previous'] else r['row']['blue_packet_pre'] for r in rawrows],dtype=float)
    rel=np.column_stack((np.deg2rad(p[:,20]-p[:,0])*6378137.,np.deg2rad(p[:,21]-p[:,1])*6378137.*np.cos(np.deg2rad((p[:,20]+p[:,0])/2)),(p[:,2]-p[:,22])*.3048))
    distance=np.linalg.norm(rel,axis=1);ratio=np.clip(p[:,12]/np.maximum(p[:,13],1.),.4,1.2)
    enemy=np.linalg.norm(p[:,23:26]*.3048,axis=1);eq=enemy*1.9438444924*ratio
    band=(distance>=152.4)&(distance<=914.4);close=np.where(band,0.,np.clip((distance-600.)*.07,-30.,65.))
    raw=eq+close*1.9438444924*ratio
    los=np.rad2deg(np.arctan2(rel[:,1],rel[:,0]))%360
    seconds=np.minimum(10.,distance/np.maximum(np.maximum(p[:,13]*.3048,100.),150.))
    lead=rel+p[:,23:26]*.3048*seconds[:,None]
    leadbearing=np.rad2deg(np.arctan2(lead[:,1],lead[:,0]))%360
    he=(los+np.where(band,0.,np.clip((leadbearing-los+180)%360-180,-20,20)*.35)-p[:,5]+180)%360-180
    def check(k,a,tol=1e-7):np.testing.assert_allclose([v[k] for v in computed],a,rtol=0,atol=tol,err_msg=k)
    check('distance_pre_m',distance);check('raw_speed_kts',raw);check('enemy_equivalent_cas_proxy_kts',eq);check('desired_close_mps',close);check('heading_error_deg',he)
    check('actual_CAS_kts',p[:,12]*.3048*3600/1852,1e-6);check('actual_TAS_kts',p[:,13]*.3048*3600/1852,1e-6)
    check('closure_mps',-np.sum(rel*(p[:,23:26]-p[:,6:9])*.3048,axis=1)/distance)
    dt=np.asarray([60. if r['previous'] else 0. for r in rawrows])
    check('own_heading_rate_deg_s',((p[:,5]-prev[:,5]+180)%360-180)*dt)
    losprev=np.rad2deg(np.arctan2(np.deg2rad(prev[:,21]-prev[:,1])*np.cos(np.deg2rad((prev[:,20]+prev[:,0])/2)),np.deg2rad(prev[:,20]-prev[:,0])))%360
    check('LOS_rate_deg_s',((los-losprev+180)%360-180)*dt)
    for key,n,e in [('own_ground_course_rate_deg_s',6,7),('enemy_velocity_course_proxy_rate_deg_s',23,24)]:
        delta=np.rad2deg(np.arctan2(p[:,e],p[:,n]))-np.rad2deg(np.arctan2(prev[:,e],prev[:,n]));check(key,((delta+180)%360-180)*dt)
    assert np.array_equal([v['raw_at450'] for v in computed],raw>=450)
    assert np.array_equal([v['eligible'] for v in computed],(distance>914.4)&(np.abs(he)>45))
    return dict(selected_rows=len(computed),independent_vector_geometry_speed_and_rates=True,errors=[])

def worker(out):
    spec=read(out/'CONTRACT.json');assert os.getppid()==spec['guardian']['pid'] and b.live(spec['guardian'])
    assert sha(Path(__file__))==spec['analysis_worker_sha256'];b.source_gate(read(RUN/'CONTRACT.json'))
    comparison=Path(spec['comparison_path']);assert sha(comparison)==spec['comparison_sha256']
    verified=read(comparison);assert verified['verified_comparison'] and verified['errors']==[]
    results=[];total=0
    for case in b.plan():
        folder=RUN/'cases'/case['id'];r=read(folder/'RESULT.json')
        for name in ('telemetry.csv','telemetry.jsonl'):assert sha(folder/name)==r['artifacts'][name]
        with (folder/'telemetry.csv').open(encoding='utf8',newline='') as f:
            nearest=min(csv.DictReader(f),key=lambda row:float(row['distance_m']));anchor=int(nearest['tick'])
        # Windows refer to pre-command times; anchor is saved post-step min range.
        windows={'early0to10s':(1,601),'late240to260s':(14401,15601),'closest_pm5s':(max(1,anchor-300),min(18001,anchor+300))}
        selected=[];rawrows=[];prior=None
        with (folder/'telemetry.jsonl').open(encoding='utf8') as f:
            for line in f:
                row=json.loads(line);n=int(row['tick'])
                if n%300==0 and (b.expired(spec) or b.stop(out) or not b.live(spec['guardian'])):raise RuntimeError('Original deadline/STOP/parent')
                if any(start<=n<end for start,end in windows.values()):
                    selected.append(metrics(row,prior));rawrows.append(dict(row=row,previous=prior))
                prior=row
        expected=len(set(n for start,end in windows.values() for n in range(start,end)));assert len(selected)==expected
        audit=independent_audit(rawrows,selected)
        target=out/(case['id']+'.csv')
        with target.open('w',encoding='utf8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(selected[0]));w.writeheader();w.writerows(selected)
        summaries={name:summary([x for x in selected if start<=x['tick']<end]) for name,(start,end) in windows.items()}
        results.append(dict(case=case,source_artifact_sha256=r['artifacts'],anchor_minimum_post_distance_tick=anchor,anchor_minimum_post_distance_m=float(nearest['distance_m']),
            window_bounds=windows,unique_selected_rows=len(selected),windows=summaries,independent_audit=audit,csv=str(target),csv_sha256=sha(target)))
        total+=len(selected)
    b.source_gate(read(RUN/'CONTRACT.json'));assert not b.expired(spec) and not b.stop(out)
    payload=dict(status='verified_saved_window_math',results=results,selected_rows=total,window_scope='early 0–10s, late240–260s, saved minimum-range +/-5s; only selected rows numerically projected',
        scope='Own packet CAS/TAS/heading. Enemy-equivalent CAS is velocity-magnitude proxy times own CAS/TAS ratio, not measured enemy CAS/TAS. AGL post-step separate from HSL pre-command. Rates use preceding saved packet.',
        new_FDM_ticks=0,controller_projection_calls=0,model_inference_calls=0,training_started=False,seed_claims=[],deployment_allowed=False)
    write(out/'ANALYSIS.json',payload)
    write(out/'VERIFICATION.json',dict(verified_selected_saved_packet_math=True,errors=[],cases=4,selected_rows=total,independent_numpy_audit=True,source_fixed=True,
        saved_artifacts_hashed=True,logged_speed_mapping_recomputed=True,unchanged_non_speed_goals=True,new_FDM_ticks=0,model_inference_calls=0,controller_calls=0,seed_claims=[]))
    print(json.dumps(dict(verified=True,selected_rows=total,results=results),ensure_ascii=False),flush=True)
    return 0
if __name__=='__main__':raise SystemExit(worker(Path(sys.argv[1])))
