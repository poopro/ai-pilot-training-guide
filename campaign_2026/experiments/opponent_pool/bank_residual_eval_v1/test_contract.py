from pathlib import Path
import ast,copy,json,sys
import numpy as np
import common as c
def run(out):
    spec=c.check(out,'PRECHECK');c.gate(spec)
    import policy as p
    import combat_v3.interface as interface
    settings=c.read(Path(interface.__file__).parent/'config.json');checks=[];manifest=c.read(c.BUNDLE/'BUNDLE_MANIFEST.json')
    assert manifest['result_sha256']==c.sha(c.BUNDLE/'RESULT.json') and c.read(c.BUNDLE/'VERIFICATION.json')['verified_fresh_bank_residual_pilot'] and c.read(c.BUNDLE/'PARENT_EXIT_OBSERVED.json')['actual_exit']==0
    model=p.model();other=p.model();assert model is not other and c.tc.actor_digest(model)==c.tc.actor_digest(other);checks.append('true frozen17x1 deterministic actor bytes/reload/dimensions/source')
    folder=c.ROOT/'experiments/opponent_pool/bank_residual_fdm_v1/run_20261018_153511_6fb16a/neutral';packets=[];saved=[]
    with (folder/'telemetry.jsonl').open(encoding='utf8') as stream:
        for _ in range(100):
            row=json.loads(next(stream));packets.append(row['blue_packet_pre']);saved.append(row['blue_command'])
    neutral=p.BluePolicy('neutral',settings);direct=c.bridge.controller(settings);learned=p.BluePolicy('learned',settings,model);second=p.BluePolicy('learned',settings,other)
    assert neutral.controller is not direct and learned.controller is not second.controller
    for n,packet in enumerate(packets):
        np.testing.assert_array_equal(neutral.next(packet,n),saved[n]);np.testing.assert_array_equal(direct.act(packet,residual=None)[0],saved[n])
        value=learned.next(packet,n);np.testing.assert_array_equal(value,second.next(packet,n));assert learned.guard==second.guard
    assert learned.predict_calls==second.predict_calls==5 and neutral.predict_calls==0 and learned.command_calls==neutral.command_calls==100
    checks.append('100 saved real packets original neutral=None exact, fresh deterministic/reset state, one act-command and3Hz')
    before=learned.predict_calls
    try:learned.next(packets[-1],99)
    except RuntimeError:pass
    else:raise AssertionError('Duplicate act accepted')
    assert learned.predict_calls==before;checks.append('duplicate act/private clock failclosed')
    packet=np.asarray(packets[0],dtype=float);packet[3:6]=0.;packet[20]=packet[0]+.005;packet[21]=packet[1];packet[22]=packet[2]
    private=p.BluePolicy('neutral',settings);private.observe(packet,0);assert private.attack==0;private.observe(packet,1);private.observe(packet,1);assert private.attack==1;checks.append('first frame START private counter once and duplicate observe idempotent')
    rng=np.random.default_rng(123).bit_generator.state
    for kind in ('sac5000','rule','mirror'):
        red=p.make_red(kind,settings,packets[0],rng);another=p.make_red(kind,settings,packets[0],rng);assert red is not another
        for n in range(3):
            a,g,mode=p.fixed.opponent_command(red,kind,np.asarray(packets[n],dtype=float),n);z,h,mode2=p.fixed.opponent_command(another,kind,np.asarray(packets[n],dtype=float),n)
            np.testing.assert_array_equal(a,z);assert g==h and mode==mode2 and 'fallback' not in mode
    checks.append('all three actual CPU opponent APIs/private RNG/reset sources no fallback')
    import verify
    pose=verify.poses(folder/'duel.acmi');verify.pose_check(pose[0],c.read(c.ROOT/'experiments/opponent_pool/bank_residual_fdm_v1/run_20261018_153511_6fb16a/RESULT.json')['episodes'][0]['initial']);checks.append('strict ACMI WGS84 geodetic versus packet geocentric mapping')
    for path in c.HERE.glob('*.py'):ast.parse(path.read_text(encoding='utf8'))
    tree=ast.parse((c.HERE/'policy.py').read_text(encoding='utf8'));blue=next(x for x in tree.body if isinstance(x,ast.ClassDef));assert not any(isinstance(x,ast.Attribute) and x.attr in ('judge','fdm','score','winner') for x in ast.walk(blue))
    checks.append('policy boundary AST no hidden judge/env/simulator state')
    c.check(out,'PRECHECK');c.gate(spec);c.write(out/'PRECHECK.json',dict(verified_prelaunch_evaluation=True,groups=len(checks),checks=checks,new_FDM_ticks=0,training_started=False));print(json.dumps(dict(precheck=True,groups=len(checks),new_FDM_ticks=0)),flush=True);return 0
if __name__=='__main__':raise SystemExit(run(Path(sys.argv[1])))
