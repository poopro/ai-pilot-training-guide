#!/bin/bash
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
python3 -u fly_bfm.py --opt random:0.15 --arms fly_tuned --opponents lead,defender,pp0,ctl:tuned,ctl:base_t3 --n 18 --seed0 1010000 --workers 2 --out runs/t1_rand_rest > runs_t1_rand_rest.log 2>&1
echo done > t1_rand_rest.done
