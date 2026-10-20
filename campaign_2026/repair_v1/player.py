"""Single-PC offline player. 208-byte OBS -> shared v3 controller -> 30-byte CMD.
Restart before each round: the published 26-double packet has no round ID/INIT flag.
"""
import argparse,json,socket,time,hashlib,sys
from collections import deque
from pathlib import Path
import numpy as np
from artifacts import BASE
ROOT=BASE;sys.path.insert(0,str(ROOT))
from combat_v3.interface import decode_packet,encode_command,policy_state
from controller import RepairController as PacketController
from artifacts import load_policy
class RoundState:
    def __init__(self):self.anchor=None;self.count=0;self.started=False;self.previous=None
    def observe(self,o):
        if self.anchor is None:self.anchor=o[[0,1]].copy()
        self.count+=1
        if np.any(np.abs(o[[0,1]]-self.anchor)>1e-10):self.started=True
        duplicate=self.previous is not None and np.array_equal(o,self.previous)
        self.previous=o.copy()
        return (2 if self.count>60 else 1),self.started,duplicate
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--network',type=Path,default=Path('E:/ai_pilot/autopilot/combat_fix/udp_config.json'))
    ap.add_argument('--bundle',type=Path);ap.add_argument('--guide',action='store_true')
    a=ap.parse_args()
    if a.guide and a.bundle:ap.error('guide 與 bundle 擇一')
    from artifacts import BASE
    cfg=json.loads((BASE/'combat_v3/config.json').read_text(encoding='utf-8'))
    net=json.loads(a.network.read_text(encoding='utf-8'));model=None
    if a.bundle:
        model=load_policy(a.bundle)
        if not hasattr(model,'combat_fix_manifest'):ap.error('只接受修正版模型；舊actor請先移植並重新訓練')
    controller=PacketController(cfg);round_state=RoundState()
    action=np.array([0.,0.,0.,.8]);residual=np.zeros(4,dtype=np.float32);active_ticks=0;bad=0;rx=0;worst_ms=0.;send_times=deque()
    host=socket.gethostbyname(net['host_ip']);max_hz=min(60,int(net.get('max_hz',60)))
    if max_hz<=0:ap.error('max_hz must be positive')
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.bind((net['listen_ip'],int(net['listen_port'])));sock.settimeout(.5)
    out=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    print('修正版純引導器（本地測試；官方Host待驗證）' if model is None else '修正版模型＋引導器（官方Host待驗證）',flush=True)
    print(f"OBS {net['listen_ip']}:{net['listen_port']} -> CMD {host}:{net['host_port']}",flush=True)
    print('每回合開始前重新啟動；INIT 期間不累計飛行控制狀態。',flush=True)
    try:
        while True:
            try:data,addr=sock.recvfrom(4096)
            except socket.timeout:continue  # Host retains the last valid command; no extra packets.
            if addr[0]!=host:continue
            try:o=decode_packet(data)
            except ValueError:bad+=1;continue
            now=time.monotonic()
            while send_times and now-send_times[0]>=1:send_times.popleft()
            if len(send_times)>=max_hz:continue
            state,started,duplicate=round_state.observe(o)
            start=time.perf_counter()
            if not duplicate or not started:
                if model is not None and started and active_ticks%4==0:
                    residual=model.predict(policy_state(o),deterministic=True)[0]
                if started:active_ticks+=1
                action,_=controller.act(o,residual,started)
            out.sendto(encode_command(action,state),(host,int(net['host_port'])))
            send_times.append(time.monotonic());rx+=1;worst_ms=max(worst_ms,(time.perf_counter()-start)*1000)
            if rx%300==0:print(f'有效回傳 {rx}；狀態 {state}；已起飛 {started}；無效 OBS {bad}；最慢處理 {worst_ms:.2f} ms',flush=True)
    except KeyboardInterrupt:print('已停止 Player。',flush=True)
    finally:sock.close();out.close()
if __name__=='__main__':main()

