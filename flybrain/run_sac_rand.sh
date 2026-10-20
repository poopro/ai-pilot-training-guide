#!/bin/bash
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
python3 -u fly_bfm.py --opt random:0.15 --arms fly_t3 --opponents sac:25600000 --n 24 --seed0 1000000 --workers 2 --out runs/s1_rand15 > runs_s1_rand15.log 2>&1
echo done > s1_rand.done
