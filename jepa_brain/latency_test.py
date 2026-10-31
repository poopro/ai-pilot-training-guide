"""Robustness of a blue arm to command latency and observation jitter (2026-10-27).

The Host/LAN path adds delay between the observation the pilot sees and the moment its command is applied.
Here blue's command is applied `delay` ticks late (60 Hz), optionally with Gaussian noise on its own
attitude/rates/position observation.  python latency_test.py OUT.jsonl ARM delays reds n seed0
"""
import sys, json, time
from collections import deque
import numpy as np
import eval_pool3  # noqa: F401
import dcsvet_pool as P
import rollout
from multiprocessing import Pool


def play_delay(cfg, arm, red_kind, delay, noise):
    from arena import Arena
    from opponents import DECISION_TICKS
    t0 = time.time()
    a = Arena(cfg['seed'], cfg['distance_ft'], cfg['side'], cfg['altitude_ft'], host_fidelity=True)
    pilot, pol = P.make_blue(arm)
    red = rollout.ScriptedRed(red_kind, cfg['seed'] + 1)
    rng = np.random.default_rng(cfg['seed'] + 77)
    q = deque([np.array([0., 0., 0., .8])] * delay)
    done = False
    while not done and a.tick < cfg['max_ticks']:
        ob = np.array(a.obs_blue(), dtype=np.float64)
        if noise > 0:
            ob[3:6] += rng.normal(0, .3 * noise, 3)          # deg
            ob[9:12] += rng.normal(0, .01 * noise, 3)        # rad/s
            ob[14] += rng.normal(0, .1 * noise)              # g
        if pol is not None and a.tick % DECISION_TICKS == 0:
            pilot.set_tactic(int(pol.decide(None, ob, a)))
        cmd, _ = pilot.act(ob)
        q.append(np.asarray(cmd, dtype=np.float64))
        done = a.step(q.popleft(), red.act(a.obs_red(), a.tick))
    s = a.judge.snapshot()
    return dict(arm=arm, red=red_kind, delay=delay, noise=noise, seed=cfg['seed'], event=s['event'], winner=s['winner'],
                ticks=s['ticks'], atk_b=s['attack_ticks'][0], atk_r=s['attack_ticks'][1], overg_b=s['over_g_ticks'][0],
                wall=round(time.time() - t0, 1))


def job(x):
    return play_delay(*x)


if __name__ == '__main__':
    out, arm = sys.argv[1], sys.argv[2]
    delays = [int(v) for v in sys.argv[3].split(',')]
    reds = sys.argv[4].split(';')
    n, seed0 = int(sys.argv[5]), int(sys.argv[6])
    noise = float(sys.argv[7]) if len(sys.argv) > 7 else 0.
    args = [(P.game_cfg(seed0 + i, i), arm, r, d, noise) for d in delays for r in reds for i in range(n)]
    with Pool(2) as p, open(out, 'a') as f:
        for r in p.imap_unordered(job, args):
            f.write(json.dumps(r) + '\n'); f.flush()
