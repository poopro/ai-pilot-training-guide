#!/bin/bash
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
while [ ! -f c1.done ]; do sleep 15; done
D="--opt ro/opt_b1_frozen.npz --prune-cache cache480 --backend numba"
python3 -u fly_bfm.py --resume $D --arms fly_tuned --opponents guide,lag,lead,defender,pp0,pp2,pp5,ctl:tuned,ctl:base_t3 --n 24 --seed0 1030000 --workers 2 --out runs/c1_dn1 >> runs_c1_dn1.log 2>&1
python3 -u fly_bfm.py --resume $D --arms fly_tuned --opponents sac:25600000,sac:50400000 --n 24 --seed0 1030000 --workers 2 --out runs/c1_dn1_sac >> runs_c1_dn1_sac.log 2>&1
echo done > c1_dn.done
