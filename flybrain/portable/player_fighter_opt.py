"""Frozen repair_guide player. Restart for every round; no actor or training."""
import argparse,json,socket,time,sys
from collections import deque
from pathlib import Path
from bootstrap import ROOT,DLL_HANDLES
import numpy as np
from combat_v3.interface import decode_packet,encode_command
from controller import RepairController;from fighter_opt import build as build_pilot
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
    ap=argparse.ArgumentParser();ap.add_argument('--network',type=Path,default=ROOT/'network.json')
    ap.add_argument('--max-seconds',type=float);ap.add_argument('--guide',action='store_true');ap.add_argument('--profile',default=None);ap.add_argument('--resume',action='store_true')
    a=ap.parse_args();net=json.loads(a.network.read_text(encoding='utf-8-sig'))
    config=json.loads((ROOT/'policy/combat_v3/config.json').read_text(encoding='utf-8'))
    max_hz=int(net.get('max_hz',60))
    if not 1<=max_hz<=60:ap.error('max_hz must be between1 and60')
    host=socket.gethostbyname(net['host_ip']);profile=a.profile or net.get('profile') or 'base_t3';controller=build_pilot(profile);round_state=RoundState();round_state.count=61 if a.resume else 0
    action=np.array([0.,0.,0.,.8]);residual=np.zeros(4,dtype=np.float32);rx=0;bad=0;send_times=deque()
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.bind((net['listen_ip'],int(net['listen_port'])));sock.settimeout(.5)
    out=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);began=time.monotonic()
    print('Profile:',profile,'(fighter_opt.py；無SAC)。每回合前重啟Player。',flush=True)
    print(f"OBS {net['listen_ip']}:{net['listen_port']} -> CMD {host}:{net['host_port']}",flush=True)
    try:
        while a.max_seconds is None or time.monotonic()-began<a.max_seconds:
            try:data,addr=sock.recvfrom(4096)
            except socket.timeout:continue
            if addr[0]!=host:continue
            try:o=decode_packet(data)
            except ValueError:bad+=1;continue
            now=time.monotonic()
            while send_times and now-send_times[0]>=1:send_times.popleft()
            if len(send_times)>=max_hz:continue
            state,started,duplicate=round_state.observe(o)
            if not duplicate or not started:action,_=controller.act(o,residual,started)
            out.sendto(encode_command(action,state),(host,int(net['host_port'])))
            send_times.append(time.monotonic());rx+=1
            if rx%300==0:print(f'有效回傳 {rx}；狀態 {state}；已起飛 {started}；無效OBS {bad}',flush=True)
    except KeyboardInterrupt:print('已停止Player。',flush=True)
    finally:sock.close();out.close()
    return 0
if __name__=='__main__':raise SystemExit(main())
