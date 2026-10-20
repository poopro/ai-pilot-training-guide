from pathlib import Path
import importlib.util,sys,time
ROOT=Path(r'E:\ai_pilot\campaign_2026');HERE=Path(__file__).resolve().parent;TRAIN=ROOT/'experiments/opponent_pool/bank_residual_train_v4';BUNDLE=TRAIN/'run_20261018_184640_29092b'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
tc=load('bank_eval_fixed_training_common',TRAIN/'common.py');b=tc.b;bridge=tc.bridge
read,write,sha,digest,identity,live=tc.read,tc.write,tc.sha,tc.digest,tc.identity,tc.live
MODEL=BUNDLE/'model.zip';MODEL_SHA='b9bcce79185343c4fdf1b022feb42c4dceb62c8e312da29962c07ae34513b176';SEEDS=(2026315000,2026315001,2026315002)
def plan():
    return [dict(id=f'{opp}_{mode}',pair=i,episode=0,seed=SEEDS[i],opponent=opp,side=('normal','mirrored','normal')[i],distance_ft=6000,mode=mode,max_ticks=18000) for i,opp in enumerate(('sac5000','rule','mirror')) for mode in ('neutral','learned')]
def runtime():
    features=load('bank_eval_fixed17_features',TRAIN/'policy_features.py');sys.modules['policy_features']=features
    environment=load('bank_eval_fixed_training_environment',TRAIN/'environment.py');environment.m.torch.set_num_threads(1)
    return environment.m,features,environment
def sources():
    own=[HERE/n for n in ('common.py','policy.py','worker.py','verify.py','guard.py','test_contract.py','USAGE_OBSERVATION.json')]
    saved=[BUNDLE/n for n in ('model.zip','RESULT.json','BUNDLE_MANIFEST.json','VERIFICATION.json','FINAL_REVIEW.json','PARENT_EXIT_OBSERVED.json')]
    return dict(fixed_training_sources=tc.sources(),files={str(p):sha(p) for p in own+saved})
def gate(spec):
    if sources()!=spec['sources'] or sha(MODEL)!=MODEL_SHA:raise RuntimeError('Frozen evaluation/source/XML/model changed')
def stop(out):return tc.stop(out) or (HERE/'STOP').exists()
def check(out,phase):
    spec=read(out/'CONTRACT.json');limits=read(out/(phase+'_LIMITS.json'))
    if stop(out) or b.expired(spec,limits) or not live(spec['guardian']):raise RuntimeError('STOP/original phase wall/guardian')
    return spec
