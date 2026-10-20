import ast
import unittest
from unittest.mock import patch
import common as c


class AlignedFixtureTests(unittest.TestCase):
    def test_only_one_new_seed_and_explicit_nonofficial_opening(self):
        cases=c.plan_cases_for_mode(2026101610)
        self.assertEqual(len(cases),1)
        self.assertTrue(cases[0]['coaxial_init'])
        self.assertTrue(cases[0]['expect_nonzero'])
        self.assertEqual(cases[0]['stage'],'rear')
        self.assertFalse(cases[0]['score_eligible'])
        self.assertEqual(cases[0]['max_steps'],300)

    def test_changed_initial_fixture_contract_rejected(self):
        cases=c.plan_cases_for_mode(2026101610);cases[0]['coaxial_init']=False
        with self.assertRaises(ValueError):c.validate_execution_plan(cases,2026101610)

    def test_ninety_seconds_cannot_be_extended(self):
        plan={'cases':c.plan_cases_for_mode(2026101610),'base_seed':2026101610,
              'mode_contract':c.MODE_CONTRACT['m4_aligned1'],'execution_mode':'m4_aligned1',
              'total_wall_seconds':91,'case_wall_seconds':45}
        with self.assertRaises(ValueError):c.execution_mode_gate(plan)

    def test_actual_judge_attack_counter_is_never_written_by_fixture(self):
        tree=ast.parse((c.HERE/'run_smoke.py').read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node,(ast.Assign,ast.AugAssign)):
                targets=node.targets if isinstance(node,ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target,ast.Attribute):
                        self.assertNotIn(target.attr,('attack','blue_frames','red_frames','ticks'))

    def test_exact_guard_algorithm_reused_not_relaxed(self):
        self.assertEqual((c.HERE/'guard.py').read_bytes(),(c.ROOT/'experiments'/'opponent_pool'/'smoke_executor'/'v5'/'guard.py').read_bytes())


if __name__=='__main__':unittest.main()
