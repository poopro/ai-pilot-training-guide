"""(1+lambda)-ES on the close-range finisher parameters of tuned2f (2026-10-27).

Blue = tuned2 + finisher (dcsvet_pool arm 'tuned2f:<k=v>...'), starting from F4 (runs/eval_fin/F4.txt).
Fitness = 0.5 * mean family utility + 0.5 * worst family utility, families:
  general : guide, lag, lead, defender, hturn, pp2
  turn    : adversarial turn-fighters (adv:f1s_1, adv:f2w80_02 and the confirmed adv_pool/fin1_* found against F4)
  sac     : sacn:22400000, sacn:25600000
  mirror  : arm=<current F4>   (never get worse than the version we already have)
Game utility = +-1 (winner) + 0.5*clip(margin/3000,-1,1) + 0.5*(blue kill) - 1.0*(blue shot down / collision / crash).
A child is accepted only if it beats the parent on the generation seeds AND on separate confirmation seeds
(both evaluated paired on the same seeds).  Resumable: state in <out>/state.json, log in <out>/log.jsonl.

  python tune_fin.py --out runs/tune_fin1 --gens 12 --lam 6
"""
import argparse, json, math, time, glob
from pathlib import Path
import numpy as np
import eval_pool3  # noqa: F401  (adv:, sacn:, tuned2w)
import dcsvet_pool as P
from multiprocessing import Pool
from common import HERE

SPACE = dict(k_ang=(1.2, 3.5), k_ff=(.5, 1.5), hold_m=(350., 750.), turn_cas=(280., 420.), n_cap=(7.5, 9.5),
             enter_m=(2000., 4000.), merge_off_m=(250., 700.), k_spd=(.05, .2), tcpa_s=(2., 4.), miss_m=(100., 250.))
FIXED = dict(aa_max=180., enter_deg=180., exit_deg=180.)


def f4_params():
    s = (HERE / 'runs' / 'eval_fin' / 'F4.txt').read_text().strip()
    d = {kv.split('=')[0]: float(kv.split('=')[1]) for kv in s.split(':')[1:]}
    p = {k: d.get(k, None) for k in SPACE}
    defaults = dict(k_ang=2.2, k_ff=1.0, hold_m=500., turn_cas=340., n_cap=8., enter_m=3000., merge_off_m=400., k_spd=.12, tcpa_s=3., miss_m=150.)
    return {k: (p[k] if p[k] is not None else defaults[k]) for k in SPACE}


def arm_of(p):
    q = dict(FIXED, **p)
    q['exit_m'] = q['enter_m'] + 500.
    return 'tuned2f:' + ':'.join('%s=%.4g' % (k, v) for k, v in q.items())


def families(f4_arm):
    turn = ['adv:f1s_1', 'adv:f2w80_02'] + ['adv:' + Path(f).stem for f in sorted(glob.glob(str(HERE / 'adv_pool' / 'fin1_*.json')))][:4]
    return dict(general=['guide', 'lag', 'lead', 'defender', 'hturn', 'pp2'], turn=turn,
                sac=['sacn:22400000', 'sacn:25600000'], mirror=['arm=' + f4_arm])


def util(r):
    w = 1. if r['winner'] == 'blue' else (-1. if r['winner'] == 'red' else 0.)
    u = w + .5 * float(np.clip(r['margin'] / 3000., -1, 1)) + .5 * (r['event'] == 'blue_kill')
    if r['event'] in ('red_kill', 'collision', 'blue_crash'):
        u -= 1.
    return u


def job(t):
    key, cfg, arm, red = t
    try:
        return key, P.play(cfg, arm, red)
    except Exception as e:   # an error counts as a loss for the candidate
        return key, dict(error=repr(e), winner='red', margin=-3000., event='error')


def evaluate(pool, arms, fams, seed0, per_opp):
    """arms: list of arm strings -> list of fitness dicts (paired: same seeds for every arm)."""
    tasks = []
    for ai, arm in enumerate(arms):
        for fam, reds in fams.items():
            for red in reds:
                for i in range(per_opp):
                    s = seed0 + i * 7 + (sum(map(ord, red)) % 5)
                    tasks.append(((ai, fam, red, i), P.game_cfg(s, i), arm, red))
    res = pool.map(job, tasks, chunksize=1)
    out = []
    for ai in range(len(arms)):
        fu = {}
        for fam in fams:
            us = [util(r) for (k, r) in res if k[0] == ai and k[1] == fam]
            fu[fam] = float(np.mean(us))
        kills = sum(r.get('event') == 'blue_kill' for (k, r) in res if k[0] == ai)
        died = sum(r.get('event') in ('red_kill', 'collision', 'blue_crash') for (k, r) in res if k[0] == ai)
        errs = sum('error' in r for (k, r) in res if k[0] == ai)
        fit = .5 * float(np.mean(list(fu.values()))) + .5 * min(fu.values())
        out.append(dict(fit=fit, fam=fu, kills=int(kills), died=int(died), errors=int(errs)))
    return out


def to_x(p):
    return np.array([(p[k] - lo) / (hi - lo) for k, (lo, hi) in SPACE.items()])


def from_x(x):
    x = np.clip(x, 0, 1)
    return {k: lo + (hi - lo) * float(v) for (k, (lo, hi)), v in zip(SPACE.items(), x)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='runs/tune_fin1')
    ap.add_argument('--gens', type=int, default=12)
    ap.add_argument('--lam', type=int, default=6)
    ap.add_argument('--per-opp', type=int, default=2)
    ap.add_argument('--sigma', type=float, default=.12)
    ap.add_argument('--seed0', type=int, default=7100000)
    ap.add_argument('--workers', type=int, default=2)
    a = ap.parse_args()
    out = HERE / a.out
    out.mkdir(parents=True, exist_ok=True)
    st_path = out / 'state.json'
    f4 = f4_params()
    f4_arm = arm_of(f4)
    fams = families((HERE / 'runs' / 'eval_fin' / 'F4.txt').read_text().strip())
    if st_path.exists():
        st = json.loads(st_path.read_text())
    else:
        st = dict(gen=0, parent=f4, sigma=a.sigma, accepted=[])
    rng = np.random.default_rng(a.seed0 + 17 * st['gen'])
    log = (out / 'log.jsonl').open('a')
    (out / 'families.json').write_text(json.dumps(fams, indent=1))
    with Pool(a.workers) as pool:
        while st['gen'] < a.gens:
            g = st['gen']
            t0 = time.time()
            px = to_x(st['parent'])
            kids = [from_x(px + rng.normal(0, st['sigma'], len(px))) for _ in range(a.lam)]
            arms = [arm_of(st['parent'])] + [arm_of(k) for k in kids]
            seeds = a.seed0 + 10000 * (g + 1)
            ev = evaluate(pool, arms, fams, seeds, a.per_opp)
            par, ch = ev[0], ev[1:]
            bi = int(np.argmax([c['fit'] for c in ch]))
            rec = dict(gen=g, parent_fit=par['fit'], parent_fam=par['fam'], kids=[dict(params=k, **c) for k, c in zip(kids, ch)], best=bi)
            accepted = False
            if ch[bi]['fit'] > par['fit'] + .02 and ch[bi]['died'] <= par['died'] and ch[bi]['errors'] == 0:
                cf = evaluate(pool, [arm_of(st['parent']), arm_of(kids[bi])], fams, seeds + 5000, a.per_opp)
                rec['confirm'] = cf
                if cf[1]['fit'] > cf[0]['fit'] and cf[1]['died'] <= cf[0]['died']:
                    st['parent'] = kids[bi]
                    st['accepted'].append(g)
                    accepted = True
            st['sigma'] = float(np.clip(st['sigma'] * (1.15 if accepted else .92), .04, .25))
            rec.update(accepted=accepted, sigma=st['sigma'], secs=round(time.time() - t0))
            log.write(json.dumps(rec) + '\n'); log.flush()
            st['gen'] = g + 1
            st_path.write_text(json.dumps(st, indent=1))
            (out / 'best_arm.txt').write_text(arm_of(st['parent']))
            print('gen %d parent %.3f best kid %.3f %s accepted=%s sigma %.3f %ds fam=%s' % (
                g, par['fit'], ch[bi]['fit'], '' if not accepted else '(confirmed)', accepted, st['sigma'], rec['secs'],
                {k: round(v, 2) for k, v in ch[bi]['fam'].items()}), flush=True)


if __name__ == '__main__':
    main()
