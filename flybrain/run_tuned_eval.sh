#!/bin/bash
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
while [ ! -f v2a_eval2.done ]; do sleep 20; done
python3 fly_bfm.py --opt ro/opt_mlp_v2a.npz --arms fly_t3,base_t3 --opponents ctl:tuned --n 24 --seed0 990000 --workers 2 --out runs/v2a_mlp_tuned > runs_v2a_mlp_tuned.log 2>&1
python3 fly_bfm.py --opt ro/opt_b1_frozen.feat.npz --arms fly_t3 --opponents ctl:tuned --n 24 --seed0 990000 --workers 2 --out runs/v2a_feat1_tuned > runs_v2a_feat1_tuned.log 2>&1
python3 fly_bfm.py --opt ro/opt_b1_frozen.npz --prune-cache cache480 --backend numba --arms fly_t3 --opponents ctl:tuned --n 24 --seed0 990000 --workers 2 --out runs/v2a_dn1_tuned > runs_v2a_dn1_tuned.log 2>&1
echo done > tuned_eval.done
