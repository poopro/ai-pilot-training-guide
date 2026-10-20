#!/bin/bash
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
L="labels/pilot labels/b1 labels/d1a labels/d1b_sac labels/d1b"
python3 -u train_mlp.py --labels $L --alphas 3,10 --out ro/opt_mlp_v3.npz > explore/train_mlp_v3.log 2>&1
python3 -u train_branch.py --labels $L --cache cache480 --out ro/opt_v3.npz > explore/train_v3.log 2>&1
echo done > train_v3.done
