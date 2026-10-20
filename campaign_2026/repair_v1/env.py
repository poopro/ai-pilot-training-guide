"""Isolated controller/reward repair. Curriculum never labels itself official.

The unchanged judge counts true simulation ticks. Policy and controller see
only OWN20+ENEMY6, not judge truth or hidden enemy attitude.
"""
from pathlib import Path
import math
import sys
import numpy as np

LAB = Path('E:/ai_pilot/autopilot/opponent_lab')
sys.path.insert(0, str(LAB))
from duel_lab import (DuelLab, simulator_observation, policy_state, load_policy,
                      DEFAULT_BUNDLE, file_hash, BASE, JsbsimFdm)
from combat_v3.interface import geometry_from_observation
from combat_v3.controller import relative_geometry
from controller import RepairController

REWARD_CONFIG = {
    'progress_scale':4., 'alignment_per_second':.12,
    'precision_per_second':1., 'attack_per_second':4.,
    'residual_per_second':.03, 'guard_per_second':.1,
    'low_altitude_per_second':.7, 'over_g_per_second':2.,
    'kill_bonus':30., 'loss_penalty':35.,
}


def precision_terms(g):
    a=g['blue_angle_deg']; d=g['distance_m']
    alignment=(1+math.cos(math.radians(a)))/2
    range_score=math.exp(-((d-550)/400)**2)
    precision=math.exp(-(a/8)**2)*range_score
    potential=.35*alignment+.35*alignment*range_score+.3*precision
    return potential,alignment*math.exp(-d/3000),precision


class RepairDuel(DuelLab):
    def __init__(self,*args,controller='repair',reward_profile='old',
                 stage='official',reward_gamma=.999,**kwargs):
        if stage not in ('rear','maneuver','official'): raise ValueError('Unknown stage')
        if reward_profile not in ('old','precision'): raise ValueError('Unknown reward profile')
        self.controller_variant=controller; self.reward_profile=reward_profile
        self.curriculum_stage=stage; self.reward_gamma=float(reward_gamma)
        self.requested_p2=kwargs.get('p2',args[0] if args else 'rule')
        super().__init__(*args,**kwargs)

    def reset(self,**kwargs):
        observation,info=super().reset(**kwargs)
        stage=self.curriculum_stage
        self.p2_type=('rl' if self.np_random.random()<.25 else 'rule') if (
            self.requested_p2=='mixed' and stage=='official') else (
            'rule' if stage!='official' else self.requested_p2)
        if self.p2_type=='rl' and self.frozen_policy is None: raise ValueError('Frozen P2 policy required')
        if stage!='official':
            red=simulator_observation(self.fdm2,self.fdm1)
            distance=float(self.np_random.uniform(500,750) if stage=='rear' else self.np_random.uniform(850,1600))
            heading=float(red[5]); bearing=math.radians(heading+180)
            lat=red[0]+math.degrees(math.cos(bearing)*distance/6378137)
            lon=red[1]+math.degrees(math.sin(bearing)*distance/(6378137*math.cos(math.radians(red[0]))))
            jitter=2 if stage=='rear' else 15
            self.fdm1=JsbsimFdm(fdm_id=1,fdm_ic_lat=lat,fdm_ic_long=lon,fdm_ic_h=red[2],fdm_ic_v=340,
                fdm_ic_psi=(heading+self.np_random.uniform(-jitter,jitter))%360)
            self.geometry=relative_geometry(self.fdm1,self.fdm2)
            self.min_altitude_m=self.fdm1.fdm['position/h-agl-ft']*.3048
            self.training_red=RepairController(self.settings)
            self.training_red_altitude=red[2]*.3048
            self.training_turn_sign=float(self.np_random.choice([-1,1]))
            self.spawn_distance_ft=distance/.3048
        if self.controller_variant!='old': self.packet_controller=RepairController(self.settings,self.controller_variant)
        self.prev_potential=self._potential(self.geometry)
        legal=geometry_from_observation(simulator_observation(self.fdm1,self.fdm2))
        self.precision_previous=precision_terms(legal)[0]
        info=self._info(); info.update(training_stage=stage,official_validation=False)
        return policy_state(simulator_observation(self.fdm1,self.fdm2)),info

    def _red_action(self):
        if self.curriculum_stage=='official': return super()._red_action()
        obs=simulator_observation(self.fdm2,self.fdm1)
        bank=0. if self.curriculum_stage=='rear' else 15*math.sin(self.current_step/60/12)*self.training_turn_sign
        phi=math.radians(obs[3])
        level_pitch=math.degrees(math.atan2(obs[16]*math.sin(phi)+obs[17]*math.cos(phi),max(obs[15],1.)))
        correction=np.clip((self.training_red_altitude-obs[2]*.3048)*.012+obs[8]*.3048*.16,-8,12)
        command,self.p2_guard=self.training_red.command(obs,bank,level_pitch+correction,340.)
        self.p2_mode='training_level' if self.curriculum_stage=='rear' else 'training_maneuver'
        return command

    def step(self,action):
        observation,reward,terminated,truncated,info=super().step(action)
        blue_obs=simulator_observation(self.fdm1,self.fdm2)
        legal=geometry_from_observation(blue_obs)
        if self.reward_profile=='precision':
            potential,alignment,precision=precision_terms(legal)
            if terminated: potential=0.
            w=REWARD_CONFIG
            bw=self.judge.window(self.geometry['distance_m'],self.geometry['blue_angle_deg'])
            rw=self.judge.window(self.geometry['distance_m'],self.geometry['red_angle_deg'])
            reward=w['progress_scale']*(self.reward_gamma*potential-self.precision_previous)
            reward+=self.dt*(w['alignment_per_second']*alignment+w['precision_per_second']*precision+
                w['attack_per_second']*(int(bw)-int(rw))-
                w['residual_per_second']*float(np.mean(np.asarray(action)**2))-
                w['guard_per_second']*int(info['guard_active'])-
                w['low_altitude_per_second']*max(0,(1500-blue_obs[2]*.3048)/1500)**2-
                w['over_g_per_second']*int(abs(blue_obs[14])>9))
            if terminated:
                if self.outcome=='kill': reward+=w['kill_bonus']
                elif self.outcome=='enemy_crash': reward+=w['kill_bonus']/2
                elif self.outcome in ('own_crash','shot_down','mutual_crash','simultaneous_hit'): reward-=w['loss_penalty']
            self.precision_previous=potential
            info.update(precision_reward=precision,alignment_reward=alignment)
        info.update(controller_variant=self.controller_variant,controller_mode=getattr(self.packet_controller,'mode','old'),
            bank_deg=float(blue_obs[3]),pitch_deg=float(blue_obs[4]),alpha_deg=float(blue_obs[18]),
            closing_mps=legal['closing_mps'],training_stage=self.curriculum_stage,official_validation=False)
        if isinstance(self.packet_controller,RepairController): info.update(self.packet_controller.telemetry)
        return observation,float(reward),terminated,truncated,info
