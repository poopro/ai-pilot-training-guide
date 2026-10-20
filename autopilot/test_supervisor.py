import tempfile,unittest,sys,os,time
from pathlib import Path
from common import *
from supervisor import run_stage,execute

CHILD=r'''import sys,time,json,os
from pathlib import Path
p=Path(sys.argv[1]);mode=sys.argv[2]
sys.path.insert(0,r'E:\ai_pilot\autopilot')
from common import atomic
for i in range(1,51):
 atomic(p/'progress.json',{'timesteps':i,'work_tick':i})
 if (p/'STOP').exists():break
 if mode=='fail':sys.exit(7)
 if mode=='done' and i==3:break
 if mode=='hang':time.sleep(30)
 time.sleep(.01)
(p/'saved').write_text(str(i))
'''
class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name)
        self.job={'job_id':'test','job_dir':str(self.folder),'status':'running','stage':'test',
          'first_started_epoch':time.time(),'deadline_epoch':time.time()+60000,'step_budget':200000,
          'new_steps':0,'results':[],'config':{'stall_seconds':10,'save_grace_seconds':2,'poll_seconds':.01}}
        self.child=self.folder/'child.py';self.child.write_text(CHILD)
        # Tests must never overwrite the real latest job files.
        import supervisor
        self.publish=supervisor.publish;self.report=supervisor.report
        supervisor.publish=lambda j:atomic(self.folder/'state.json',j)
        supervisor.report=lambda j:None
    def tearDown(self):
        import supervisor
        supervisor.publish=self.publish;supervisor.report=self.report
        self.temp.cleanup()
    def run_child(self,mode,timeout=5):
        out=self.folder/'stage'
        return run_stage(self.job,'test',[sys.executable,self.child,out,mode],out,timeout,True,0)
    def test_complete_and_count(self):
        r=self.run_child('done');self.assertEqual(r['exit_code'],0,(self.folder/'stage/stderr.log').read_text())
        self.assertEqual(self.job['new_steps'],3);self.assertTrue((self.folder/'stage/saved').exists())
    def test_error_exit(self):self.assertEqual(self.run_child('fail')['exit_code'],7)
    def test_stale_progress_is_not_counted_twice(self):
        out=self.folder/'stage';out.mkdir()
        atomic(out/'progress.json',{'timesteps':99999})
        self.run_child('done')
        self.assertEqual(self.job['new_steps'],3)
    def test_completion_runs_next_stage(self):
        tasks=[{'name':name,'folder':str(self.folder/name),'command':[sys.executable,self.child,self.folder/name,'done']} for name in ('train','evaluate')]
        execute(self.job,tasks)
        self.assertEqual(self.job['status'],'completed')
        self.assertEqual([r['name'] for r in self.job['results']],['train','evaluate'])
        self.assertTrue((self.folder/'evaluate/saved').exists())
    def test_resume_counts_only_increment(self):
        self.job['new_steps']=7
        result=run_stage(self.job,'resume',[sys.executable,self.child,self.folder/'resume','done'],self.folder/'resume',5,True,1)
        self.assertEqual(self.job['new_steps'],9)
    def test_stop_and_save(self):
        (self.folder/'STOP').write_text('stop')
        r=self.run_child('long');self.assertEqual(r['reason'],'interrupted')
        self.assertTrue((self.folder/'stage/saved').exists())
    def test_timeout_owned_only(self):
        r=self.run_child('hang',.15);self.assertEqual(r['reason'],'timeout')
        self.assertFalse(alive(r['process']));self.assertTrue(psutil.Process(os.getpid()).is_running())
    def test_duplicate_lock(self):
        with JobLock(self.folder/'lock'):
            with self.assertRaises(RuntimeError):
                with JobLock(self.folder/'lock'):pass
    def test_atomic_and_checksum(self):
        path=self.folder/'bundle';path.mkdir()
        (path/'model.zip').write_bytes(b'test');(path/'replay.pkl').write_bytes(b'replay')
        atomic(path/'manifest.json',{'format':'guided_combat_v3','timesteps':17,
          'model_sha256':digest(path/'model.zip'),'replay_sha256':digest(path/'replay.pkl')})
        self.assertEqual(valid_bundle(path)['timesteps'],17)
        (path/'replay.pkl').write_bytes(b'corrupt')
        with self.assertRaises(ValueError):valid_bundle(path)
if __name__=='__main__':unittest.main(verbosity=2)
