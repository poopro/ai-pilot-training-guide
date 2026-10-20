#!/bin/bash
# resume after the container restart; then the remaining queued runs
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
REST=lead,defender,pp0,ctl:tuned,ctl:base_t3
python3 -u fly_bfm.py --resume --opt ro/opt_mlp_v3.npz --arms tuned,fly_tuned --opponents $REST --n 18 --seed0 1010000 --workers 2 --out runs/t1_mlp3_rest >> runs_t1_mlp3_rest.log 2>&1
python3 -u fly_bfm.py --resume --opt random:0.15 --arms fly_tuned --opponents $REST --n 18 --seed0 1010000 --workers 2 --out runs/t1_rand_rest >> runs_t1_rand_rest.log 2>&1
echo done > t1_resume.done
