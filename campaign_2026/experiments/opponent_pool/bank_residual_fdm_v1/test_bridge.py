"""Prelaunch API wiring and saved neutral regression; no physics/model call."""
import ast,json,sys
from pathlib import Path
import numpy as np
import common as c
import bridge
def run(out):
    spec=c.check(out,'PRECHECK');c.gate(spec)
    checks=[]
    for a in (-1.,0.,1.):
        v=bridge.residual([a]);np.testing.assert_array_equal(v,[a,0,0,0]);assert v.dtype==np.float32
    checks.append('scalar_to4_residual_exact')
    for bad in ([0,0,0],[0,0,0,0],float('nan'),1.01,-1.01):
        try:bridge.residual(bad)
        except ValueError:pass
        else:raise AssertionError('Invalid action')
    checks.append('invalid_shape_finite_bound_failclosed')
    seq=[bridge.scheduled('exercise',n) for n in range(300)]
    assert seq==[0.]*100+[-1.]*100+[1.]*100 and all(seq[n]==seq[(n//20)*20] for n in range(300))
    assert all(bridge.scheduled('neutral',n)==0. for n in range(300));checks.append('20tick_hold_and_first100_neutral')
    for bad in (-1,300,0.,True):
        try:bridge.scheduled('exercise',bad)
        except ValueError:pass
        else:raise AssertionError('Bad clock')
    checks.append('clock_type_range')
    pure=bridge.factory.exact_module('rule_family_v1_exact_repair',bridge.factory.REPAIR)
    import combat_v3.interface as interface
    settings=c.read(Path(interface.__file__).parent/'config.json')
    for case in c.b.plan():
        if case['actor']!='station_zero':continue
        folder=c.ROOT/'experiments/opponent_pool/far_speed_v1/run_20261018_033053_98bc0f/cases'/case['id'];r=c.read(folder/'RESULT.json');assert c.sha(folder/'telemetry.jsonl')==r['artifacts']['telemetry.jsonl']
        blue=bridge.controller(settings);reference=bridge.controller(settings)
        assert blue is not reference and blue.settings is not reference.settings
        rec=bridge.receipt(blue);assert rec['act_path']==rec['command_path']==str(c.ROOT/'repair_v1/controller.py')
        count=0
        with (folder/'telemetry.jsonl').open(encoding='utf8') as f:
            for line in f:
                row=json.loads(line)
                if row['tick']>20:break
                c.check(out,'PRECHECK');a=blue.act(row['blue_packet_pre'],bridge.residual(0.));z=reference.act(row['blue_packet_pre'],residual=None)
                np.testing.assert_array_equal(a[0],z[0]);np.testing.assert_array_equal(a[0],row['blue_command']);assert a[1]==z[1]==row['blue_private_guard'];count+=1
        assert count==20
    checks.append('two20packet_new_bridge_neutral_exact_private_controllers')
    worker=ast.parse((c.HERE/'probe.py').read_text(encoding='utf8'))
    assert not any(isinstance(n,ast.Attribute) and n.attr in ('learn','set_tactical') for n in ast.walk(worker))
    assert any(isinstance(n,ast.Attribute) and n.attr=='RepairDuel' for n in ast.walk(worker));checks.append('parent4residual_path_no_tactical_or_learning')
    for p in c.HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf8'))
    checks.append('all_source_AST')
    c.gate(spec);c.write(out/'PRECHECK.json',dict(verified_prelaunch_bridge=True,checks=checks,groups=len(checks),saved_neutral_frames=40,new_FDM_ticks=0,model_inference_calls=0))
    print(json.dumps(dict(precheck=True,groups=len(checks))),flush=True);return 0
if __name__=='__main__':raise SystemExit(run(Path(sys.argv[1])))
