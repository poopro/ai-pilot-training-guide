import sys, json
import eval_pool3  # noqa: F401  adv:/sacn: opponents, tuned2w arms
import dcsvet_pool as P
from multiprocessing import Pool
def job(a):
    cfg, arm, red = a
    r = P.play(cfg, arm, red); r['arm'] = arm; r['red_full'] = red; return r
if __name__ == '__main__':
    out, arm, reds, n, seed0 = sys.argv[1], sys.argv[2], sys.argv[3].split(';'), int(sys.argv[4]), int(sys.argv[5])
    args = [(P.game_cfg(seed0 + i, i), arm, red) for red in reds for i in range(n)]
    with Pool(2) as p, open(out, 'a') as f:
        for r in p.imap_unordered(job, args):
            f.write(json.dumps(r) + '\n'); f.flush()
