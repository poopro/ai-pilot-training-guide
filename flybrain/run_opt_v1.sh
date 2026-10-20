#!/bin/bash
cd /home/claude/arena2/ai_pilot/flybrain
export OMP_NUM_THREADS=1
python3 fly_bfm.py --opt ro/opt_b1.feat.npz --arms fly_t3 --opponents guide,lead,lag --n 12 --seed0 950000 --workers 2 --out runs/opt_b1_feat > runs_opt_b1_feat.log 2>&1
python3 fly_bfm.py --opt ro/opt_b1.npz --prune-cache cache480 --backend numba --arms fly_t3 --opponents guide,lead,lag --n 12 --seed0 950000 --workers 2 --out runs/opt_b1_dn > runs_opt_b1_dn.log 2>&1
echo done > opt_v1.done
