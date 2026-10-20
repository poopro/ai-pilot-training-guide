#!/bin/bash
# MLP v3 head, fresh-seed check against the scripted pool (same seeds/opponents as c1_feat1) -- collision/lead safety
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
while [ ! -f rr.done ]; do sleep 15; done
python3 -u fly_bfm.py --resume --opt ro/opt_mlp_v3.npz --arms fly_tuned \
   --opponents guide,lag,lead,defender,pp0,pp2,pp5,ctl:tuned,ctl:base_t3,sac:25600000,sac:50400000 --n 24 --seed0 1030000 --workers 2 --out runs/c2_mlp3 >> runs_c2_mlp3.log 2>&1
echo done > c2.done
