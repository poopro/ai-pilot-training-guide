from pathlib import Path
import importlib.util,time
ROOT=Path(r'E:\ai_pilot\campaign_2026');HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('bank_fdm_fixed_reference',ROOT/'experiments/opponent_pool/far_speed_v1/battle.py');b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
read,write,sha,digest,identity,live=b.read,b.write,b.sha,b.digest,b.identity,b.live
SEED=2026310800;TOTAL=240;TICKS=300
def sources():
    files=[HERE/n for n in ('common.py','bridge.py','test_bridge.py','probe.py','verify.py','guard.py','USAGE_OBSERVATION.json')]
    files += [ROOT/'experiments/opponent_pool/rule_family_v1/policy.py',ROOT/'experiments/rules_v20261014/judge.py']
    return dict(fixed_reference=b.sources(),new_files={str(p):sha(p) for p in files})
def gate(spec):
    if sources()!=spec['sources']:raise RuntimeError('Frozen sources/XML/model changed')
def stop(out):return b.stop(out) or (HERE/'STOP').exists()
def check(out,phase):
    spec=read(out/'CONTRACT.json');limits=read(out/(phase+'_LIMITS.json'))
    if stop(out) or b.expired(spec,limits) or not live(spec['guardian']):raise RuntimeError('Original wall/phase/STOP/guardian gate')
    return spec
