"""No FDM/model inference: plan/AST, actual event semantics and read-only metadata."""
import ast,json,unittest,hashlib
from pathlib import Path
from event_tags import classify_event,EVENTS
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

class GridTests(unittest.TestCase):
    def test_plan_exact_grid_and_alternation(self):
        tree=ast.parse((HERE/'common.py').read_text(encoding='utf8'))
        body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('plan_cases_for_mode','validate_execution_plan')]
        scope={};exec(compile(ast.Module(body=body,type_ignores=[]),'plan-only','exec'),scope)
        plan=scope['plan_cases_for_mode'](2026300300)
        self.assertEqual(len(plan),18);self.assertEqual({c['seed'] for c in plan},set(range(2026300300,2026300309)))
        self.assertEqual({(c['opponent_id'],c['distance_ft']) for c in plan},{(o,d) for o in ('rule','mirror','rl') for d in (3000,6000,9000)})
        for i in range(9):
            pair=plan[2*i:2*i+2]
            self.assertEqual([c['actor_id'] for c in pair],['sac5000','transfer10000'] if i%2==0 else ['transfer10000','sac5000'])
            self.assertEqual(pair[0]['seed'],pair[1]['seed']);self.assertFalse(any(c['coaxial_init'] for c in pair))
        self.assertEqual(scope['validate_execution_plan'](plan,2026300300),'m4_grid18')
        plan[0]['distance_ft']=6001
        with self.assertRaises(ValueError):scope['validate_execution_plan'](plan,2026300300)
    def test_worker_guard_identical(self):
        old=HERE.parent/'m4_transfer_eval_v1'
        for name in ('run_smoke.py','guard.py'):
            self.assertEqual((HERE/name).read_bytes(),(old/name).read_bytes())
    def test_deadline_and_judge_source_ast(self):
        for f in HERE.glob('*.py'):ast.parse(f.read_text(encoding='utf8'))
        text=(HERE/'common.py').read_text(encoding='utf8')
        self.assertIn("'total_wall_seconds':900",text);self.assertIn("'case_wall_seconds':90",text)
        self.assertIn("launch.get('total_wall_seconds')!=900",text)
        v=(HERE/'verify_final.py').read_text(encoding='utf8')
        self.assertIn('len(groups)==9',v);self.assertIn("'complete_worker_count':18,'paired_openings':9",v)
        self.assertNotIn("judge_event']=='kill'",v);self.assertIn("**classify_event(data['episode']['judge_event'])",v)
        self.assertNotIn('np.zeros(',v)
    def test_exact_actual_event_tags(self):
        expected={'blue_kill':(1,0,0,0),'red_kill':(0,1,0,0),'simultaneous_kill':(1,1,0,0),
                  'blue_crash':(0,0,1,0),'red_crash':(0,0,0,1),'mutual_crash':(0,0,1,1),
                  'collision':(0,0,0,0),'timeout':(0,0,0,0),'ongoing':(0,0,0,0)}
        self.assertEqual(set(expected),EVENTS)
        for event,values in expected.items():
            with self.subTest(event=event):
                stats=classify_event(event)
                self.assertEqual(tuple(stats[k] for k in ('kill','death','own_crash','opponent_crash')),values)
                self.assertEqual(stats['actual_judge_event'],event)
        with self.assertRaises(ValueError):classify_event('kill')
    def test_winner_cannot_imply_kill(self):
        # Actual blue point wins at timeout/collision and red-crash wins remain zero kills.
        for event in ('timeout','collision','red_crash','mutual_crash'):
            self.assertEqual(classify_event(event)['kill'],0)
    def test_seed_registry_readonly(self):
        import sys
        sys.path.insert(0,str(HERE.parent));sys.path.insert(0,str(ROOT))
        import prepare_smoke
        registry=json.loads((ROOT/'seed_registry.json').read_text(encoding='utf8'))
        status=prepare_smoke.seed_status(registry,[{'seed':s} for s in range(2026300300,2026300309)])
        self.assertTrue(status['fresh_relative_to_registry']);self.assertEqual(len(status['requested']),9)
    def test_frozen_model_metadata_unchanged(self):
        old=json.loads((HERE.parent/'m4_transfer_eval_v1/MODEL_FREEZE.json').read_text(encoding='utf8'))
        new=json.loads((HERE/'MODEL_FREEZE.json').read_text(encoding='utf8'))
        self.assertEqual(old['sac5000'],new['sac5000']);self.assertEqual(old['transfer10000'],new['transfer10000'])

if __name__=='__main__':unittest.main()
