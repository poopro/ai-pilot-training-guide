from pathlib import Path
ROOT=Path(r'E:\ai_pilot\campaign_2026')
old=(ROOT/'diagnostics/rear_latch_precheck_v1.py').read_text(encoding='utf8')
head=old[:old.index('def worker(out):')]
worker='''def worker(out):
    import runpy,importlib.util,inspect
    spec=read(out/'CONTRACT.json')
    if os.getppid()!=spec['guardian']['pid'] or not live(spec['guardian']):raise RuntimeError('Wrong parent identity')
    for path,h in spec['new_sources'].items():
        if sha(Path(path))!=h:raise RuntimeError('New source changed')
    new=ROOT/'experiments/opponent_pool/far_speed_v1';sys.path.insert(0,str(new))
    exact=importlib.util.spec_from_file_location('battle',new/'battle.py');module=importlib.util.module_from_spec(exact);exact.loader.exec_module(module);sys.modules['battle']=module
    runpy.run_path(str(new/'test_static.py'))
    import numpy as np
    import m4_tactical_rl as m
    import combat_v3.env as ce
    settings=read(Path(ce.__file__).parent/'config.json');records=[];total_changed=0
    for case in b.plan():
        if case['actor']!='station_zero':continue
        folder=RUN/'cases'/case['id'];r=read(folder/'RESULT.json');assert sha(folder/'telemetry.jsonl')==r['artifacts']['telemetry.jsonl']
        controllers=[m.TacticalDuel._build_blue(types.SimpleNamespace(settings=settings)) for _ in range(2)]
        assert all(Path(inspect.getfile(type(c))).resolve()==ROOT/'experiments/m4_tactical_v4/m1_station.py' for c in controllers)
        row=None;changes=0;calls=[0,0];emitted=[None,None]
        def make_hook(index,original):
            def hook(packet,roll,pitch,speed,rudder=0.,safety=True):
                nonlocal changes
                requested=[float(roll),float(pitch),float(speed),float(rudder)]
                assert requested==row['blue_guidance']['requested']
                applied,trace=module.project_goal(packet,requested,enabled=index==1)
                assert applied[0]==requested[0] and applied[1]==requested[1] and applied[3]==requested[3] and safety is True
                if index==0:assert applied==requested
                else:changes+=int(applied[2]!=requested[2]);json.dumps(trace,allow_nan=False)
                calls[index]+=1
                return original(packet,*applied,safety=safety)
            return hook
        for index,ctrl in enumerate(controllers):ctrl.command=make_hook(index,ctrl.command)
        with (folder/'telemetry.jsonl').open(encoding='utf8') as stream:
            for line in stream:
                row=json.loads(line)
                if row['tick']>300:break
                if b.expired(spec) or b.stop(out):raise RuntimeError('Precheck deadline/STOP')
                outputs=[ctrl.act(row['blue_packet_pre'],np.zeros(4),started=True) for ctrl in controllers]
                np.testing.assert_array_equal(outputs[0][0],row['blue_command']);assert outputs[0][1]==row['blue_private_guard']
        assert calls==[300,300] and changes>0;total_changed+=changes
        records.append(dict(case=case['id'],saved_packet_frames=300,baseline_actual_inner_commands_exact=True,single_act_and_command_counts=calls,candidate_only_speed_goal_changed_frames=changes,fresh_controller_state_per_case=True))
    for path,h in spec['new_sources'].items():
        if sha(Path(path))!=h:raise RuntimeError('New source changed')
    b.source_gate(read(RUN/'CONTRACT.json'))
    write(out/'VERIFICATION.json',dict(verified_saved_packet_precheck=True,static_checks=16,results=records,saved_packet_frames=600,candidate_goal_changes=total_changed,new_FDM_ticks=0,new_model_inference=False,training_started=False,scope='Two new controller instances per saved prefix, original baseline exact command replay, candidate changes speed target only. No closed-loop strength result.'))
    print(json.dumps(dict(verified_saved_packet_precheck=True,results=records)),flush=True);return 0

'''
launch=old[old.index('def launch():'):]
launch=launch.replace('rear_latch_precheck_v1_','far_speed_precheck_v1_').replace('latest_rear_latch_precheck','latest_far_speed_precheck').replace('offline_rear_latch_precheck','offline_far_speed_precheck').replace("ROOT/'experiments/opponent_pool/rear_latch60_v1'","ROOT/'experiments/opponent_pool/far_speed_v1'")
launch=launch.replace("ledger=read(lp);ledger['items']", "ledger=read(lp) if lp.exists() else dict(date_taipei=datetime.datetime.now().date().isoformat(),daily_limit_hours=6.,reserved_hours=0.,items=[],policy='warning_only_no_refund');ledger['items']")
(ROOT/'diagnostics/far_speed_precheck_guardian_v1.py').write_text(head+worker+launch,encoding='utf8')
print('Prepared120s static/saved-packet precheck; no new FDM')
