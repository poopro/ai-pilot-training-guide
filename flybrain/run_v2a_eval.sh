#!/bin/bash
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
# candidate-selection seeds 980000 (core opponents). lead x24, guide x12, lag x12 -> run guide/lag with n=12 and lead with n=24
run() { # name opt extra...
  name=$1; opt=$2; shift 2
  python3 fly_bfm.py --opt $opt --opponents lead --n 24 --seed0 980000 --workers 2 --out runs/v2a_$name "$@" > runs_v2a_$name.log 2>&1
  python3 fly_bfm.py --opt $opt --opponents guide,lag --n 12 --seed0 980000 --workers 2 --out runs/v2a_${name}_gl "$@" > runs_v2a_${name}_gl.log 2>&1
}
run mlp ro/opt_mlp_v2a.npz --arms fly_t3,base_t3
run feat1 ro/opt_b1_frozen.feat.npz --arms fly_t3
run dn2a ro/opt_v2a.npz --arms fly_t3 --prune-cache cache480 --backend numba
run dn1 ro/opt_b1_frozen.npz --arms fly_t3 --prune-cache cache480 --backend numba
echo done > v2a_eval.done
