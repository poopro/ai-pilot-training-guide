from pathlib import Path
ROOT=Path(r'E:\ai_pilot\campaign_2026')
original=(ROOT/'diagnostics/sac_goal_projection_v1.py').read_text(encoding='utf8')
prefix=original[:original.index('def worker(out):')]
tail=original[original.index('def launch():'):]
prefix=prefix.replace("SOURCE=ROOT/'experiments/opponent_pool/frozen_sac_battle_v2'","SOURCE=ROOT/'experiments/opponent_pool/far_bank60_v2'").replace("RUN=SOURCE/'run_20261017_093943_16bee6'","RUN=SOURCE/'run_20261017_153047_104619'")
tail=tail.replace("'sac_goal_projection_'","'pursuit_window_trace_'").replace('offline_goal_projection','offline_pursuit_trace').replace('offline_projection','offline_pursuit_trace').replace("j['latest_goal_projection']","j['latest_pursuit_trace']")
worker=r'''def worker(out):
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
                     in_band_requested_opposite_heading=sum(x['requested_bank_deg']*x['heading_error_deg']<0 for x in band),
                     in_band_actual_bank_opposite_heading=sum(x['actual_bank_deg']*x['heading_error_deg']<0 for x in band),
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
    return 0

'''
path=ROOT/'diagnostics/pursuit_window_trace_v1.py';path.write_text(prefix+worker+tail,encoding='utf8');print(str(path))
