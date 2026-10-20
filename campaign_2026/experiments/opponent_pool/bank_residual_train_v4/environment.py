"""Fresh17x1 learning environment. One original60Hz act/send/physics/judge."""
from pathlib import Path
import copy,csv,inspect,json,sys,time
import numpy as np
import gymnasium as gym
import common as c
from policy_features import observation,reward
sys.path.insert(0,str(c.ROOT/'experiments/m4_tactical_v4'));import m4_tactical_rl as m
sys.path.insert(0,str(c.b.base.ADAPTER));from factory import build_frozen_opponent
from adapter import legal_command
from packet_features import geometry_from_observation
STATE_FIELDS=('variant','last','recovering','mode','previous_bearing','bearing_rate','bank_target','pitch_target','speed_target','pitch_integral','speed_integral')
def snapshot(controller):
    return {key:(getattr(controller,key).tolist() if isinstance(getattr(controller,key),np.ndarray) else getattr(controller,key)) for key in STATE_FIELDS}
def restore(controller,state):
    if set(state)!=set(STATE_FIELDS):raise ValueError('Exact original controller state')
    for key,value in state.items():setattr(controller,key,np.asarray(value,dtype=float) if key=='last' else value)
def runtime_receipt(obj):
    path=Path(inspect.getfile(obj.act)).resolve();return dict(class_name=type(obj).__name__,module=type(obj).__module__,path=str(path),sha256=c.sha(path))
def opponent_command(red,kind,packet,n):
    if kind=='sac5000':
        value=red.command(packet,completed_tick=n);status=red.status();guard=status['guard_active'];mode='frozen_sac5000'
    elif kind=='rule':value=red.act(packet,n/60.);guard=red.guard;mode=red.mode
    elif kind=='mirror':value,guard=red.act(packet,n,started=True);mode=red.mode
    else:raise RuntimeError('Unregistered opponent')
    if 'fallback' in mode:raise RuntimeError('No opponent fallback permitted')
    if not isinstance(guard,(bool,np.bool_)):raise RuntimeError('Opponent guard must be explicit boolean')
    return legal_command(value),bool(guard),mode
class BankGym(gym.Env):
    def __init__(self,out,spec):
        self.out=out;self.spec=spec;self.limits=c.read(out/'WORKER_LIMITS.json');self.observation_space=gym.spaces.Box(-2.,2.,(17,),dtype=np.float32);self.action_space=gym.spaces.Box(-1.,1.,(1,),dtype=np.float32)
        self.physics=None;self.red=None;self.previous_red=[];self.previous_blue=[];self.next_episode=0;self.total_ticks=0;self.decisions=0;self.starts=[];self.completed=[];self.episode_ticks={};self.over9G=0;self.peak_g=0.;self.min_AGL=None
        self.csv=(out/'physics.csv').open('w',encoding='utf8',newline='');self.samples=(out/'decisions.jsonl').open('w',encoding='utf8')
        self.fields=['episode','tick','total_tick','act','command','blue_send','red_send','blue_physics','red_physics','judge','distance_m','blue_angle_deg','red_angle_deg','blue_G','red_G','blue_AGL_m','red_AGL_m','blue_attack','red_attack','blue_overG','red_overG','blue_position','red_position','blue_advantage','red_advantage','event','winner','aileron','elevator','rudder','throttle','bank_action']
        self.writer=csv.DictWriter(self.csv,fieldnames=self.fields);self.writer.writeheader()
    def runtime(self):
        if c.stop(self.out) or time.monotonic()>=min(self.spec['deadline_monotonic'],self.limits['deadline_monotonic'])-20 or not c.live(self.spec['guardian']):raise RuntimeError('Original wall/STOP/parent with save margin')
    def features(self):return observation(m.simulator_observation(self.physics.fdm1,self.physics.fdm2),self.private_attack,self.guard,self.physics.current_step)
    def reset(self,*,seed=None,options=None):
        super().reset(seed=seed);self.runtime();c.b.base.resources()
        if self.physics is not None:self.physics.close()
        if self.next_episode>=len(self.spec['episodes']):raise RuntimeError('Reserved schedule exhausted')
        case=self.spec['episodes'][self.next_episode];self.case=case;self.next_episode+=1;self.episode_ticks[case['episode']]=0
        env=m.TacticalDuel(opponent='rule',distance_ft=case['distance_ft'],max_steps=18000);self.physics=env;env.reset(seed=case['seed'])
        side=c.b.initialize_side(env,case['side'],m);env.packet_controller=blue=c.bridge.controller(env.settings);env.controller_variant='repair'
        self.private_attack=0;self.guard=False;self.counts={k:0 for k in ('act','command','blue_send','red_send','blue_physics','red_physics','judge')};self.bank=0.;self.first=None
        if case['opponent']=='sac5000':self.red=build_frozen_opponent('sac5000',env.settings);red_obj=self.red.controller;self.red_kind='frozen_sac5000'
        elif case['opponent']=='rule':
            self.red=type(env.red_fighter)(copy.deepcopy(env.settings),float(env.fdm2.fdm['position/h-sl-ft'])*.3048,copy.deepcopy(env.np_random));red_obj=self.red;self.red_kind='RuleFighter'
            assert self.red.rng is not env.np_random
        else:
            mod=c.load('bank17_frozen_mirror',c.ROOT/'experiments/m4_tactical_v4/m3_mirror_league.py');self.red=mod.MirrorP2Controller(copy.deepcopy(env.settings),.72,6.,9.);red_obj=self.red;self.red_kind='perturbed_MirrorP2Controller'
        assert all(blue is not old for old in self.previous_blue) and all(red_obj is not old for old in self.previous_red);self.previous_blue.append(blue);self.previous_red.append(red_obj)
        initial=[m.simulator_observation(env.fdm1,env.fdm2).tolist(),m.simulator_observation(env.fdm2,env.fdm1).tolist()]
        start=dict(case=case,initial=initial,initial_sha256=c.digest(initial),side_transform=side,blue=c.bridge.receipt(blue),red=runtime_receipt(red_obj),red_kind=self.red_kind,opponent_fallback=False);self.starts.append(start);c.write(self.out/f"episode_{case['episode']:03d}_start.json",start)
        orig_command=blue.command
        def command(packet,roll,pitch,speed,rudder=0.,safety=True):
            self.counts['command']+=1;assert safety is True
            return orig_command(packet,roll,pitch,speed,rudder,safety=True)
        blue.command=command;original_act=blue.act
        def act(packet,residual=None,started=True):
            np.testing.assert_array_equal(residual,c.bridge.residual(self.bank));assert started is True
            if self.counts['act']%20==0:
                self.first=dict(blue_pre=np.asarray(packet).tolist(),blue_state=snapshot(blue),red_guard_pre=bool(env.p2_guard))
            self.counts['act']+=1;value,guard=original_act(packet,residual=residual,started=True);self.expected_blue=legal_command(value).tolist();self.guard=bool(guard)
            if self.counts['act']%20==1:self.first['actual_blue_command']=self.expected_blue.copy()
            return value,guard
        blue.act=act
        def red_action():
            n=self.counts['red_physics'];assert n==env.current_step==self.counts['blue_physics']
            packet=m.simulator_observation(env.fdm2,env.fdm1)
            value,guard,mode=opponent_command(self.red,case['opponent'],packet,n)
            if case['opponent']=='sac5000':assert self.red.attack_ticks==env.judge.attack[1]
            env.p2_mode=mode;env.p2_guard=bool(guard);self.expected_red=legal_command(value).tolist()
            if n%20==0:self.first.update(red_pre=packet.tolist(),first_red_command=self.expected_red.copy(),red_tactical=self.red.status()['tactical'] if case['opponent']=='sac5000' else None)
            return value
        env._red_action=red_action
        for plane,key in ((env.fdm1,'blue_send'),(env.fdm2,'red_send')):
            original=plane.sendAction
            def send(value,key=key,original=original):
                self.counts[key]+=1;np.testing.assert_array_equal(legal_command(value),self.expected_blue if key=='blue_send' else self.expected_red);return original(value)
            plane.sendAction=send
        for plane,key in ((env.fdm1,'blue_physics'),(env.fdm2,'red_physics')):
            original=plane.step
            def physical(key=key,plane=plane,original=original):
                before=plane.fdm.get_sim_time();value=original();assert abs(plane.fdm.get_sim_time()-before-1/60)<1e-9;self.counts[key]+=1;return value
            plane.step=physical
        original_judge=env.judge.update
        def judge(geo,bg,rg):
            original_judge(geo,bg,rg);self.counts['judge']+=1;tick=env.current_step;assert all(n==tick for n in self.counts.values())
            self.total_ticks+=1;self.episode_ticks[case['episode']]=tick
            own=m.simulator_observation(env.fdm1,env.fdm2);g=geometry_from_observation(own);self.private_attack+=int(152.4<=g['distance_m']<=914.4 and g['blue_angle_deg']<=1.)
            assert self.private_attack==env.judge.attack[0]
            snap=env.judge.core.snapshot();alts=[float(p.fdm['position/h-agl-ft'])*.3048 for p in (env.fdm1,env.fdm2)]
            row=dict(episode=case['episode'],tick=tick,total_tick=self.total_ticks,**self.counts,distance_m=geo['distance_m'],blue_angle_deg=geo['blue_angle_deg'],red_angle_deg=geo['red_angle_deg'],blue_G=bg,red_G=rg,blue_AGL_m=alts[0],red_AGL_m=alts[1],blue_attack=snap['attack_ticks'][0],red_attack=snap['attack_ticks'][1],blue_overG=snap['over_g_ticks'][0],red_overG=snap['over_g_ticks'][1],blue_position=snap['position_sum'][0],red_position=snap['position_sum'][1],blue_advantage=snap['advantage'][0],red_advantage=snap['advantage'][1],event=snap['event'],winner=snap['winner'],aileron=self.expected_blue[0],elevator=self.expected_blue[1],rudder=self.expected_blue[2],throttle=self.expected_blue[3],bank_action=self.bank)
            self.writer.writerow(row);self.peak_g=max(self.peak_g,abs(float(bg)));self.min_AGL=alts[0] if self.min_AGL is None else min(self.min_AGL,alts[0]);self.over9G+=int(abs(bg)>9)
            if abs(bg)>9:raise RuntimeError('Blue over9G: stop pilot, no retry or promotion')
            if self.total_ticks>c.MAX_TICKS:raise RuntimeError('Tick budget exceeded')
        env.judge.update=judge
        return self.features(),dict(case=case)
    def step(self,action):
        self.runtime();self.bank=float(np.asarray(action).item());residual=c.bridge.residual(action);env=self.physics
        before=env.judge.core.snapshot();pre=self.features();completed=env.current_step;self.first=None
        for _ in range(20):
            _,_,term,trunc,_=m.RepairDuel.step(env,residual)
            if term or trunc:break
        after=env.judge.core.snapshot();value,terminal=reward(before,after)
        trunc=bool(not terminal and env.current_step>=18000)
        post=self.features();self.decisions+=1
        record=dict(decision=self.decisions,episode=self.case['episode'],completed_tick=completed,physical_ticks=env.current_step-completed,action=[self.bank],features_pre=pre.tolist(),features_post=post.tolist(),**self.first,
            blue_post=m.simulator_observation(env.fdm1,env.fdm2).tolist(),own_attack_pre=before['attack_ticks'][0],own_guard_pre=bool(pre[11]),own_attack_post=self.private_attack,own_guard_post=self.guard,before=before,after=after,reward=value,terminated=terminal,truncated=trunc)
        self.samples.write(json.dumps(record,separators=(',',':'),allow_nan=False)+'\n')
        if terminal or trunc:self.completed.append(dict(case=self.case,ticks=env.current_step,final=after,terminated=terminal,truncated=trunc))
        return post,value,terminal,trunc,dict(judge_snapshot=after)
    def summary(self):
        return dict(decisions=self.decisions,new_FDM_ticks=self.total_ticks,episode_starts=self.starts,completed_episodes=self.completed,last_episode=dict(case=self.case,ticks=self.physics.current_step,final=self.physics.judge.core.snapshot()),
            blue_over9G=self.over9G,peak_abs_blue_G=self.peak_g,min_AGL_m=self.min_AGL,actual_reached_cells=[s['case'] for s in self.starts if self.episode_ticks[s['case']['episode']]>0],episode_physics_ticks=self.episode_ticks)
    def close(self):
        if self.physics is not None:self.physics.close();self.physics=None
        for f in (self.csv,self.samples):
            if not f.closed:f.flush();f.close()
