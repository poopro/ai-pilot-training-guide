"""Real guidance AST and reward algebra fixtures; no FDM or learner."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
import math
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from reward_wrapper import WinPotentialReward

HERE=Path(__file__).resolve().parent


class ParentController:
    def __init__(self,*args):pass
    def command(self,o,bank,pitch,speed,rudder):return bank,False


def load_station(path):
    tree=ast.parse(path.read_text(encoding='utf-8-sig'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='StationController')
    namespace={'RepairController':ParentController,'np':np,'math':math,
               'BAND_LO_M':152.4,'BAND_HI_M':914.4,
               'wrap_deg':lambda x:(x+180)%360-180,
               'validate_observation':lambda x:x}
    exec(compile(ast.Module(body=[cls],type_ignores=[]),str(path),'exec'),namespace)
    return namespace


def bank(namespace,heading_error,nose_magnitude=None):
    ns=namespace.copy()
    #Class methods share the original namespace, so update that mapping in place.
    namespace['geometry_from_observation']=lambda o:{
        'distance_m':625.,'bearing_deg':heading_error,'lead_bearing_deg':heading_error,
        'blue_angle_deg':abs(heading_error) if nose_magnitude is None else nose_magnitude,
        'own_tas_mps':220.,'elevation_deg':0.,'enemy_equivalent_cas_kts':340.,'cas_ratio':1.}
    controller=namespace['StationController']({},'station')
    obs=np.zeros(26);obs[2]=obs[22]=14000.;obs[12]=340.*1.687809857
    return controller.act(obs)[0]


class ScoreTrace(gym.Env):
    observation_space=spaces.Box(-2.,2.,(13,),dtype=np.float32)
    action_space=spaces.Box(-1.,1.,(3,),dtype=np.float32)
    def __init__(self,gaps,winner='blue',prefix=False):
        self.gaps=gaps;self.winner=winner;self.prefix=prefix
    def reset(self,**kwargs):
        self.index=0
        return np.zeros(13),{'advantage_blue_estimate':0.,'advantage_red_estimate':0.}
    def step(self,action):
        gap=self.gaps[self.index];self.index+=1;last=self.index==len(self.gaps)
        terminal=last and not self.prefix
        return np.zeros(13),999.,terminal,last and self.prefix,{
            'judge_snapshot':{'event':'timeout' if terminal else 'ongoing',
                              'winner':self.winner if terminal else None,'advantage':[gap,0.]}}


class CandidateTests(unittest.TestCase):
    def test_original_wrong_sign_is_reproduced(self):
        old=load_station(HERE.parent/'m4_tactical_v3'/'m1_station.py')
        self.assertAlmostEqual(bank(old,-1.2),.96)

    def test_signed_candidate_is_mirror_symmetric(self):
        candidate=load_station(HERE/'m1_station.py')
        left,right=bank(candidate,-1.2),bank(candidate,1.2)
        self.assertAlmostEqual(left,-5.28)
        self.assertAlmostEqual(right,5.28)
        self.assertAlmostEqual(left,-right)

    def test_vertical_nose_error_does_not_invent_lateral_bank(self):
        candidate=load_station(HERE/'m1_station.py')
        self.assertEqual(bank(candidate,0.,nose_magnitude=5.),0.)

    def test_only_one_control_assignment_changed(self):
        original=(HERE.parent/'m4_tactical_v3'/'m1_station.py').read_text(encoding='utf-8-sig')
        changed=(HERE/'m1_station.py').read_text(encoding='utf-8-sig')
        self.assertEqual(changed,original.replace('nose_err = geo["blue_angle_deg"]','nose_err = heading_error'))

    def test_discounted_shaping_telescopes_to_actual_winner(self):
        gamma=.9
        for winner,value in [('blue',10.),('red',-10.),('draw',0.)]:
            for gaps in ([50000.,-100000.,30000.],[-50000.,200000.,0.]):
                env=WinPotentialReward(ScoreTrace(gaps,winner),gamma=gamma)
                env.reset();total=0.
                for tick in range(len(gaps)):
                    _,reward,_,_,_=env.step(np.zeros(3));total+=gamma**tick*reward
                self.assertAlmostEqual(total,gamma**(len(gaps)-1)*value)

    def test_learner_gamma_must_match(self):
        env=WinPotentialReward(ScoreTrace([0.]))
        with self.assertRaises(ValueError):env.verify_learner_gamma(SimpleNamespace(gamma=.995))
        env.verify_learner_gamma(SimpleNamespace(gamma=.9995))

    def test_short_cutoff_is_not_a_win_and_does_not_get_terminal_bonus(self):
        env=WinPotentialReward(ScoreTrace([10000.],prefix=True))
        env.reset();_,reward,terminated,truncated,info=env.step(np.zeros(3))
        self.assertFalse(terminated);self.assertTrue(truncated)
        self.assertEqual(info['base_outcome_reward'],0.)
        self.assertAlmostEqual(reward,.9995)

    def test_unknown_terminal_winner_has_no_learning_target(self):
        env=WinPotentialReward(ScoreTrace([0.],winner=None));env.reset()
        with self.assertRaises(ValueError):env.step(np.zeros(3))


if __name__=='__main__':unittest.main()
