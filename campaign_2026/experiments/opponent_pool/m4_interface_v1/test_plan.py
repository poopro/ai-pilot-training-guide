"""Static gates only; no FDM/model import, source claim, or simulator launch."""
import ast
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock
import common as c


class PlanTests(unittest.TestCase):
    def test_exact_three_opponents_two_same_seed_resets(self):
        cases=c.plan_cases_for_mode(2026103100)
        self.assertEqual([p['opponent_id'] for p in cases],['rule','mirror','rl'])
        self.assertEqual(len({p['seed'] for p in cases}),3)
        self.assertTrue(all(p['max_steps']==300 and p['reset_repeats']==2 and not p['score_eligible'] for p in cases))

    def test_altered_plan_rejected(self):
        cases=c.plan_cases_for_mode(2026103100)
        cases[0]['max_steps']=301
        with self.assertRaises(ValueError):c.validate_execution_plan(cases,2026103100)

    def test_original_deadline_not_extendable(self):
        launch={'cases':c.plan_cases_for_mode(2026103100),'base_seed':2026103100,
                'execution_mode':'m4_interface3','mode_contract':c.MODE_CONTRACT['m4_interface3'],
                'total_wall_seconds':181,'case_wall_seconds':45}
        with self.assertRaises(ValueError):c.execution_mode_gate(launch)

    def test_executable_identity_mismatch_rejected(self):
        process=MagicMock();process.create_time.return_value=123.;process.cmdline.return_value=['a'];process.exe.return_value='other.exe'
        with patch.object(c.psutil,'Process',return_value=process):
            self.assertIsNone(c.matching({'pid':1,'creation_epoch':123.,'cmdline':['a'],'exe':'expected.exe'}))

    def test_access_denied_remains_unknown(self):
        with patch.object(c.psutil,'Process',side_effect=c.psutil.AccessDenied(1)):
            with self.assertRaises(c.psutil.AccessDenied):c.matching({'pid':1})

    def test_invalid_commands_fail(self):
        for command in ([0,0,0,2],[2,0,0,.5],[0,float('nan'),0,.5],[0,0,0]):
            with self.assertRaises(ValueError):c.legal_command(command)

    def test_guard_algorithm_byte_identical_to_completed_v5(self):
        donor=c.ROOT/'experiments'/'opponent_pool'/'smoke_executor'/'v5'/'guard.py'
        self.assertEqual((c.HERE/'guard.py').read_bytes(),donor.read_bytes())

    def test_worker_checks_guard_before_model_import(self):
        tree=ast.parse((c.HERE/'run_smoke.py').read_text(encoding='utf-8'))
        worker=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='worker')
        text=ast.get_source_segment((c.HERE/'run_smoke.py').read_text(encoding='utf-8'),worker)
        self.assertLess(text.index("guard['status']"),text.index('import m4_tactical_rl'))
        self.assertLess(text.index('source_gate'),text.index('import m4_tactical_rl'))


if __name__=='__main__':unittest.main()
