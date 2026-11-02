"""League: arms x reds, 12 games each (3 distances x 2 sides x 2 seeds) -> jsonl."""
import sys, json, os
import dcsvet_pool as P
from multiprocessing import Pool
REDS = ['guide', 'lead', 'lag', 'mix', 'breaker', 'level', 'weave', 'jink', 'vosc', 'hturn', 'defender',
        'pp0', 'pp1', 'pp2', 'pp3', 'pp4', 'pp5', 'ctl:base_t3', 'ctl:tuned', 'ctl:user_nz_t', 'dcsvet:runs/bc_ace_night.npz']
def job(a):
    cfg, arm, red = a
    r = P.play(cfg, arm, red)
    r['arm'] = arm; r['red_full'] = red
    return r
if __name__ == '__main__':
    out = sys.argv[1]; arms = sys.argv[2].split(','); n = int(sys.argv[3]) if len(sys.argv) > 3 else 12
    seed0 = int(sys.argv[4]) if len(sys.argv) > 4 else 990000
    args = [(P.game_cfg(seed0 + i, i), arm, red) for arm in arms for red in REDS for i in range(n)]
    with Pool(2) as p, open(out, 'a') as f:
        for r in p.imap_unordered(job, args):
            f.write(json.dumps(r) + '\n'); f.flush()
