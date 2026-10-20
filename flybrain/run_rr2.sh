#!/bin/bash
# confirmation of MLP v4 on seeds 1090000: head-to-head vs F1 / M3 / M4 (both colours), then the scripted pool on the usual fresh seeds 1030000
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
P=$(pwd)
F1=$P/ro/opt_b1_frozen.feat.npz; M3=$P/ro/opt_mlp_v3.npz; M4=$P/ro/opt_mlp_v4.npz
python3 -u fly_bfm.py --resume --opt $M4 --arms fly_t3 --opponents flyred:$F1,flyred:$M3,flyred:$M4 --n 24 --seed0 1090000 --workers 2 --out runs/rr2_M4 >> runs_rr2_M4.log 2>&1
python3 -u fly_bfm.py --resume --opt $M3 --arms fly_t3 --opponents flyred:$M4 --n 24 --seed0 1090000 --workers 2 --out runs/rr2_M3 >> runs_rr2_M3.log 2>&1
python3 -u fly_bfm.py --resume --opt $F1 --arms fly_t3 --opponents flyred:$M4 --n 24 --seed0 1090000 --workers 2 --out runs/rr2_F1 >> runs_rr2_F1.log 2>&1
echo done > rr2.done
python3 -u fly_bfm.py --resume --opt ro/opt_mlp_v4.npz --arms fly_tuned --opponents guide,lag,lead,defender,pp0,pp2,pp5,ctl:tuned,ctl:base_t3,sac:25600000,sac:50400000 --n 24 --seed0 1030000 --workers 2 --out runs/c3_mlp4 >> runs_c3_mlp4.log 2>&1
echo done > c3.done
