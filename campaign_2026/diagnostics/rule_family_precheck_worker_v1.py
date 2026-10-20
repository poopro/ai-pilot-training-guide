"""Real act/command wiring on saved prefixes. No FDM or model calls."""
from pathlib import Path
import ast,copy,importlib.util,json,os,sys
import numpy as np
ROOT=Path(r'E:\ai_pilot\campaign_2026');SOURCE=ROOT/'experiments/opponent_pool/far_speed_v1'
RUN=SOURCE/'run_20261018_033053_98bc0f'
sys.path.insert(0,str(SOURCE));import battle as b
read,write,sha=b.read,b.write,b.sha
def worker(out):
    spec=read(out/'CONTRACT.json')
    assert os.getppid()==spec['guardian']['pid'] and b.live(spec['guardian'])
    for path,h in spec['new_sources'].items():assert sha(Path(path))==h
    path=ROOT/'experiments/opponent_pool/rule_family_v1/policy.py'
    exact=importlib.util.spec_from_file_location('rule_family_precheck_exact',path);f=importlib.util.module_from_spec(exact);exact.loader.exec_module(f)
    # Framework import is allowed only to resolve real production classes and
    # configuration; no environment construction, reset or physics call.
    sys.path.insert(0,str(ROOT/'experiments/m4_tactical_v4'));import m4_tactical_rl as m
    import combat_v3.env as ce
    settings=read(Path(ce.__file__).parent/'config.json')
    checks=[];records=[];first_packets=[]
    tree=ast.parse(path.read_text(encoding='utf8'))
    imports=[node for node in ast.walk(tree) if isinstance(node,(ast.Import,ast.ImportFrom))]
    assert not any(any(word in ast.unparse(node) for word in ('torch','stable_baselines','judge','m4_tactical_rl','env','factory')) for node in imports)
    checks.append('adapter imports no environment/judge/actor/telemetry')
    act=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='act')
    calls=[n for n in ast.walk(act) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='act'];assert len(calls)==1
    assert any(k.arg=='residual' and isinstance(k.value,ast.Constant) and k.value.value is None for k in calls[0].keywords)
    checks.append('one underlying act, explicit residual=None')
    for case in b.plan():
        if case['actor']!='station_zero':continue
        folder=RUN/'cases'/case['id'];result=read(folder/'RESULT.json');assert sha(folder/'telemetry.jsonl')==result['artifacts']['telemetry.jsonl']
        rows=[]
        with (folder/'telemetry.jsonl').open(encoding='utf8') as stream:
            for line in stream:
                row=json.loads(line)
                if row['tick']>300:break
                rows.append(row)
        assert len(rows)==300;first_packets.append(rows[0]['blue_packet_pre'])
        policies={family:f.RulePolicy(family,settings) for family in f.FAMILIES}
        direct=f.build_controller('pure_guide',settings)
        baseline_reference=m.TacticalDuel._build_blue(type('SettingsOnly',(),{'settings':copy.deepcopy(settings)})())
        assert policies['station_zero'].controller is not policies['pure_guide'].controller
        assert policies['station_zero'].controller.settings is not policies['pure_guide'].controller.settings
        assert f.controller_receipt(baseline_reference)['act_path']==str(f.STATION)
        differences=0;outputs={family:[] for family in f.FAMILIES}
        for row in rows:
            if b.expired(spec) or b.stop(out) or not b.live(spec['guardian']):raise RuntimeError('Original precheck deadline/STOP/parent')
            packet=row['blue_packet_pre'];original=np.asarray(packet).copy()
            values={family:policy.act(packet,np.zeros(4),started=True) for family,policy in policies.items()}
            reference=baseline_reference.act(packet,residual=np.zeros(4),started=True)
            np.testing.assert_array_equal(values['station_zero'][0],row['blue_command'])
            np.testing.assert_array_equal(values['station_zero'][0],reference[0]);assert values['station_zero'][1]==row['blue_private_guard']==reference[1]
            pure=direct.act(packet,residual=None,started=True)
            np.testing.assert_array_equal(values['pure_guide'][0],pure[0]);assert values['pure_guide'][1]==pure[1]
            np.testing.assert_array_equal(packet,original)
            differences+=int(not np.array_equal(values['station_zero'][0],values['pure_guide'][0]))
            for family in f.FAMILIES:
                output=values[family][0];assert np.isfinite(output).all() and output.shape==(4,)
                assert np.all(output[:3]>=-1) and np.all(output[:3]<=1) and 0<=output[3]<=1
                assert policies[family].last['requested']==policies[family].last['applied']
                outputs[family].append((output.copy(),values[family][1]))
        receipts={family:policy.receipt for family,policy in policies.items()}
        for family,policy in policies.items():
            assert policy.act_calls==policy.command_calls==300
            old=policy.controller;old_settings=old.settings
            policy.reset();assert policy.controller is not old and policy.controller.settings is not old_settings
            assert policy.act_calls==policy.command_calls==0
            for row,expected in zip(rows,outputs[family]):
                if b.expired(spec) or b.stop(out):raise RuntimeError('Original precheck deadline/STOP')
                replay=policy.act(row['blue_packet_pre'],residual=None,started=True)
                np.testing.assert_array_equal(replay[0],expected[0]);assert replay[1]==expected[1]
        records.append(dict(case=case['id'],saved_packet_frames=300,source_artifact_sha256=result['artifacts']['telemetry.jsonl'],runtime_receipts=receipts,
            baseline_actual_saved_commands_exact=True,pure_guide_matches_direct_original_act=True,each_policy_single_command_per_act=True,reset_all300_commands_exact=True,
            changed_actual_commands=differences,command_difference_is_not_combat_improvement=True))
    p=first_packets[0]
    for family in f.FAMILIES:
        policy=f.RulePolicy(family,settings);before=policy.controller.last.copy()
        value=policy.act(p,started=False);np.testing.assert_array_equal(value[0],[0,0,0,.8]);np.testing.assert_array_equal(policy.controller.last,before);assert policy.command_calls==0
        checks.append(family+' STARTfalse no command/state movement')
        policy.reset();calls_before=policy.act_calls
        for residual in ([1,0,0,0],[0,0,0],[0,0,float('nan'),0]):
            try:policy.act(p,residual=residual)
            except ValueError:pass
            else:raise AssertionError('Residual accepted')
        assert policy.act_calls==calls_before==0
        checks.append(family+' nonzero/wrongsize/NaN residual fail before act')
        for bad in (p[:-1],[float('nan')]+p[1:]):
            try:policy.act(bad)
            except ValueError:pass
            else:raise AssertionError('Invalid packet accepted')
        assert policy.act_calls==0
        checks.append(family+' invalid packet fail before act')
        # Probe own state and command safety against the same direct original,
        # not an assumed sign convention or fabricated lower G threshold.
        direct=f.build_controller(family,settings)
        for kind in ('low_altitude','low_speed','overG'):
            probe=np.asarray(p).copy()
            if kind=='low_altitude':probe[2]=1.;probe[8]=0.
            if kind=='low_speed':probe[12]=150.*1.6878098571011957
            if kind=='overG':probe[14]=8.6
            policy.reset();direct=f.build_controller(family,settings)
            got=policy.act(probe,residual=None);expected=direct.act(probe,residual=None,started=True)
            np.testing.assert_array_equal(got[0],expected[0]);assert got[1]==expected[1] and policy.last['safety'] is True
        checks.append(family+' original lowalt/energy/G safety exact synthetic checks')
        if family=='station_zero':
            policy.reset();policy.controller.set_tactical(.1,0,0)
            try:policy.act(p)
            except RuntimeError:pass
            else:raise AssertionError('Tactical injection accepted')
            checks.append('station nonzero tactical failclosed')
    # The ordinary tactical environment step is incompatible with pure guide:
    # new comparison must use the identical frozen RepairDuel.step zero4 path
    # for both families. Assert that prerequisite from actual source structure.
    step=ast.parse(Path(m.__file__).read_text(encoding='utf8'))
    tactical=next(n for n in ast.walk(step) if isinstance(n,ast.ClassDef) and n.name=='TacticalDuel')
    step_method=next(n for n in tactical.body if isinstance(n,ast.FunctionDef) and n.name=='step')
    assert any(isinstance(n,ast.Attribute) and n.attr=='set_tactical' for n in ast.walk(step_method))
    assert not hasattr(f.RulePolicy('pure_guide',settings),'set_tactical')
    checks.append('TacticalDuel.step zero3 prohibited; common RepairDuel.step zero4 still requires future real FDM verification')
    for path,h in spec['new_sources'].items():assert sha(Path(path))==h
    b.source_gate(read(RUN/'CONTRACT.json'))
    write(out/'VERIFICATION.json',dict(verified_rule_family_saved_packet_wiring=True,checks=checks,check_groups=len(checks),results=records,saved_input_frames=600,
        actual_act_command_replays_per_family=1200,scope='Two saved baseline prefixes. Station replay exact; pureguide actual act and command exact versus direct source, reset replay exact. Synthetic safety checks are not physical safety validation.',
        new_FDM_ticks=0,model_inference_calls=0,training_started=False,seed_claims=[],deployment_allowed=False,
        remaining='No full comparison runner/verifier yet; no parent env.step/FDM wiring or full combat result established.'))
    print(json.dumps(dict(verified_rule_family_saved_packet_wiring=True,check_groups=len(checks),results=records),ensure_ascii=False),flush=True)
    return 0
if __name__=='__main__':raise SystemExit(worker(Path(sys.argv[1])))
