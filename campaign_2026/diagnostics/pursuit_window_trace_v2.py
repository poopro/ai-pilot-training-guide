"""Bounded offline guidance projection over saved packets; no FDM/model call.

The frozen StationController.act and its bearing history are used unchanged.
command() is a recorder: it does not replay the inner actuator controller.
Actual sent-command equality is prior independently verified evidence.
"""
from pathlib import Path
import datetime,hashlib,inspect,json,math,os,subprocess,sys,time,types,uuid
import psutil

ROOT=Path(r'E:\ai_pilot\campaign_2026')
SOURCE=ROOT/'experiments/opponent_pool/far_bank60_v2'
RUN=SOURCE/'run_20261017_153047_104619'
sys.path.insert(0,str(SOURCE))
import battle as b
read,write,sha,identity,live=b.read,b.write,b.sha,b.identity,b.live
LIMIT=120

def worker(out):
    import csv,statistics
    spec=read(out/'CONTRACT.json');t0=time.monotonic()
    if os.getppid()!=spec['guardian']['pid'] or not live(spec['guardian']):raise RuntimeError('Wrong direct parent identity')
    if sha(Path(__file__))!=spec['diagnostic_source_sha256']:raise RuntimeError('Diagnostic source changed')
    b.source_gate(read(RUN/'CONTRACT.json'))
    sys.path.insert(0,str(ROOT/'experiments/m4_tactical_v4'))
    import m4_tactical_rl as m
    import numpy as np
    m.torch.set_num_threads(1);results=[]
    for case in b.plan():
        if case['opening']==0:continue  # Two normal traces are already durably saved; do not replay them.
        folder=RUN/'cases'/case['id'];r=read(folder/'RESULT.json')
        if sha(folder/'telemetry.jsonl')!=r['artifacts']['telemetry.jsonl']:raise RuntimeError('Saved telemetry changed')
        ctrl=m.TacticalDuel._build_blue(types.SimpleNamespace(settings={}))
        module=Path(inspect.getfile(type(ctrl))).resolve()
        if module!=ROOT/'experiments/m4_tactical_v4/m1_station.py':raise RuntimeError('Wrong controller source')
        decisions={d['tick']:d['action'] for d in r['tactical_decisions']};held=[0.,0.,0.];row=None;compact=[]
        counts=dict(frames=0,in_band=0,heading_wraps=0,goal_sign_reversals=0,range_cap_crossings=0,requested_bank_opposes_heading=0,actual_bank_opposes_heading=0)
        previous=None;wraps=[];reversals=[];crossings=[]
        def recorder(obs,bank,pitch,speed,rudder=0.,safety=True):
            nonlocal previous
            f=sys._getframe(1);v=f.f_locals
            if f.f_code.co_filename!=str(module) or f.f_code.co_name!='act':raise RuntimeError('Wrong act caller')
            requested=[bank,pitch,speed,rudder];g=row['blue_guidance']
            if requested!=g['requested'] or b.project_goal(g['distance_m'],requested,enabled=case['actor']=='far_bank60')!=g['applied']:raise RuntimeError('Offline guidance differs from actual logged target')
            if [ctrl.tac_aggression,ctrl.tac_break,ctrl.tac_range]!=held:raise RuntimeError('Lost tactical input')
            he=v['heading_error'];packet=row['blue_packet_pre'];bearing=v['geo']['bearing_deg'];applied=g['applied'][0]
            point=dict(tick=row['tick'],distance_m=g['distance_m'],nose_deg=row['blue_angle_deg'],red_nose_deg=row['red_angle_deg'],heading_error_deg=he,filtered_bearing_rate_deg_s=v['rate'],feedforward_deg=v['feedforward'],requested_bank_deg=bank,applied_bank_deg=applied,actual_bank_deg=packet[3],heading_deg=packet[5],raw_LOS_rate_deg_s=0.,actual_heading_rate_deg_s=0.,in_band=v['in_band'],cap_far=g['distance_m']>914.4)
            if previous:
                point['raw_LOS_rate_deg_s']=(bearing-previous['bearing']+180)%360*60-180*60
                point['actual_heading_rate_deg_s']=(packet[5]-previous['heading_deg']+180)%360*60-180*60
                if he*previous['heading_error_deg']<0 and abs(he-previous['heading_error_deg'])>300:wraps.append(row['tick']);counts['heading_wraps']+=1
                if applied*previous['applied_bank_deg']<0:reversals.append(row['tick']);counts['goal_sign_reversals']+=1
                if point['cap_far']!=previous['cap_far']:crossings.append(row['tick']);counts['range_cap_crossings']+=1
            counts['frames']+=1;counts['in_band']+=int(v['in_band']);counts['requested_bank_opposes_heading']+=int(bank*he<0);counts['actual_bank_opposes_heading']+=int(packet[3]*he<0)
            compact.append(point);previous=dict(point,bearing=bearing)
            return np.asarray(row['blue_command']),row['blue_private_guard']
        ctrl.command=recorder
        with (folder/'telemetry.jsonl').open(encoding='utf8') as stream:
            for line in stream:
                if counts['frames']%300==0 and (b.expired(spec) or b.stop(out)):raise RuntimeError('Original diagnostic deadline/STOP')
                row=json.loads(line);tick=row['tick']-1
                if tick%20==0:held=decisions[tick]
                ctrl.set_tactical(*held);ctrl.act(row['blue_packet_pre'],np.zeros(4,dtype=np.float32),started=True)
        if counts['frames']!=r['final']['ticks']:raise RuntimeError('Missing frames')
        trace=out/(case['id']+'.csv')
        with trace.open('w',encoding='utf8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(compact[0]));writer.writeheader();writer.writerows(compact)
        band=[x for x in compact if x['in_band']];anchors={}
        if band:
            anchors['first_in_band']=band[0]['tick'];anchors['worst_nose_in_band']=max(band,key=lambda x:x['nose_deg'])['tick']
        if wraps:anchors['first_heading_wrap']=wraps[0]
        if reversals:anchors['first_goal_reversal']=reversals[0]
        summary=dict(case=case,counts=counts,heading_wrap_ticks=wraps,goal_sign_reversal_ticks=reversals,cap_crossing_ticks=crossings,
                     goal_reversals_within_2s_of_heading_wrap=sum(any(abs(x-w)<=120 for w in wraps) for x in reversals),
                     goal_reversals_within_2s_of_cap_crossing=sum(any(abs(x-w)<=120 for w in crossings) for x in reversals),
                     in_band_requested_opposite_heading=sum(int(x['requested_bank_deg']*x['heading_error_deg']<0) for x in band),
                     in_band_actual_bank_opposite_heading=sum(int(x['actual_bank_deg']*x['heading_error_deg']<0) for x in band),
                     in_band_median_heading_error_abs_deg=statistics.median(abs(x['heading_error_deg']) for x in band) if band else None,
                     in_band_median_abs_LOS_rate_deg_s=statistics.median(abs(x['raw_LOS_rate_deg_s']) for x in band) if band else None,
                     in_band_median_abs_heading_rate_deg_s=statistics.median(abs(x['actual_heading_rate_deg_s']) for x in band) if band else None,
                     trace_sha256=sha(trace),controller_source=str(module),controller_sha256=sha(module),requested_goal_replay_exact=True,
                     anchors=anchors,windows={key:compact[max(0,tick-121):min(len(compact),tick+120)] for key,tick in anchors.items()})
        results.append(summary)
        print(json.dumps({k:summary[k] for k in ('case','counts','goal_reversals_within_2s_of_heading_wrap','goal_reversals_within_2s_of_cap_crossing','in_band_requested_opposite_heading','in_band_actual_bank_opposite_heading','in_band_median_heading_error_abs_deg','in_band_median_abs_LOS_rate_deg_s','in_band_median_abs_heading_rate_deg_s')}),flush=True)
        write(out/'progress.json',dict(completed_cases=len(results),elapsed=time.monotonic()-t0))
    b.source_gate(read(RUN/'CONTRACT.json'))
    write(out/'ANALYSIS.json',dict(status='completed_offline_pursuit_trace',source_run=str(RUN),results=results,saved_frames=sum(r['counts']['frames'] for r in results),new_FDM_ticks=0,new_model_inference=False,training_started=False,inner_command_replayed=False,stub_return_is_saved_command=True,intervention_tested=False,causal_limit='Observed timing/sign correlations in saved trajectories. No new closed-loop fix or combat improvement was tested.',deployment_allowed=False,wall_seconds=time.monotonic()-t0))
    audit_traces(out)
    return 0


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

def launch():
    sys.path.insert(0,str(ROOT));from runner import JobLock
    with JobLock(ROOT/'launch.lock'):
        if b.base.inventory():raise RuntimeError('Other or unknown work active')
        resources=b.base.resources()
        if b.stop(RUN):raise RuntimeError('STOP')
        b.source_gate(read(RUN/'CONTRACT.json'))
        out=ROOT/'diagnostics'/('pursuit_window_trace_v2_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_')+uuid.uuid4().hex[:6]);out.mkdir()
        started=time.monotonic();spec=dict(guardian=identity(),deadline_epoch=time.time()+LIMIT,deadline_monotonic=started+LIMIT,seconds=LIMIT,diagnostic_source_sha256=sha(Path(__file__)),source_run=str(RUN),original_source_contract_sha256=sha(RUN/'CONTRACT.json'),resources=resources,usage_observation=read(Path(__file__).with_suffix('.usage.json')),new_FDM_ticks=0,seed_claims=[],training_started=False)
        old=ROOT/'diagnostics/pursuit_window_trace_20261017_183319_9e78be'
        spec['prior_trace_inputs']={str(p):sha(p) for p in old.glob('normal_*.csv')}
        spec['prior_failed_worker_receipt']=read(old/'WORKER_EXIT.json')
        spec['prior_failed_source_sha256']=sha(ROOT/'diagnostics/pursuit_window_trace_v1.py')
        if len(spec['prior_trace_inputs'])!=2:raise RuntimeError('Need the two preserved normal traces')
        write(out/'CONTRACT.json',spec)
        lp=ROOT/'compute_budgets'/f'{datetime.datetime.now().date().isoformat()}.json';ledger=read(lp);ledger['items'].append(dict(id=out.name,hours=LIMIT/3600,status='reserved_offline_pursuit_trace',output=str(out),warning_only=True));ledger['reserved_hours']=sum(i['hours'] for i in ledger['items']);write(lp,ledger)
        j=read(ROOT/'research_latest.json');j['active_workload']=dict(status='running_offline_pursuit_trace',run=str(out),supervisor=b.normalized(spec['guardian']),worker=None);j['current_live_workloads']=dict(learners=[],loops=[],evaluations=[j['active_workload']]);write(ROOT/'research_latest.json',j)
        with (out/'worker.log').open('w',encoding='utf8') as log:
            p=subprocess.Popen([sys.executable,'-B','-X','utf8',str(Path(__file__)),'--worker',str(out)],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW);i=identity(p.pid);descendants={};reason=None
            write(out/'worker_identity.json',i)
            while p.poll() is None:
                try:
                    for child in psutil.Process(i['pid']).children(recursive=True):
                        try:
                            d=identity(child.pid);chain=[];node=child
                            while node.pid!=i['pid']:
                                chain.append(identity(node.pid));node=node.parent()
                                if node is None:raise RuntimeError('Lost own chain')
                            if not live(i):raise RuntimeError('Worker identity changed')
                            descendants[(d['pid'],d['create'])]=dict(identity=d,chain=chain,worker=i)
                        except psutil.NoSuchProcess:continue
                except psutil.NoSuchProcess:
                    if p.poll() is None:raise
                if b.expired(spec) or b.stop(out):reason='original_diagnostic_deadline_or_STOP';code,actions=b.terminate_known(p,i,descendants);break
                time.sleep(.1)
            else:code=p.wait(timeout=3);actions=[]
            for d in descendants.values():
                if live(d['identity']):
                    try:psutil.Process(d['identity']['pid']).wait(timeout=1)
                    except psutil.TimeoutExpired:
                        if live(d['identity']):psutil.Process(d['identity']['pid']).terminate()
            absent=not live(i) and all(not live(d['identity']) for d in descendants.values())
        passed=code==0 and reason is None and absent
        write(out/'WORKER_EXIT.json',dict(actual_worker_exit=code,reason=reason,identity=i,descendants=list(descendants.values()),absent=absent,cleanup_actions=actions,wall_seconds=time.monotonic()-started,guardian_return_intended=0 if passed else 2))
        ledger=read(lp)
        for item in ledger['items']:
            if item['id']==out.name:item.update(status='offline_pursuit_trace_complete_pending_parent' if passed else 'failed_offline_pursuit_trace',actual_worker_exit=code,actual_wall_seconds=time.monotonic()-started)
        write(lp,ledger)
        j=read(ROOT/'research_latest.json');j['active_workload']=None;j['current_live_workloads']=dict(learners=[],loops=[],evaluations=[]);j['latest_pursuit_trace']=str(out);write(ROOT/'research_latest.json',j)
        print(json.dumps(dict(out=str(out),actual_worker_exit=code,reason=reason,absent=absent,wall_seconds=time.monotonic()-started)),flush=True)
        return 0 if passed else 2

if __name__=='__main__':
    raise SystemExit(worker(Path(sys.argv[2])) if len(sys.argv)==3 and sys.argv[1]=='--worker' else launch())
