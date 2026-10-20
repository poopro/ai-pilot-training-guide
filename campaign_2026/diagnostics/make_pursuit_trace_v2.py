from pathlib import Path
ROOT=Path(r'E:\ai_pilot\campaign_2026')
source=(ROOT/'diagnostics/pursuit_window_trace_v1.py').read_text(encoding='utf8')
source=source.replace("    for case in b.plan():\n", "    for case in b.plan():\n        if case['opening']==0:continue  # Two normal traces are already durably saved; do not replay them.\n",1)
source=source.replace("sum(x['requested_bank_deg']*x['heading_error_deg']<0 for x in band)","sum(int(x['requested_bank_deg']*x['heading_error_deg']<0) for x in band)")
source=source.replace("sum(x['actual_bank_deg']*x['heading_error_deg']<0 for x in band)","sum(int(x['actual_bank_deg']*x['heading_error_deg']<0) for x in band)")
source=source.replace("'pursuit_window_trace_'","'pursuit_window_trace_v2_'")
marker="        write(out/'CONTRACT.json',spec)"
assert source.count(marker)==1
source=source.replace(marker,"""        old=ROOT/'diagnostics/pursuit_window_trace_20261017_183319_9e78be'
        spec['prior_trace_inputs']={str(p):sha(p) for p in old.glob('normal_*.csv')}
        spec['prior_failed_worker_receipt']=read(old/'WORKER_EXIT.json')
        spec['prior_failed_source_sha256']=sha(ROOT/'diagnostics/pursuit_window_trace_v1.py')
        if len(spec['prior_trace_inputs'])!=2:raise RuntimeError('Need the two preserved normal traces')
        write(out/'CONTRACT.json',spec)""")
end="    return 0\n\ndef launch():"
assert source.count(end)==1
source=source.replace(end,"    audit_traces(out)\n    return 0\n\ndef launch():")
audit=r'''
def audit_traces(out):
    import csv,statistics
    spec=read(out/'CONTRACT.json');results=[]
    prior=ROOT/'diagnostics/pursuit_window_trace_20261017_183319_9e78be'
    if sha(ROOT/'diagnostics/pursuit_window_trace_v1.py')!=spec['prior_failed_source_sha256']:raise RuntimeError('Prior failed diagnostic source changed')
    for path,h in spec['prior_trace_inputs'].items():
        if sha(Path(path))!=h:raise RuntimeError('Preserved prior trace changed')
    sys.path.insert(0,str(ROOT/'experiments/m4_tactical_v4'))
    import m4_tactical_rl as m
    from combat_v3.interface import geometry_from_observation
    def wrap(x):return (x+180)%360-180
    def check(x,y):
        if abs(float(x)-float(y))>1e-8:raise RuntimeError('Independent saved-trace math differs: '+str((x,y)))
    for case in b.plan():
        trace=(prior if case['opening']==0 else out)/(case['id']+'.csv')
        rawfolder=RUN/'cases'/case['id'];r=read(rawfolder/'RESULT.json')
        if not all(d['action']==[0.,0.,0.] for d in r['tactical_decisions']):raise RuntimeError('This audit is zero-tactical only')
        if sha(rawfolder/'telemetry.jsonl')!=r['artifacts']['telemetry.jsonl']:raise RuntimeError('Original packets changed')
        compact=[];old=None;p1=p2=None;rate=0.;wraps=[];flips=[];crossings=[]
        with trace.open(encoding='utf8',newline='') as f,(rawfolder/'telemetry.jsonl').open(encoding='utf8') as raw:
            stream=csv.DictReader(f)
            for n,line in enumerate(raw,1):
                if n%300==0 and (b.expired(spec) or b.stop(out)):raise RuntimeError('Original new diagnostic deadline/STOP')
                actual=json.loads(line);row=next(stream,None)
                if row is None or int(row['tick'])!=n:raise RuntimeError('Missing trace row')
                obs=actual['blue_packet_pre'];geo=geometry_from_observation(obs);d=geo['distance_m'];band=152.4<=d<=914.4
                bearing=geo['bearing_deg']
                if not band:bearing+=max(-20.,min(20.,wrap(geo['lead_bearing_deg']-bearing)))*.35
                he=wrap(bearing-obs[5])
                if p1 is None:p1=p2=bearing
                else:
                    newrate=.5*wrap(bearing-p2)*60;p2,p1=p1,bearing
                    if math.isfinite(newrate) and abs(newrate)<=90:rate=.65*rate+.35*newrate
                ff=math.degrees(math.atan(geo['own_tas_mps']*math.radians(rate)/9.80665))
                bank=1.8*he+ff
                if band:bank+=2.6*max(-25.,min(25.,he))-.35*rate
                bank=max(-72.,min(72.,bank));g=actual['blue_guidance']
                for value,expected in ((row['distance_m'],d),(row['heading_error_deg'],he),(row['filtered_bearing_rate_deg_s'],rate),(row['feedforward_deg'],ff),(row['requested_bank_deg'],bank),(row['requested_bank_deg'],g['requested'][0]),(row['applied_bank_deg'],g['applied'][0]),(row['actual_bank_deg'],obs[3]),(row['heading_deg'],obs[5]),(row['nose_deg'],actual['blue_angle_deg']),(row['red_nose_deg'],actual['red_angle_deg'])):check(value,expected)
                item={key:float(value) for key,value in row.items() if key not in ('in_band','cap_far')};item['in_band']=row['in_band']=='True';item['cap_far']=row['cap_far']=='True'
                if item['in_band']!=band or item['cap_far']!=(d>914.4):raise RuntimeError('Trace branch flag differs')
                if old:
                    check(item['raw_LOS_rate_deg_s'],wrap(geo['bearing_deg']-old['bearing'])*60)
                    check(item['actual_heading_rate_deg_s'],wrap(obs[5]-old['heading_deg'])*60)
                    if he*old['heading_error_deg']<0 and abs(he-old['heading_error_deg'])>300:wraps.append(n)
                    if item['applied_bank_deg']*old['applied_bank_deg']<0:flips.append(n)
                    if item['cap_far']!=old['cap_far']:crossings.append(n)
                compact.append(item);old=dict(item,bearing=geo['bearing_deg'])
            if next(stream,None) is not None or n!=18000:raise RuntimeError('Incomplete/extra trace')
        bandrows=[x for x in compact if x['in_band']]
        result=dict(case=case,frames=n,in_band=len(bandrows),heading_wraps=wraps,goal_reversals=flips,cap_crossings=crossings,
                    reversals_near_heading_wrap=sum(any(abs(t-w)<=120 for w in wraps) for t in flips),reversals_near_cap_crossing=sum(any(abs(t-w)<=120 for w in crossings) for t in flips),
                    in_band_requested_bank_opposite_heading=sum(x['requested_bank_deg']*x['heading_error_deg']<0 for x in bandrows),in_band_actual_bank_opposite_heading=sum(x['actual_bank_deg']*x['heading_error_deg']<0 for x in bandrows),
                    in_band_median_heading_error_abs_deg=statistics.median(abs(x['heading_error_deg']) for x in bandrows) if bandrows else None,
                    in_band_median_abs_LOS_rate_deg_s=statistics.median(abs(x['raw_LOS_rate_deg_s']) for x in bandrows) if bandrows else None,
                    in_band_median_abs_heading_rate_deg_s=statistics.median(abs(x['actual_heading_rate_deg_s']) for x in bandrows) if bandrows else None,
                    trace=str(trace),trace_sha256=sha(trace),scope='independently recalculated from original legal saved packets; no FDM')
        results.append(result)
    write(out/'TRACE_AUDIT.json',dict(verified_saved_trace_math=True,results=results,saved_frames=72000,prior_worker_actual_exit=spec['prior_failed_worker_receipt']['actual_worker_exit'],prior_failure_not_reclassified=True,new_worker_projected_frames=36000,normal_trace_replayed_again=False,new_FDM_ticks=0,new_model_inference=False,training_started=False,intervention_tested=False,scope='4 saved trajectories audited; prior normal traces retained from failed output serialization, fresh mirror projections only',deployment_allowed=False))
    print(json.dumps(dict(verified_saved_trace_math=True,results=results)),flush=True)

'''
insertion=source.index('def launch():')
source=source[:insertion]+audit+source[insertion:]
path=ROOT/'diagnostics/pursuit_window_trace_v2.py';path.write_text(source,encoding='utf8');print(str(path))
