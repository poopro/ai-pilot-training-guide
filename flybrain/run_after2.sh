#!/bin/bash
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
while [ ! -f t1_after.done ]; do sleep 15; done
GL=guide,lag
REST=lead,defender,pp0,ctl:tuned,ctl:base_t3
F=ro/opt_v3.feat.npz
python3 -u fly_bfm.py --resume --opt $F --arms fly_tuned --opponents $GL --n 36 --seed0 1010000 --workers 2 --out runs/t1_feat3_gl >> runs_t1_feat3_gl.log 2>&1
python3 -u fly_bfm.py --resume --opt $F --arms fly_tuned --opponents $REST --n 18 --seed0 1010000 --workers 2 --out runs/t1_feat3_rest >> runs_t1_feat3_rest.log 2>&1
echo done > t1_after2.done
