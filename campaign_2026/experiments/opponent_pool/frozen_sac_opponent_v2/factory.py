"""Read-only local frozen production factories; not invoked by synthetic tests."""
from pathlib import Path
import copy,hashlib,importlib.util,json,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
MODELS={
 'sac5000':(ROOT/'experiments/opponent_pool/m4_train_pilot_v1/run_20261016_003919_a5c748/cases/fresh_sac_5000/model.zip','9f93eb56483558ad56283c00b1ba34af96a236583bc977ef7d9fad375d9a0fea'),
 'transfer10000':(ROOT/'experiments/opponent_pool/m4_actor_transfer_10k_v1/run_20261016_102640_412524/cases/actor_transfer_10000/model.zip','6c7ceea74457557be60f4156313cf1d75ffff20196159ae8fe22a7809190c012')}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def source_gate():
    contract=json.loads((HERE/'CONTRACT.json').read_text(encoding='utf8'))
    for path,digest in contract['source_sha256'].items():
        if sha(path)!=digest:raise RuntimeError('Frozen controller/features source changed')
    if sha(contract['model_provenance_freeze_path'])!=contract['model_provenance_freeze_sha256']:raise RuntimeError('Terminal model evidence changed')
    for name,digest in contract['executor_sha256'].items():
        if sha(HERE/name)!=digest:raise RuntimeError('Adapter source changed')
    return contract

def frozen_actor(model_id):
    if model_id not in MODELS:raise ValueError('Only two explicitly verified local frozen bundles allowed')
    contract=source_gate();path,digest=MODELS[model_id]
    if contract['models'][model_id]['model_path']!=str(path) or contract['models'][model_id]['model_sha256']!=digest or sha(path)!=digest:
        raise RuntimeError('Frozen actor path/SHA changed')
    # SAC.load initializes global RNGs; restore them before returning a privately
    # owned actor. Deterministic forward does not sample any RNG or use replay.
    import random,numpy as np,torch
    python_state=random.getstate();numpy_state=np.random.get_state()
    try:
        with torch.random.fork_rng(devices=[]):
            # Cold-import side effects belong inside the same RNG restore scope.
            from stable_baselines3 import SAC
            donor=SAC.load(path,device='cpu')
            if donor.observation_space.shape!=(13,) or donor.action_space.shape!=(3,):raise RuntimeError('Wrong frozen actor dimensions')
            actor=donor.actor
            actor.eval()
            for parameter in actor.parameters():parameter.requires_grad_(False)
            actor.optimizer=None
            del donor
    finally:
        random.setstate(python_state);np.random.set_state(numpy_state)
    class ReadOnlyActor:
        def predict(self,observation,*,state=None,episode_start=None,deterministic):
            if deterministic is not True or state is not None:raise ValueError('Frozen SAC must be deterministic/stateless')
            with torch.inference_mode():
                tensor=torch.as_tensor(observation,dtype=torch.float32).reshape(1,13)
                values=actor(tensor,deterministic=True).cpu().numpy()[0]
            return values,None
    return ReadOnlyActor()

def station_controller(settings):
    source_gate()
    path=ROOT/'experiments/m4_tactical_v4/m1_station.py'
    spec=importlib.util.spec_from_file_location('frozen_opponent_station_v1',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    parent=sys.modules[module.StationController.__mro__[1].__module__]
    if Path(parent.__file__).resolve()!=ROOT/'repair_v1/controller.py':raise RuntimeError('Mixed controller import')
    return module.StationController(copy.deepcopy(settings),'station')

def build_frozen_opponent(model_id,settings):
    if model_id not in MODELS:raise ValueError('Unknown frozen actor')
    from adapter import FrozenSACOpponent
    private_settings=copy.deepcopy(settings)
    return FrozenSACOpponent(controller_factory=lambda:station_controller(private_settings),
                             actor_factory=lambda:frozen_actor(model_id))
