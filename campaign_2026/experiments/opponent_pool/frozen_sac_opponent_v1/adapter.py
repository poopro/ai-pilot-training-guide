"""Packet-only frozen tactical opponent. No simulator/environment wiring."""
import copy
import math
import weakref
import numpy as np
from packet_features import validate_observation,geometry_from_observation,tactical_obs

_owners=weakref.WeakKeyDictionary()

def legal_command(command):
    values=np.asarray(command,dtype=np.float64)
    if values.shape!=(4,) or not np.isfinite(values).all() or np.any(np.abs(values[:3])>1) or not 0<=values[3]<=1:
        raise ValueError('Four finite bounded actuator commands required')
    return values.copy()

class FrozenSACOpponent:
    """command(packet, completed_tick=n) emits command for physics interval n->n+1.

    Incoming packet is the state AFTER exactly n completed physical steps, or
    n=0 reset state. Only n>0 contributes one post-step legal attack window.
    Command is evaluated once at n; duplicate identical n/packet returns cache.
    The caller must not infer n from an unverified environment current_step.
    """
    def __init__(self,*,controller_factory,actor_factory):
        self._controller_factory=controller_factory;self._actor_factory=actor_factory
        self.controller=None;self.actor=None
        self.reset()

    def _own(self,obj,previous):
        if obj is previous:raise ValueError('Reset requires fresh independent object')
        owner=_owners.get(obj)
        if owner is not None:raise ValueError('Controller/actor must never be shared or reused across resets')
        _owners[obj]=weakref.ref(self)
        return obj

    def reset(self):
        # Factories must create fresh objects; no reference to the other player.
        self.faulted=True
        controller=self._controller_factory();actor=self._actor_factory()
        self.controller=self._own(controller,self.controller)
        self.actor=self._own(actor,self.actor)
        self.attack_ticks=0;self.completed_tick=None;self._last_packet=None
        self._cached_command=None;self._last_guard=False;self._hidden_state=None
        self._first_decision=True;self._tactical=np.zeros(3,dtype=np.float32)
        self.act_calls=0;self.predict_calls=0;self.faulted=False
        self.controller.set_tactical(0.,0.,0.)

    def command(self,packet,*,completed_tick):
        if self.faulted:raise RuntimeError('Previous runtime failure; reset required')
        if isinstance(completed_tick,bool) or not isinstance(completed_tick,int) or not 0<=completed_tick<=18000:
            raise ValueError('Explicit nonnegative integer completed_tick <=18000 required')
        observation=validate_observation(packet).copy()
        if self.completed_tick==completed_tick:
            if not np.array_equal(observation,self._last_packet):raise ValueError('Duplicate tick with changed packet')
            return self._cached_command.copy()
        expected=0 if self.completed_tick is None else self.completed_tick+1
        if completed_tick!=expected:raise ValueError('Missing/reset/regressed completed state; no guessed counters')
        try:
            geometry=geometry_from_observation(observation)
            if completed_tick>0:
                self.attack_ticks+=int(500*.3048<=geometry['distance_m']<=3000*.3048 and geometry['blue_angle_deg']<=1.)
            if completed_tick%20==0:
                features=tactical_obs(observation,geometry,self.attack_ticks,self._last_guard,elapsed_ticks=completed_tick)
                if features.shape!=(13,) or not np.isfinite(features).all():raise ValueError('Illegal own tactical features')
                action,state=self.actor.predict(features.copy(),state=copy.deepcopy(self._hidden_state),
                    episode_start=np.asarray([self._first_decision],dtype=bool),deterministic=True)
                action=np.asarray(action,dtype=np.float32)
                if action.shape!=(3,) or not np.isfinite(action).all() or np.any(np.abs(action)>1):raise ValueError('Illegal three-value tactical action')
                self._hidden_state=copy.deepcopy(state);self._first_decision=False
                self._tactical=action.copy();self.predict_calls+=1
                self.controller.set_tactical(*[float(v) for v in self._tactical])
            # Tactical vector never becomes residual; exactly one frozen act.
            command,guard=self.controller.act(observation.copy(),started=True)
            command=legal_command(command)
            if not isinstance(guard,(bool,np.bool_)):raise ValueError('Own controller guard must be boolean')
            self._last_guard=bool(guard);self.act_calls+=1
            self.completed_tick=completed_tick;self._last_packet=observation.copy();self._cached_command=command.copy()
            return command.copy()
        except BaseException:
            self.faulted=True
            raise

    def status(self):
        return {'completed_tick':self.completed_tick,'attack_ticks':self.attack_ticks,'act_calls':self.act_calls,
                'predict_calls':self.predict_calls,'guard_active':self._last_guard,'faulted':self.faulted,
                'tactical':self._tactical.tolist(),'simulator_wiring_verified':False}

