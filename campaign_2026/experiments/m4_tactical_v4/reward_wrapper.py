"""Outcome-preserving shaping for a fresh learner, not an old-model resume.

F(s,s')=gamma*Phi(s')-Phi(s), with Phi=0 on actual terminal games.
Matched learner gamma makes the discounted shaping sum telescope. A positive
intermediate score cannot turn a loss/draw into a positive terminal objective.
"""
import math
import gymnasium as gym


class WinPotentialReward(gym.Wrapper):
    def __init__(self,env,*,gamma=.9995,terminal_bonus=10.,potential_scale=10000.):
        super().__init__(env)
        if not 0<gamma<=1 or not math.isfinite(gamma):raise ValueError('Invalid gamma')
        if not 0<terminal_bonus<math.inf or not 0<potential_scale<math.inf:raise ValueError('Invalid reward scale')
        self.gamma=float(gamma)
        self.terminal_bonus=float(terminal_bonus)
        self.potential_scale=float(potential_scale)
        self.previous=None

    def verify_learner_gamma(self,learner):
        if learner.gamma!=self.gamma:raise ValueError('Learner/shaping gamma mismatch')

    def reset(self,**kwargs):
        obs,info=self.env.reset(**kwargs)
        gap=float(info['advantage_blue_estimate'])-float(info['advantage_red_estimate'])
        if not math.isfinite(gap) or gap!=0.:raise ValueError('Fresh judge must start from zero score')
        self.previous=0.
        return obs,info

    def step(self,action):
        if self.previous is None:raise RuntimeError('Reset before reward steps')
        obs,diagnostic_reward,terminated,truncated,info=self.env.step(action)
        snapshot=info['judge_snapshot']
        terminal=snapshot['event']!='ongoing'
        gap=float(snapshot['advantage'][0])-float(snapshot['advantage'][1])
        if not math.isfinite(gap):raise ValueError('Nonfinite private judge score')
        if terminal and (not terminated or truncated):raise ValueError('Game terminal incorrectly mapped')
        if terminal and snapshot['winner'] not in ('blue','red','draw'):raise ValueError('Unknown game winner')
        next_potential=0. if terminal else gap/self.potential_scale
        base=0.
        if terminal:
            base=self.terminal_bonus if snapshot['winner']=='blue' else (-self.terminal_bonus if snapshot['winner']=='red' else 0.)
        shaped=self.gamma*next_potential-self.previous
        reward=base+shaped
        self.previous=next_potential
        result=dict(info)
        result.update(reward_contract='winner_plus_gamma_matched_potential_v1',
                      base_outcome_reward=base,potential_shaping_reward=shaped,
                      unused_diagnostic_reward=float(diagnostic_reward),
                      reward_gamma=self.gamma,prefix_not_round_win=bool(truncated and not terminal))
        return obs,float(reward),terminated,truncated,result
