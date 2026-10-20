#!/bin/bash
# ensemble head = 0.5 ridge v1 + 0.5 MLP v4  (tuning seeds 1070000, same protocol as run_m4.sh)
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
P=$(pwd)
OPP="lead,flyred:$P/ro/opt_mlp_v3.npz,flyred:$P/ro/opt_b1_frozen.feat.npz"
E="$P/ro/opt_b1_frozen.feat.npz+$P/ro/opt_mlp_v4.npz"
python3 -u fly_bfm.py --resume --opt "$E" --arms fly_t3 --opponents "$OPP" --n 24 --seed0 1070000 --workers 2 --out runs/m4_ens >> runs_m4_ens.log 2>&1
echo done > ens.done
