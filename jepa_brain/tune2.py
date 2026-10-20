"""ROUND 2 (generated from tune.py). (1+lambda)-ES tuning of the frozen-pursuit constants (bfm.PARAM_SPEC) against the scripted-opponent pool.
Every candidate flies with shield v3. Fitness = weighted mean game utility on common random seeds; a child only
replaces the parent after it also wins on an independent confirmation seed set.

  python tune.py --budget-min 240 --out runs/tune01
Resumable: state in <out>/state.json; best parameters in <out>/best.json.
"""
import argparse, json, time, sys
from pathlib import Path
import numpy as np
import rollout
import rollout_bfm
from common import HERE
from bfm import PARAM_SPEC as _SPEC1, PARAM_DEFAULT as _DEF1
# round 2: add the two corner-speed constants of ParamPilot (defaults reproduce the frozen law exactly)
PARAM_SPEC = dict(_SPEC1, turn_cap_deg=(45., 30., 70.), turn_cap=(290., 240., 380.))
PARAM_DEFAULT = {k: v[0] for k, v in PARAM_SPEC.items()}
_BEST1 = json.loads((HERE / 'runs' / 'tune01' / 'best.json').read_text(encoding='utf-8'))['params']

NAMES = list(PARAM_SPEC)
LO = np.array([PARAM_SPEC[k][1] for k in NAMES]); HI = np.array([PARAM_SPEC[k][2] for k in NAMES])
X0 = np.array([_BEST1.get(k, PARAM_SPEC[k][0]) for k in NAMES])      # parent = tune01 optimum
PLAN = (('guide', 12, 3.0), ('lag', 6, 1.5), ('defender', 6, 1.0), ('pp2', 6, .5))     # multiples of 6 -> both sides balanced


def to_params(x):
    return {k: float(v) for k, v in zip(NAMES, np.clip(x, LO, HI))}


def utility(r):
    if 'error' in r:
        return -1.5
    sign = 1. if r['winner'] == 'blue' else (-1. if r['winner'] == 'red' else 0.)
    return sign + .5 * float(np.clip(r['margin'] / 300., -1., 1.))


def _task(args):
    cfg, params = args
    r = rollout_bfm._task((cfg, {'params': params}))
    r['_u'] = utility(r)
    return r


def evaluate(pool, cands, seed0, max_ticks=18000):
    """cands: list of param dicts -> list of fitness (weighted mean utility), same games for every candidate."""
    tasks, owner, weight = [], [], []
    for ci, p in enumerate(cands):
        for opp, n, w in PLAN:
            for i in range(n):
                cfg = dict(rollout.game_config(i + 5 * [p_[0] for p_ in PLAN].index(opp), seed0, opp, max_ticks), host_fidelity=True)
                tasks.append((cfg, p)); owner.append(ci); weight.append((opp, w, n))
    out = [[] for _ in cands]
    for k, r in enumerate(pool.imap(_task, tasks, chunksize=1)):
        opp, w, n = weight[k]
        out[owner[k]].append((opp, w, n, r['_u']))
    fit = []
    for lst in out:
        by = {}
        for opp, w, n, u in lst:
            by.setdefault(opp, [w, []])[1].append(u)
        fit.append(float(sum(w * np.mean(us) for w, us in by.values()) / sum(w for w, _ in by.values())))
    return fit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--budget-min', type=float, default=240)
    ap.add_argument('--lam', type=int, default=6)
    ap.add_argument('--sigma', type=float, default=.12)
    ap.add_argument('--workers', type=int, default=3)
    ap.add_argument('--out', default='runs/tune02')
    ap.add_argument('--smoke', action='store_true')
    a = ap.parse_args()
    out = HERE / a.out; out.mkdir(parents=True, exist_ok=True)
    st_path = out / 'state.json'
    rng = np.random.default_rng(12345)
    if st_path.exists():
        st = json.loads(st_path.read_text())
        parent = np.array(st['parent']); sigma = st['sigma']; gen = st['gen']
    else:
        parent = X0.copy(); sigma = a.sigma; gen = 0
    t_end = time.time() + a.budget_min * 60
    import multiprocessing as mp
    pool = mp.get_context('spawn').Pool(a.workers, maxtasksperchild=40)
    if a.smoke:
        t0 = time.time()
        f = evaluate(pool, [to_params(X0), to_params(X0 + .05 * (HI - LO))], 1199000, max_ticks=1200)
        print('SMOKE fitness (defaults, +5%% perturbed):', f, 'in %.0fs' % (time.time() - t0), flush=True)
        pool.terminate()
        return
    log = (out / 'log.jsonl').open('a', encoding='utf-8')
    span = HI - LO
    while time.time() < t_end - 1500:      # a generation needs ~25 min; do not start one that cannot finish
        seed0 = 1200000 + gen * 1000
        kids = [np.clip(parent + sigma * span * rng.standard_normal(len(NAMES)), LO, HI) for _ in range(a.lam)]
        fit = evaluate(pool, [to_params(parent)] + [to_params(k) for k in kids], seed0)
        fp, fk = fit[0], fit[1:]
        b = int(np.argmax(fk))
        accepted = False
        conf = None
        if fk[b] > fp + .02:
            conf = evaluate(pool, [to_params(parent), to_params(kids[b])], seed0 + 500)
            if conf[1] > conf[0]:
                parent = kids[b]; accepted = True
        sigma = float(np.clip(sigma * (1.2 if accepted else .85), .03, .3))
        gen += 1
        rec = dict(gen=gen, t=time.strftime('%F %T'), parent_fit=round(fp, 4), best_kid_fit=round(fk[b], 4), conf=conf, accepted=accepted,
                   sigma=round(sigma, 4), parent=to_params(parent))
        log.write(json.dumps(rec, ensure_ascii=False) + '\n'); log.flush()
        print(json.dumps(rec, ensure_ascii=False), flush=True)
        st_path.write_text(json.dumps(dict(parent=parent.tolist(), sigma=sigma, gen=gen)))
        (out / 'best.json').write_text(json.dumps(dict(params=to_params(parent), gen=gen, default=PARAM_DEFAULT), indent=1))
    pool.terminate()
    print('TUNE DONE gen', gen, flush=True)


if __name__ == '__main__':
    main()
