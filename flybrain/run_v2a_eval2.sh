#!/bin/bash
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
STRONG=ctl:tuned,ctl:user_nz_t
OTHER=pp3,pp4,sac:10400000,sac:1600000,sacc:1000000,hturn
python3 fly_bfm.py --opt ro/opt_mlp_v2a.npz --arms fly_t3,base_t3 --opponents $STRONG --n 24 --seed0 990000 --workers 2 --out runs/v2a_mlp_strong > runs_v2a_mlp_strong.log 2>&1
python3 fly_bfm.py --opt ro/opt_b1_frozen.feat.npz --arms fly_t3 --opponents $STRONG --n 24 --seed0 990000 --workers 2 --out runs/v2a_feat1_strong > runs_v2a_feat1_strong.log 2>&1
python3 fly_bfm.py --opt ro/opt_b1_frozen.npz --prune-cache cache480 --backend numba --arms fly_t3 --opponents $STRONG --n 24 --seed0 990000 --workers 2 --out runs/v2a_dn1_strong > runs_v2a_dn1_strong.log 2>&1
python3 fly_bfm.py --opt ro/opt_mlp_v2a.npz --arms fly_t3,base_t3 --opponents $OTHER --n 12 --seed0 990000 --workers 2 --out runs/v2a_mlp_other > runs_v2a_mlp_other.log 2>&1
python3 fly_bfm.py --opt ro/opt_b1_frozen.feat.npz --arms fly_t3 --opponents $OTHER --n 12 --seed0 990000 --workers 2 --out runs/v2a_feat1_other > runs_v2a_feat1_other.log 2>&1
echo done > v2a_eval2.done
