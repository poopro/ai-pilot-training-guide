#!/bin/bash
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
while [ ! -f s1_noext.done ]; do sleep 20; done
python3 -u fly_bfm.py --opt ro/opt_v3.npz --prune-cache cache480 --backend numba --arms fly_t3 --opponents sac:25600000 --n 24 --seed0 1000000 --workers 2 --out runs/s1_dn3 > runs_s1_dn3.log 2>&1
echo done > s1_dn3.done
