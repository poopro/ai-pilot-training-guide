"""Bounded real-factory CPU interface probe. No FDM, network, training or victory claim."""
from pathlib import Path
import sys,json,time,hashlib,subprocess,uuid,datetime,traceback,os
import psutil
ROOT=Path(r'E:\ai_pilot\campaign_2026')
BRANCH=ROOT/'experiments/opponent_pool/frozen_sac_opponent_v2'
SELF=Path(__file__).resolve()
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def identity(pid=None):
    p=psutil.Process(pid or os.getpid())
    return {'pid':p.pid,'create':p.create_time(),'cmd':p.cmdline(),'exe':p.exe(),'parent':p.ppid()}
def match(i):
    try:return identity(i['pid'])==i
    except psutil.NoSuchProcess:return False
def stop(out):return (ROOT/'STOP').exists() or (out/'STOP').exists()
def gate(spec):
    for path,h in spec['source_sha256'].items():assert sha(path)==h,path
def worker(out):
    spec=read(out/'CONTRACT.json');gate(spec)
    assert psutil.Process().ppid()==spec['watchdog']['pid'] and match(spec['watchdog'])
    assert time.time()<spec['deadline_epoch'] and not stop(out)
    sys.path.insert(0,str(BRANCH))
    import numpy as np,torch,random,pickle
    from factory import build_frozen_opponent,source_gate
    source_gate();torch.set_num_threads(1)
    def rng():
        n=np.random.get_state()
        return {'python':hashlib.sha256(repr(random.getstate()).encode()).hexdigest(),
                'numpy':hashlib.sha256(n[0].encode()+n[1].tobytes()+repr(n[2:]).encode()).hexdigest(),
                'torch_cpu':hashlib.sha256(torch.random.get_rng_state().numpy().tobytes()).hexdigest()}
    settings=read(spec['settings_path'])
    observation=np.array(read(spec['packet_source'])['episodes'][0]['initial_legal_blue'],dtype=np.float64)
    assert observation.shape==(26,)
    output={'scope':'real frozen SAC and StationController on repeated legal packet; synthetic clock only','new_FDM_ticks':0,'training_started':False,'models':{},'FDM_timing_verified':False,'strength_verified':False}
    objects=[]
    for model in ('sac5000','transfer10000'):
        before=rng();t=time.perf_counter();op=build_frozen_opponent(model,settings);load_seconds=time.perf_counter()-t
        after=rng();write(out/('RNG_'+model+'.json'),{'before':before,'after_construct':after,'equal_by_stream':{k:before[k]==after[k] for k in before}})
        assert after==before,'RNG changed on factory construction'
        commands=[];latency=[]
        for tick in range(100):
            assert time.time()<spec['deadline_epoch'] and not stop(out)
            t=time.perf_counter();cmd=op.command(observation,completed_tick=tick);latency.append((time.perf_counter()-t)*1000)
            status=op.status();np.testing.assert_array_equal(op.command(observation.copy(),completed_tick=tick),cmd)
            assert status==op.status(),'Duplicate mutated state'
            commands.append(cmd.tolist())
        assert op.act_calls==100 and op.predict_calls==5 and op.completed_tick==99
        assert rng()==before,'Deterministic policy unexpectedly sampled global RNG'
        previous_controller=op.controller;previous_actor=op.actor
        op.reset();assert op.controller is not previous_controller and op.actor is not previous_actor
        assert rng()==before,'RNG changed on reset'
        np.testing.assert_array_equal(op.command(observation,completed_tick=0),np.array(commands[0]))
        assert op.act_calls==1 and op.predict_calls==1 and op.attack_ticks==0
        objects.append((op,previous_controller,previous_actor))
        output['models'][model]={'load_seconds':load_seconds,'unique_packet_commands':100,'real_controller_act_calls_before_reset':100,'real_actor_predictions_before_reset':5,'duplicate_cache_verified':True,'rng_restore_and_no_sampling_verified':True,'reset_fresh_controller_actor_verified':True,'reset_command_exact_reproduction':True,'max_full_command_ms':max(latency),'p99_full_command_ms':sorted(latency)[98],'commands_sha256':hashlib.sha256(json.dumps(commands).encode()).hexdigest(),'simulator_wiring_verified':False}
    assert objects[0][0].controller is not objects[1][0].controller and objects[0][0].actor is not objects[1][0].actor
    gate(spec);source_gate();output['source_unchanged']=True
    write(out/'RESULT.json',output)
    return 0
def main():
    if len(sys.argv)==3 and sys.argv[1]=='--worker':return worker(Path(sys.argv[2]))
    sys.path.insert(0,str(ROOT));from runner import JobLock
    with JobLock(ROOT/'launch.lock'):
        inventory=[]
        for p in psutil.process_iter(['pid','name','cmdline','create_time','exe','ppid']):
            try:
                cmd=' '.join(p.info['cmdline'] or [])
                if p.pid!=os.getpid() and 'python' in (p.info['name'] or '').lower() and str(ROOT).lower() in cmd.lower() and any(x in cmd for x in ('run_smoke.py','win_loop.py','m4_tactical_rl.py','portable_host.py','--worker')):inventory.append(p.info)
            except psutil.NoSuchProcess:pass
        assert not inventory,inventory
        resources={'ram_gib':psutil.virtual_memory().available/2**30,'disk_gib':psutil.disk_usage(str(ROOT)).free/2**30,'cpu_percent':psutil.cpu_percent(interval=.2),'GPU_used':False}
        assert resources['ram_gib']>=2 and resources['disk_gib']>=1 and resources['cpu_percent']<95
        assert not (ROOT/'STOP').exists()
        out=ROOT/'diagnostics'/('frozen_sac_cpu_probe_v2_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]);out.mkdir()
        contract=read(BRANCH/'CONTRACT.json');paths=[SELF,BRANCH/'CONTRACT.json',*[BRANCH/x for x in contract['executor_sha256']],*[Path(x) for x in contract['source_sha256']]]
        paths += [Path(v['model_path']) for v in contract['models'].values()]
        base=next(Path(x).parents[1] for x in contract['source_sha256'] if x.endswith('combat_v3\\interface.py'))
        settings=base/'combat_v3/config.json'
        packet=ROOT/'experiments/opponent_pool/m4_grid_eval_v1/run_20261016_104729_96f65a/cases/final_mirror_sac5000_2026300303/result.json'
        paths += [settings,packet]
        started=time.time();spec={'hypothesis':'Production frozen model and private controller factories obey packet interface and RNG isolation before FDM wiring','single_change':'Exercise existing immutable production factories with synthetic repeated legal packet; no control changes','source_sha256':{str(p):sha(p) for p in paths},'settings_path':str(settings),'packet_source':str(packet),'watchdog':identity(),'deadline_epoch':started+120,'resources':resources,'seed_role':'no new random opening; saved development legal packet only','models_fixed':contract['models'],'usage_observation':{'captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'five_hour_remaining':78,'weekly_remaining':54,'primary_reset':1792169034,'weekly_reset':1792654206}}
        write(out/'CONTRACT.json',spec)
        budget_date=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()
        ledgerpath=ROOT/('compute_budgets/'+budget_date+'.json')
        ledger=read(ledgerpath) if ledgerpath.exists() else {'date_taipei':budget_date,'daily_limit_hours':6.0,'reserved_hours':0.0,'items':[]}
        item={'id':out.name,'hours':120/3600,'status':'reserved_cpu_interface_probe_noFDM','output':str(out),'warning_only':True}
        ledger['items'].append(item);ledger['reserved_hours']+=120/3600;write(ledgerpath,ledger)
        with (out/'worker.log').open('w',encoding='utf8') as log:
            p=subprocess.Popen([sys.executable,'-B','-X','utf8',str(SELF),'--worker',str(out)],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            child=identity(p.pid);write(out/'worker_identity.json',child)
            reason=None
            while p.poll() is None:
                if time.time()>=spec['deadline_epoch'] or stop(out):
                    reason='STOP_or_original_120s_deadline'
                    assert match(child),'Refuse to terminate unknown identity'
                    p.terminate();break
                time.sleep(.1)
            code=p.wait(timeout=10)
        gate(spec)
        receipt={'actual_worker_exit':code,'watchdog_finished_normally':True,'elapsed_seconds':time.time()-started,'termination_reason':reason,'worker_identity_absent':not match(child),'result_sha256':sha(out/'RESULT.json') if (out/'RESULT.json').exists() else None,'source_unchanged':True,'new_FDM_ticks':0}
        write(out/'EXIT_RECEIPT.json',receipt)
        ledger=read(ledgerpath);ledger['items'][-1].update(status='terminal_cpu_probe',actual_worker_exit=code,actual_wall_seconds=receipt['elapsed_seconds']);write(ledgerpath,ledger)
        print(json.dumps({'out':str(out),**receipt},ensure_ascii=False));return code
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception:traceback.print_exc();raise SystemExit(1)
