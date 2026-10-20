import ast,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
import guard
from common import *

class BoundedRead(unittest.TestCase):
    def test_transient_read_recovers_without_fake_identity(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);(out/'active_worker.json').write_text('{}')
            expected={'identity':{'pid':123,'creation_epoch':1},'deadline_monotonic':9}
            with patch.object(guard,'read',side_effect=[PermissionError(13,'test'),PermissionError(13,'test'),expected]) as reader:
                self.assertEqual(guard.read_active_receipt(out,time.monotonic()+1),expected)
                self.assertEqual(reader.call_count,3)
    def test_persistent_error_has_bounded_wait(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);(out/'active_worker.json').write_text('{}')
            began=time.monotonic()
            with patch.object(guard,'read',side_effect=PermissionError(13,'test')):
                with self.assertRaises(PermissionError):guard.read_active_receipt(out,began+1)
            self.assertLess(time.monotonic()-began,.5)
    def test_original_deadline_not_extended(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);(out/'active_worker.json').write_text('{}')
            began=time.monotonic()
            with patch.object(guard,'read',side_effect=PermissionError(13,'test')):
                with self.assertRaises(PermissionError):guard.read_active_receipt(out,began-.1)
            self.assertLess(time.monotonic()-began,.1)
    def test_stop_not_swallowed(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);(out/'active_worker.json').write_text('{}');(out/'STOP').write_text('test')
            with patch.object(guard,'read',side_effect=PermissionError(13,'test')) as reader:
                with self.assertRaises(PermissionError):guard.read_active_receipt(out,time.monotonic()+1)
                self.assertEqual(reader.call_count,1)
    def test_identity_unknown_not_retried(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);(out/'active_worker.json').write_text('{}')
            with patch.object(guard,'read',side_effect=psutil.AccessDenied(123)) as reader:
                with self.assertRaises(psutil.AccessDenied):guard.read_active_receipt(out,time.monotonic()+1)
                self.assertEqual(reader.call_count,1)
    def test_only_guard_change_is_read_helper(self):
        old=ast.parse((POOL/'smoke_executor/v5/guard.py').read_text(encoding='utf8'))
        new=ast.parse((HERE/'guard.py').read_text(encoding='utf8'))
        new.body=[n for n in new.body if not(isinstance(n,ast.FunctionDef) and n.name=='read_active_receipt')]
        class Restore(ast.NodeTransformer):
            def visit_Assign(self,node):
                if isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='read_active_receipt':
                    node.value=ast.parse("read(out / 'active_worker.json') if (out / 'active_worker.json').exists() else None",mode='eval').body
                return node
        self.assertEqual(ast.dump(old,include_attributes=False),ast.dump(Restore().visit(new),include_attributes=False))
    def test_only_new_RL_pair(self):
        cases=plan_cases_for_mode(2026300010)
        self.assertEqual(len(cases),2);self.assertEqual({x['actor_id'] for x in cases},{'zero','sac5000'})
        self.assertEqual({x['opponent_id'] for x in cases},{'rl'});self.assertEqual({x['seed'] for x in cases},{2026300010})
        self.assertEqual(MODE_CONTRACT['m4_recovery2']['total_wall_seconds'],240)

if __name__=='__main__':unittest.main()
