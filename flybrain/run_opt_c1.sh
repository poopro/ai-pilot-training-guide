#!/bin/bash
# fresh-seed confirmation, configs frozen (ro/opt_b1_frozen*): seed0 960000, 6 opponents x 24 games, paired with base_t3
cd /home/claude/arena2/ai_pilot/flybrain
export OMP_NUM_THREADS=1
python3 fly_bfm.py --opt ro/opt_b1_frozen.npz --prune-cache cache480 --backend numba --arms fly_t3,base_t3 --n 24 --seed0 960000 --workers 2 --out runs/conf_dn > runs_conf_dn.log 2>&1
python3 fly_bfm.py --opt ro/opt_b1_frozen.feat.npz --arms fly_t3 --n 24 --seed0 960000 --workers 2 --out runs/conf_feat > runs_conf_feat.log 2>&1
echo done > conf_c1.done
