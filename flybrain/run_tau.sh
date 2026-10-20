#!/bin/bash
# conservative threshold for the MLP head: does a larger tau remove the lead weakness without losing self-play strength?  (tuning seeds 1070000)
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
P=$(pwd)
for T in 0 20 40 80; do
  python3 -u fly_bfm.py --resume --opt ro/opt_mlp_v3.npz --tau $T --arms fly_tuned --opponents lead,flyred:$P/ro/opt_b1_frozen.feat.npz --n 24 --seed0 1070000 --workers 1 --out runs/tau_$T >> runs_tau_$T.log 2>&1
done
echo done > tau.done
