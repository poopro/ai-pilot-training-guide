"""Synthetic legal packets/fake actor only: no FDM, Host or real inference."""
import ast,math,unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from adapter import FrozenSACOpponent
from packet_features import geometry_from_observation

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

def packet(distance=500.,yaw=0.):
    value=np.zeros(26,dtype=np.float64)
    value[0]=23.;value[1]=120.;value[2]=6000.;value[5]=yaw
    value[6]=1000.;value[12]=1000.;value[13]=1100.;value[14]=1.;value[15]=1100.
    value[20]=value[0]+math.degrees(distance/6378137);value[21]=120.;value[22]=6000.;value[23]=900.
    return value

class FakeController:
    def __init__(self):self.calls=[];self.tactical=[]
    def set_tactical(self,*values):self.tactical=list(values)
    def act(self,observation,residual=None,started=True):
        assert residual is None and started is True
        self.calls.append(observation.copy())
        return np.array([.01,.02,.03,.8]),bool(observation[14]>8.5)

class FakeActor:
    def __init__(self):self.calls=[]
    def predict(self,observation,**kwargs):
        assert kwargs['deterministic'] is True
        self.calls.append((observation.copy(),kwargs))
        return np.array([.1,.2,-.3]),{'private_counter':len(self.calls)}

def opponent():return FrozenSACOpponent(controller_factory=FakeController,actor_factory=FakeActor)

class AdapterTests(unittest.TestCase):
    def test_100_unique_commands_and_duplicate_cache(self):
        red=opponent();p=packet()
        for tick in range(100):
            first=red.command(p,completed_tick=tick);second=red.command(p,completed_tick=tick)
            np.testing.assert_array_equal(first,second)
            second[:]=0
            np.testing.assert_array_equal(first,red.command(p,completed_tick=tick))
        self.assertEqual(red.act_calls,100);self.assertEqual(len(red.controller.calls),100)
        self.assertEqual(red.predict_calls,5);self.assertEqual(red.attack_ticks,99)
        self.assertEqual([int(round(18000*(1-v[0][-1]))) for v in red.actor.calls],[0,20,40,60,80])
        self.assertEqual([int(round(v[0][10]*180)) for v in red.actor.calls],[0,20,40,60,80])
        self.assertEqual(red.actor.calls[0][1]['state'],None)
        self.assertTrue(red.actor.calls[0][1]['episode_start'][0])
    def test_poststep_counter_matches_pure_judge_window(self):
        tree=ast.parse((ROOT/'experiments/rules_v20261014/judge.py').read_text(encoding='utf8'))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='attack_window')
        scope={'FT_TO_M':.3048};exec(compile(ast.Module(body=[fn],type_ignores=[]),'pure-window','exec'),scope)
        red=opponent();red.command(packet(),completed_tick=0);count=0
        for tick in range(1,101):
            p=packet(distance=(151.,152.4,500.,914.4,915.)[tick%5],yaw=(0.,.5,1.,1.1)[tick%4])
            geo=geometry_from_observation(p)
            count+=scope['attack_window'](geo['distance_m'],geo['blue_angle_deg'],SimpleNamespace(attack_angle_deg=1.))
            red.command(p,completed_tick=tick)
            self.assertEqual(red.attack_ticks,count)
    def test_reset_all_local_state_and_factory_objects(self):
        red=opponent()
        for tick in range(21):red.command(packet(),completed_tick=tick)
        controller,actor=red.controller,red.actor
        red.reset();self.assertIsNot(red.controller,controller);self.assertIsNot(red.actor,actor)
        self.assertEqual((red.attack_ticks,red.act_calls,red.predict_calls),(0,0,0))
        self.assertEqual(red.completed_tick,None);self.assertIsNone(red._hidden_state)
        self.assertFalse(red._last_guard);np.testing.assert_array_equal(red._tactical,[0,0,0])
        red.command(packet(),completed_tick=0)
        self.assertIsNone(red.actor.calls[0][1]['state']);self.assertEqual(red.attack_ticks,0)
    def test_two_actors_independent(self):
        first,second=opponent(),opponent();first.command(packet(),completed_tick=0)
        first.command(packet(),completed_tick=1);second.command(packet(yaw=20),completed_tick=0)
        self.assertEqual((first.attack_ticks,second.attack_ticks),(1,0))
        first.reset();self.assertEqual(second.act_calls,1)
        shared=FakeActor()
        one=FrozenSACOpponent(controller_factory=FakeController,actor_factory=lambda:shared)
        with self.assertRaises(ValueError):FrozenSACOpponent(controller_factory=FakeController,actor_factory=lambda:shared)
        with self.assertRaises(ValueError):one.reset()
        self.assertTrue(one.faulted)
    def test_invalid_tick_packet_and_action(self):
        for tick in (-1,True,1.5,18001,1):
            with self.assertRaises(ValueError):opponent().command(packet(),completed_tick=tick)
        red=opponent();red.command(packet(),completed_tick=0)
        with self.assertRaises(ValueError):red.command(packet(),completed_tick=2)
        with self.assertRaises(ValueError):red.command(packet(yaw=1),completed_tick=0)
        bad=packet();bad[23]=float('nan')
        with self.assertRaises(ValueError):opponent().command(bad,completed_tick=0)
        class BadActor(FakeActor):
            def predict(self,*args,**kwargs):return np.array([2.,0.,0.]),None
        red=FrozenSACOpponent(controller_factory=FakeController,actor_factory=BadActor)
        with self.assertRaises(ValueError):red.command(packet(),completed_tick=0)
        self.assertTrue(red.faulted)
        with self.assertRaises(RuntimeError):red.command(packet(),completed_tick=0)
    def test_illegal_actuator_command_rejected(self):
        class BadController(FakeController):
            def act(self,*args,**kwargs):return np.array([0.,0.,0.,1.1]),False
        red=FrozenSACOpponent(controller_factory=BadController,actor_factory=FakeActor)
        with self.assertRaises(ValueError):red.command(packet(),completed_tick=0)
    def test_guard_is_own_prior_controller_only(self):
        red=opponent();p=packet();p[14]=8.6
        red.command(p,completed_tick=0);self.assertTrue(red._last_guard)
        for tick in range(1,21):red.command(p,completed_tick=tick)
        self.assertEqual(red.actor.calls[0][0][11],0.)
        self.assertEqual(red.actor.calls[1][0][11],1.)
    def test_privileged_access_ast_and_no_random(self):
        for name in ('adapter.py','packet_features.py'):
            tree=ast.parse((HERE/name).read_text(encoding='utf-8-sig'))
            forbidden={'fdm','fdm1','fdm2','judge','env','health','optimizer','replay_buffer','act_buf','random','rng','enemy_attitude'}
            for node in ast.walk(tree):
                if isinstance(node,ast.Attribute):self.assertNotIn(node.attr,forbidden)
                if isinstance(node,ast.Name):self.assertNotIn(node.id,forbidden)
    def test_copied_feature_asts_exact(self):
        copied=ast.parse((HERE/'packet_features.py').read_text(encoding='utf8'))
        expected={n.name:ast.dump(n) for file in (ROOT/'experiments/m4_tactical_v4/m4_tactical_rl.py',Path(r'E:\ai_pilot\2026 AI 飛行員  相關資料\AI空戰競賽系統安裝及測試指引\AI空戰競賽系統安裝及測試指引\AirCombat_Train_Test\combat_v3\interface.py')) for n in ast.parse(file.read_text(encoding='utf8')).body if isinstance(n,ast.FunctionDef)}
        for node in copied.body:
            if isinstance(node,ast.FunctionDef):self.assertEqual(ast.dump(node),expected[node.name])
    def test_production_factory_fixed_selection_without_model_load(self):
        import factory
        self.assertEqual(set(factory.MODELS),{'sac5000','transfer10000'})
        with self.assertRaises(ValueError):factory.frozen_actor('shared_live_checkpoint')
        with self.assertRaises(ValueError):factory.build_frozen_opponent('external_model',{})

if __name__=='__main__':unittest.main()
