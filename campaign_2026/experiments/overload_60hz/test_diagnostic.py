import importlib.util
from pathlib import Path
import unittest
import tempfile
from unittest.mock import Mock, patch

spec=importlib.util.spec_from_file_location('overload_diagnostic',Path(__file__).with_name('launch_diagnostic.py'))
diag=importlib.util.module_from_spec(spec); spec.loader.exec_module(diag)


def row(tick,g=1.,overload=0):
    result={k:0. for k in diag.COLUMNS}
    result.update(tick=tick,simulation_seconds=tick/60,controller_mode='track',
        signed_g=g,abs_g=abs(g),overload_ticks=overload,throttle=.8)
    return result


class DiagnosticTests(unittest.TestCase):
    def test_every_tick_and_one_tick_overload(self):
        data=[row(1),row(2,-9.01,1),row(3,2.,1)]
        events=diag.validate_rows(data,3,1)
        self.assertEqual(events[0]['tick'],2)
        self.assertEqual(len(events),1)

    def test_missing_tick_rejected(self):
        with self.assertRaises(RuntimeError): diag.validate_rows([row(1),row(3)],2,0)

    def test_wrong_original_counter_rejected(self):
        with self.assertRaises(RuntimeError): diag.validate_rows([row(1,9.1,1)],1,0)

    def test_exact_9g_is_not_overload(self):
        self.assertEqual(diag.validate_rows([row(1,-9.,0)],1,0),[])

    def test_nonfinite_or_illegal_command_rejected(self):
        bad=row(1); bad['signed_g']=float('nan')
        with self.assertRaises(RuntimeError): diag.validate_rows([bad],1,0)
        bad=row(1); bad['aileron']=1.01
        with self.assertRaises(RuntimeError): diag.validate_rows([bad],1,0)

    def test_reused_pid_or_changed_command_not_owned(self):
        identity={'pid':12,'create_time':10.,'cmdline':['python','owned.py']}
        process=Mock(); process.create_time.return_value=11.; process.cmdline.return_value=identity['cmdline']
        with patch.object(diag.psutil,'Process',return_value=process):
            self.assertIsNone(diag.live(identity))
            process.create_time.return_value=10.; process.cmdline.return_value=['python','other.py']
            self.assertIsNone(diag.live(identity))

    def test_cleanup_children_before_parent(self):
        parent={'pid':1,'parent_pid':0,'create_time':1.,'cmdline':['parent']}
        child={'pid':2,'parent_pid':1,'create_time':2.,'cmdline':['child']}
        processes={1:Mock(),2:Mock()}; order=[]; terminated=set()
        for pid,p in processes.items():
            p.children.return_value=[]
            p.terminate.side_effect=lambda pid=pid:(order.append(pid),terminated.add(pid))
        def alive(item): return None if item['pid'] in terminated else processes[item['pid']]
        with patch.object(diag,'live',side_effect=alive),patch.object(diag.psutil,'wait_procs',return_value=([],[])):
            diag.cleanup([parent,child])
        self.assertEqual(order,[2,1])

    def test_plan_units_and_schema(self):
        self.assertIn('signed_g',diag.COLUMNS)
        self.assertIn('overload_ticks',diag.COLUMNS)
        self.assertIn('elevator',diag.COLUMNS)
        self.assertAlmostEqual(6000*.3048,1828.8)

    def test_guard_deadline_without_simulator_or_process(self):
        with tempfile.TemporaryDirectory(dir=diag.EXP) as temporary:
            folder=Path(temporary)
            diag.bench.atomic_json(folder/'launch.json',{'deadline_epoch':10.})
            diag.bench.atomic_json(folder/'state.json',{'status':'preparing','supervisor':None,'worker':None})
            with patch.object(diag.time,'time',return_value=11.),patch.object(diag,'ident',return_value={'pid':9}):
                diag.guard(folder)
            self.assertEqual(diag.read(folder/'guard_status.json')['reason'],'deadline')


if __name__=='__main__': unittest.main()
