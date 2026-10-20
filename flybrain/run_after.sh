#!/bin/bash
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
while [ ! -f t1_resume.done ]; do sleep 15; done
GL=guide,lag
REST=lead,defender,pp0,ctl:tuned,ctl:base_t3
F=ro/opt_b1_frozen.feat.npz
python3 -u fly_bfm.py --resume --opt $F --arms fly_tuned --opponents $GL --n 36 --seed0 1010000 --workers 2 --out runs/t1_feat1_gl >> runs_t1_feat1_gl.log 2>&1
python3 -u fly_bfm.py --resume --opt $F --arms fly_tuned --opponents $REST --n 18 --seed0 1010000 --workers 2 --out runs/t1_feat1_rest >> runs_t1_feat1_rest.log 2>&1
python3 -u fly_bfm.py --resume --opt ro/opt_mlp_v3.npz --arms base_t3,fly_t3 --opponents $GL --n 36 --seed0 1010000 --workers 2 --out runs/t1_mlp3_b3_gl >> runs_t1_mlp3_b3_gl.log 2>&1
python3 -u fly_bfm.py --resume --opt ro/opt_mlp_v3.npz --arms base_t3,fly_t3 --opponents $REST --n 18 --seed0 1010000 --workers 2 --out runs/t1_mlp3_b3_rest >> runs_t1_mlp3_b3_rest.log 2>&1
python3 -u fly_bfm.py --resume --opt ro/opt_b1_frozen.npz --prune-cache cache480 --backend numba --arms fly_tuned --opponents $GL --n 36 --seed0 1010000 --workers 2 --out runs/t1_dn1_gl >> runs_t1_dn1_gl.log 2>&1
python3 -u fly_bfm.py --resume --opt ro/opt_b1_frozen.npz --prune-cache cache480 --backend numba --arms fly_tuned --opponents $REST --n 18 --seed0 1010000 --workers 2 --out runs/t1_dn1_rest >> runs_t1_dn1_rest.log 2>&1
echo done > t1_after.done
