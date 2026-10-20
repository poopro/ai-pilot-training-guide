#!/bin/bash
# head-to-head round robin of option-tactician heads (same frozen pilot + shield on both sides; only the head differs)
cd /home/claude/arena3/ai_pilot/flybrain
export OMP_NUM_THREADS=1
P=$(pwd)
F1=$P/ro/opt_b1_frozen.feat.npz; F3=$P/ro/opt_v3.feat.npz; M3=$P/ro/opt_mlp_v3.npz; M2=$P/ro/opt_mlp_v2a.npz; R=random:0.15
OPP="flyred:$F1,flyred:$F3,flyred:$M3,flyred:$M2,flyred:$R"
mkdir -p runs/rr_F1
# reuse the F1 blue rows already played in sp1 (same seeds, same arm, same red names)
python3 - <<'PY'
import json
out = open('runs/rr_F1/results.jsonl', 'a')
seen = set()
try:
    for l in open('runs/rr_F1/results.jsonl'):
        r = json.loads(l); seen.add((r['red'], r['seed'], r['policy']))
except Exception:
    pass
n = 0
for l in open('runs/sp1/results.jsonl'):
    r = json.loads(l)
    if 'error' in r or r['policy'] != 'fly_t3' or 'opt_b1_frozen.feat' not in r['red'].split('/')[-1] and 'opt_mlp_v3' not in r['red'].split('/')[-1]:
        continue
    k = (r['red'], r['seed'], r['policy'])
    if k not in seen:
        out.write(l if l.endswith('\n') else l + '\n'); n += 1
print('reused', n)
PY
for H in F1 F3 M3 M2 R; do
  eval "O=\$$H"
  python3 -u fly_bfm.py --resume --opt $O --arms fly_t3 --opponents "$OPP" --n 24 --seed0 1050000 --workers 2 --out runs/rr_$H >> runs_rr_$H.log 2>&1
done
echo done > rr.done
