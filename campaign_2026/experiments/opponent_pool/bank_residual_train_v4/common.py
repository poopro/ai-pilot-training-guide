from pathlib import Path
import importlib.util,sys,time
ROOT=Path(r'E:\ai_pilot\campaign_2026');HERE=Path(__file__).resolve().parent
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
base=load('bank17_verified_interface',ROOT/'experiments/opponent_pool/bank_residual_fdm_v1/common.py')
b=base.b;bridge=load('bank17_fixed_bridge',ROOT/'experiments/opponent_pool/bank_residual_fdm_v1/bridge.py')
read,write,sha,digest,identity,live=base.read,base.write,base.sha,base.digest,base.identity,base.live
LEARNER_SEED=2026312999;EPISODE_SEEDS=tuple(range(2026314000,2026314032));SEEDS=(LEARNER_SEED,*EPISODE_SEEDS)
TOTAL=900;DECISIONS=3000;MAX_TICKS=60000
def plan():
    return [dict(episode=i,seed=seed,opponent=('sac5000','rule','mirror')[i%3],distance_ft=(6000,3000,9000)[(i//3+i%3)%3],side=('normal','mirrored')[(i//9+i%3)%2]) for i,seed in enumerate(EPISODE_SEEDS)]
def sources():
    paths=[HERE/n for n in ('common.py','policy_features.py','environment.py','train.py','test_contract.py','verify.py','guard.py','USAGE_OBSERVATION.json')]
    paths += [ROOT/'experiments/m4_tactical_v4/m3_mirror_league.py']
    return dict(verified_interface_sources=base.sources(),new_files={str(p):sha(p) for p in paths})
def gate(spec):
    if sources()!=spec['sources']:raise RuntimeError('Frozen training/interface/XML/red source changed')
def stop(out):return base.stop(out) or (HERE/'STOP').exists()
def check(out,phase):
    spec=read(out/'CONTRACT.json');limits=read(out/(phase+'_LIMITS.json'))
    if stop(out) or b.expired(spec,limits) or not live(spec['guardian']):raise RuntimeError('Original/phase wall STOP or parent')
    return spec
def actor_digest(model):
    import hashlib
    value=hashlib.sha256()
    for key,tensor in sorted(model.actor.state_dict().items()):value.update(key.encode());value.update(tensor.detach().cpu().numpy().tobytes())
    return value.hexdigest()
