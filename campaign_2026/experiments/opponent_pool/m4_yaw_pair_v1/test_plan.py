from collections import defaultdict
import ast
import unittest
import common as c


class PairedPlanTests(unittest.TestCase):
    def test_four_workers_two_paired_seeds_and_both_signs(self):
        cases=c.plan_cases_for_mode(2026101620)
        self.assertEqual(len(cases),4)
        self.assertEqual({p['seed'] for p in cases},{2026101620,2026101621})
        pairs=defaultdict(list)
        for item in cases:pairs[item['pair_key']].append(item)
        self.assertEqual(len(pairs),2)
        for pair in pairs.values():
            self.assertEqual({p['actor_id'] for p in pair},{'v3_unsigned','v4_signed'})
            self.assertEqual(len({(p['seed'],p['heading_error_deg'],p['stage']) for p in pair}),1)
        self.assertEqual({p['heading_error_deg'] for p in cases},{-1.2,1.2})

    def test_changed_actor_or_seed_cannot_be_reserved(self):
        for key,value in [('actor_source','other'),('seed',123)]:
            cases=c.plan_cases_for_mode(2026101620);cases[0][key]=value
            with self.assertRaises(ValueError):c.validate_execution_plan(cases,2026101620)

    def test_original_deadline_is_fixed(self):
        launch={'cases':c.plan_cases_for_mode(2026101620),'base_seed':2026101620,
                'execution_mode':'m4_yaw4','mode_contract':c.MODE_CONTRACT['m4_yaw4'],
                'total_wall_seconds':241,'case_wall_seconds':45}
        with self.assertRaises(ValueError):c.execution_mode_gate(launch)

    def test_no_attack_counter_injection(self):
        tree=ast.parse((c.HERE/'run_smoke.py').read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node,(ast.Assign,ast.AugAssign)):
                targets=node.targets if isinstance(node,ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target,ast.Attribute):self.assertNotIn(target.attr,('attack','blue_frames','red_frames','ticks'))

    def test_guard_algorithm_same_as_completed_v5(self):
        self.assertEqual((c.HERE/'guard.py').read_bytes(),(c.ROOT/'experiments'/'opponent_pool'/'smoke_executor'/'v5'/'guard.py').read_bytes())


if __name__=='__main__':unittest.main()
