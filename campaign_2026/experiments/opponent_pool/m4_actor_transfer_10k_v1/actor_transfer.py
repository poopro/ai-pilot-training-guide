"""Actor-only initialization; never loads source replay or optimizer into learner."""
from pathlib import Path
import hashlib,json

def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def module_digest(module):
    digest=hashlib.sha256()
    for key,value in sorted(module.state_dict().items()):
        digest.update(key.encode());digest.update(value.detach().cpu().numpy().tobytes())
    return digest.hexdigest()

def source_actor_gate(spec):
    for key in ('model','manifest','review'):
        if file_sha(spec[key+'_path'])!=spec[key+'_sha256']:raise RuntimeError('Changed actor source '+key)
    manifest=json.loads(Path(spec['manifest_path']).read_text(encoding='utf8'))
    review=json.loads(Path(spec['review_path']).read_text(encoding='utf8'))
    if manifest['model_sha256']!=spec['model_sha256'] or manifest['model_path']!=spec['model_path']:raise RuntimeError('Manifest actor provenance')
    if not review.get('verified_fresh_training_pilot') or not review.get('zero_over9G'):raise RuntimeError('Source technical gate')
    if manifest['observation_dimensions']!=13 or manifest['tactical_action_dimensions']!=3 or manifest['gamma']!=.9995:raise RuntimeError('Incompatible source dimensions/gamma')
    return manifest

def transfer_actor_only(learner,spec):
    from stable_baselines3 import SAC
    source_actor_gate(spec)
    if learner.num_timesteps!=0 or learner._n_updates!=0 or learner.replay_buffer.size()!=0:raise RuntimeError('Target learner is not fresh')
    if learner.actor.optimizer.state or learner.critic.optimizer.state:raise RuntimeError('Target optimizer is not fresh')
    before=(module_digest(learner.critic),module_digest(learner.critic_target))
    donor=SAC.load(spec['model_path'],device='cpu')
    learner.actor.load_state_dict(donor.actor.state_dict(),strict=True)
    donor_sha=module_digest(donor.actor);target_sha=module_digest(learner.actor)
    del donor
    unchanged=before==(module_digest(learner.critic),module_digest(learner.critic_target))
    if not unchanged or donor_sha!=target_sha or learner.actor.optimizer.state or learner.critic.optimizer.state:raise RuntimeError('Actor-only transfer invariant')
    return {'verified_actor_only_transfer':True,'source_model_sha256':spec['model_sha256'],
            'source_actor_sha256':donor_sha,'initial_actor_sha256':target_sha,'fresh_critic_unchanged':unchanged,
            'fresh_actor_optimizer':True,'fresh_critic_optimizer':True,'replay_size':0,'gradient_updates':0,'exact_resume':False}
