"""No FDM, no learner updates and no live registry/budget mutation."""
import ast,copy,unittest,tempfile
from unittest.mock import patch
from common import *
import guard
from actor_transfer import transfer_actor_only,source_actor_gate

class PreparationTests(unittest.TestCase):
    def test_contract_sources(self):
        contract_gate();self.assertTrue(source_gate()['verified'])
    def test_balanced_new_seed_plan(self):
        plan=plan_cases_for_mode(POLICY_SEED)[0]
        self.assertEqual((plan['decisions'],plan['max_physics_ticks']),(10000,200000))
        self.assertEqual(HYPERPARAMETERS['buffer_size'],50000)
        self.assertEqual(HYPERPARAMETERS['net_arch'],[128,128])
        episodes=plan['episodes'];self.assertEqual(len({e['seed'] for e in episodes}),256)
        for i in range(0,252,9):self.assertEqual(len({(e['opponent'],e['distance_ft']) for e in episodes[i:i+9]}),9)
        status=prep.seed_status(read(ROOT/'seed_registry.json'),[{'seed':POLICY_SEED}]+episodes)
        self.assertTrue(status['fresh_relative_to_registry'])
    def test_plan_mutation_rejected(self):
        changed=plan_cases_for_mode(POLICY_SEED);changed[0]['decisions']=10001
        with self.assertRaises(ValueError):validate_execution_plan(changed,POLICY_SEED)
    def test_no_review_no_reservation(self):
        with patch('common.write',side_effect=AssertionError('No live writes')):
            with self.assertRaises(FileNotFoundError):reserve(POLICY_SEED,HERE/'not_created',50,time.time())
    def test_original_deadlines_and_per_tick_gates(self):
        worker=ast.unparse(ast.parse((HERE/'train_worker.py').read_text(encoding='utf8')))
        supervisor=ast.unparse(ast.parse((HERE/'run_smoke.py').read_text(encoding='utf8')))
        self.assertIn('began + 810',worker);self.assertIn('worker_deadline - 25',worker)
        self.assertIn('worker_start_monotonic + 840',supervisor)
        self.assertIn("counts[key] != tick",worker);self.assertIn('if g > 9.0:',worker)
        self.assertIn("'publication_error_count'",(HERE/'guard.py').read_text(encoding='utf8'))
        self.assertEqual(MODE_CONTRACT['actor_transfer_10k']['total_wall_seconds'],900)
    def test_guard_transient_read(self):
        clock=[0.]
        def sleep(s):clock[0]+=s
        with patch.object(guard.Path,'exists',return_value=True),patch.object(guard,'read',side_effect=[PermissionError(),{'ok':True}]),patch.object(guard,'stop',return_value=False),patch.object(guard.time,'monotonic',side_effect=lambda:clock[0]),patch.object(guard.time,'sleep',side_effect=sleep):
            self.assertEqual(guard.read_active_receipt(HERE,1.),{'ok':True});self.assertLessEqual(clock[0],.25)
    def test_guard_persistent_read(self):
        clock=[0.]
        def sleep(s):clock[0]+=s
        with patch.object(guard.Path,'exists',return_value=True),patch.object(guard,'read',side_effect=PermissionError()),patch.object(guard,'stop',return_value=False),patch.object(guard.time,'monotonic',side_effect=lambda:clock[0]),patch.object(guard.time,'sleep',side_effect=sleep):
            with self.assertRaises(PermissionError):guard.read_active_receipt(HERE,1.)
        self.assertLessEqual(clock[0],.25000001)
    def test_guard_stop_read(self):
        with patch.object(guard.Path,'exists',return_value=True),patch.object(guard,'read',side_effect=PermissionError()),patch.object(guard,'stop',return_value=True):
            with self.assertRaises(PermissionError):guard.read_active_receipt(HERE,time.monotonic()+1)
    def test_guard_access_denied_not_retried(self):
        with patch.object(guard.Path,'exists',return_value=True),patch.object(guard,'read',side_effect=psutil.AccessDenied(42)):
            with self.assertRaises(psutil.AccessDenied):guard.read_active_receipt(HERE,time.monotonic()+1)
    def test_actual_actor_only_transfer_without_fdm(self):
        import gymnasium as gym,numpy as np,torch
        from stable_baselines3 import SAC
        class NoStep(gym.Env):
            observation_space=gym.spaces.Box(-2.,2.,(13,),dtype=np.float32)
            action_space=gym.spaces.Box(-1.,1.,(3,),dtype=np.float32)
            def reset(self,**kw):raise AssertionError('No reset/FDM/training in preparation')
            def step(self,action):raise AssertionError('No step/training in preparation')
        hp=dict(HYPERPARAMETERS);architecture=hp.pop('net_arch');hp.pop('activation')
        learner=SAC('MlpPolicy',NoStep(),**hp,policy_kwargs={'net_arch':architecture,'activation_fn':torch.nn.Tanh,'log_std_init':-1.},seed=POLICY_SEED,verbose=0)
        audit=transfer_actor_only(learner,read(HERE/'CONTRACT.json')['actor_transfer_source'])
        self.assertTrue(audit['verified_actor_only_transfer']);self.assertEqual(learner.num_timesteps,0)
        self.assertEqual(learner._n_updates,0);self.assertEqual(learner.replay_buffer.size(),0)
        learner.num_timesteps=1
        with self.assertRaises(RuntimeError):transfer_actor_only(learner,read(HERE/'CONTRACT.json')['actor_transfer_source'])
    def test_source_tamper_rejected(self):
        spec=copy.deepcopy(read(HERE/'CONTRACT.json')['actor_transfer_source']);spec['model_sha256']='0'*64
        with self.assertRaises(RuntimeError):source_actor_gate(spec)

if __name__=='__main__':unittest.main()
