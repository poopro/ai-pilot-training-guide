#!/bin/bash
# generalisation of MLP v4 to tactician heads it never saw as labels' red side (ridge v3, MLP v2a), seeds 1090000, M4 as blue and as red
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
while [ ! -f c3.done ]; do sleep 15; done
P=$(pwd)
F3=$P/ro/opt_v3.feat.npz; M2=$P/ro/opt_mlp_v2a.npz; M4=$P/ro/opt_mlp_v4.npz
python3 -u fly_bfm.py --resume --opt $M4 --arms fly_t3 --opponents flyred:$F3,flyred:$M2 --n 24 --seed0 1090000 --workers 2 --out runs/rr3_M4 >> runs_rr3_M4.log 2>&1
python3 -u fly_bfm.py --resume --opt $F3 --arms fly_t3 --opponents flyred:$M4 --n 24 --seed0 1090000 --workers 2 --out runs/rr3_F3 >> runs_rr3_F3.log 2>&1
python3 -u fly_bfm.py --resume --opt $M2 --arms fly_t3 --opponents flyred:$M4 --n 24 --seed0 1090000 --workers 2 --out runs/rr3_M2 >> runs_rr3_M2.log 2>&1
echo done > rr3.done
