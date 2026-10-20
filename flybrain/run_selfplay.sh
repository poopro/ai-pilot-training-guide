#!/bin/bash
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
while [ ! -f c1_dn.done ]; do sleep 15; done
F=$(pwd)/ro/opt_b1_frozen.feat.npz
M=$(pwd)/ro/opt_mlp_v3.npz
python3 -u fly_bfm.py --resume --opt $F --arms fly_tuned,fly_t3,tuned,base_t3 --opponents flyred:$F,flyred:$M --n 24 --seed0 1050000 --workers 2 --out runs/sp1 >> runs_sp1.log 2>&1
echo done > sp1.done
