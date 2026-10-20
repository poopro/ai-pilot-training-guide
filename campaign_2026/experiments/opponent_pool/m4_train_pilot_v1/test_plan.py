import ast,unittest
from common import *

class Gates(unittest.TestCase):
    def test_balanced_schedule(self):
        schedule=episode_schedule()
        self.assertEqual(schedule,episode_schedule())
        self.assertEqual(len({s['seed'] for s in schedule}),256)
        self.assertNotIn(POLICY_SEED,{s['seed'] for s in schedule})
        for start in range(0,252,9):
            self.assertEqual({(s['opponent'],s['distance_ft']) for s in schedule[start:start+9]},
                {(o,d) for o in ('rule','mirror','rl') for d in (3000,6000,9000)})
    def test_plan_tamper_rejected(self):
        cases=plan_cases_for_mode(POLICY_SEED);cases[0]['decisions']+=1
        with self.assertRaises(ValueError):validate_execution_plan(cases,POLICY_SEED)
    def test_seed_check_covers_all_257(self):
        schedule=episode_schedule();inputs=[{'seed':POLICY_SEED}]+schedule
        status=prep.seed_status({'observed_seeds':{str(schedule[-1]['seed']):{}},'trials':{}},inputs)
        self.assertFalse(status['fresh_relative_to_registry']);self.assertEqual(len(status['requested']),257)
    def test_guard_and_original_deadlines(self):
        tree=ast.parse((HERE/'run_smoke.py').read_text(encoding='utf8'))
        text=ast.unparse(tree)
        self.assertIn('worker_start_monotonic + 840',text)
        self.assertEqual(sha(HERE/'guard.py'),sha(POOL/'smoke_executor/v5/guard.py'))
        self.assertEqual(MODE_CONTRACT['fresh_sac_pilot']['total_wall_seconds'],900)
    def test_import_has_no_worker_execution(self):
        tree=ast.parse((HERE/'train_worker.py').read_text(encoding='utf8'))
        self.assertEqual([n.name for n in tree.body if isinstance(n,ast.FunctionDef)],['run'])
        self.assertFalse(any(isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) for n in tree.body))
    def test_cpu_and_gamma_and_step_budget(self):
        self.assertEqual(HYPERPARAMETERS['device'],'cpu');self.assertEqual(HYPERPARAMETERS['gamma'],.9995)
        case=plan_cases_for_mode(POLICY_SEED)[0]
        self.assertEqual(case['decisions']*20,case['max_physics_ticks'])
        self.assertEqual(case['decisions']%HYPERPARAMETERS['train_freq'],0)

if __name__=='__main__':unittest.main()
