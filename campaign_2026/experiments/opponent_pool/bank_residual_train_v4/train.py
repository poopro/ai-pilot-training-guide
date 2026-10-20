"""One fresh bounded17x1 CPU SAC pilot; no prior model/optimizer/replay."""
from pathlib import Path
import json,sys,time,traceback
import numpy as np
import common as c
def run(out):
    spec=c.check(out,'WORKER');c.gate(spec)
    import torch
    torch.set_num_threads(1)
    from stable_baselines3 import SAC
    from stable_baselines3.common.callbacks import BaseCallback
    from environment import BankGym
    env=BankGym(out,spec);model=None;began=time.monotonic();result=dict(status='running',fresh_actor=True,fresh_critic_optimizer_replay=True,exact_resume=False,actor_transfer=False,training_started=True,formal_deployment='repair_guide',deployment_allowed=False)
    class Progress(BaseCallback):
        def _on_step(self):
            if self.num_timesteps%100==0:
                env.csv.flush();env.samples.flush();env.runtime();c.b.base.resources()
                c.write(out/'progress.json',dict(status='training',updates=self.model._n_updates,replay=self.model.replay_buffer.size(),**env.summary()))
            if self.num_timesteps%500==0:c.gate(spec)
            return True
    try:
        hp=spec['hyperparameters'].copy();architecture=hp.pop('net_arch')
        model=SAC('MlpPolicy',env,**hp,policy_kwargs=dict(net_arch=architecture,activation_fn=torch.nn.Tanh,log_std_init=-1.),seed=c.LEARNER_SEED,verbose=0)
        initial=c.actor_digest(model);assert model.observation_space.shape==(17,) and model.action_space.shape==(1,) and model.replay_buffer.size()==0 and model._n_updates==0
        result['initial_actor_sha256']=initial
        model.learn(total_timesteps=c.DECISIONS,callback=Progress())
        result.update(status='training_complete_pending_bundle_verification',actual_decisions=int(model.num_timesteps),gradient_updates=int(model._n_updates),replay_size=int(model.replay_buffer.size()),final_actor_sha256=c.actor_digest(model))
    except BaseException as exc:traceback.print_exc();result.update(status='failed_partial_training',error=repr(exc))
    finally:
        try:
            if model is not None:
                result.update(actual_decisions=int(model.num_timesteps),gradient_updates=int(model._n_updates),replay_size=int(model.replay_buffer.size()),final_actor_sha256=c.actor_digest(model))
                model.save(out/'model.zip');model.save_replay_buffer(out/'replay.pkl')
                probes=np.stack((np.zeros(17,dtype=np.float32),env.features())) if env.physics is not None else np.zeros((1,17),dtype=np.float32)
                before=model.predict(probes,deterministic=True)[0]
                loaded=SAC.load(out/'model.zip',device='cpu');loaded.load_replay_buffer(out/'replay.pkl')
                np.testing.assert_array_equal(before,loaded.predict(probes,deterministic=True)[0]);assert loaded.replay_buffer.size()==model.replay_buffer.size()
                assert loaded.observation_space.shape==(17,) and loaded.action_space.shape==(1,) and loaded.gamma==.9995
                result.update(bundle_reload_exact=True,probe_observations=probes.tolist(),probe_outputs=before.tolist(),artifact_sha256={n:c.sha(out/n) for n in ('model.zip','replay.pkl')})
            result.update(env.summary())
            if result['status']=='training_complete_pending_bundle_verification':
                assert result['actual_decisions']==result['decisions']==c.DECISIONS and result['gradient_updates']>0 and result['replay_size']==c.DECISIONS and result['initial_actor_sha256']!=result['final_actor_sha256'] and result['blue_over9G']==0 and result['new_FDM_ticks']<=c.MAX_TICKS
                result['status']='fresh_training_complete_pending_independent_verification'
        except BaseException as exc:traceback.print_exc();result.update(status='failed_bundle_or_completion',save_error=repr(exc))
        env.close();result['artifact_sha256']=result.get('artifact_sha256',{})|{n:c.sha(out/n) for n in ('physics.csv','decisions.jsonl')}
        result['wall_seconds']=time.monotonic()-began
        try:c.gate(spec)
        except BaseException as exc:result.update(status='failed_source_gate',source_error=repr(exc))
        c.write(out/'RESULT.json',result);c.write(out/'progress.json',result)
    print(json.dumps(dict(status=result['status'],decisions=result.get('actual_decisions'),updates=result.get('gradient_updates'),new_FDM_ticks=result.get('new_FDM_ticks'),error=result.get('error',result.get('save_error')))),flush=True)
    return 0 if result['status']=='fresh_training_complete_pending_independent_verification' else 2
if __name__=='__main__':raise SystemExit(run(Path(sys.argv[1])))
