#!/bin/bash
# ridge v4 (raw features, same 103 games of labels as MLP v4): tuning seeds, head-to-head, scripted pool
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
while [ ! -f rr3.done ]; do sleep 15; done
P=$(pwd)
F1=$P/ro/opt_b1_frozen.feat.npz; M3=$P/ro/opt_mlp_v3.npz; M4=$P/ro/opt_mlp_v4.npz; F4=$P/ro/opt_v4.feat.npz
python3 -u fly_bfm.py --resume --opt $F4 --arms fly_t3 --opponents "lead,flyred:$M3,flyred:$F1" --n 24 --seed0 1070000 --workers 2 --out runs/m4_F4 >> runs_m4_F4.log 2>&1
python3 -u fly_bfm.py --resume --opt $F4 --arms fly_t3 --opponents flyred:$F1,flyred:$M3,flyred:$M4 --n 24 --seed0 1090000 --workers 2 --out runs/rr4_F4 >> runs_rr4_F4.log 2>&1
python3 -u fly_bfm.py --resume --opt $M4 --arms fly_t3 --opponents flyred:$F4 --n 24 --seed0 1090000 --workers 2 --out runs/rr4_M4 >> runs_rr4_M4.log 2>&1
python3 -u fly_bfm.py --resume --opt $M3 --arms fly_t3 --opponents flyred:$F4 --n 24 --seed0 1090000 --workers 2 --out runs/rr4_M3 >> runs_rr4_M3.log 2>&1
echo done > f4_rr.done
python3 -u fly_bfm.py --resume --opt $F4 --arms fly_tuned --opponents guide,lag,lead,defender,pp0,pp2,pp5,ctl:tuned,ctl:base_t3,sac:25600000,sac:50400000 --n 24 --seed0 1030000 --workers 2 --out runs/c4_feat4 >> runs_c4_feat4.log 2>&1
echo done > f4.done
