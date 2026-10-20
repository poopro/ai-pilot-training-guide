"""Lifecycle checks without launching a trainer or loading PyTorch."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

spec = importlib.util.spec_from_file_location('campaign_runner', Path(__file__).parents[1] / 'runner.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class LifecycleTests(unittest.TestCase):
    def test_pid_reuse_and_command_change_are_not_owned(self):
        record = {'pid': 42, 'creation_epoch': 100., 'cmdline': ['python', 'train.py']}
        proc = Mock()
        proc.is_running.return_value = True
        proc.create_time.return_value = 101.
        proc.cmdline.return_value = record['cmdline']
        with patch.object(runner.psutil, 'Process', return_value=proc):
            self.assertFalse(runner.owned_alive(record))
            proc.create_time.return_value = 100.
            proc.cmdline.return_value = ['python', 'unrelated.py']
            self.assertFalse(runner.owned_alive(record))
            proc.cmdline.return_value = record['cmdline']
            self.assertTrue(runner.owned_alive(record))

    def test_refuses_to_terminate_reused_pid(self):
        with patch.object(runner, 'owned_alive', return_value=False), patch.object(runner.psutil, 'Process') as process:
            self.assertFalse(runner.terminate_owned({'pid': 42}))
            process.assert_not_called()

    def test_budget_counts_once_and_includes_lost_work(self):
        job = {'new_decisions': 0}
        stage = {'start_decisions': 24000, 'requested_decisions': 50000, 'counted_decisions': 0}
        runner.add_observed_steps(job, stage, 34000)
        runner.add_observed_steps(job, stage, 34000)
        runner.add_observed_steps(job, stage, 32000)  # older saved checkpoint
        self.assertEqual(job['new_decisions'], 10000)
        runner.add_observed_steps(job, stage, 100000)
        self.assertEqual(job['new_decisions'], 50000)

    def test_deadline_and_cooperative_stop(self):
        with tempfile.TemporaryDirectory() as temporary:
            job = {'job_dir': temporary, 'training_deadline_epoch': 100., 'deadline_epoch': 200., 'stall_seconds': 600}
            record = {'training': True}
            with patch.object(runner.time, 'time', return_value=101.), patch.object(runner, 'resources', return_value={'available_ram_gb': 4., 'free_disk_gb': 20.}):
                self.assertEqual(runner.should_stop(job, record, {}, 1., 1., 1., 1000.), 'time_limit')
                record['training'] = False
                self.assertIsNone(runner.should_stop(job, record, {}, 1., 1., 1., 1000.))
                (Path(temporary) / 'STOP').write_text('stop')
                self.assertEqual(runner.should_stop(job, record, {}, 1., 1., 1., 1000.), 'stopped_by_user')

    def test_status_stop_writes_only_job_stop(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'job'
            folder.mkdir()
            job = {'job_dir': str(folder), 'status': 'running', 'phase': 'train_01',
                   'new_decisions': 100, 'decision_budget': 150000, 'supervisor': {'pid': 42}, 'child': None}
            pointer = Path(temporary) / 'pointer.json'
            runner.atomic_json(pointer, job)
            with patch.object(runner, 'POINTER', pointer), patch.object(runner, 'owned_alive', return_value=True), patch('builtins.print'):
                runner.status_or_stop('status')
                self.assertFalse((folder / 'STOP').exists())
                runner.status_or_stop('stop')
                self.assertTrue((folder / 'STOP').exists())

    def test_source_drift_refuses_continuation(self):
        with patch.object(runner, 'source_hashes', return_value={'a': 'changed'}):
            with self.assertRaises(RuntimeError):
                runner.check_sources({'source_sha256': {'a': 'original'}})

    def test_futility_needs_two_complete_paired_regressions(self):
        poor = {'status': 'completed', 'summary': {'guide': {'kills': 3, 'mean_attack_seconds': 1.},
                'candidate': {'kills': 1, 'mean_attack_seconds': .2}}}
        self.assertFalse(runner.futile([poor]))
        self.assertTrue(runner.futile([poor, poor]))
        partial = {**poor, 'status': 'partial'}
        self.assertFalse(runner.futile([poor, partial]))
        tied = {'status': 'completed', 'summary': {'guide': {'kills': 1, 'mean_attack_seconds': 1.},
                'candidate': {'kills': 1, 'mean_attack_seconds': .2}}}
        self.assertFalse(runner.futile([poor, tied]))

    def test_known_trainers_are_detected(self):
        self.assertTrue(runner.is_trainer_command(['python', r'E:\ai_pilot\autopilot\combat_fix\train.py']))
        self.assertTrue(runner.is_trainer_command(['python', r'E:\ai_pilot\campaign_2026\repair_v1\train.py']))
        self.assertTrue(runner.is_trainer_command(['python', r'E:\ai_pilot\autopilot\opponent_lab\train_opponents.py']))
        self.assertFalse(runner.is_trainer_command(['python', r'E:\ai_pilot\campaign_2026\benchmark.py']))


if __name__ == '__main__':
    unittest.main()
