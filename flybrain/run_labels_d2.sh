#!/bin/bash
# DAgger round 2: SELF-PLAY labels.  Blue roll-in = MLP v3 tactician; red = a fly-style tactician (ridge v1 / MLP v3) on the same frozen pilot.
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
while [ ! -f c2.done ]; do sleep 15; done
P=$(pwd)
COMMON="--rollin opt --opt ro/opt_mlp_v3.npz --hold 6 --horizon 900 --workers 2 --no-null --near-stride 8 --far-stride 60 --max-states 40"
python3 branch_labels.py --opponents flyred:$P/ro/opt_b1_frozen.feat.npz,flyred:$P/ro/opt_mlp_v3.npz --n 8 --seed0 811100 $COMMON --out labels/d2 > labels_d2.log 2>&1
echo done > labels_d2.done
