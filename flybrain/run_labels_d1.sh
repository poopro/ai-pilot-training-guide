#!/bin/bash
# DAgger round 1: label states visited by the frozen DN option policy (roll-in), on the two weak opponent types first.
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
COMMON="--rollin opt --opt ro/opt_b1_frozen.npz --prune-cache cache480 --backend numba --hold 6 --horizon 900 --near-stride 10 --far-stride 60 --max-states 48 --no-null --workers 2"
python3 branch_labels.py --opponents lead,sac:25600000 --n 12 --seed0 810000 $COMMON --out labels/d1a > labels_d1a.log 2>&1
echo done > labels_d1a.done
python3 branch_labels.py --opponents guide,lag,defender,pp0 --n 6 --seed0 810000 $COMMON --out labels/d1b > labels_d1b.log 2>&1
echo done > labels_d1b.done
