from pathlib import Path
ROOT=Path(r'E:\ai_pilot\campaign_2026')
old=(ROOT/'diagnostics/pursuit_window_trace_v2.py').read_text(encoding='utf8')
head=old[:old.index('def worker(out):')]
worker='''def worker(out):
    import runpy,inspect
    spec=read(out/'CONTRACT.json')
    if os.getppid()!=spec['guardian']['pid'] or not live(spec['guardian']):raise RuntimeError('Wrong direct parent')
    for path,h in spec['new_sources'].items():
        if sha(Path(path))!=h:raise RuntimeError('Precheck source changed')
    new=ROOT/'experiments/opponent_pool/rear_latch60_v1'
    sys.path.insert(0,str(new));runpy.run_path(str(new/'test_static.py'))
    helper=sys.modules['battle'];c=helper._goal_module
    import numpy as np
    import m4_tactical_rl as m
    from combat_v3.interface import geometry_from_observation
    settings=read(m.BASE/'combat_v3/config.json') if hasattr(m,'BASE') else read(__import__('combat_v3.env',fromlist=['x']).Path(__import__('combat_v3.env',fromlist=['x']).__file__).parent/'config.json')
    results=[]
    for case in b.plan():
        if case['actor']!='far_bank60':continue
        folder=RUN/'cases'/case['id'];result=read(folder/'RESULT.json')
        if sha(folder/'telemetry.jsonl')!=result['artifacts']['telemetry.jsonl']:raise RuntimeError('Saved packets changed')
        controls=[m.TacticalDuel._build_blue(types.SimpleNamespace(settings=settings)) for _ in range(2)]
        original=[ctrl.command for ctrl in controls];latch=c.RearLatch();row=None;first=None;precommands=0
        def originalcap(packet,roll,pitch,speed,rudder=0.,safety=True):
            geo=geometry_from_observation(packet);g=[roll,pitch,speed,rudder]
            if g!=row['blue_guidance']['requested']:raise RuntimeError('Original act goals changed')
            applied=c.project_goal(geo['distance_m'],g,enabled=True)
            return original[0](packet,*applied,safety=safety)
        def latchedcap(packet,roll,pitch,speed,rudder=0.,safety=True):
            nonlocal first
            geo=geometry_from_observation(packet);g=[roll,pitch,speed,rudder]
            capped=c.project_goal(geo['distance_m'],g,enabled=True)
            he=c.heading_error(packet,geo)
            caller=sys._getframe(1)
            if abs(he-caller.f_locals['heading_error'])>1e-9:raise RuntimeError('Legal heading projection differs from original act')
            applied,t=latch.apply(capped,he,geo['blue_angle_deg'],enabled=True)
            if t['triggered'] and first is None:first=row['tick']
            if first is None and applied!=row['blue_guidance']['applied']:raise RuntimeError('Pretrigger goals changed')
            return original[1](packet,*applied,safety=safety)
        controls[0].command=originalcap;controls[1].command=latchedcap
        with (folder/'telemetry.jsonl').open(encoding='utf8') as stream:
            for line in stream:
                if b.expired(spec) or b.stop(out):raise RuntimeError('Precheck original deadline/STOP')
                row=json.loads(line)
                commands=[ctrl.act(row['blue_packet_pre'],np.zeros(4),started=True) for ctrl in controls]
                np.testing.assert_array_equal(commands[0][0],row['blue_command'])
                if first is not None:break
                np.testing.assert_array_equal(commands[0][0],commands[1][0]);assert commands[0][1]==commands[1][1]==row['blue_private_guard'];precommands+=1
        expected=3591 if case['side']=='normal' else 3974
        if first!=expected or precommands!=first-1:raise RuntimeError('Unexpected saved first rear wrap')
        results.append(dict(case=case['id'],first_saved_packet_trigger_tick=first,pretrigger_actual_inner_commands_exact=precommands,baseline_replayed_against_recorded_actual_command=True,settings_sha256=sha(Path(__import__('combat_v3.env',fromlist=['x']).__file__).parent/'config.json')))
    for path,h in spec['new_sources'].items():
        if sha(Path(path))!=h:raise RuntimeError('Precheck source changed')
    b.source_gate(read(RUN/'CONTRACT.json'))
    write(out/'VERIFICATION.json',dict(verified_pretrigger_actual_command_replay=True,results=results,new_FDM_ticks=0,new_model_inference=False,training_started=False,closed_loop_advantage_verified=False))
    print(json.dumps(dict(verified_pretrigger_actual_command_replay=True,results=results)),flush=True)
    return 0

'''
launch=old[old.index('def launch():'):]
start=launch.index("        old=ROOT/'diagnostics/pursuit_window_trace_")
end=launch.index("        write(out/'CONTRACT.json',spec)",start)
launch=launch[:start]+"        spec['new_sources']={str(p):sha(p) for p in (ROOT/'experiments/opponent_pool/rear_latch60_v1').glob('*.py')}\n"+launch[end:]
launch=launch.replace('pursuit_window_trace_v2_','rear_latch_precheck_v1_').replace('latest_pursuit_trace','latest_rear_latch_precheck')
launch=launch.replace('offline_pursuit_trace','offline_rear_latch_precheck')
(ROOT/'diagnostics/rear_latch_precheck_v1.py').write_text(head+worker+launch,encoding='utf8')
print('prepared precheck guardian, 120s, no FDM')
