#!/bin/bash
# final confirmation of the simple ridge tactician (frozen v1 head) on seeds nobody has looked at (1030000)
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
while [ ! -f t1_after2.done ]; do sleep 15; done
python3 -u fly_bfm.py --resume --opt ro/opt_b1_frozen.feat.npz --arms tuned,base_t3,fly_tuned,fly_t3 \
   --opponents guide,lag,lead,defender,pp0,pp2,pp5,ctl:tuned,ctl:base_t3 --n 24 --seed0 1030000 --workers 2 --out runs/c1_feat1 >> runs_c1_feat1.log 2>&1
python3 -u fly_bfm.py --resume --opt ro/opt_b1_frozen.feat.npz --arms tuned,base_t3,fly_tuned,fly_t3 \
   --opponents sac:25600000,sac:50400000 --n 24 --seed0 1030000 --workers 2 --out runs/c1_feat1_sac >> runs_c1_feat1_sac.log 2>&1
echo done > c1.done
