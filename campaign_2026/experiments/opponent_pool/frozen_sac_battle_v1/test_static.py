"""Offline plan and gate checks; no flight simulator or model inference."""
import unittest,sys,tempfile
from pathlib import Path
from unittest.mock import patch
import battle

class Tests(unittest.TestCase):
    def test_six_and_fair_cells(self):
        p=battle.plan();self.assertEqual(len(p),6)
        for opening in (0,1):
            rows=[r for r in p if r['opening']==opening]
            self.assertEqual({r['actor'] for r in rows},set(battle.ACTORS))
            for key in ('seed','red','side','distance_ft','max_ticks'):self.assertEqual(len({r[key] for r in rows}),1)
        self.assertEqual({r['side'] for r in p},{'normal','mirrored'})
        self.assertEqual(len({r['id'] for r in p}),6)
    def test_deadline_never_extended(self):
        s=dict(deadline_epoch=100,deadline_monotonic=200)
        with patch.object(battle.time,'time',return_value=101),patch.object(battle.time,'monotonic',return_value=1):self.assertTrue(battle.expired(s))
        with patch.object(battle.time,'time',return_value=1),patch.object(battle.time,'monotonic',return_value=201):self.assertTrue(battle.expired(s))
        with patch.object(battle.time,'time',return_value=51),patch.object(battle.time,'monotonic',return_value=1):self.assertTrue(battle.expired(s,dict(deadline_epoch=50,deadline_monotonic=190)))
    def test_unknown_process_not_absent(self):
        with patch.object(battle.base.psutil,'Process',side_effect=battle.psutil.AccessDenied):
            with self.assertRaises(battle.psutil.AccessDenied):battle.live(dict(pid=1))
    def test_source_change_rejects(self):
        with patch.object(battle,'sources',return_value={'changed':True}):
            with self.assertRaises(RuntimeError):battle.source_gate({'sources':{'changed':False}})
    def test_atomic_json_and_readback(self):
        with tempfile.TemporaryDirectory(dir=battle.HERE) as temp:
            p=Path(temp)/'a.json';battle.write(p,{'測試':[1,2]});self.assertEqual(battle.read(p),{'測試':[1,2]});self.assertEqual(len(list(Path(temp).iterdir())),1)

if __name__=='__main__':unittest.main()
