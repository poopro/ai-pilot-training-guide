#!/bin/bash
# information-free control on top of tuned pursuit, same games as runs/t1_mlp3_gl (seeds 1010000)
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
python3 -u fly_bfm.py --opt random:0.15 --arms fly_tuned --opponents guide,lag --n 36 --seed0 1010000 --workers 2 --out runs/t1_rand_gl > runs_t1_rand_gl.log 2>&1
echo done > t1_rand.done
