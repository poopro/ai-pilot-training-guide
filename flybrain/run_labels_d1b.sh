#!/bin/bash
# DAgger round 1b (the 7 failed SAC games of d1a are redone, with denser far-range labels and a reduced option set)
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
COMMON="--rollin opt --opt ro/opt_b1_frozen.npz --prune-cache cache480 --backend numba --hold 6 --horizon 900 --workers 2"
python3 branch_labels.py --opponents sac:25600000 --n 8 --seed0 811000 $COMMON --options 0,1,2,3,6 --near-stride 6 --far-stride 12 --max-states 48 --no-null --out labels/d1b_sac > labels_d1b_sac.log 2>&1
python3 branch_labels.py --opponents defender,guide,lag,pp0 --n 4 --seed0 811000 $COMMON --options 0,1,2,3,5,6 --near-stride 10 --far-stride 60 --max-states 40 --no-null --out labels/d1b > labels_d1b.log 2>&1
echo done > labels_d1b.done
