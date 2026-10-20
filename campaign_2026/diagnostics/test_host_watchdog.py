import subprocess
import sys
import time
import unittest

import psutil

import host_watchdog as watchdog


class WatchdogIdentityTests(unittest.TestCase):
    def spawn_sleep(self):
        process = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)"],
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        identity = watchdog.process_identity(psutil.Process(process.pid))
        return process, identity

    def test_exact_identity_is_terminated(self):
        process, identity = self.spawn_sleep()
        result = watchdog.cleanup({"root": {"role": "mock_owned_root", "identity": identity}}, "unit_test")
        self.assertEqual(result["results"][0]["after"], "absent")
        self.assertIsNotNone(process.poll())

    def test_changed_command_is_not_terminated(self):
        process, identity = self.spawn_sleep()
        try:
            identity["command"] = identity["command"] + ["not-the-real-command"]
            result = watchdog.cleanup({"root": {"role": "mock_owned_root", "identity": identity}}, "unit_test")
            self.assertEqual(result["results"][0]["before"], "command_changed")
            self.assertIsNone(process.poll())
        finally:
            process.terminate()
            process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
