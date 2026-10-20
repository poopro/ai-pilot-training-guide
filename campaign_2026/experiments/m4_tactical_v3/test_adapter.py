"""Small real adapter tests with explicit private-state fixtures, no FDM."""
from types import SimpleNamespace
from pathlib import Path
import ast
import unittest
import math
import numpy as np
from judge_adapter import RuleJudgeAdapter, RESEARCH_RULE_PROFILE


def environment(blue_agl=1000.,red_agl=1000.,blue_hsl=1500.,red_hsl=1500.):
    plane=lambda a,h:SimpleNamespace(fdm={'position/h-agl-ft':a/.3048,'position/h-sl-ft':h/.3048})
    return SimpleNamespace(current_step=0,fdm1=plane(blue_agl,blue_hsl),fdm2=plane(red_agl,red_hsl))


class AdapterTests(unittest.TestCase):
    def test_one_update_per_real_step_and_no_silent_double_update(self):
        env=environment();adapter=RuleJudgeAdapter(env,RESEARCH_RULE_PROFILE)
        env.current_step=1
        adapter.update({'distance_m':200.,'blue_angle_deg':0.,'red_angle_deg':180.},1.,1.)
        self.assertEqual(adapter.attack,[1,0])
        with self.assertRaises(RuntimeError):adapter.update({'distance_m':200.,'blue_angle_deg':0.,'red_angle_deg':180.},1.,1.)
        self.assertEqual(adapter.attack,[1,0])

    def test_old_crash_booleans_cannot_override_new50metres(self):
        env=environment(blue_agl=49.,blue_hsl=1000.);adapter=RuleJudgeAdapter(env,RESEARCH_RULE_PROFILE)
        env.current_step=1
        adapter.update({'distance_m':200.,'blue_angle_deg':90.,'red_angle_deg':90.},1.,1.)
        self.assertEqual(adapter.outcome(False,False),'own_crash')
        self.assertEqual(adapter.estimated_winner('timeout'),'red')

    def test_collision_reaches_parent_terminal_api(self):
        env=environment();adapter=RuleJudgeAdapter(env,RESEARCH_RULE_PROFILE);env.current_step=1
        adapter.update({'distance_m':14.,'blue_angle_deg':0.,'red_angle_deg':180.},1.,1.)
        self.assertEqual(adapter.outcome(False,False),'collision')
        self.assertEqual(adapter.estimated_winner('collision'),'blue')

    def test_short_cutoff_cannot_be_claimed_as_timeout_win(self):
        env=environment();adapter=RuleJudgeAdapter(env,RESEARCH_RULE_PROFILE);env.current_step=1
        adapter.update({'distance_m':200.,'blue_angle_deg':0.,'red_angle_deg':180.},1.,1.)
        self.assertEqual(adapter.estimated_winner('timeout'),'undecided')

    def test_real_time_feature_is_legal_clock_and_not_hidden_enemy_state(self):
        path=Path(__file__).with_name('m4_tactical_rl.py');tree=ast.parse(path.read_text(encoding='utf-8'))
        func=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='tactical_obs')
        heading=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='enemy_heading_proxy_deg')
        ns={'np':np,'math':math,'BAND_LO_M':152.4,'BAND_HI_M':914.4,'KILL_TICKS':180}
        exec(compile(ast.Module(body=[heading,func],type_ignores=[]),str(path),'exec'),ns)
        obs=np.zeros(26);obs[23]=500.
        geo={'distance_m':500.,'blue_angle_deg':10.,'bearing_deg':20.,'closing_mps':0.}
        start=ns['tactical_obs'](obs,geo,0,False,elapsed_ticks=0)
        end=ns['tactical_obs'](obs,geo,0,False,elapsed_ticks=18000)
        self.assertEqual(start.shape,(13,));self.assertEqual(end.shape,(13,))
        self.assertEqual(start[-1],1.);self.assertEqual(end[-1],0.)
        self.assertTrue(np.array_equal(start[:-1],end[:-1]))


if __name__=='__main__':unittest.main()
