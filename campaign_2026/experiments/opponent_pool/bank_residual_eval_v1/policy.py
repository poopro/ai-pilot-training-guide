"""Legal packet-only deterministic blue policy and exact frozen red APIs."""
import copy,math,sys
import numpy as np
import common as c
m,features,fixed=c.runtime()
def model():
    from stable_baselines3 import SAC
    if c.sha(c.MODEL)!=c.MODEL_SHA:raise RuntimeError('Candidate bytes changed')
    value=SAC.load(c.MODEL,device='cpu');assert value.observation_space.shape==(17,) and value.action_space.shape==(1,)
    value.actor.eval()
    for p in value.actor.parameters():p.requires_grad_(False)
    assert c.tc.actor_digest(value)==c.read(c.BUNDLE/'RESULT.json')['final_actor_sha256']
    return value
class BluePolicy:
    def __init__(self,mode,settings,actor=None):
        if mode not in ('neutral','learned'):raise ValueError('Explicit mode')
        self.mode=mode;self.actor=actor;self.controller=c.bridge.controller(settings);self.receipt=c.bridge.receipt(self.controller)
        self.counted=None;self.packet=None;self.attack=0;self.guard=False;self.bank=0.;self.act_calls=0;self.predict_calls=0;self.last_features=None;self.goals=None;self.decision_tick=None;self.original_act=self.controller.act
        original=self.controller.command
        self.command_source=dict(path=original.__code__.co_filename,sha256=c.sha(original.__code__.co_filename))
        self.command_calls=0
        def command(packet,roll,pitch,speed,rudder=0.,safety=True):
            assert safety is True;self.command_calls+=1;self.goals=[float(roll),float(pitch),float(speed),float(rudder)]
            return original(packet,roll,pitch,speed,rudder,safety=True)
        self.controller.command=command
    def observe(self,packet,n):
        own=features.validate_observation(packet)
        if type(n) is not int or not 0<=n<=18000:raise ValueError('Explicit completed clock')
        if self.counted==n:
            if not np.array_equal(own,self.packet):raise RuntimeError('Duplicate clock changed own packet')
            return
        if n!=(0 if self.counted is None else self.counted+1):raise RuntimeError('Missing private clock step')
        if n>0:
            geo=features.geometry_from_observation(own);self.attack+=int(152.4<=geo['distance_m']<=914.4 and geo['blue_angle_deg']<=1.)
        self.counted=n;self.packet=own.copy()
    def select(self,packet,n):
        self.observe(packet,n)
        if n%20==0 and self.decision_tick!=n:
            self.last_features=features.observation(packet,self.attack,bool(self.guard),n)
            if self.mode=='learned':
                if self.actor is None:raise RuntimeError('Frozen actor required')
                action=self.actor.predict(self.last_features,deterministic=True)[0];self.bank=float(np.asarray(action).item());self.predict_calls+=1
            else:self.bank=0.
            self.decision_tick=n
        return c.bridge.residual(self.bank)
    def next(self,packet,n):
        residual=self.select(packet,n)
        if n!=self.act_calls:raise RuntimeError('One act per completed tick')
        value,guard=self.original_act(packet,residual=residual,started=True);self.act_calls+=1;self.guard=bool(guard)
        if self.command_calls!=self.act_calls:raise RuntimeError('One original command per act')
        return fixed.legal_command(value)
def make_red(kind,settings,initial_red,rng_state):
    if kind=='sac5000':return fixed.build_frozen_opponent('sac5000',settings)
    if kind=='rule':
        from duel_lab import RuleFighter
        rng=np.random.default_rng();rng.bit_generator.state=copy.deepcopy(rng_state)
        return RuleFighter(copy.deepcopy(settings),float(initial_red[2])*.3048,rng)
    if kind=='mirror':
        mod=c.load('bank_eval_exact_mirror',c.ROOT/'experiments/m4_tactical_v4/m3_mirror_league.py')
        return mod.MirrorP2Controller(copy.deepcopy(settings),.72,6.,9.)
    raise ValueError('Explicit frozen opponent')
def red_receipt(red,kind):return fixed.runtime_receipt(red.controller if kind=='sac5000' else red)
