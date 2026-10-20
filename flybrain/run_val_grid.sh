#!/bin/bash
cd /home/claude/arena2/ai_pilot/flybrain
export OMP_NUM_THREADS=1
run() { # name readout extra...
  name=$1; ro=$2; shift 2
  python3 fly_bfm.py --readout $ro --arms fly_t3 --n 12 --seed0 950000 --workers 2 --out runs/val_$name "$@" > runs_val_$name.log 2>&1
}
run feat_b0   ro/feat_g99.npz --feat
run feat_b3   ro/feat_g99.npz --feat --pursue-bonus 0.3
run dn_b3     ro/dn_g99.npz --prune-cache cache480 --backend numba --pursue-bonus 0.3
run dn_b5     ro/dn_g99.npz --prune-cache cache480 --backend numba --pursue-bonus 0.5
echo ALLDONE > val_grid.done
