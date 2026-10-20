import ast,unittest
from common import *

class Plan(unittest.TestCase):
    def test_complete_pairs(self):
        cases=plan_cases_for_mode(2026300000)
        self.assertEqual(len(cases),6)
        for index,opponent in enumerate(('rule','mirror','rl')):
            pair=cases[index*2:index*2+2]
            self.assertEqual({c['actor_id'] for c in pair},{'zero','sac5000'})
            self.assertEqual({c['seed'] for c in pair},{2026300000+index})
            self.assertEqual({c['opponent_id'] for c in pair},{opponent})
            self.assertEqual({c['stage'] for c in pair},{'official'})
            self.assertTrue(all(c['max_steps']==18000 and c['reset_repeats']==1 and not c['coaxial_init'] for c in pair))
    def test_plan_changes_rejected(self):
        cases=plan_cases_for_mode(2026300000);cases[1]['seed']+=1
        with self.assertRaises(ValueError):validate_execution_plan(cases,2026300000)
    def test_trained_bundle_provenance(self):
        manifest=read(MODEL_MANIFEST)
        self.assertEqual(sha(MODEL),manifest['model_sha256'])
        self.assertTrue(manifest['verified_training_technical'])
        self.assertFalse(manifest['deployment_allowed'])
        self.assertEqual(manifest['observation_dimensions'],13)
    def test_guard_unchanged_and_deadlines(self):
        self.assertEqual(sha(HERE/'guard.py'),sha(POOL/'smoke_executor/v5/guard.py'))
        text=ast.unparse(ast.parse((HERE/'run_smoke.py').read_text(encoding='utf8')))
        self.assertIn('worker_start_monotonic + 90',text)
        self.assertEqual(MODE_CONTRACT['m4_final6']['total_wall_seconds'],600)
    def test_actual_frozen_actor_not_learner(self):
        tree=ast.parse((HERE/'run_smoke.py').read_text(encoding='utf8'))
        attributes=[n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)]
        self.assertIn('predict',attributes);self.assertNotIn('learn',attributes)
        self.assertIn('deterministic=True',ast.unparse(tree))
    def test_no_heading_fixture_mutation(self):
        # All planned cases disable the inherited fixture branch before physics.
        for case in plan_cases_for_mode(2026300000):
            self.assertFalse(case['coaxial_init']);self.assertIsNone(case['heading_error_deg'])

if __name__=='__main__':unittest.main()
