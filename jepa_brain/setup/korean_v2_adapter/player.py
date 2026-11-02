"""Explicit network configuration required; restart before every round."""
from .bootstrap import HERE
import argparse
import json
import socket
import time
from collections import deque
from .policy import KoreanV1
from .clock import PolicyClock
from combat_v3.interface import decode_packet,encode_command

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--network',type=__import__('pathlib').Path,required=True)
    p.add_argument('--max-seconds',type=float)
    p.add_argument('--model',choices=('gylee_69k','gylee_20k'),default='gylee_69k')
    p.add_argument('--callsign',choices=('korean_v1','korean_v2'),default='korean_v1')
    args=p.parse_args()
    net=json.loads(args.network.read_text(encoding='utf-8-sig'))
    host=socket.gethostbyname(net['host_ip'])
    clock=PolicyClock(KoreanV1(args.model))
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    sock.bind((net['listen_ip'],int(net['listen_port'])))
    sock.settimeout(.5)
    out=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    if int(net.get('max_hz',60)) != 60: raise ValueError('This player requires the 60Hz official stream')
    began=time.monotonic();anchor=None;started=False;count=0;send_times=deque()
    display_name='Korea V2' if args.callsign=='korean_v2' else 'korean_v1'
    print(f'{display_name} ({args.model}), estimated enemy state; restart for every round',flush=True)
    try:
        while args.max_seconds is None or time.monotonic()-began<args.max_seconds:
            try: data,addr=sock.recvfrom(4096)
            except socket.timeout: continue
            if addr[0]!=host: continue
            try: o=decode_packet(data)
            except ValueError: continue
            now=time.monotonic()
            while send_times and now-send_times[0]>=1.: send_times.popleft()
            if len(send_times)>=60: continue
            if anchor is None: anchor=o[:2].copy()
            if abs(o[0]-anchor[0])+abs(o[1]-anchor[1])>1e-10: started=True
            count+=1
            action=clock.step(o,started)
            out.sendto(encode_command(action,2 if count>60 else 1),(host,int(net['host_port'])))
            send_times.append(time.monotonic())
    except KeyboardInterrupt: pass
    finally: sock.close();out.close()

if __name__=='__main__': main()
