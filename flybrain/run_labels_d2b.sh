#!/bin/bash
# DAgger round 2b: MLP v3 roll-in against the scripted lead opponent (where MLP/DN lose ground)
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
while [ ! -f labels_d2.done ]; do sleep 15; done
python3 branch_labels.py --opponents lead --n 10 --seed0 811200 --rollin opt --opt ro/opt_mlp_v3.npz --hold 6 --horizon 900 --workers 2 --no-null --near-stride 8 --far-stride 60 --max-states 40 --out labels/d2 > labels_d2b.log 2>&1
echo done > labels_d2b.done
