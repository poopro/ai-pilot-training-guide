#!/bin/bash
# tactician on top of the user's tuned pursuit, fresh seeds 1010000 (never used for labels / selection)
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
GL=guide,lag
REST=lead,defender,pp0,ctl:tuned,ctl:base_t3
for HEAD in mlp3 feat1; do
  if [ $HEAD = mlp3 ]; then RO=ro/opt_mlp_v3.npz; ARMS=tuned,fly_tuned; else RO=ro/opt_b1_frozen.feat.npz; ARMS=fly_tuned; fi
  python3 -u fly_bfm.py --opt $RO --arms $ARMS --opponents $GL --n 36 --seed0 1010000 --workers 2 --out runs/t1_${HEAD}_gl > runs_t1_${HEAD}_gl.log 2>&1
  python3 -u fly_bfm.py --opt $RO --arms $ARMS --opponents $REST --n 18 --seed0 1010000 --workers 2 --out runs/t1_${HEAD}_rest > runs_t1_${HEAD}_rest.log 2>&1
done
echo done > t1.done
