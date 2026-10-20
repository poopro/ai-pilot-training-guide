"""Only saved ±5/10/20/40s windows. No controller projection or simulator."""
from pathlib import Path
import sys,math,json,csv,statistics,os
ROOT=Path(r'E:\ai_pilot\campaign_2026');SOURCE=ROOT/'experiments/opponent_pool/rear_latch60_v2';RUN=SOURCE/'run_20261017_203915_d840e7'
sys.path.insert(0,str(SOURCE));import battle as b
read,write,sha=b.read,b.write,b.sha
WINDOWS=[('before5s',-300,0),('after0to5s',0,300),('after5to10s',300,600),('after10to20s',600,1200),('after20to40s',1200,2400)]
def wrap(v):return (v+180.)%360.-180.
def median(v):return float(statistics.median(v))
def bearing(p):
    north=math.radians(p[20]-p[0])*6378137.
    east=math.radians(p[21]-p[1])*6378137.*math.cos(math.radians((p[0]+p[20])/2.))
    return math.degrees(math.atan2(east,north))%360.
def course(n,e):return math.degrees(math.atan2(e,n))%360.

def point(row,prior):
    p=row['blue_packet_pre'];g=row['blue_guidance'];tas=p[13]*.3048;cas=p[12]/1.6878098571011957
    los=bearing(p);owncourse=course(p[6],p[7]);enemycourse=course(p[23],p[24])
    x=dict(tick=int(row['tick']),distance_m=float(g['distance_m']),heading_error_deg=float(g['heading_error_deg']),pre_body_nose_deg=float(g['body_angle_deg']),actual_bank_deg=float(p[3]),roll_goal_deg=float(g['applied'][0]),roll_goal_error_deg=wrap(g['applied'][0]-p[3]),pitch_goal_deg=float(g['applied'][1]),actual_pitch_deg=float(p[4]),cas_kts=float(cas),tas_mps=float(tas),speed_goal_kts=float(g['applied'][2]),speed_goal_error_kts=float(g['applied'][2]-cas),own_HSL_m=float(p[2]*.3048),own_AGL_post_m=float(row['blue_agl_m']),own_specific_energy_m2_s2=float(9.80665*p[2]*.3048+.5*tas*tas),alpha_deg=float(p[18]),own_signed_G=float(p[14]),actual_aileron=float(row['blue_command'][0]),actual_elevator=float(row['blue_command'][1]),actual_throttle=float(row['blue_command'][3]),guard_active=bool(row['blue_private_guard']),g_guard_input=bool(abs(p[14])>8.5),energy_guard_input=bool(cas<180 or p[18]>22),latch_active=bool(g['latch']['active']),turn_sign_opposes_short_heading=bool(g['applied'][0]*g['heading_error_deg']<0),los_rate_deg_s=0.,own_heading_rate_deg_s=0.,own_ground_course_rate_deg_s=0.,enemy_velocity_course_rate_deg_s=0.)
    if prior:
        prev=prior['blue_packet_pre']
        x.update(los_rate_deg_s=wrap(los-bearing(prev))*60.,own_heading_rate_deg_s=wrap(p[5]-prev[5])*60.,own_ground_course_rate_deg_s=wrap(owncourse-course(prev[6],prev[7]))*60.,enemy_velocity_course_rate_deg_s=wrap(enemycourse-course(prev[23],prev[24]))*60.)
    return x

def summarize(rows):
    return dict(rows=len(rows),first_tick=rows[0]['tick'],last_tick=rows[-1]['tick'],median_abs_heading_error_deg=median([abs(x['heading_error_deg']) for x in rows]),best_pre_body_nose_deg=min(x['pre_body_nose_deg'] for x in rows),forward_nose_ticks=sum(x['pre_body_nose_deg']<=90 for x in rows),inband_ticks=sum(152.4<=x['distance_m']<=914.4 for x in rows),median_abs_actual_bank_deg=median([abs(x['actual_bank_deg']) for x in rows]),median_abs_roll_goal_deg=median([abs(x['roll_goal_deg']) for x in rows]),median_abs_roll_tracking_error_deg=median([abs(x['roll_goal_error_deg']) for x in rows]),median_CAS_kts=median([x['cas_kts'] for x in rows]),median_TAS_mps=median([x['tas_mps'] for x in rows]),median_speed_goal_kts=median([x['speed_goal_kts'] for x in rows]),median_abs_speed_error_kts=median([abs(x['speed_goal_error_kts']) for x in rows]),throttle_at_max_ticks=sum(x['actual_throttle']>=.999 for x in rows),aileron_at_limit_ticks=sum(abs(x['actual_aileron'])>=.999 for x in rows),guard_ticks=sum(x['guard_active'] for x in rows),g_guard_input_ticks=sum(x['g_guard_input'] for x in rows),energy_guard_input_ticks=sum(x['energy_guard_input'] for x in rows),latch_ticks=sum(x['latch_active'] for x in rows),turn_sign_opposes_short_heading_ticks=sum(x['turn_sign_opposes_short_heading'] for x in rows),median_abs_LOS_rate_deg_s=median([abs(x['los_rate_deg_s']) for x in rows]),median_abs_own_heading_rate_deg_s=median([abs(x['own_heading_rate_deg_s']) for x in rows]),median_abs_own_ground_course_rate_deg_s=median([abs(x['own_ground_course_rate_deg_s']) for x in rows]),median_abs_enemy_velocity_course_rate_deg_s=median([abs(x['enemy_velocity_course_rate_deg_s']) for x in rows]),HSL_change_m=rows[-1]['own_HSL_m']-rows[0]['own_HSL_m'],AGL_post_change_m=rows[-1]['own_AGL_post_m']-rows[0]['own_AGL_post_m'],TAS_change_mps=rows[-1]['tas_mps']-rows[0]['tas_mps'],specific_energy_change_m2_s2=rows[-1]['own_specific_energy_m2_s2']-rows[0]['own_specific_energy_m2_s2'])

def worker(out):
    spec=read(out/'CONTRACT.json')
    assert os.getppid()==spec['guardian']['pid'] and b.live(spec['guardian'])
    assert sha(Path(__file__))==spec['analysis_worker_sha256']
    audit=Path(spec['comparison_path']);assert sha(audit)==spec['comparison_sha256'];comparison=read(audit);assert comparison['verified_comparison'] and not comparison['errors']
    b.source_gate(read(RUN/'CONTRACT.json'))
    assert wrap(-179.-179.)==2. and wrap(179.-(-179.))==-2.
    results=[];processed=0
    for case in b.plan():
        anchor=spec['anchors'][str(case['opening'])];start=anchor-300;end=anchor+2400
        folder=RUN/'cases'/case['id'];r=read(folder/'RESULT.json');assert sha(folder/'telemetry.jsonl')==r['artifacts']['telemetry.jsonl']
        selected=[];prior=None
        with (folder/'telemetry.jsonl').open(encoding='utf8') as stream:
            for line in stream:
                row=json.loads(line);n=row['tick']
                if n%300==0 and (b.expired(spec) or b.stop(out)):raise RuntimeError('Original window deadline/STOP')
                if n>=end:break
                if n>=start:selected.append(point(row,prior))
                prior=row
        assert len(selected)==2700 and selected[0]['tick']==start and selected[-1]['tick']==end-1
        windows={}
        for name,a,z in WINDOWS:
            items=[x for x in selected if anchor+a<=x['tick']<anchor+z];assert len(items)==z-a
            windows[name]=summarize(items)
        target=out/(case['id']+'.csv')
        with target.open('w',encoding='utf8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(selected[0]));writer.writeheader();writer.writerows(selected)
        # Independent audit from the stored legal packet: central-frame geometry,
        # every selected heading rate and command/error values, without act().
        with target.open(encoding='utf8',newline='') as f:serialized=list(csv.DictReader(f))
        assert len(serialized)==len(selected)
        for expected,actual in zip(selected,serialized):
            assert int(actual['tick'])==expected['tick']
            for k,v in expected.items():
                if type(v) is bool:assert actual[k]==str(v)
                else:assert abs(float(actual[k])-v)<1e-10
        processed+=len(selected)
        results.append(dict(case=case,anchor_actual_first_command_difference_tick=anchor,selected_rows=len(selected),source_artifact_sha256=r['artifacts']['telemetry.jsonl'],window_csv=str(target),window_csv_sha256=sha(target),windows=windows))
    b.source_gate(read(RUN/'CONTRACT.json'));assert processed==10800
    write(out/'ANALYSIS.json',dict(status='completed_saved_window_diagnostic',results=results,selected_rows=processed,new_FDM_ticks=0,controller_projection_calls=0,model_inference_calls=0,training_started=False,scope='Windows only; packet TAS/CAS/G are OWN; enemy velocity course proxy is ENEMY6, never enemy attitude/G. AGL is logged post-step and labeled; HSL/speed/rates are pre-command.',counterfactual_or_closed_loop_fix_tested=False,deployment_allowed=False))
    write(out/'VERIFICATION.json',dict(verified_saved_window_extract=True,selected_rows=processed,window_definitions=WINDOWS,source_fixed=True,comparison_verified=True,window_CSV_exact=True,wrap_boundary_test=True,metric_units='rates degree/s, CAS knots, TAS m/s, altitude metres; HSL and AGL separate',new_FDM_ticks=0,controller_projection_calls=0,model_inference_calls=0,training_started=False))
    print(json.dumps(dict(verified_saved_window_extract=True,selected_rows=processed,summary=[dict(case=x['case']['id'],windows=x['windows']) for x in results])),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(worker(Path(sys.argv[1])))
