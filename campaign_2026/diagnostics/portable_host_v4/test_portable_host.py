"""Static and receipt/identity boundary tests. No Host/FDM launch."""
from pathlib import Path
import copy
import json
import os
import sys
import tempfile
import subprocess
import time
import csv
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


class OwnedCacheTreeTests(unittest.TestCase):
    def fixture(self, folder):
        original = folder / "original" / "JSB_host_GUI_publish.exe"
        cached = folder / "cache" / "JSB_host_GUI_publish.exe"
        original.parent.mkdir(); cached.parent.mkdir()
        original.write_bytes(b"MOCK original executable; never launched")
        cached.write_bytes(b"MOCK different cached executable; never launched")
        root_snapshot, cache_snapshot = folder / "originalHost.bin", folder / "cachedHost.bin"
        root_snapshot.write_bytes(original.read_bytes()); cache_snapshot.write_bytes(cached.read_bytes())
        nodes = {}
        class ProcessFixture:
            def __init__(self, pid, parent, exe, internal=False):
                self.pid, self.parent_pid, self.executable, self.internal = pid, parent, exe, internal
            def create_time(self): return 1000. + self.pid
            def cmdline(self): return [str(original)] + (["--internal-player2"] if self.internal else [])
            def exe(self): return str(self.executable)
            def ppid(self): return self.parent_pid
            def children(self, recursive=False):
                if recursive: raise AssertionError("Expected scoped direct children only")
                return [child for child in nodes.values() if child.parent_pid == self.pid]
            def parents(self): raise AssertionError("Never inspect service/system ancestors")
            def parent(self): raise AssertionError("No scope-external parent query")
        for pid, parent, exe, internal in ((10, 9999, original, False), (20, 10, cached, False),
                                           (30, 20, original, True), (40, 30, cached, True)):
            nodes[pid] = ProcessFixture(pid, parent, exe, internal)
        root = portable.identity(nodes[10])
        root_key = f"{root['pid']}:{root['create_time']:.6f}"
        tracked = {root_key: {"role": "host_root", "identity": root}}
        allowed = {
            os.path.normcase(str(original)): {"sha256": portable.sha(original), "snapshot": str(root_snapshot),
                "phase": "before_host_Popen", "kind": "original_host"},
            os.path.normcase(str(cached)): {"sha256": portable.sha(cached), "snapshot": str(cache_snapshot),
                "phase": "before_host_Popen", "kind": "cached_host"}}
        cache_receipt = {"path": str(cached), "sha256": portable.sha(cached),
                         "snapshot": str(cache_snapshot), "phase": "before_host_Popen"}
        launch = folder / "launch.json"
        portable.atomic(launch, {"cached_executable_receipt": cache_receipt})
        session = {"watchdog_token": "mock_scoped_tree", "host_launch_record": str(launch),
                   "host_launch_identity": {key: root[key] for key in ("pid", "create_time", "command")},
                   "cached_executable_receipt": cache_receipt,
                   "fixed_profile": {"cached_host_sha256": portable.sha(cached), "cached_host_executable": str(cached)}}
        return nodes, tracked, allowed, session

    def test_different_cache_binary_is_captured_only_under_owned_root(self):
        with tempfile.TemporaryDirectory(dir=portable.HERE) as directory:
            folder = Path(directory)
            nodes, tracked, allowed, session = self.fixture(folder)
            self.assertNotEqual(allowed[list(allowed)[0]]["sha256"], allowed[list(allowed)[1]]["sha256"])
            with patch.object(portable.psutil, "Process", side_effect=lambda pid: nodes[pid]):
                portable.discover(tracked, allowed)
            self.assertEqual({entry["identity"]["pid"] for entry in tracked.values()}, {10, 20, 30, 40})
            checks = portable.child_inventory_checks(session, {"token": session["watchdog_token"], "tracked": tracked}, folder)
            self.assertTrue(all(checks.values()), checks)
            cache_p2 = next(entry for entry in tracked.values() if entry["identity"]["pid"] == 40)
            self.assertEqual(cache_p2["parent_identity_at_observation"]["pid"], 30)

    def test_missed_cache_executable_rejects_completeness_instead_of_silent_skip(self):
        with tempfile.TemporaryDirectory(dir=portable.HERE) as directory:
            folder = Path(directory)
            nodes, tracked, allowed, session = self.fixture(folder)
            allowed = {key: value for key, value in allowed.items() if value["kind"] != "cached_host"}
            with patch.object(portable.psutil, "Process", side_effect=lambda pid: nodes[pid]):
                portable.discover(tracked, allowed)
            checks = portable.child_inventory_checks(session, {"token": session["watchdog_token"], "tracked": tracked}, folder)
            self.assertFalse(checks["all_owned_children_captured"])
            self.assertFalse(checks["cached_gui_captured"])
            self.assertFalse(all(checks.values()))

    def test_same_cache_executable_outside_root_is_never_discovered(self):
        with tempfile.TemporaryDirectory(dir=portable.HERE) as directory:
            folder = Path(directory)
            nodes, tracked, allowed, session = self.fixture(folder)
            outside = copy.copy(nodes[20]); outside.pid = 99; outside.parent_pid = 7777
            nodes[99] = outside
            queried = []
            def process(pid): queried.append(pid); return nodes[pid]
            with patch.object(portable.psutil, "Process", side_effect=process):
                portable.discover(tracked, allowed)
            self.assertNotIn(99, queried)
            self.assertNotIn(9999, queried)
            self.assertNotIn(7777, queried)
            self.assertNotIn(99, {entry["identity"]["pid"] for entry in tracked.values()})

    def test_cache_bytes_changed_after_prelaunch_snapshot_are_unknown(self):
        with tempfile.TemporaryDirectory(dir=portable.HERE) as directory:
            folder = Path(directory)
            nodes, tracked, allowed, session = self.fixture(folder)
            Path(nodes[20].exe()).write_bytes(b"MOCK changed cached bytes")
            with patch.object(portable.psutil, "Process", side_effect=lambda pid: nodes[pid]):
                portable.discover(tracked, allowed)
            self.assertTrue(next(iter(tracked.values()))["descendants_unknown"])

    def test_broken_parent_chain_or_postlaunch_snapshot_cannot_count(self):
        with tempfile.TemporaryDirectory(dir=portable.HERE) as directory:
            folder = Path(directory)
            nodes, tracked, allowed, session = self.fixture(folder)
            with patch.object(portable.psutil, "Process", side_effect=lambda pid: nodes[pid]):
                portable.discover(tracked, allowed)
            damaged = copy.deepcopy(tracked)
            next(entry for entry in damaged.values() if entry["identity"]["pid"] == 40)["identity"]["parent_pid"] = 9999
            checks = portable.child_inventory_checks(session, {"token": session["watchdog_token"], "tracked": damaged}, folder)
            self.assertFalse(checks["all_direct_parent_chains_verified"])
            bad_session = copy.deepcopy(session)
            bad_session["cached_executable_receipt"]["phase"] = "after_terminal"
            checks = portable.child_inventory_checks(bad_session, {"token": session["watchdog_token"], "tracked": tracked}, folder)
            self.assertFalse(checks["prelaunch_cache_receipt_matches"])

    def test_v1_metadata_key_failure_is_fixed_in_memory_without_reclassifying_old_round(self):
        old = portable.HERE.parent / "portable_host_v1" / "runs" / "portable_20261014_203837_2976b892"
        session = portable.read(old / "session.json")
        result = portable.read(old / "portable_result.json")
        source = old / Path(result["source_csv"]).name
        with source.open(encoding="utf-8-sig", newline="") as stream: rows = list(csv.DictReader(stream))
        before = portable.terminal.verify(old, session, rows, portable.sha(source))
        self.assertFalse(before["prelaunch_p2_receipt_matches"])
        fixed = copy.deepcopy(session)
        fixed["host_process_identity"] = fixed["host_launch_identity"]
        fixed["host_launch_identity"] = {key: fixed["host_launch_identity"][key] for key in ("pid", "create_time", "command")}
        after = portable.terminal.verify(old, fixed, rows, portable.sha(source))
        self.assertTrue(after["prelaunch_p2_receipt_matches"])
        self.assertFalse(result["portable_rehearsal_complete"])


class ConsoleHelperTests(unittest.TestCase):
    fixture=OwnedCacheTreeTests.fixture
    def console_fixture(self,folder):
        nodes,tracked,allowed,session=self.fixture(folder)
        helper=folder/'conhost.exe';helper.write_bytes(b'MOCK own console, never launched')
        snapshot=folder/'console_helper.bin';snapshot.write_bytes(helper.read_bytes())
        player=copy.copy(nodes[10]);player.pid=50;player.parent_pid=8888;nodes[50]=player
        console=copy.copy(nodes[10]);console.pid=60;console.parent_pid=50;console.executable=helper;nodes[60]=console
        identity=portable.identity(player);key=f"{identity['pid']}:{identity['create_time']:.6f}"
        tracked[key]={'role':'player_root','identity':identity};session['player']=identity
        session['fixed_profile'].update(console_helper_executable=str(helper),console_helper_sha256=portable.sha(helper))
        allowed[os.path.normcase(str(helper))]={'sha256':portable.sha(helper),'snapshot':str(snapshot),'phase':'before_host_Popen','kind':'console_helper'}
        return nodes,tracked,allowed,session
    def test_exact_player_console_chain_and_snapshot_pass(self):
        with tempfile.TemporaryDirectory(dir=portable.HERE) as d:
            folder=Path(d);nodes,tracked,allowed,session=self.console_fixture(folder)
            with patch.object(portable.psutil,'Process',side_effect=lambda pid:nodes[pid]):portable.discover(tracked,allowed)
            checks=portable.child_inventory_checks(session,{'token':session['watchdog_token'],'tracked':tracked},folder)
            self.assertTrue(all(checks.values()),checks)
            self.assertEqual([e['role'] for e in tracked.values() if e['identity']['pid']==60],['owned_console_helper'])
    def test_foreign_console_not_captured(self):
        with tempfile.TemporaryDirectory(dir=portable.HERE) as d:
            folder=Path(d);nodes,tracked,allowed,session=self.console_fixture(folder)
            foreign=copy.copy(nodes[60]);foreign.pid=99;foreign.parent_pid=7777;nodes[99]=foreign
            with patch.object(portable.psutil,'Process',side_effect=lambda pid:nodes[pid]):portable.discover(tracked,allowed)
            self.assertNotIn(99,{e['identity']['pid'] for e in tracked.values()})
    def test_changed_helper_bytes_reject(self):
        with tempfile.TemporaryDirectory(dir=portable.HERE) as d:
            folder=Path(d);nodes,tracked,allowed,session=self.console_fixture(folder)
            nodes[60].executable.write_bytes(b'changed')
            with patch.object(portable.psutil,'Process',side_effect=lambda pid:nodes[pid]):portable.discover(tracked,allowed)
            self.assertFalse(portable.child_inventory_checks(session,{'token':session['watchdog_token'],'tracked':tracked},folder)['all_owned_children_captured'])
    def test_altered_player_identity_rejects_chain(self):
        with tempfile.TemporaryDirectory(dir=portable.HERE) as d:
            folder=Path(d);nodes,tracked,allowed,session=self.console_fixture(folder)
            with patch.object(portable.psutil,'Process',side_effect=lambda pid:nodes[pid]):portable.discover(tracked,allowed)
            session['player']['create_time']-=1
            #Session and ledger must be independent records, as in real JSON.
            entry=next(e for e in tracked.values() if e['identity']['pid']==50);entry['identity']=portable.identity(nodes[50])
            self.assertFalse(portable.child_inventory_checks(session,{'token':session['watchdog_token'],'tracked':tracked},folder)['all_direct_parent_chains_verified'])
    def test_missing_helper_allowance_rejects(self):
        with tempfile.TemporaryDirectory(dir=portable.HERE) as d:
            folder=Path(d);nodes,tracked,allowed,session=self.console_fixture(folder)
            allowed={k:v for k,v in allowed.items() if v['kind']!='console_helper'}
            with patch.object(portable.psutil,'Process',side_effect=lambda pid:nodes[pid]):portable.discover(tracked,allowed)
            self.assertFalse(portable.child_inventory_checks(session,{'token':session['watchdog_token'],'tracked':tracked},folder)['all_owned_children_captured'])


class TerminalCleanupTests(unittest.TestCase):
    fixture=OwnedCacheTreeTests.fixture
    def cleanup_fixture(self,folder,target='30'):
        nodes,tracked,allowed,session=self.fixture(folder)
        binary=folder/'taskkill.exe';binary.write_bytes(b'MOCK observed terminal helper never executed')
        snapshot=folder/'terminal_cleanup.bin';snapshot.write_bytes(binary.read_bytes())
        helper=copy.copy(nodes[30]);helper.pid=45;helper.parent_pid=20;helper.executable=binary
        helper.cmdline=lambda:['taskkill.exe','/PID',target,'/T','/F'];nodes[45]=helper
        session['fixed_profile'].update(terminal_cleanup_executable=str(binary),terminal_cleanup_sha256=portable.sha(binary))
        allowed[os.path.normcase(str(binary))]={'sha256':portable.sha(binary),'snapshot':str(snapshot),'phase':'before_host_Popen','kind':'terminal_cleanup'}
        return nodes,tracked,allowed,session
    def test_observed_exact_own_P2_cleanup_passes(self):
        with tempfile.TemporaryDirectory(dir=portable.HERE) as d:
            folder=Path(d);nodes,tracked,allowed,session=self.cleanup_fixture(folder)
            with patch.object(portable.psutil,'Process',side_effect=lambda pid:nodes[pid]):portable.discover(tracked,allowed)
            self.assertTrue(all(portable.child_inventory_checks(session,{'token':session['watchdog_token'],'tracked':tracked},folder).values()))
            helper=next(e for e in tracked.values() if e['identity']['pid']==45)
            self.assertEqual(helper['role'],'owned_terminal_cleanup_helper');self.assertEqual(helper['cleanup_target_identity']['pid'],30)
    def test_foreign_target_not_recognized(self):
        with tempfile.TemporaryDirectory(dir=portable.HERE) as d:
            folder=Path(d);nodes,tracked,allowed,session=self.cleanup_fixture(folder,'999')
            with patch.object(portable.psutil,'Process',side_effect=lambda pid:nodes[pid]):portable.discover(tracked,allowed)
            self.assertNotIn(45,{e['identity']['pid'] for e in tracked.values()})
            self.assertFalse(portable.child_inventory_checks(session,{'token':session['watchdog_token'],'tracked':tracked},folder)['all_owned_children_captured'])
    def test_changed_cleanup_bytes_rejects(self):
        with tempfile.TemporaryDirectory(dir=portable.HERE) as d:
            folder=Path(d);nodes,tracked,allowed,session=self.cleanup_fixture(folder);nodes[45].executable.write_bytes(b'changed')
            with patch.object(portable.psutil,'Process',side_effect=lambda pid:nodes[pid]):portable.discover(tracked,allowed)
            self.assertNotIn(45,{e['identity']['pid'] for e in tracked.values()})
    def test_command_cannot_target_GUI_or_use_other_flags(self):
        with tempfile.TemporaryDirectory(dir=portable.HERE) as d:
            folder=Path(d);nodes,tracked,allowed,session=self.cleanup_fixture(folder,'20')
            with patch.object(portable.psutil,'Process',side_effect=lambda pid:nodes[pid]):portable.discover(tracked,allowed)
            self.assertNotIn(45,{e['identity']['pid'] for e in tracked.values()})
    def test_changed_saved_target_identity_rejects_inventory(self):
        with tempfile.TemporaryDirectory(dir=portable.HERE) as d:
            folder=Path(d);nodes,tracked,allowed,session=self.cleanup_fixture(folder)
            with patch.object(portable.psutil,'Process',side_effect=lambda pid:nodes[pid]):portable.discover(tracked,allowed)
            helper=next(e for e in tracked.values() if e['identity']['pid']==45);helper['cleanup_target_identity']=dict(helper['cleanup_target_identity']);helper['cleanup_target_identity']['create_time']-=1
            self.assertFalse(portable.child_inventory_checks(session,{'token':session['watchdog_token'],'tracked':tracked},folder)['all_direct_parent_chains_verified'])


if __name__ == "__main__":
    unittest.main()
