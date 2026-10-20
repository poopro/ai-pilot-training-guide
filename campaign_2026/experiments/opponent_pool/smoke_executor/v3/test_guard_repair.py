"""Fault injection only: no simulator, seed reservation, or real workload."""
import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import common
import guard


class FakeProcess:
    def __init__(self, pid, records, processes, ancestors=()):
        self.pid=pid;self.records=records;self.processes=processes;self.ancestors=ancestors
        self.alive=True;self.terminated=False;self.enumerations=0;self.race_after=None
    def children(self, recursive=True):
        self.enumerations+=1
        if self.race_after and self.enumerations>=self.race_after:raise common.psutil.NoSuchProcess(self.pid)
        return [p for p in self.processes.values() if self in p.ancestors and p.alive]
    def parents(self):return list(self.ancestors)
    def terminate(self):self.terminated=True;self.alive=False
    def kill(self):self.terminate()
    def wait(self,timeout):return 0


class GuardRepair(unittest.TestCase):
    def exercise(self, reason='STOP', permanent_failure=False, transient_failure=False, race=False, unknown=False, forged=False, worker_deadline=False, initial_failure=False, late_start=False):
        records={p:{'pid':p,'creation_epoch':float(p),'cmdline':['owned' if p<999 else 'unrelated']} for p in (100,101,102,999)}
        processes={}
        root=FakeProcess(100,records,processes);processes[100]=root
        child=FakeProcess(101,records,processes,(root,));processes[101]=child
        grand=FakeProcess(102,records,processes,(child,root));processes[102]=grand
        unrelated=FakeProcess(999,records,processes);processes[999]=unrelated
        if race:root.race_after=2
        clock=[29.9 if late_start else 0.0];publications=[0];stream=io.StringIO()
        with tempfile.TemporaryDirectory(dir=common.HERE) as folder:
            out=Path(folder)
            common.write(out/'launch.json',{'supervisor':records[100],'total_wall_seconds':30,
                'reservation_start_monotonic':0,'deadline_monotonic':30,'reservation_start_epoch':100,'deadline_epoch':130})
            if forged or worker_deadline:
                common.write(out/'active_worker.json',{'identity':records[999 if forged else 101],'deadline_epoch':100,'deadline_monotonic':0})
            def get_identity(pid=None):return records[pid] if pid is not None else {'pid':500,'creation_epoch':1,'cmdline':['guard']}
            def matching(rec):
                if unknown and rec==records[100]:raise common.psutil.AccessDenied(100)
                p=processes.get(rec['pid'])
                return p if p and p.alive and records[rec['pid']]==rec else None
            def save(path,value):
                publications[0]+=1
                if initial_failure or (publications[0]>1 and (permanent_failure or (transient_failure and publications[0]==2))):raise PermissionError('injected WinError 5')
                common.write(path,value)
            def stopped(_):return reason=='STOP' and (clock[0]>.1 or unknown)
            def sleeping(seconds):
                clock[0]+=seconds
                if worker_deadline and not child.alive:common.write(out/'supervisor_exit.json',{'exit':0})
            with patch.object(guard,'write',side_effect=save),patch.object(guard,'matching',side_effect=matching),patch.object(guard,'identity',side_effect=get_identity),patch.object(guard,'stop',side_effect=stopped),patch.object(guard.time,'monotonic',side_effect=lambda:clock[0]),patch.object(guard.time,'time',side_effect=lambda:100-clock[0]*100),patch.object(guard.time,'sleep',side_effect=sleeping),contextlib.redirect_stdout(stream),contextlib.redirect_stderr(io.StringIO()):
                code=guard.run_guard(out)
            final=json.loads(stream.getvalue().splitlines()[-1])
        return code,final,processes,publications[0]

    def test_atomic_replace_transient_retry_preserves_bytes(self):
        actual=common.os.replace
        with tempfile.TemporaryDirectory(dir=common.HERE) as folder:
            path=Path(folder)/'receipt.json';common.write(path,{'old':True});calls=[]
            def replacement(src,dst):
                calls.append((src,dst))
                if len(calls)<4:raise PermissionError('sharing violation')
                actual(src,dst)
            with patch.object(common.os,'replace',side_effect=replacement),patch.object(common.time,'sleep') as sleep:
                common.write(path,{'new':True})
            self.assertEqual(len(calls),4);self.assertEqual(len({str(x[0]) for x in calls}),1)
            self.assertEqual(common.read(path),{'new':True});self.assertEqual(sleep.call_count,3)

    def test_atomic_replace_permanent_failure_bounded_eight(self):
        with tempfile.TemporaryDirectory(dir=common.HERE) as folder:
            path=Path(folder)/'receipt.json';common.write(path,{'old':True})
            with patch.object(common.os,'replace',side_effect=PermissionError('sharing violation')) as replacement,patch.object(common.time,'sleep') as sleep:
                with self.assertRaises(PermissionError):common.write(path,{'new':True})
            self.assertEqual(replacement.call_count,8);self.assertEqual(sleep.call_count,7)
            self.assertLessEqual(sum(x.args[0] for x in sleep.call_args_list),.4)
            self.assertEqual(common.read(path),{'old':True});self.assertEqual(list(Path(folder).glob('*.tmp_*')),[])

    def test_permanent_publication_failure_still_stop_and_descendant_cleanup(self):
        code,final,processes,count=self.exercise(permanent_failure=True)
        self.assertEqual(code,3);self.assertFalse(final['receipt_saved']);self.assertGreaterEqual(count,3)
        self.assertEqual(final['guard_final_receipt']['reason'],'STOP')
        self.assertTrue(all(processes[p].terminated for p in (100,101,102)));self.assertFalse(processes[999].terminated)

    def test_permanent_publication_failure_still_original_deadline(self):
        code,final,processes,_=self.exercise(reason='deadline',permanent_failure=True)
        self.assertEqual(code,3);self.assertEqual(final['guard_final_receipt']['reason'],'deadline')
        self.assertLess(final['guard_final_receipt']['wall_seconds'],30.3)
        self.assertTrue(all(processes[p].terminated for p in (100,101,102)))

    def test_transient_publication_recovers_and_saves_error_evidence(self):
        code,final,_,_=self.exercise(transient_failure=True)
        self.assertEqual(code,0);self.assertTrue(final['receipt_saved'])
        self.assertEqual(final['guard_final_receipt']['publication_error_count'],1)

    def test_initial_publication_failure_still_cleans_owned_tree(self):
        code,final,processes,_=self.exercise(initial_failure=True)
        self.assertEqual(code,3);self.assertEqual(final['guard_final_receipt']['reason'],'initial_receipt_unavailable')
        self.assertTrue(all(processes[p].terminated for p in (100,101,102)));self.assertFalse(processes[999].terminated)

    def test_late_guard_does_not_restart_reserved_clock(self):
        code,final,_,_=self.exercise(reason='deadline',late_start=True)
        self.assertEqual(code,0);self.assertEqual(final['guard_final_receipt']['reason'],'deadline')
        self.assertLess(final['guard_final_receipt']['wall_seconds'],.3)

    def test_parent_exit_enumeration_race_still_cleans_known_children(self):
        code,final,processes,_=self.exercise(reason='race',race=True)
        self.assertEqual(code,0);self.assertEqual(final['guard_final_receipt']['reason'],'supervisor_missing')
        self.assertTrue(all(processes[p].terminated for p in (100,101,102)))

    def test_access_denied_remains_unknown_and_cannot_pass(self):
        code,final,processes,_=self.exercise(unknown=True)
        self.assertEqual(code,2);self.assertTrue(final['guard_final_receipt']['unknown'])
        self.assertFalse(processes[100].terminated)

    def test_forged_active_receipt_never_stops_unowned_process(self):
        code,final,processes,_=self.exercise(reason='none',forged=True)
        self.assertEqual(code,2);self.assertEqual(final['guard_final_receipt']['reason'],'worker_identity_unknown')
        self.assertFalse(processes[999].terminated)

    def test_worker_deadline_cleans_its_owned_descendants(self):
        code,final,processes,_=self.exercise(reason='none',worker_deadline=True,transient_failure=True)
        self.assertEqual(code,0);self.assertTrue(processes[101].terminated);self.assertTrue(processes[102].terminated)
        stopped=final['guard_final_receipt']['stopped']
        self.assertEqual({x['identity']['pid'] for x in stopped if x['reason']=='case_deadline'},{101,102})

    def test_identity_pid_reuse_or_access_denied_never_matches(self):
        from unittest.mock import Mock
        fake=Mock();fake.create_time.return_value=999;fake.cmdline.return_value=['owned']
        with patch.object(common.psutil,'Process',return_value=fake):
            self.assertIsNone(common.matching({'pid':100,'creation_epoch':100,'cmdline':['owned']}))
        with patch.object(common.psutil,'Process',side_effect=common.psutil.AccessDenied(100)):
            with self.assertRaises(common.psutil.AccessDenied):common.matching({'pid':100,'creation_epoch':100,'cmdline':['owned']})

    def test_launcher_repeated_timeouts_preserve_unknown_actual_exit(self):
        import launch_smoke
        from types import SimpleNamespace
        from unittest.mock import Mock
        supervisor=Mock(pid=100);supervisor.wait.side_effect=subprocess.TimeoutExpired('supervisor',1);supervisor.poll.return_value=None
        watchdog=Mock(pid=500);watchdog.wait.side_effect=subprocess.TimeoutExpired('guard',1)
        with tempfile.TemporaryDirectory(dir=common.HERE) as folder:
            root=Path(folder);ledger=root/'budget.json';common.write(ledger,{'items':[{'id':'test'}]})
            common.write(root/'seed_registry.json',{'trials':{'test':{}}})
            spec={'trial_id':'test','ledger':str(ledger),'deadline_monotonic':common.time.monotonic()+30,'total_wall_seconds':30}
            args=SimpleNamespace(check_only=False,seed=2026102500,remaining_percent=50,usage_epoch=common.time.time(),diagnostic_case_index=0)
            with patch.object(launch_smoke,'HERE',root),patch.object(launch_smoke,'ROOT',root),patch.object(launch_smoke,'JobLock',return_value=contextlib.nullcontext()),patch.object(launch_smoke,'reserve',return_value=spec),patch.object(launch_smoke,'identity',side_effect=lambda pid=None:{'pid':pid or 1,'creation_epoch':1,'cmdline':['mock']}),patch.object(launch_smoke.subprocess,'Popen',side_effect=[supervisor,watchdog]),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(launch_smoke.main(args),2)
            out=next(root.glob('run_*'));receipt=common.read(out/'launcher_receipt.json')
            self.assertIsNone(receipt['actual_parent_exit_code']);self.assertIsNone(receipt['actual_guard_exit_code'])
            self.assertTrue(common.read(out/'supervisor_exit.json')['exit_observation_unknown'])
            self.assertEqual(supervisor.wait.call_count,2);self.assertEqual(watchdog.wait.call_count,2)


if __name__=='__main__':unittest.main(verbosity=2)
