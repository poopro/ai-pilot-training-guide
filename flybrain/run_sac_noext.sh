#!/bin/bash
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
OPP=sac:25600000
python3 -u fly_bfm.py --opt ro/opt_mlp_v3.npz --only 1,2,3,4,5,6 --arms fly_t3 --opponents $OPP --n 24 --seed0 1000000 --workers 2 --out runs/s1_mlp3_noext > runs_s1_mlp3_noext.log 2>&1
python3 -u fly_bfm.py --opt ro/opt_b1_frozen.feat.npz --arms fly_t3 --opponents $OPP --n 24 --seed0 1000000 --workers 2 --out runs/s1_feat1 > runs_s1_feat1.log 2>&1
python3 -u fly_bfm.py --opt ro/opt_b1_frozen.feat.npz --only 1,2,3,4,5,6 --arms fly_t3 --opponents $OPP --n 24 --seed0 1000000 --workers 2 --out runs/s1_feat1_noext > runs_s1_feat1_noext.log 2>&1
echo done > s1_noext.done
