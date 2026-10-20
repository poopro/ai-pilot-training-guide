"""Actual relocated executable UDP tests against private loopback; no Host/FDM."""
from pathlib import Path
import json,os,sys,time,socket,struct,subprocess,hashlib,psutil
import numpy as np
ROOT=Path(r'E:\ai_pilot\campaign_2026');OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'repair_v1'))
from controller import RepairController
settings=json.loads(Path(r'E:\ai_pilot\2026 AI 飛行員  相關資料\AI空戰競賽系統安裝及測試指引\AI空戰競賽系統安裝及測試指引\AirCombat_Train_Test\combat_v3\config.json').read_text(encoding='utf-8'))
packages=[ROOT/'deployment/repair_guide_portable_20261012',OUT/'不同路徑 空白 賽場副本']
env={k:v for k,v in os.environ.items() if not k.upper().startswith(('PYTHON','CONDA','VIRTUAL_ENV'))};env.update(PATH=r'C:\Windows\System32;C:\Windows',PYTHONHOME=r'Z:\DO_NOT_USE_ORIGINAL_ENV',PYTHONPATH=r'Z:\DO_NOT_USE_ORIGINAL_ENV')
results=[]
for index,package in enumerate(packages):
    run=OUT/f'udp_round_{index+1}';run.mkdir(exist_ok=False)
    rx=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);rx.bind(('127.0.0.1',0));rx.settimeout(.5)
    reserve=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1];reserve.close()
    tx=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    network={'listen_ip':'127.0.0.1','listen_port':port,'host_ip':'127.0.0.1','host_port':rx.getsockname()[1],'max_hz':60}
    config=run/'network.json';config.write_text(json.dumps(network),encoding='utf-8')
    cmd=[str(package/'runtime/python.exe'),'-I','-S','-B','-X','utf8',str(package/'tools/player.py'),'--network',str(config),'--max-seconds','8']
    log=(run/'player.log').open('w',encoding='utf-8');proc=subprocess.Popen(cmd,cwd=r'C:\Windows',env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    ps=psutil.Process(proc.pid);identity={'pid':proc.pid,'creation_epoch':ps.create_time(),'cmdline':ps.cmdline()};start=time.monotonic()
    source_hashes={rel:hashlib.sha256((package/rel).read_bytes()).hexdigest() for rel in ['policy/controller.py','policy/combat_v3/interface.py','policy/combat_v3/controller.py','tools/player.py','manifest.json']}
    metrics=[];tests={};baseline=RepairController(settings);o=np.zeros(26)
    o[[0,20]]=23.;o[[1,21]]=121.;o[[2,22]]=12000.;o[12]=340*1.6878098571011957;o[13]=o[12];o[15]=o[12];o[[6,23]]=o[12];o[20]+=.005
    def exchange():
        began=time.perf_counter();tx.sendto(struct.pack('<26d',*o),('127.0.0.1',port));raw,_=rx.recvfrom(4096)
        elapsed=(time.perf_counter()-began)*1000;assert len(raw)==30
        values=struct.unpack('<fffff10s',raw);assert values[-1]==b'PLAYER_CMD'
        assert all(np.isfinite(values[:5])) and all(-1<=v<=1 for v in values[:3]) and 0<=values[3]<=1
        return values,elapsed
    def silence():
        rx.settimeout(.2)
        try:rx.recvfrom(4096);return False
        except socket.timeout:return True
        finally:rx.settimeout(.5)
    try:
        while True:
            try:first,_=exchange();break
            except socket.timeout:
                if proc.poll() is not None or time.monotonic()-start>3:raise RuntimeError('Player did not start')
        tests['fresh_process_starts_state1']=first[4]==1
        tests['init_frozen']=bool(np.allclose(first[:4],[0,0,0,.8],atol=1e-6))
        for _ in range(65):
            time.sleep(.021);last,_=exchange()
        tests['ready_state2_before_motion']=last[4]==2
        tests['still_frozen_before_motion']=bool(np.allclose(last[:4],[0,0,0,.8],atol=1e-6))
        for i in range(60):
            time.sleep(.021);o[0]+=.0000003;o[5]=float((i*.13)%360);o[3]=3*np.sin(i/12);o[4]=.6*np.sin(i/9)
            expected,_=baseline.act(o,np.zeros(4,dtype=np.float32),True)
            values,elapsed=exchange();metrics.append(elapsed)
            np.testing.assert_allclose(values[:4],expected,rtol=0,atol=1e-6)
        tests['60_stateful_commands_match_original_guide']=True
        time.sleep(.022);duplicate,_=exchange();tests['duplicate_preserves_command']=duplicate==values
        tests['no_unsolicited_on_missing_obs']=silence()
        for malformed in [b'bad',struct.pack('<26d',*np.full(26,np.nan))]:
            tx.sendto(malformed,('127.0.0.1',port));assert silence()
        tests['malformed_and_nan_ignored']=True
        time.sleep(.022);resumed,_=exchange();tests['resumes_after_missing_obs']=resumed[4]==2 and resumed[:4]==values[:4]
        code=proc.wait(timeout=9)
        assert code==0
        assert all(hashlib.sha256((package/rel).read_bytes()).hexdigest()==h for rel,h in source_hashes.items())
        report={'passed':all(tests.values()),'tests':tests,'actual_exit_code':code,'identity':identity,'cmdline':cmd,'source_sha256':source_hashes,'loopback_ports':network,
                'samples':len(metrics),'latency_p50_ms':float(np.percentile(metrics,50)),'latency_p95_ms':float(np.percentile(metrics,95)),'latency_p99_ms':float(np.percentile(metrics,99)),
                'latency_max_ms':max(metrics),'wall_seconds':time.monotonic()-start,'scope':'Actual packaged player and private loopback; no simulator or official Host. Stateful outputs compare with original guide.','new_fdm_ticks':0,'official_host_validation':False}
        assert report['passed'];(run/'REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');results.append(report)
        print(json.dumps({'round':index+1,'passed':report['passed'],'actual_exit':code,'commands_match':60,'latency_p95_ms':report['latency_p95_ms'],'new_fdm_ticks':0},ensure_ascii=False),flush=True)
    finally:
        if proc.poll() is None:
            current=psutil.Process(proc.pid)
            if abs(current.create_time()-identity['creation_epoch'])<.01 and current.cmdline()==identity['cmdline']:
                proc.terminate();proc.wait(timeout=3)
            else:raise RuntimeError('Cannot stop process without matching identity')
        log.close();tx.close();rx.close()
assert len(results)==2 and all(r['tests']['fresh_process_starts_state1'] for r in results)
(OUT/'UDP_VERIFICATION.json').write_text(json.dumps({'passed':True,'rounds':results,'fresh_process_reset_verified':True,'original_guide_stateful_commands_compared':120,'new_fdm_ticks':0,'learner_started':False,'official_host_validation':False},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
