"""AST and metadata only. Never imports torch/SAC/FDM or reads model zip."""
import ast,json,unittest,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

class StaticTests(unittest.TestCase):
    def test_all_sources_parse(self):
        for f in HERE.glob('*.py'):ast.parse(f.read_text(encoding='utf8'))
    def test_six_case_plan(self):
        tree=ast.parse((HERE/'common.py').read_text(encoding='utf8'))
        functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('plan_cases_for_mode','validate_execution_plan')]
        namespace={};exec(compile(ast.Module(body=functions,type_ignores=[]),'plan-only','exec'),namespace)
        plan=namespace['plan_cases_for_mode'](2026300200)
        self.assertEqual(len(plan),6);self.assertEqual(len({c['seed'] for c in plan}),3)
        for i,(opponent,distance) in enumerate((('rule',3000),('mirror',6000),('rl',9000))):
            pair=plan[2*i:2*i+2]
            self.assertEqual({c['opponent_id'] for c in pair},{opponent});self.assertEqual({c['distance_ft'] for c in pair},{distance})
            self.assertEqual([c['actor_id'] for c in pair],['sac5000','transfer10000'] if i%2==0 else ['transfer10000','sac5000'])
        self.assertEqual(namespace['validate_execution_plan'](plan,2026300200),'m4_transfer6')
        plan[0]['actor_id']='zero'
        with self.assertRaises(ValueError):namespace['validate_execution_plan'](plan,2026300200)
    def test_seeds_unclaimed_read_only(self):
        # Registry's known numeric seed positions; do not claim complete historical novelty.
        registry=json.loads((ROOT/'seed_registry.json').read_text(encoding='utf8'))
        found=set()
        def walk(value,key=''):
            if isinstance(value,dict):
                for k,v in value.items():
                    if k in ('observed_seeds','seeds') and isinstance(v,dict):found.update(int(s) for s in v if str(s).isdigit())
                    walk(v,k)
            elif isinstance(value,list):
                for v in value:walk(v,key)
            elif isinstance(value,int) and ('seed' in key):found.add(value)
        walk(registry)
        self.assertFalse(set(range(2026300200,2026300203))&found)
    def test_only_intended_worker_changes(self):
        old=(HERE.parent/'m4_rule_mirror_eval_v1/run_smoke.py').read_text(encoding='utf8')
        expected=old.replace("actor_policy=m.SAC.load(MODEL,device='cpu') if case['actor_id']=='sac5000' else None","actor_policy=m.SAC.load(model_for_actor(case['actor_id']),device='cpu')").replace("distance_ft=6000,max_steps","distance_ft=case['distance_ft'],max_steps").replace("action=actor_policy.predict(before,deterministic=True)[0] if actor_policy is not None else np.zeros(3,dtype=np.float32)","action=actor_policy.predict(before,deterministic=True)[0]")
        self.assertEqual(ast.dump(ast.parse(expected)),ast.dump(ast.parse((HERE/'run_smoke.py').read_text(encoding='utf8'))))
    def test_guard_identical_and_bounds(self):
        self.assertEqual((HERE/'guard.py').read_bytes(),(HERE.parent/'m4_rule_mirror_eval_v1/guard.py').read_bytes())
        common=(HERE/'common.py').read_text(encoding='utf8')
        self.assertIn("'total_wall_seconds':360",common);self.assertIn("'case_wall_seconds':90",common)
        self.assertIn('RAM 2GiB, disk 10GiB',common);self.assertIn('source_gate()',common)
    def test_candidate_not_read_before_freeze(self):
        if (HERE/'MODEL_FREEZE.json').exists():
            self.assertTrue(json.loads((HERE/'MODEL_FREEZE.json').read_text(encoding='utf8'))['candidate_finalized'])
        tree=ast.parse((HERE/'common.py').read_text(encoding='utf8'))
        top=ast.unparse(ast.Module(body=[n for n in tree.body if not isinstance(n,(ast.FunctionDef,ast.ClassDef))],type_ignores=[]))
        self.assertNotIn('MODEL_FREEZE',top);self.assertNotIn('SAC.load',top)
        gate=ast.unparse(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='frozen_model_gate'))
        self.assertIn("verified_actor_transfer_training",gate);self.assertIn('actual_worker_exit_code',gate)
        self.assertIn('actual_parent_exit_code',gate);self.assertIn('actual_guard_exit_code',gate)
    def test_verifier_no_zero_and_three_pairs(self):
        text=(HERE/'verify_final.py').read_text(encoding='utf8')
        self.assertNotIn('np.zeros(',text);self.assertIn('len(groups)==3',text)
        self.assertIn("'complete_worker_count':6,'paired_openings':3",text)
        self.assertIn("models[case['actor_id']].predict(obs,deterministic=True)",text)
        self.assertIn('common_score_margin',text);self.assertIn('same_initial_blue_red_SHA',text)

if __name__=='__main__':unittest.main()
