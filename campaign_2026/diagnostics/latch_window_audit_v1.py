"""Independent NumPy unwrapped-rate/unit/statistics audit of selected saved windows."""
from pathlib import Path
import sys,os,json,csv,math
ROOT=Path(r'E:\ai_pilot\campaign_2026');SOURCE=ROOT/'experiments/opponent_pool/rear_latch60_v2';RUN=SOURCE/'run_20261017_203915_d840e7'
sys.path.insert(0,str(SOURCE));import battle as b
read,write,sha=b.read,b.write,b.sha
def worker(out):
    import numpy as np
    spec=read(out/'CONTRACT.json');extract=Path(spec['extract_path'])
    assert os.getppid()==spec['guardian']['pid'] and b.live(spec['guardian'])
    assert sha(Path(__file__))==spec['analysis_worker_sha256']
    assert sha(extract/'ANALYSIS.json')==spec['extract_analysis_sha256']
    a=read(extract/'ANALYSIS.json');assert read(extract/'PARENT_EXIT_OBSERVED.json')['actual_exit']==0 and read(extract/'WORKER_EXIT.json')['actual_worker_exit']==0
    checked=0;results=[]
    for result in a['results']:
        if b.expired(spec) or b.stop(out):raise RuntimeError('Audit original deadline/STOP')
        case=result['case'];anchor=result['anchor_actual_first_command_difference_tick'];start=anchor-300;end=anchor+2400
        src=RUN/'cases'/case['id']/'telemetry.jsonl';assert sha(src)==result['source_artifact_sha256']
        raw=[]
        with src.open(encoding='utf8') as f:
            for line in f:
                r=json.loads(line)
                if r['tick']>=end:break
                if r['tick']>=start-1:raw.append(r)
        assert len(raw)==2701
        p=np.array([r['blue_packet_pre'] for r in raw],dtype=float)
        north=np.deg2rad(p[:,20]-p[:,0])*6378137
        east=np.deg2rad(p[:,21]-p[:,1])*6378137*np.cos(np.deg2rad((p[:,0]+p[:,20])/2))
        def angular_rate(angles):return np.rad2deg(np.diff(np.unwrap(np.deg2rad(angles))))*60
        expected={'los_rate_deg_s':angular_rate(np.rad2deg(np.arctan2(east,north))),'own_heading_rate_deg_s':angular_rate(p[:,5]),'own_ground_course_rate_deg_s':angular_rate(np.rad2deg(np.arctan2(p[:,7],p[:,6]))),'enemy_velocity_course_rate_deg_s':angular_rate(np.rad2deg(np.arctan2(p[:,24],p[:,23])))}
        expected['cas_kts']=p[1:,12]*.3048*3600/1852
        expected['tas_mps']=p[1:,13]*.3048;expected['own_HSL_m']=p[1:,2]*.3048
        expected['actual_bank_deg']=p[1:,3];expected['own_signed_G']=p[1:,14]
        expected['roll_goal_deg']=np.array([r['blue_guidance']['applied'][0] for r in raw[1:]])
        expected['roll_goal_error_deg']=(expected['roll_goal_deg']-p[1:,3]+180)%360-180
        expected['speed_goal_kts']=np.array([r['blue_guidance']['applied'][2] for r in raw[1:]])
        expected['speed_goal_error_kts']=expected['speed_goal_kts']-expected['cas_kts']
        expected['own_specific_energy_m2_s2']=9.80665*expected['own_HSL_m']+.5*expected['tas_mps']**2
        trace=Path(result['window_csv']);assert sha(trace)==result['window_csv_sha256']
        with trace.open(encoding='utf8',newline='') as f:rows=list(csv.DictReader(f))
        assert len(rows)==2700 and [int(r['tick']) for r in rows]==list(range(start,end))
        for k,v in expected.items():np.testing.assert_allclose(np.array([float(r[k]) for r in rows]),v,atol=1e-8,rtol=0,err_msg=case['id']+' '+k)
        for i,r in enumerate(raw[1:]):
            assert (rows[i]['guard_active']=='True')==r['blue_private_guard']
            assert (rows[i]['energy_guard_input']=='True')==bool(expected['cas_kts'][i]<180 or p[i+1,18]>22)
            assert (rows[i]['g_guard_input']=='True')==bool(abs(p[i+1,14])>8.5)
        for name,win in result['windows'].items():
            lo,hi=win['first_tick']-start,win['last_tick']-start+1;assert hi-lo==win['rows']
            for stat,k in [('median_abs_roll_tracking_error_deg','roll_goal_error_deg'),('median_abs_speed_error_kts','speed_goal_error_kts'),('median_abs_LOS_rate_deg_s','los_rate_deg_s'),('median_abs_own_heading_rate_deg_s','own_heading_rate_deg_s'),('median_abs_enemy_velocity_course_rate_deg_s','enemy_velocity_course_rate_deg_s')]:assert abs(float(np.median(np.abs(expected[k][lo:hi])))-win[stat])<1e-8
            assert sum(r['blue_private_guard'] for r in raw[1:][lo:hi])==win['guard_ticks']
        results.append(dict(case=case['id'],rows=2700,independent_unwrapped_rates_units_and_key_medians=True));checked+=2700
    b.source_gate(read(RUN/'CONTRACT.json'))
    write(out/'VERIFICATION.json',dict(verified_independent_window_audit=True,rows=checked,results=results,extract=str(extract),extract_analysis_sha256=sha(extract/'ANALYSIS.json'),new_FDM_ticks=0,controller_projection_calls=0,model_inference_calls=0,scope='NumPy unwrapped finite differences, independently vectorized geometry and fps-to-knots conversion; selected 45s windows only',causality_limit='No counterfactual intervention or fix tested. Course from enemy velocity is not true nose attitude.'))
    print(json.dumps(dict(verified_independent_window_audit=True,rows=checked)),flush=True);return 0

if __name__=='__main__':raise SystemExit(worker(Path(sys.argv[1])))
