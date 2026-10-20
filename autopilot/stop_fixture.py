"""Request a cooperative stop after the resumed learner has actually progressed."""
import argparse,time
from common import *
p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);a=p.parse_args()
deadline=time.monotonic()+150
while time.monotonic()<deadline:
    progress=read(a.folder/'progress.json',{})
    if progress.get('timesteps',0)>512:
        (a.folder/'STOP').write_text('interrupted',encoding='utf-8');break
    time.sleep(.05)
else:raise SystemExit('未看到實際訓練進度，停止測試失敗')
