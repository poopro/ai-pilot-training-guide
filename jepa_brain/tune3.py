"""ROUND 3 (2026-10-23): (1+lambda)-ES of the tuned2 pursuit constants PLUS the final bank clip (bank_cap 72-88 deg),
against a pool that includes the adversarial opponents, with a worst-group objective.

Why: the adversarial search showed every opponent that turns harder than us (bank > our clip) sits on our tail all game
(tuned2 0-48 vs the f1s family). Widening to 80 deg helped (wide1/wide2) but round-2 search still finds 84-deg
opponents that beat it. Here the clip is tuned jointly with the other constants, and the fitness cares about the worst family.

  python tune3.py --budget-min 720 --workers 7 --out runs/tune03      (resumable: state in <out>/state.json)
  python tune3.py --smoke --workers 2                                   (two short candidates, ~2 min)

Pilot: wide_pilot.WidePilot(params) + collision shield v3, FixedTactic (PURSUE) -- the same pilot as arm tuned2w:<cap>.
Families (train):  mirror = guide (x2 weight) | lag | defender | pp2 | adv = f1s_0..3 | sac = sacn:25600000 | mirror72 = ctl:tuned2
Fitness = 0.5 * weighted mean family utility + 0.5 * min family utility; game utility = sign(winner) + 0.5*clip(margin/300).
A child replaces the parent only if it is better on the generation seeds by > 0.02 AND on an independent confirmation set.
Held out (never used here): round-2 search opponents (adv_f2w80), SAC 22.4/24.0/26.4M, lead, pp0, pp5, ctl:base_t3.
"""
import argparse, json, time
from pathlib import Path
import numpy as np
import pool3  # noqa: F401  adv:<name>, sacn:<N> opponents (patch active in spawned workers: they re-import this module)
import rollout
import rollout_bfm
import wide_pilot
from common import HERE

_make = rollout_bfm.make_arm


def make_arm(name):
    if isinstance(name, dict) and 'wide' in name:
        return wide_pilot.WidePilot(name['wide']), rollout_bfm.FixedTactic()
    if name == 'tuned2':
        return _make({'params': wide_pilot.tuned2_params()})
    return _make(name)


rollout_bfm.make_arm = make_arm

BEST2 = wide_pilot.tuned2_params()
SPEC = {   # name: (low, high)
    'kp_head': (1.0, 3.0), 'hold_m': (250., 1200.), 'close_gain': (.03, .15), 'lead_blend': (0., .8), 'near_m': (700., 1600.),
    'elev_rate_gain': (0., 1.2), 'ff_gain': (0., 1.5), 'turn_cap_deg': (30., 70.), 'turn_cap': (240., 380.), 'bank_cap': (72., 88.),
}
NAMES = list(SPEC)
LO = np.array([SPEC[k][0] for k in NAMES]); HI = np.array([SPEC[k][1] for k in NAMES])
X0 = np.array([dict(BEST2, bank_cap=80.)[k] for k in NAMES])
# family, opponents, games per opponent (multiple of 6 -> both sides x 3 distances), weight in the mean
PLAN = (('mirror', ('guide',), 12, 2.0), ('lag', ('lag',), 6, 1.0), ('defender', ('defender',), 6, 1.0), ('pp', ('pp2',), 6, .5),
        ('adv', ('adv:f1s_0', 'adv:f1s_1', 'adv:f1s_2', 'adv:f1s_3'), 6, 1.5), ('sac', ('sacn:25600000',), 6, 1.0),
        ('mirror72', ('ctl:tuned2',), 6, 1.0))


def to_params(x):
    p = dict(BEST2)
    p.update({k: float(v) for k, v in zip(NAMES, np.clip(x, LO, HI))})
    return p


def utility(r):
    if 'error' in r:
        return -1.5
    sign = 1. if r['winner'] == 'blue' else (-1. if r['winner'] == 'red' else 0.)
    return sign + .5 * float(np.clip(r['margin'] / 300., -1., 1.))


def _task(args):
    cfg, params = args
    r = rollout_bfm._task((cfg, {'wide': params}))
    r['_u'] = utility(r)
    return r


def evaluate(pool, cands, seed0, max_ticks=18000):
    """cands: list of param dicts -> (fitness list, per-family utilities list); same games for every candidate."""
    tasks, owner = [], []
    for ci, p in enumerate(cands):
        for fi, (fam, opps, n, w) in enumerate(PLAN):
            for oi, opp in enumerate(opps):
                for i in range(n):
                    cfg = dict(rollout.game_config(i, seed0 + 100 * fi + 20 * oi, opp, max_ticks), host_fidelity=True)
                    tasks.append((cfg, p)); owner.append((ci, fam))
    us = [dict() for _ in cands]
    for k, r in enumerate(pool.imap(_task, tasks, chunksize=1)):
        ci, fam = owner[k]
        us[ci].setdefault(fam, []).append(r['_u'])
    fits, fams = [], []
    for d in us:
        fm = {fam: float(np.mean(v)) for fam, v in d.items()}
        wmean = sum(w * fm[fam] for fam, _, _, w in PLAN) / sum(w for *_, w in PLAN)
        fits.append(.5 * wmean + .5 * min(fm.values()))
        fams.append({k: round(v, 3) for k, v in fm.items()})
    return fits, fams


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--budget-min', type=float, default=720)
    ap.add_argument('--lam', type=int, default=6)
    ap.add_argument('--sigma', type=float, default=.12)
    ap.add_argument('--workers', type=int, default=7)
    ap.add_argument('--out', default='runs/tune03')
    ap.add_argument('--gen-minutes', type=float, default=60, help='expected minutes per generation (no new gen near the budget end)')
    ap.add_argument('--smoke', action='store_true')
    a = ap.parse_args()
    import os
    if os.name == 'nt':   # keep Windows awake while tuning (no setting is changed)
        try:
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
        except Exception:
            pass
    out = HERE / a.out; out.mkdir(parents=True, exist_ok=True)
    st_path = out / 'state.json'
    rng = np.random.default_rng(23456)
    if st_path.exists():
        st = json.loads(st_path.read_text())
        parent = np.array(st['parent']); sigma = st['sigma']; gen = st['gen']
        rng = np.random.default_rng(23456 + gen)
    else:
        parent = X0.copy(); sigma = a.sigma; gen = 0
    t_end = time.time() + a.budget_min * 60
    import multiprocessing as mp
    pool = mp.get_context('spawn').Pool(a.workers, maxtasksperchild=40)
    if a.smoke:
        t0 = time.time()
        f, fam = evaluate(pool, [to_params(X0), to_params(np.clip(X0 + .05 * (HI - LO), LO, HI))], 7199000, max_ticks=600)
        print('SMOKE fitness', [round(x, 3) for x in f], fam, 'in %.0fs' % (time.time() - t0), flush=True)
        pool.terminate()
        return
    log = (out / 'log.jsonl').open('a', encoding='utf-8')
    span = HI - LO
    while time.time() < t_end - a.gen_minutes * 60:
        seed0 = 7200000 + gen * 1000
        kids = [np.clip(parent + sigma * span * rng.standard_normal(len(NAMES)), LO, HI) for _ in range(a.lam)]
        t0 = time.time()
        fit, fam = evaluate(pool, [to_params(parent)] + [to_params(k) for k in kids], seed0)
        fp, fk = fit[0], fit[1:]
        b = int(np.argmax(fk))
        accepted, conf = False, None
        if fk[b] > fp + .02:
            conf, _ = evaluate(pool, [to_params(parent), to_params(kids[b])], seed0 + 500)
            if conf[1] > conf[0]:
                parent = kids[b]; accepted = True
        sigma = float(np.clip(sigma * (1.2 if accepted else .85), .03, .3))
        gen += 1
        rec = dict(gen=gen, t=time.strftime('%F %T'), minutes=round((time.time() - t0) / 60, 1), parent_fit=round(fp, 4),
                   parent_families=fam[0], best_kid_fit=round(fk[b], 4), best_kid_families=fam[1 + b], conf=conf,
                   accepted=accepted, sigma=round(sigma, 4), parent={k: round(v, 4) for k, v in to_params(parent).items() if k in NAMES})
        log.write(json.dumps(rec, ensure_ascii=False) + '\n'); log.flush()
        print(json.dumps(rec, ensure_ascii=False), flush=True)
        st_path.write_text(json.dumps(dict(parent=parent.tolist(), sigma=sigma, gen=gen)))
        (out / 'best.json').write_text(json.dumps(dict(params=to_params(parent), gen=gen, names=NAMES), indent=1))
    pool.terminate()
    print('TUNE DONE gen', gen, flush=True)


if __name__ == '__main__':
    main()
