"""Exercise the actual UDP player on private loopback ports; no official Host claim."""
import argparse,json,os,socket,struct,subprocess,time
import numpy as np
import sys
sys.path.insert(0,'E:/ai_pilot/autopilot')
from common import *
FIX_ROOT=Path('E:/ai_pilot/autopilot/combat_fix')

def check(out,bundle=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    receive=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    receive.bind(('127.0.0.1',0));receive.settimeout(.7)
    probe=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);probe.bind(('127.0.0.1',0))
    port=probe.getsockname()[1];probe.close()
    network={'listen_ip':'127.0.0.1','listen_port':port,'host_ip':'127.0.0.1',
             'host_port':receive.getsockname()[1],'max_hz':60}
    atomic(out/'network.json',network)
    cmd=[str(PYTHON),'-u',str(FIX_ROOT/'player.py'),'--network',str(out/'network.json')]
    cmd+=['--bundle',str(bundle)] if bundle else ['--guide']
    log=(out/'player.log').open('w',encoding='utf-8')
    proc=subprocess.Popen(cmd,cwd=str(BASE),stdout=log,stderr=log,
                          env={**os.environ,'PYTHONUTF8':'1'},creationflags=subprocess.CREATE_NO_WINDOW)
    owned=identity(proc.pid);send=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    o=np.zeros(26);o[[0,20]]=23;o[[1,21]]=121;o[[2,22]]=12000
    o[12]=340*1.68781;o[13]=o[12];o[15]=o[12];o[[6,23]]=o[12];o[20]+=.005
    times=[];test={}
    def exchange(packet):
        t=time.perf_counter();send.sendto(packet,('127.0.0.1',port));raw,_=receive.recvfrom(4096)
        times.append((time.perf_counter()-t)*1000)
        assert len(raw)==30
        values=struct.unpack('<fffff10s',raw)
        assert values[-1]==b'PLAYER_CMD' and all(-1<=v<=1 for v in values[:3]) and 0<=values[3]<=1
        return values
    def silence():
        try:receive.recvfrom(4096)
        except socket.timeout:return True
        return False
    try:
        deadline=time.monotonic()+40
        while True:
            try:initial=exchange(struct.pack('<26d',*o));break
            except socket.timeout:
                if proc.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Player did not start')
        test['init_frozen']=bool(np.allclose(initial[:4],[0,0,0,.8],atol=1e-6))
        test['initializing_state']=initial[4]==1
        for _ in range(65):
            time.sleep(.02);last=exchange(struct.pack('<26d',*o))
        test['ready_state']=last[4]==2
        test['still_frozen_before_motion']=bool(np.allclose(last[:4],[0,0,0,.8],atol=1e-6))
        o[0]+=.00001;time.sleep(.025);first=exchange(struct.pack('<26d',*o))
        time.sleep(.025);duplicate=exchange(struct.pack('<26d',*o))
        test['duplicate_preserves_command']=first==duplicate
        test['no_unsolicited_on_missing_obs']=silence()
        for malformed in (b'bad',struct.pack('<26d',*np.full(26,np.nan))):
            send.sendto(malformed,('127.0.0.1',port));assert silence()
        test['invalid_length_and_nan_ignored']=True
        time.sleep(.025);after_timeout=exchange(struct.pack('<26d',*o))
        test['resume_after_missing_obs']=after_timeout[4]==2
        for k in range(200):
            time.sleep(.018);o[0]+=.0000001;exchange(struct.pack('<26d',*o))
        warm=times[-200:]
        result={'passed':all(test.values()),'tests':test,'scope':'real UDP player loopback; NOT official Host',
                'bundle':str(bundle) if bundle else None,'utc':stamp(),
                'round_reset':'must restart player before every round; no round ID in published OBS',
                'network_latency_p50_ms':float(np.percentile(warm,50)),
                'network_latency_p95_ms':float(np.percentile(warm,95)),
                'network_latency_p99_ms':float(np.percentile(warm,99)),
                'network_latency_max_ms':float(max(warm)),
                'source_sha256':{n:digest(BASE/'combat_v3'/n) for n in ('interface.py','config.json')}}
        result['repair_source_sha256']={n:digest(FIX_ROOT/n) for n in ('player.py','controller.py','artifacts.py')};result['official_validation']=False
        atomic(out/'report.json',result);print(json.dumps(result),flush=True)
        if not result['passed']:raise RuntimeError('Deployment test failed')
    finally:
        terminate_owned(owned);send.close();receive.close();log.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--bundle',type=Path)
    a=p.parse_args();check(a.out,a.bundle)

