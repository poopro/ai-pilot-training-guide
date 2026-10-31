"""ROUND 4 (2026-10-27): (1+lambda)-ES of the FINISHER (tuned2f) constants + the base pursuit bank clip,
with a worst-group objective that rewards kills and punishes deaths.

Why: tuned2f (tuned2 + close-range lift-vector finisher, setting F4) is our match program: official Host 6/6 kills,
local 252-0 / hard set 171-9.  What is left are turn-fighters (bank ~85-88 deg that break/extend when chased:
adv:f1s_1 and the opponents an adversarial search against tuned2f found, adv:fin1_*), where both sides pure-pursue
and the game is decided on position points.  This round tunes how the finisher fights (gain, lead, speed, G cap,
hold range, merge offset, entry range) and the bank clip of the tuned2 base underneath.

  python tune4.py --smoke --workers 2                                 (2 short candidates, ~2 min)
  python tune4.py --budget-min 600 --workers 30 --out runs/tune04     (resumable: <out>/state.json)
  python tune4.py --heldout runs/tune04 --workers 30                  (final judgement on held-out opponents, new seeds)
  python tune4.py --advfin fin12 ...                                  (also train on the round-2 adversaries adv:fin2_01/03/05)
  python tune4.py --x0 B86N94 ...                                     (start from bank 86 / n_cap 9.4 / turn_cas 320 instead of F4)
  python tune4.py --rec-v2 1 --x0 F4R ...                             (finisher ground recovery v2 fixed on; F4R = F4 + rec_v2)
  python judge4.py ...                                                (common held-out judgement of several candidates incl. fin2)

Pilot: FinisherPilot(WidePilot(tuned2 params, bank_cap)), FixedTactic -- bank_cap 72 + F4 = the current match program.
Fitness = 0.5 * weighted mean family utility + 0.5 * min family utility.
Game utility = sign(winner) + 0.5*clip(margin/3000) + 0.5*[blue kill] - 1.0*[blue shot down / crashed / collision loss].
A child replaces the parent only if it is better on the generation seeds by > 0.02 AND on an independent confirmation set.
"""
import argparse, json, time
from pathlib import Path
import numpy as np
import pool3  # noqa: F401  adv:<name>, sacn:<N> opponents
import dcsvet_pool  # noqa: F401  arm=<spec> red kind (our own pilots as red)
import rollout
import rollout_bfm
import wide_pilot
from bfm import FixedTactic
from common import HERE

F4 = dict(aa_max=180., enter_deg=180., exit_deg=180., enter_m=3000., exit_m=3500., turn_cas=340., n_cap=8., merge_off_m=400.)
F4_ARM = 'tuned2f:' + ':'.join('%s=%g' % kv for kv in F4.items())
_make = rollout_bfm.make_arm


def make_arm(name):
    if isinstance(name, dict) and 'fin' in name:
        from finisher import FinisherPilot
        p = dict(wide_pilot.tuned2_params(), bank_cap=float(name['fin']['bank_cap']))
        cfg = dict(F4); cfg.update({k: float(v) for k, v in name['fin'].items() if k != 'bank_cap'})
        return FinisherPilot(wide_pilot.WidePilot(p), cfg), FixedTactic()
    if isinstance(name, str) and name.split(':')[0] in ('tuned2f', 'dcsv2f', 'dcsv2fr', 'dcsv2frs', 'fin4'):   # any dcsvet_pool arm as blue (2026-10-27)
        return dcsvet_pool.make_blue(name)
    if isinstance(name, str) and name.startswith('tuned2w:'):    # red 'arm=tuned2w:80' (held-out self family); fixed 2026-10-27
        return wide_pilot.make_wide(float(name.split(':')[1]))
    return _make(name)


rollout_bfm.make_arm = make_arm

SPEC = {   # name: (low, high, start = F4 / 72 deg)
    'k_ang': (1.0, 3.5, 2.2), 'k_ff': (.4, 1.6, 1.0), 'hold_m': (300., 850., 500.), 'turn_cas': (280., 420., 340.),
    'turn_deg': (10., 50., 30.), 'n_cap': (7., 9.6, 8.), 'enter_m': (2000., 4500., 3000.), 'merge_off_m': (200., 800., 400.),
    'bank_cap': (72., 88., 72.),   # widened 86 -> 88 on 2026-10-27 (adversaries fly 85-88)
    'floor_m': (800., 1500., 1200.),   # finisher ground-recovery floor (added 2026-10-27 with rec_v2)
}
NAMES = list(SPEC)
LO = np.array([SPEC[k][0] for k in NAMES]); HI = np.array([SPEC[k][1] for k in NAMES])
X0 = np.array([SPEC[k][2] for k in NAMES])


FIN1_TRAIN = ('fin1_00', 'fin1_03', 'fin1_04', 'fin1_06')     # confirmed vs F4 (new seeds): 4-8, 4-8, 4-8, 2-10
FIN1_HO = ('fin1_01', 'fin1_02', 'fin1_05', 'fin1_07')        # 6-6, 7-5, 4-8, 3-9 -- held out
# round-2 adversarial search vs F4 (runs/adv_fin2, confirmed on new seeds; all timeouts lost on POSITION points)
FIN2_TRAIN = ('fin2_01', 'fin2_03', 'fin2_05')                 # 2-10, 3-9, 2-10   (only with --advfin fin12)
FIN2_HO = ('fin2_02', 'fin2_04', 'fin2_07')                    # 3-9, 2-10, 3-9    -- held out (judge4.py)


def fin1_opponents():
    have = [n for n in FIN1_TRAIN if (HERE / 'adv_pool' / (n + '.json')).exists()]
    return tuple('adv:' + n for n in have) or ('adv:f1s_1',)


# family, opponents, games per opponent (multiple of 6), weight
PLAN = (('mirror', ('guide', 'ctl:base_t3'), 6, 1.5), ('lag', ('lag',), 6, 1.0), ('turners', ('defender', 'hturn'), 6, 1.0),
        ('pp', ('pp2',), 6, .5), ('adv', ('adv:f1s_0', 'adv:f1s_1', 'adv:f1s_2', 'adv:f1s_3'), 6, 1.5),
        ('advfin', fin1_opponents(), 6, 2.0), ('sac', ('sacn:25600000',), 6, 1.0), ('self', ('arm=' + F4_ARM,), 6, 1.0))
PLAN_FIN12 = PLAN + (('advfin2', tuple('adv:' + n for n in FIN2_TRAIN), 6, 2.0),)
# 2026-10-28 round 5 (from T17): the opponent families found against T17 -- reds with our finisher (t17fp/t17fs) and
# reds with vertical moves (t17vs) -- plus T17 itself.  Held out for judge4: the other t17fp/t17fs/t17vs/t17vp.
NEW_TRAIN = ('t17fp_03', 't17fp_04', 't17fs_02', 't17fs_03', 't17vs_00', 't17vs_03')
NEW_HO = ('t17fp_00', 't17fp_01', 't17fp_02', 't17fs_00', 't17fs_07', 't17vs_04', 't17vs_05', 't17vp_03')
PLAN_FIN123 = PLAN_FIN12 + (('advnew', tuple('adv:' + n for n in NEW_TRAIN), 6, 2.0),
                            ('selfT17', ('arm=fin4:runs/tune04_fin12d',), 6, 1.0))
# 2026-10-28 round 6: external RL opponents (Korean TOPGUN 1st-place PPO pilots, kr_red.py) as sparring partners.
# Train on 3 of them, hold out the rest for judge4.  Small safety families keep T17's old strengths.
KR_TRAIN = ('krl:junhwa_final', 'krl:gylee_20k', 'krl:junhwa_exploiter_survive_v1')
KR_HO = ('krl:gylee_46k_headon', 'krl:junhwa_wide1_v2', 'krl:gylee_69k')
PLAN_KR = (('krtrain', KR_TRAIN, 6, 4.0), ('advnew', tuple('adv:' + n for n in NEW_TRAIN[::3]), 6, 1.5),
           ('selfT17', ('arm=fin4:runs/tune04_fin12d',), 6, 1.0))
HELDOUT = (('fin1_ho', tuple('adv:' + n for n in FIN1_HO)), ('f2w80', tuple('adv:f2w80_%02d' % i for i in range(6))), ('sac_ho', ('sacn:22400000', 'sacn:24000000', 'sacn:26400000', 'sacn:50400000')),
           ('script_ho', ('lead', 'level', 'weave', 'pp0', 'pp5', 'mix', 'breaker')), ('self_ho', ('arm=tuned2', 'arm=tuned2w:80')))


def to_cfg(x):
    return {k: float(v) for k, v in zip(NAMES, np.clip(x, LO, HI))}


EXTRA = {}   # fixed (not tuned) finisher settings for this run, e.g. {'rec_v2': 1.}; set in main(), carried in each task


def cfg_of(x):
    return dict(to_cfg(x), **EXTRA)


def utility(r):
    if 'error' in r:
        return -2.
    sign = 1. if r['winner'] == 'blue' else (-1. if r['winner'] == 'red' else 0.)
    ev = r.get('event', '')
    died = ev in ('red_kill', 'blue_crash') or (ev == 'collision' and r['winner'] != 'blue')
    return sign + .5 * float(np.clip(r['margin'] / 3000., -1., 1.)) + .5 * (ev == 'blue_kill') - 1. * died


def _task(args):
    cfg, arm = args
    r = rollout_bfm._task((cfg, arm))
    r['_u'] = utility(r)
    return r


def evaluate(pool, cands, seed0, plan=PLAN, max_ticks=18000):
    tasks, owner = [], []
    for ci, c in enumerate(cands):
        for fi, fam in enumerate(plan):
            name, opps, n = fam[0], fam[1], (fam[2] if len(fam) > 2 else 6)
            for oi, opp in enumerate(opps):
                for i in range(n):
                    cfg = dict(rollout.game_config(i, seed0 + 100 * fi + 20 * oi, opp, max_ticks), host_fidelity=True)
                    tasks.append((cfg, c if isinstance(c, str) else {'fin': c})); owner.append((ci, name))
    us = [dict() for _ in cands]
    raw = [list() for _ in cands]
    for k, r in enumerate(pool.imap(_task, tasks, chunksize=1)):
        ci, fam = owner[k]
        us[ci].setdefault(fam, []).append(r['_u'])
        raw[ci].append({key: r.get(key) for key in ('red', 'side', 'distance_ft', 'event', 'winner', 'margin', 'atk_b', 'atk_r')})
    fits, fams = [], []
    for d in us:
        fm = {fam: float(np.mean(v)) for fam, v in d.items()}
        ws = {f[0]: (f[3] if len(f) > 3 else 1.) for f in plan}
        wmean = sum(ws[f] * fm[f] for f in fm) / sum(ws[f] for f in fm)
        fits.append(.5 * wmean + .5 * min(fm.values()))
        fams.append({k: round(v, 3) for k, v in fm.items()})
    return fits, fams, raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--budget-min', type=float, default=600)
    ap.add_argument('--lam', type=int, default=8)
    ap.add_argument('--sigma', type=float, default=.12)
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--out', default='runs/tune04')
    ap.add_argument('--gen-minutes', type=float, default=20)
    ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--rng', type=int, default=45678, help='ES random stream (use a different value for a parallel run)')
    ap.add_argument('--seed-base', type=int, default=7300000, help='game seeds of generation g = seed_base + 1000 g')
    ap.add_argument('--advfin', default='fin1', choices=['fin1', 'fin12', 'fin123', 'kr'],
                    help='fin12 = also train against adv:fin2_01/03/05 (separate family advfin2, weight 2)')
    ap.add_argument('--rec-v2', type=float, default=0., help='1 = finisher ground recovery v2 (corner-speed G at idle), fixed for the run')
    ap.add_argument('--x0', default=None, help='start point when no state.json: B86N94 / B80N90 (diag_full.py) or a json file {cfg:..}')
    ap.add_argument('--heldout', default=None, help='run dir: judge its best.json against the current F4 on held-out opponents')
    a = ap.parse_args()
    import multiprocessing as mp
    pool = mp.get_context('spawn').Pool(a.workers, maxtasksperchild=40)
    if a.smoke:
        t0 = time.time()
        f, fam, _ = evaluate(pool, [to_cfg(X0), to_cfg(np.clip(X0 + .05 * (HI - LO), LO, HI))], 7299000, max_ticks=600)
        print('SMOKE fitness', [round(x, 3) for x in f], fam, 'in %.0fs' % (time.time() - t0), flush=True)
        pool.terminate(); return
    if a.heldout:
        best = json.loads((HERE / a.heldout / 'best.json').read_text())['cfg']
        cands = [to_cfg(X0), best]
        plan = tuple((n, o, 12, 1.) for n, o in HELDOUT)
        f, fam, raw = evaluate(pool, cands, 7900000, plan=plan)
        rep = dict(F4=dict(fit=f[0], fam=fam[0]), best=dict(fit=f[1], fam=fam[1], cfg=best))
        for ci, nm in ((0, 'F4'), (1, 'best')):
            rr = raw[ci]
            rep[nm].update(W=sum(r['winner'] == 'blue' for r in rr), L=sum(r['winner'] == 'red' for r in rr),
                           kills=sum(r['event'] == 'blue_kill' for r in rr),
                           died=sum(r['event'] in ('red_kill', 'blue_crash') for r in rr), n=len(rr))
        (HERE / a.heldout / 'heldout.json').write_text(json.dumps(dict(rep=rep, raw=raw), indent=1))
        print(json.dumps(rep, indent=1), flush=True)
        pool.terminate(); return
    if a.rec_v2:
        EXTRA['rec_v2'] = float(a.rec_v2)
    out = HERE / a.out; out.mkdir(parents=True, exist_ok=True)
    st_path = out / 'state.json'
    if st_path.exists():
        st = json.loads(st_path.read_text())
        parent = np.array(st['parent']); sigma = st['sigma']; gen = st['gen']
    else:
        parent = X0.copy(); sigma = a.sigma; gen = 0
        if a.x0:
            if (HERE / a.x0).is_file():
                d = json.loads((HERE / a.x0).read_text()); d = d.get('cfg', d)
            else:
                import diag_full
                d = diag_full.CANDS[a.x0]
            parent = np.clip(np.array([float(d.get(k, X0[i])) for i, k in enumerate(NAMES)]), LO, HI)
            print('x0 =', a.x0, cfg_of(parent), flush=True)
    rng = np.random.default_rng(a.rng + gen)
    t_end = time.time() + a.budget_min * 60
    log = (out / 'log.jsonl').open('a', encoding='utf-8')
    span = HI - LO
    plan = {'fin12': PLAN_FIN12, 'fin123': PLAN_FIN123, 'kr': PLAN_KR}.get(a.advfin, PLAN)
    print('families', [f[0] for f in plan], flush=True)
    while time.time() < t_end - a.gen_minutes * 60:
        seed0 = a.seed_base + gen * 1000
        kids = [np.clip(parent + sigma * span * rng.standard_normal(len(NAMES)), LO, HI) for _ in range(a.lam)]
        t0 = time.time()
        fit, fam, _ = evaluate(pool, [cfg_of(parent)] + [cfg_of(k) for k in kids], seed0, plan=plan)
        fp, fk = fit[0], fit[1:]
        b = int(np.argmax(fk))
        accepted, conf = False, None
        if fk[b] > fp + .02:
            conf, _, _ = evaluate(pool, [cfg_of(parent), cfg_of(kids[b])], seed0 + 500, plan=plan)
            if conf[1] > conf[0]:
                parent = kids[b]; accepted = True
        sigma = float(np.clip(sigma * (1.2 if accepted else .85), .03, .3))
        gen += 1
        rec = dict(gen=gen, t=time.strftime('%F %T'), minutes=round((time.time() - t0) / 60, 1), parent_fit=round(fp, 4),
                   parent_families=fam[0], best_kid_fit=round(fk[b], 4), best_kid_families=fam[1 + b], conf=conf,
                   accepted=accepted, sigma=round(sigma, 4), parent={k: round(v, 3) for k, v in cfg_of(parent).items()})
        log.write(json.dumps(rec, ensure_ascii=False) + '\n'); log.flush()
        print(json.dumps(rec, ensure_ascii=False), flush=True)
        st_path.write_text(json.dumps(dict(parent=parent.tolist(), sigma=sigma, gen=gen)))
        (out / 'best.json').write_text(json.dumps(dict(cfg=cfg_of(parent), gen=gen, names=NAMES, extra=EXTRA), indent=1))
    pool.terminate()
    print('TUNE DONE gen', gen, flush=True)


if __name__ == '__main__':
    main()
