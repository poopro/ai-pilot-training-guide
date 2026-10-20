"""Offline evidence rejection tests and mock collector subprocesses; no Host."""
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import audit_host_evidence as audit
import host_watchdog as watchdog
import p2_terminal_evidence as p2

TEXT = (b'[P2] Built-in Player2 started\n[P2] Child PID=88\n'
        b'[OWN STATE] Pos: Lat=25.01 deg, Lon=121.01 deg, Alt=15000.0 ft\n'
        b'[ENEMY] Pos: Lat=25.02 deg, Lon=121.02 deg, Alt=15000.0 ft\n'
        b'[P2] Stopping: Host state changed to STOPPED\n[P2] Process exited with code 1\n')

class TerminalEvidenceTests(unittest.TestCase):
    def fixture(self, directory):
        root=Path(directory); host=root/'host'; runtime=root/'runtime'
        host.mkdir(); runtime.mkdir(); now=time.time()
        session=dict(terminal_capture_version=1,watchdog_token='fixture',start_clicked_epoch=now-15,
                     host_dir=str(host),runtime_dir=str(runtime),preexisting_csv={})
        exe=str(host/'JSB_host_GUI_publish.exe')
        identity=dict(pid=77,create_time=now-30,command=[exe])
        session['host_processes']=[identity];session['host_launch_identity']=identity
        ledger=dict(token='fixture',tracked={
            'root':dict(role='host_root',identity=identity),
            'p2':dict(role='owned_host_descendant',discovered_from='root',
                      identity=dict(pid=88,create_time=now-20,command=[exe,'--internal-player2']))})
        path=host/'player2_runtime.log';path.write_bytes(TEXT);os.utime(path,(now-5,now-5))
        source=dict(path=str(path.resolve()),size=len(TEXT),mtime_ns=path.stat().st_mtime_ns,sha256=p2.sha(TEXT))
        session['p2_logs_before_launch']={source['path']:dict(exists=True,size=3,mtime_ns=int((now-50)*1e9),sha256=p2.sha(b'old'))}
        row=dict(time='0.033',system_Final_whoiswinner='0',player1_Score_RemainingHP='180',player2_Score_RemainingHP='180',
                 player1_lat_deg='25.02',player1_lon_deg='121.02',player1_alt_ft='15000',
                 player2_lat_deg='25.01',player2_lon_deg='121.01',player2_alt_ft='15000')
        rows=[row,{**row,'time':'116.633','system_Final_whoiswinner':'1','player2_Score_RemainingHP':'0'}]
        csv_path=host/'round.csv'
        with csv_path.open('w',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(row));writer.writeheader();writer.writerows(rows)
        os.utime(csv_path,(now-5,now-5))
        acmi=host/'output_acmi';acmi.mkdir();(acmi/'round.acmi').write_text('#0.033\n#116.633\n')
        os.utime(acmi/'round.acmi',(now-5,now-5))
        return session,source,rows,ledger,now,csv_path

    def test_fresh_owned_terminal_and_counterexamples(self):
        with tempfile.TemporaryDirectory() as directory:
            s,source,rows,ledger,now,csv_path=self.fixture(directory)
            def check(session=s,data=TEXT,entry=source,records=rows,owner=ledger):
                return p2.terminal_checks(session,data,entry,records,'csvhash',owner,now)
            self.assertTrue(all(check().values()))
            cases=[]
            stale=copy.deepcopy(s);stale['p2_logs_before_launch'][source['path']].update(sha256=source['sha256'])
            cases.append(check(session=stale))
            old=copy.deepcopy(s);old.pop('terminal_capture_version');cases.append(check(session=old))
            wrong=copy.deepcopy(ledger);wrong['tracked']['p2']['identity']['pid']=89;cases.append(check(owner=wrong))
            unrelated=copy.deepcopy(ledger);unrelated['tracked']['p2'].pop('discovered_from');cases.append(check(owner=unrelated))
            other=copy.deepcopy(rows);other[-1]['player2_Score_RemainingHP']='180';cases.append(check(records=other))
            geometry=copy.deepcopy(rows);geometry[0]['player2_lat_deg']='24.00';cases.append(check(records=geometry))
            aborted=TEXT.replace(b'code 1',b'code 7');changed={**source,'size':len(aborted),'sha256':p2.sha(aborted)}
            cases.append(check(data=aborted,entry=changed))
            self.assertTrue(all(not all(item.values()) for item in cases))

    def test_capture_verify_and_tampered_snapshot_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            s,source,rows,ledger,now,csv_path=self.fixture(directory)
            folder=Path(directory)/'round';folder.mkdir()
            pre=folder/'launch.json';pre.write_text(json.dumps(dict(terminal_capture_version=1,p2_logs_before_launch=s['p2_logs_before_launch'],**s['host_launch_identity'])))
            s['host_launch_record']=str(pre)
            s['p2_terminal_receipt']=p2.capture(s,folder,ledger)
            self.assertIsNotNone(s['p2_terminal_receipt'])
            self.assertTrue(all(p2.verify(folder,s,rows,p2.sha(csv_path.read_bytes())).values()))
            (folder/'p2_runtime_terminal.log').write_bytes(b'not evidence')
            self.assertFalse(all(p2.verify(folder,s,rows,p2.sha(csv_path.read_bytes())).values()))

    def test_missing_acmi_or_nonterminal_csv_never_triggers(self):
        with tempfile.TemporaryDirectory() as directory:
            s,source,rows,ledger,now,csv_path=self.fixture(directory)
            (Path(s['host_dir'])/'output_acmi'/'round.acmi').unlink()
            self.assertIsNone(p2.probe(s,ledger))

    def test_game_over_path_still_requires_real_line(self):
        with tempfile.TemporaryDirectory() as directory:
            s,source,rows,ledger,now,csv_path=self.fixture(directory)
            self.assertFalse(audit.completion_checks(rows,'no terminal message')['host_game_over_logged'])
            self.assertTrue(audit.completion_checks(rows,'[GAME OVER] Player 1')['host_game_over_logged'])
            self.assertFalse(audit.completion_checks(rows,'[GAME OVER] Player 2')['csv_terminal_log_consistent'])

class AutomaticCollectorTests(unittest.TestCase):
    def test_previous_completed_session_does_not_stop_new_watchdog(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy=Path(directory)
            (legacy/'active_host_test.json').write_text(json.dumps(dict(watchdog_token='old',validation_exit_code=0)))
            with patch.object(watchdog,'LEGACY',legacy):
                self.assertIsNone(watchdog.add_recorded_roots('new',{},[]))

    def run_mock(self,script,timeout):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);diagnostics=root/'diagnostics';diagnostics.mkdir()
            legacy=root/'legacy';folder=legacy/'official_validation'/'mock';folder.mkdir(parents=True)
            (diagnostics/'collect_host_recorded.py').write_text(script,encoding='utf-8')
            with patch.object(watchdog,'DIAGNOSTICS',diagnostics),patch.object(watchdog,'LEGACY',legacy),patch.object(watchdog,'STOP',root/'STOP'):
                return watchdog.collect_automatically(dict(folder=str(folder),watchdog_token='fixture'),time.time()+timeout)

    def test_actual_mock_collector_exit_observed(self):
        r=self.run_mock("print('fixture collector, no Host')\n",10)
        self.assertEqual(r['actual_exit_code'],0);self.assertFalse(r['timed_out'])
        self.assertIn('pid',r['identity'])

    def test_hanging_mock_collector_is_bounded(self):
        r=self.run_mock('import time\ntime.sleep(30)\n',.3)
        self.assertTrue(r['timed_out']);self.assertIsNotNone(r['actual_exit_code'])
        self.assertEqual(r['timeout_cleanup']['results'][0]['after'],'absent')

if __name__=='__main__':unittest.main()
