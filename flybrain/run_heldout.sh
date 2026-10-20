#!/bin/bash
# held-out opponents (pool v2): never used for labels/training/selection. seed0 970000, 24 games each, paired with base_t3.
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
OPP=defender,pp0,pp1,pp2,pp5,sac:25600000,sac:50400000,ctl:base_t3,ctl:base
python3 fly_bfm.py --opt ro/opt_b1_frozen.npz --prune-cache cache480 --backend numba --arms fly_t3,base_t3 --opponents $OPP --n 24 --seed0 970000 --workers 2 --out runs/held_dn > runs_held_dn.log 2>&1
python3 fly_bfm.py --opt ro/opt_b1_frozen.feat.npz --arms fly_t3 --opponents $OPP --n 24 --seed0 970000 --workers 2 --out runs/held_feat > runs_held_feat.log 2>&1
echo done > held.done
