#!/bin/bash
# tuning-seed (1070000) comparison: MLP v4 (DAgger round 2: self-play + lead) vs MLP v3 as blue head (fly_t3), against lead / MLP-v3 red / ridge-v1 red
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
P=$(pwd)
OPP="lead,flyred:$P/ro/opt_mlp_v3.npz,flyred:$P/ro/opt_b1_frozen.feat.npz"
python3 -u fly_bfm.py --resume --opt ro/opt_mlp_v4.npz --arms fly_t3 --opponents "$OPP" --n 24 --seed0 1070000 --workers 2 --out runs/m4_v4tau10 >> runs_m4_v4tau10.log 2>&1
python3 -u fly_bfm.py --resume --opt ro/opt_mlp_v4.npz --tau 0 --arms fly_t3 --opponents "$OPP" --n 24 --seed0 1070000 --workers 2 --out runs/m4_v4tau0 >> runs_m4_v4tau0.log 2>&1
python3 -u fly_bfm.py --resume --opt ro/opt_mlp_v3.npz --arms fly_t3 --opponents "$OPP" --n 24 --seed0 1070000 --workers 2 --out runs/m4_v3 >> runs_m4_v3.log 2>&1
echo done > m4.done
