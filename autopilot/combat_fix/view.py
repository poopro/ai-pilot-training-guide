"""Run a bounded local duel and open its Tacview replay."""
from pathlib import Path
import argparse
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--p2',choices=['rule','rl'],default='rule')
    parser.add_argument('--bundle',type=Path)
    parser.add_argument('--seed',type=int,default=20271000)
    parser.add_argument('--distance-ft',choices=[3000,6000,9000],type=int,default=3000)
    args=parser.parse_args()
    out=ROOT/'replays'/('duel_'+uuid.uuid4().hex[:8])
    cmd=[sys.executable,'-X','utf8',str(ROOT/'evaluate.py'),'--p2',args.p2,'--controller','repair',
         '--seed',str(args.seed),'--distance-ft',str(args.distance_ft),'--out',str(out)]
    if args.bundle:cmd+=['--bundle',str(args.bundle)]
    print('正在模擬。藍色=P1（你）；紅色=P2。這是本地對戰，官方Host尚未驗證。',flush=True)
    subprocess.run(cmd,check=True,timeout=180)
    tacview=Path(r'C:\Program Files (x86)\Tacview\Tacview64.exe')
    if tacview.exists():subprocess.Popen([str(tacview),str(out/'duel.acmi')])
    else:print('請用Tacview開啟：'+str(out/'duel.acmi'))

if __name__=='__main__':main()
