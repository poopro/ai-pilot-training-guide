"""Real subprocess supervision tests: progress accounting, failure, stall, lock."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

from overnight import ROOT, run_stage, JobLock, alive


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'overnight_verification')
        self.folder = Path(self.temp.name)
        self.job = {'job_id': 'fixture', 'job_dir': str(self.folder), 'status': 'running', 'phase': 'test',
                    'publish': False, 'stages': [], 'evaluations': [], 'new_steps': 0, 'step_budget': 100,
                    'deadline_taipei': 'fixture', 'deadline_epoch': time.time() + 20,
                    'training_deadline_epoch': time.time() + 20, 'poll_seconds': .05,
                    'save_grace_seconds': .2, 'stall_seconds': 5}

    def tearDown(self):
        self.temp.cleanup()

    def fixture(self, code):
        script = self.folder / 'fixture.py'
        script.write_text(code, encoding='utf-8')
        return [sys.executable, str(script), str(self.folder / 'learner')]

    def test_real_progress_counted_once_even_after_exit(self):
        command = self.fixture("import sys,json,time\nfrom pathlib import Path\np=Path(sys.argv[1]);p.mkdir()\n(p/'progress.json').write_text(json.dumps({'timesteps':31,'updates':2}))\ntime.sleep(.15)\n(p/'result.json').write_text(json.dumps({'timesteps':35,'status':'completed'}))\n")
        stage = run_stage(self.job, 'train_fixture', command, self.folder / 'learner', timeout=5, training=True, start=25)
        self.assertEqual(stage['exit_code'], 0)
        self.assertEqual(self.job['new_steps'], 10)
        self.assertFalse(alive(stage['process']))
        self.assertTrue((Path(stage['log_dir']) / 'exit.json').exists())

    def test_failed_child_has_exit_evidence(self):
        command = self.fixture("import sys\nprint('fixture failure',file=sys.stderr)\nsys.exit(7)\n")
        stage = run_stage(self.job, 'error_fixture', command, self.folder / 'learner', timeout=5)
        self.assertEqual(stage['exit_code'], 7)
        self.assertIn('fixture failure', (Path(stage['log_dir']) / 'stderr.log').read_text())

    def test_stall_sends_stop_then_terminates_only_owned_child(self):
        self.job['stall_seconds'] = .15
        command = self.fixture("import sys,json,time\nfrom pathlib import Path\np=Path(sys.argv[1]);p.mkdir()\n(p/'progress.json').write_text(json.dumps({'timesteps':1,'updates':0}))\ntime.sleep(20)\n")
        stage = run_stage(self.job, 'stall_fixture', command, self.folder / 'learner', timeout=5, training=True)
        self.assertEqual(stage['reason'], 'stalled')
        self.assertTrue(stage['forced_stop'])
        self.assertTrue((self.folder / 'learner/STOP').exists())
        self.assertFalse(alive(stage['process']))

    def test_duplicate_lock_rejected(self):
        path = self.folder / 'lock'
        with JobLock(path):
            with self.assertRaises(RuntimeError):
                with JobLock(path):
                    self.fail('second supervisor acquired same lock')


if __name__ == '__main__':
    unittest.main()
