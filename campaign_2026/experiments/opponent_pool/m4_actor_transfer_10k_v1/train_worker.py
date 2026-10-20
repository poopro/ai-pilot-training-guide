"""Private fresh SAC pilot. No unguarded CLI, no historical replay or optimizer."""
import csv
import traceback
from common import *


def run(input_path):
    spec=read(input_path); out=Path(spec['out']); folder=Path(input_path).parent
    launch=read(out/'launch.json'); case=spec['case']
    if Path(input_path).resolve()!=out/'cases'/case['case_id']/'input.json':raise RuntimeError('Unreserved worker path')
    if psutil.Process().ppid()!=launch['supervisor']['pid'] or not matching(launch['supervisor']):raise RuntimeError('Parent identity mismatch')
    execution_mode_gate(launch)
    guard=read(out/'guard.json')
    if guard['status']!='armed' or not matching(guard['guard']):raise RuntimeError('Independent guard unavailable')
    if case not in launch['cases'] or spec['tools_sha256']!=launch['tools_sha256']:raise RuntimeError('Changed reserved case')
    source_gate(spec['source_freeze']);resource_gate()
    began=time.monotonic(); worker_deadline=min(launch['deadline_monotonic'],began+810)
    sys.path.insert(0,str(ROOT/'experiments/m4_tactical_v4'))
    import m4_tactical_rl as m
    import m1_station
    import numpy as np
    import gymnasium as gym
    import torch
    from stable_baselines3 import SAC
    from stable_baselines3.common.callbacks import BaseCallback
    from reward_wrapper import WinPotentialReward
    for module in (m,m1_station):
        if Path(module.__file__).resolve().parent.name!='m4_tactical_v4':raise RuntimeError('Mixed candidate imports')
    torch.set_num_threads(1)
    result={'status':'running','worker_identity':identity(),'fresh_learner':True,'actor_transfer_only':True,'exact_resume':False,
            'official_validation':False,'deployment_allowed':False,'win_rate_evidence':False,
            'episode_starts':[],'completed_episodes':[],'new_fdm_ticks':0,'over9G_ticks':0,
            'max_abs_G':0.,'min_AGL_m':None,'hyperparameters':case['hyperparameters']}
    model=None; vec=None; shaped=None; gym_env=None
    per_tick=(folder/'physics.csv').open('w',encoding='utf8',newline='')
    writer=csv.DictWriter(per_tick,fieldnames=['episode','tick','total_tick','act_calls','blue_sends','red_sends','blue_G','AGL_m','attack_blue','attack_red','event','winner','advantage_blue','advantage_red','actual_command'])
    writer.writeheader()

    def check_runtime():
        if stop(out):raise RuntimeError('STOP')
        if time.monotonic()>=worker_deadline-25:raise RuntimeError('Reserved saving margin reached')
        resource_gate()

    class ScheduledGym(gym.Env):
        def __init__(self):
            self.observation_space=gym.spaces.Box(-2.,2.,(13,),dtype=np.float32)
            self.action_space=gym.spaces.Box(-1.,1.,(3,),dtype=np.float32)
            self.env=None;self.next_episode=0;self.tick_budget=0
            self.red_policy=None

        def reset(self,*,seed=None,options=None):
            super().reset(seed=seed);check_runtime()
            if self.next_episode>=len(case['episodes']):raise RuntimeError('Reserved episode seeds exhausted')
            if self.env is not None:self.env.close()
            episode=case['episodes'][self.next_episode];self.next_episode+=1
            if episode['opponent']=='rl' and self.red_policy is None:self.red_policy=m.load_policy(m.DEFAULT_BUNDLE)
            self.env=m.TacticalDuel(opponent=episode['opponent'],policy=self.red_policy if episode['opponent']=='rl' else None,
                                    distance_ft=episode['distance_ft'],stage='official',max_steps=18000)
            _,info=self.env.reset(seed=episode['seed'])
            initial=m.simulator_observation(self.env.fdm1,self.env.fdm2).tolist()
            initial_red=m.simulator_observation(self.env.fdm2,self.env.fdm1).tolist()
            start={**episode,'initial_blue':initial,'initial_red':initial_red,'initial_blue_sha256':jsha(initial),
                   'initial_red_sha256':jsha(initial_red),'actual_opponent':self.env.p2_type,
                   'actual_spawn_distance_ft':self.env.spawn_distance_ft,'rules_profile':vars(self.env.judge.profile)}
            if self.env.p2_type!=episode['opponent'] or abs(self.env.spawn_distance_ft-episode['distance_ft'])>1e-8:raise RuntimeError('Scheduled cell mismatch')
            result['episode_starts'].append(start)
            env=self.env;counts={'act':0,'blue':0,'red':0};state={'command':None,'actual':None}
            original_act=env.packet_controller.act;original_blue=env.fdm1.sendAction;original_red=env.fdm2.sendAction;original_judge=env.judge.update
            def act(*args,**kwargs):
                counts['act']+=1;cmd,active=original_act(*args,**kwargs);state['command']=legal_command(cmd);return cmd,active
            def blue(command):
                counts['blue']+=1;state['actual']=legal_command(command)
                if state['actual']!=state['command']:raise RuntimeError('Sent action differs from sole controller output')
                return original_blue(command)
            def red(command):
                counts['red']+=1;legal_command(command)
                if 'fallback' in env.p2_mode:raise RuntimeError('Opponent fallback')
                return original_red(command)
            def judge(geo,bg,rg):
                original_judge(geo,bg,rg);tick=env.current_step
                if any(counts[key]!=tick for key in counts):raise RuntimeError('Controller/send count differs from physics ticks')
                self.tick_budget+=1;result['new_fdm_ticks']=self.tick_budget
                g=abs(float(bg));alt=float(env.fdm1.fdm['position/h-agl-ft'])*.3048
                result['max_abs_G']=max(result['max_abs_G'],g)
                result['min_AGL_m']=alt if result['min_AGL_m'] is None else min(result['min_AGL_m'],alt)
                result['over9G_ticks']+=int(g>9.)
                advantages=env.judge.advantages()
                writer.writerow({'episode':episode['episode'],'tick':tick,'total_tick':self.tick_budget,
                    'act_calls':counts['act'],'blue_sends':counts['blue'],'red_sends':counts['red'],
                    'blue_G':bg,'AGL_m':alt,'attack_blue':env.judge.attack[0],'attack_red':env.judge.attack[1],
                    'event':env.judge.core.event,'winner':env.judge.core.winner,
                    'advantage_blue':advantages[0],'advantage_red':advantages[1],'actual_command':json.dumps(state['actual'])})
                if self.tick_budget>case['max_physics_ticks']:raise RuntimeError('Physics budget exceeded')
                if g>9.:raise RuntimeError('Own aircraft exceeded9G; preserve partial, no automatic retry')
                if tick%60==0 and (stop(out) or time.monotonic()>=worker_deadline-25):raise RuntimeError('STOP/deadline at completed physics frame')
            env.packet_controller.act=act;env.fdm1.sendAction=blue;env.fdm2.sendAction=red;env.judge.update=judge
            obs=env.tactical_obs_only()
            if not self.observation_space.contains(obs):raise RuntimeError('Illegal reset observation')
            write(folder/'progress.json',{**result,'status':'running','decisions':int(model.num_timesteps) if model else 0})
            return obs,info

        def step(self,action):
            check_runtime()
            obs,reward,terminated,truncated,info=self.env.step(action)
            if not self.observation_space.contains(obs):raise RuntimeError('Illegal tactical observation')
            if terminated or truncated:
                result['completed_episodes'].append({'episode':self.next_episode-1,'ticks':self.env.current_step,
                    'opponent':self.env.opponent_kind,'judge_snapshot':info['judge_snapshot'],
                    'terminated':bool(terminated),'truncated':bool(truncated)})
            return obs,reward,terminated,truncated,info

        def close(self):
            if self.env is not None:self.env.close();self.env=None

    def actor_digest(learner):
        import hashlib
        digest=hashlib.sha256()
        for key,value in sorted(learner.actor.state_dict().items()):digest.update(key.encode());digest.update(value.detach().cpu().numpy().tobytes())
        return digest.hexdigest()

    class Progress(BaseCallback):
        def _on_step(self):
            if self.num_timesteps%100==0:
                per_tick.flush()
                write(folder/'progress.json',{**result,'status':'running','decisions':self.num_timesteps,
                    'gradient_updates':self.model._n_updates,'replay_size':self.model.replay_buffer.size(),
                    'elapsed_seconds':time.monotonic()-began})
            if self.num_timesteps%1000==0:
                source_gate(spec['source_freeze']);self.model.save(folder/('checkpoint_'+str(self.num_timesteps)))
            return True

    try:
        gym_env=ScheduledGym();shaped=WinPotentialReward(gym_env,gamma=.9995)
        hp=dict(case['hyperparameters']);architecture=hp.pop('net_arch');hp.pop('activation')
        model=SAC('MlpPolicy',shaped,**hp,policy_kwargs={'net_arch':architecture,'activation_fn':torch.nn.Tanh,'log_std_init':-1.},
                  seed=case['seed'],verbose=0)
        shaped.verify_learner_gamma(model)
        from actor_transfer import transfer_actor_only
        result['actor_transfer_audit']=transfer_actor_only(model,read(HERE/'CONTRACT.json')['actor_transfer_source'])
        initial_actor_sha=actor_digest(model)
        model.learn(total_timesteps=case['decisions'],callback=Progress())
        result.update(status='training_finished',decisions=int(model.num_timesteps),gradient_updates=model._n_updates,
                      replay_size=model.replay_buffer.size(),initial_actor_sha256=initial_actor_sha,final_actor_sha256=actor_digest(model))
    except BaseException as error:
        traceback.print_exc();result.update(status='failed_partial',error=repr(error))
    finally:
        try:
            if model is not None:
                result.update(decisions=int(model.num_timesteps),gradient_updates=model._n_updates,replay_size=model.replay_buffer.size())
                model.save(folder/'model.zip');model.save_replay_buffer(folder/'replay.pkl')
                probe=np.zeros((1,13),dtype=np.float32)
                before=model.predict(probe,deterministic=True)[0]
                loaded=SAC.load(folder/'model.zip',device='cpu');loaded.load_replay_buffer(folder/'replay.pkl')
                after=loaded.predict(probe,deterministic=True)[0]
                reloaded=loaded.replay_buffer.size()==model.replay_buffer.size() and loaded.gamma==.9995 and loaded.observation_space.shape==(13,) and loaded.action_space.shape==(3,) and np.allclose(before,after,atol=1e-6,rtol=0)
                result['bundle_reload_verified']=bool(reloaded)
                if not reloaded:raise RuntimeError('Model/replay reload mismatch')
                result['artifact_sha256']={name:sha(folder/name) for name in ('model.zip','replay.pkl')}
            if shaped is not None:shaped.close()
        except BaseException as error:
            traceback.print_exc();result.update(status='failed_partial',save_or_close_error=repr(error))
        per_tick.close()
        result['physics_csv_sha256']=sha(folder/'physics.csv')
        result['wall_seconds']=time.monotonic()-began
        if result['status']=='training_finished':
            valid=(result['decisions']==10000 and result['gradient_updates']>0 and result['replay_size']==10000
                   and result['initial_actor_sha256']!=result['final_actor_sha256'] and result['over9G_ticks']==0
                   and result['bundle_reload_verified'] and result['new_fdm_ticks']<=200000)
            result['status']='completed_actor_transfer_training' if valid else 'failed_completion_gate'
        try:source_gate(spec['source_freeze'])
        except BaseException as error:result.update(status='failed_source_gate',error=repr(error))
        write(folder/'result.json',result);write(folder/'progress.json',result)
    return 0 if result['status']=='completed_actor_transfer_training' else 2
