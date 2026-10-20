#!/bin/bash
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
OPP=sac:25600000
while pgrep -f "out runs/s1_mlp" > /dev/null; do sleep 15; done
python3 -u fly_bfm.py --opt ro/opt_mlp_v3.npz --arms fly_t3 --opponents $OPP --n 24 --seed0 1000000 --workers 2 --out runs/s1_mlp3 > runs_s1_mlp3.log 2>&1
python3 -u fly_bfm.py --opt ro/opt_b1_frozen.npz --prune-cache cache480 --backend numba --arms fly_t3 --opponents $OPP --n 24 --seed0 1000000 --workers 2 --out runs/s1_dn1 > runs_s1_dn1.log 2>&1
echo done > s1_v3.done
