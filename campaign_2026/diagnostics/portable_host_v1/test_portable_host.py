"""Static and receipt/identity boundary tests. No Host/FDM launch."""
from pathlib import Path
import copy
import json
import os
import sys
import tempfile
import subprocess
import time
import unittest
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parent))
import portable_host as portable


class PortableHostTests(unittest.TestCase):
    def test_command_uses_frozen_package_python_and_player(self):
        profile = {"package": str(portable.ROOT / "deployment" / "repair_guide_portable_20261012"),
                   "host_dir": "E:/host"}
        command = portable.commands(profile, 720)
        self.assertEqual(command["prefix"][1:4], ["-I", "-S", "-B"])
        self.assertNotIn("anaconda3", " ".join(command["player"]))
        self.assertIn("--max-seconds", command["player"])
        self.assertEqual(command["player"][-1], "720")

    def test_clock_rollback_cannot_extend_deadline(self):
        with patch.object(portable.time, "time", return_value=1), patch.object(portable.time, "monotonic", return_value=1000):
            self.assertTrue(portable.deadline_expired({"deadline_epoch": 999999, "deadline_monotonic": 999}))

    def test_transient_winerror5_atomic_retry_is_bounded(self):
        with tempfile.TemporaryDirectory(dir=portable.HERE) as directory:
            target = Path(directory) / "receipt.json"
            original = portable.os.replace
            calls = []
            def replace(source, dest):
                calls.append(1)
                if len(calls) < 3: raise PermissionError(5, "sharing violation")
                return original(source, dest)
            with patch.object(portable.os, "replace", side_effect=replace), patch.object(portable.time, "sleep"):
                portable.atomic(target, {"test": "static_not_host"})
            self.assertEqual(len(calls), 3)
            self.assertEqual(portable.read(target)["test"], "static_not_host")

    def test_persistent_write_failure_is_reported_without_fake_success(self):
        errors = []
        with patch.object(portable, "atomic", side_effect=PermissionError(5, "sharing violation")):
            self.assertFalse(portable.publish_best_effort(Path("unused"), {}, errors))
        self.assertEqual(len(errors), 1)

    def test_reused_pid_is_not_terminated(self):
        process = MagicMock()
        process.create_time.return_value = 100
        with patch.object(portable.psutil, "Process", return_value=process):
            live, state = portable.exact_live({"pid": 123, "create_time": 99, "command": [], "exe": "unused"})
        self.assertIsNone(live)
        self.assertEqual(state, "pid_reused")
        process.terminate.assert_not_called()

    def test_access_denied_is_unknown(self):
        with patch.object(portable.psutil, "Process", side_effect=portable.psutil.AccessDenied(123)):
            live, state = portable.exact_live({"pid": 123})
        self.assertIsNone(live)
        self.assertEqual(state, "unknown_access_denied")

    def test_absent_pid_does_not_invent_exit_zero(self):
        tracked = {"mock": {"role": "host_root", "identity": {"pid": 123}}}
        with patch.object(portable, "exact_live", return_value=(None, "absent")):
            result = portable.cleanup(tracked, {})
        self.assertNotIn("actual_exit_code", result["results"][0])

    def test_legacy_six_reports_are_never_imported(self):
        with tempfile.TemporaryDirectory(dir=portable.HERE) as directory:
            paths = []
            for index in range(6):
                path = Path(directory) / f"legacy_{index}.json"
                portable.atomic(path, {"profile": "legacy_repair_guide", "eligible_for_six_round_fixed_source_gate": True})
                paths.append(path)
            result = portable.aggregate(paths)
        self.assertEqual(result["verified_unique_packaged_rounds"], 0)
        self.assertFalse(result["packaged_six_round_gate_complete"])
        self.assertFalse(result["eligible_for_old_six_round_gate"])

    def test_self_check_and_host_are_forbidden_during_plain_preflight(self):
        with patch.object(portable.subprocess, "Popen", side_effect=AssertionError("No launch in preflight")), \
                patch.object(portable.subprocess, "run", side_effect=AssertionError("No launch in preflight")):
            report = portable.preflight(720, remaining_percent=0)
        self.assertEqual(report["new_host_rounds"], 0)
        self.assertEqual(report["new_fdm_ticks"], 0)
        self.assertFalse(report["portable_package_host_completed"])
        self.assertTrue(any("quota" in warning for warning in report["warnings"]))

    def test_missing_watchdog_handle_receipt_cannot_pass_aggregate(self):
        with tempfile.TemporaryDirectory(dir=portable.HERE) as directory:
            self.assertFalse(portable.watchdog_observation_valid(Path(directory), "mock_profile"))

    def test_absent_watchdog_cannot_be_attached_or_assumed_exit_zero(self):
        with patch.object(portable, "exact_live", return_value=(None, "absent")):
            with self.assertRaisesRegex(RuntimeError, "absent/unknown"):
                portable.VerifiedWindowsWaitHandle({"pid": 123})

    def test_actual_windows_wait_observes_real_nonzero_exit_without_host(self):
        command = [sys.executable, "-I", "-S", "-B", "-c", "import time; time.sleep(1); raise SystemExit(7)"]
        child = subprocess.Popen(command, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            expected = portable.identity(portable.psutil.Process(child.pid))
            receipt = portable.wait_verified_process(expected, time.monotonic() + 10)
            self.assertEqual(receipt["actual_exit_code"], 7)
            self.assertTrue(receipt["wait_handle_acquired"])
            self.assertEqual(child.wait(timeout=3), 7)
        finally:
            if child.poll() is None: child.terminate(); child.wait(timeout=3)


if __name__ == "__main__":
    unittest.main()
