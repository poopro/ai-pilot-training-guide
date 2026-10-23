"""CMA-ES search for opponents that beat the frozen tuned2 (adversarial opponent family F, 2026-10-23).

  python adv_search.py search --out runs/adv_f1 --gens 18 --pop 12 --seed0 5100000 --workers 2
  python adv_search.py confirm --out runs/adv_f1 --top 12 --n 24 --seed0 5900000 --workers 2

search : minimises tuned2's mean utility over 6 games per candidate (3 distances x 2 sides; the same
         6 fresh seeds for every candidate of one generation, new seeds each generation).
         Utility of a game for blue = sign(winner) + 0.5 * clip(margin / 1000, -1, 1).
         Every candidate and game is logged to <out>/candidates.jsonl; CMA state in <out>/es.pkl (resumable).
confirm: re-plays the best candidates on NEW seeds (selection in the search overstates their strength),
         writes <out>/confirm.jsonl and <out>/confirm_report.md, and stores the confirmed opponents as
         adv_pool/<name>.json for pool3.py (opponent kind 'adv:<name>').
Blue is tuned2 exactly as in rollout_bfm.play_game (ParamPilot + runs/tune02/best.json + shield v3).
"""
import argparse, json, pickle, time, traceback
from pathlib import Path
import numpy as np
import rollout
import rollout_bfm
from common import HERE
from arena import Arena
from opponents import DECISION_TICKS
import adv_red

DIST = (3000, 6000, 9000)


def tuned2_arm():
    return {'params': json.loads((HERE / 'runs' / 'tune02' / 'best.json').read_text(encoding='utf-8'))['params']}


def game_cfg(seed, i, max_ticks=18000):
    rng = np.random.default_rng(seed * 7919 + 13)
    return dict(seed=int(seed), distance_ft=DIST[i % 3], side=1 if (i // 3) % 2 == 0 else -1,
                altitude_ft=float(rng.uniform(10000, 20000)), max_ticks=max_ticks)


def make_blue(blue_arm):
    if isinstance(blue_arm, str) and blue_arm.startswith('tuned2w:'):
        import wide_pilot
        return wide_pilot.make_wide(float(blue_arm.split(':')[1]))
    if blue_arm == 'tuned2':
        return rollout_bfm.make_arm(tuned2_arm())
    return rollout_bfm.make_arm(blue_arm)


def play(cfg, red_params, blue_arm):
    arena = Arena(cfg['seed'], cfg['distance_ft'], cfg['side'], cfg['altitude_ft'], host_fidelity=True)
    pilot, policy = make_blue(blue_arm)
    if policy is not None:
        policy.reset(cfg)
    red = adv_red.AdvRed(red_params, cfg['seed'] + 1)
    done = False
    while not done and arena.tick < cfg['max_ticks']:
        ob = arena.obs_blue()
        if policy is not None and arena.tick % DECISION_TICKS == 0:
            pilot.set_tactic(int(policy.decide(None, ob, arena)))
        bcmd, _ = pilot.act(ob)
        done = arena.step(bcmd, red.act(arena.obs_red(), arena.tick))
    snap = arena.judge.snapshot()
    ts = snap['total_score'] or snap['advantage']
    margin = float(ts[0] - ts[1])
    w = snap['winner']
    u = (1. if w == 'blue' else (-1. if w == 'red' else 0.)) + .5 * float(np.clip(margin / 1000., -1., 1.))
    return dict(seed=cfg['seed'], side=cfg['side'], distance_ft=cfg['distance_ft'], event=snap['event'], winner=w,
                ticks=snap['ticks'], atk_b=snap['attack_ticks'][0], atk_r=snap['attack_ticks'][1],
                pos_b=round(snap['position_sum'][0], 1), pos_r=round(snap['position_sum'][1], 1),
                overg_r=snap['over_g_ticks'][1], margin=round(margin, 1), u=round(u, 4))


def _task(args):
    key, cfg, red_params, blue_arm = args
    try:
        return key, play(cfg, red_params, blue_arm)
    except Exception:
        return key, dict(error=traceback.format_exc()[-600:])


def run_tasks(pool, tasks):
    if pool is None:
        return [_task(t) for t in tasks]
    return list(pool.imap_unordered(_task, tasks, chunksize=1))


def make_pool(workers):
    if workers <= 1:
        return None
    import multiprocessing as mp
    return mp.get_context('spawn').Pool(workers, maxtasksperchild=12)


def cmd_search(a):
    import cma
    out = HERE / a.out
    out.mkdir(parents=True, exist_ok=True)
    blue = a.blue
    state = out / 'es.pkl'
    if state.exists():
        es, gen = pickle.loads(state.read_bytes())
    else:
        es = cma.CMAEvolutionStrategy(np.full(adv_red.DIM, .5), a.sigma,
                                      {'bounds': [0., 1.], 'popsize': a.pop, 'seed': a.seed0 % 100000 + 1, 'verbose': -9})
        gen = 0
    pool = make_pool(a.workers)
    t_start = time.time()
    try:
        while gen < a.gens and (time.time() - t_start) / 60 < a.budget_min:
            t0 = time.time()
            X = es.ask()
            seeds = [a.seed0 + gen * 100 + i for i in range(6)]
            tasks = []
            for ci, x in enumerate(X):
                p = adv_red.decode(x)
                for i, s in enumerate(seeds):
                    tasks.append(((ci, i), game_cfg(s, i), p, blue))
            res = run_tasks(pool, tasks)
            by = {}
            for (ci, i), r in res:
                by.setdefault(ci, []).append(r)
            F = []
            with (out / 'candidates.jsonl').open('a', encoding='utf-8') as f:
                for ci, x in enumerate(X):
                    games = by[ci]
                    us = [g.get('u', 1.5) for g in games]          # an error counts as a blue win (worst case for search)
                    fit = float(np.mean(us))
                    F.append(fit)
                    f.write(json.dumps(dict(gen=gen, idx=ci, fit=round(fit, 4), x=[round(float(v), 5) for v in x],
                                            params=adv_red.describe(adv_red.decode(x)),
                                            red_wins=sum(g.get('winner') == 'red' for g in games),
                                            games=sorted(games, key=lambda g: g.get('seed', 0)))) + '\n')
            es.tell(X, F)
            gen += 1
            state.write_bytes(pickle.dumps((es, gen)))
            best = int(np.argmin(F))
            print('gen %d  best fit %.3f (red wins %d/6)  mean fit %.3f  sigma %.3f  %.0fs' % (
                gen, F[best], sum(g.get('winner') == 'red' for g in by[best]), float(np.mean(F)), es.sigma, time.time() - t0), flush=True)
    finally:
        if pool is not None:
            pool.close(); pool.join()


def cmd_confirm(a):
    out = HERE / a.out
    rows = [json.loads(l) for l in (out / 'candidates.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    rows.sort(key=lambda r: r['fit'])
    picked, xs = [], []
    for r in rows:                                    # best first, skip near-duplicates (L2 distance in [0,1]^D)
        x = np.array(r['x'])
        if all(np.linalg.norm(x - y) > a.min_dist for y in xs):
            picked.append(r); xs.append(x)
        if len(picked) >= a.top:
            break
    blue = a.blue
    tasks = []
    for k, r in enumerate(picked):
        p = adv_red.decode(r['x'])
        for i in range(a.n):
            tasks.append(((k, i), game_cfg(a.seed0 + i, i), p, blue))
    pool = make_pool(a.workers)
    try:
        res = run_tasks(pool, tasks)
    finally:
        if pool is not None:
            pool.close(); pool.join()
    by = {}
    for (k, i), g in res:
        by.setdefault(k, []).append(g)
    pool_dir = HERE / 'adv_pool'
    pool_dir.mkdir(exist_ok=True)
    lines = ['# 對抗搜尋 %s：新種子複驗（藍方 = %s）' % (a.out, a.blue), '',
             '搜尋期間的分數有選擇偏誤；這裡每個候選用 %d 局全新種子（%d 起）重打。' % (a.n, a.seed0), '',
             '| 名稱 | 搜尋 fit | 複驗：tuned2 勝-敗-和 | side −1 | side +1 | 分差中位數 | 紅方墜機 | 參數重點 |',
             '|---|---|---|---|---|---|---|---|']
    summ = []
    with (out / 'confirm.jsonl').open('w', encoding='utf-8') as f:
        for k, r in enumerate(picked):
            games = sorted(by[k], key=lambda g: g.get('seed', 0))
            ok = [g for g in games if 'error' not in g]
            bw = sum(g['winner'] == 'blue' for g in ok); rw = sum(g['winner'] == 'red' for g in ok)
            sm = lambda s: '%d-%d' % (sum(g['winner'] == 'blue' and g['side'] == s for g in ok), sum(g['winner'] == 'red' and g['side'] == s for g in ok))
            name = '%s_%02d' % (Path(a.out).name.replace('adv_', ''), k)
            p = r['params']
            rec = dict(name=name, search_fit=r['fit'], gen=r['gen'], blue_wins=bw, red_wins=rw, n=len(ok), errors=len(games) - len(ok),
                       median_margin=float(np.median([g['margin'] for g in ok])) if ok else None,
                       red_crash=sum(g['event'] in ('red_crash', 'mutual_crash') for g in ok), x=r['x'], params=p, games=games)
            f.write(json.dumps(rec) + '\n')
            summ.append(rec)
            (pool_dir / (name + '.json')).write_text(json.dumps(dict(name=name, x=r['x'], params=p, source=a.out,
                                                                    confirm=dict(blue_wins=bw, red_wins=rw, n=len(ok))), indent=1), encoding='utf-8')
            key = 'bank %.0f°, open %s %.0fs, def %s @%.0fm/%.0f°, off %s @%.0fm/%.0f°' % (
                p['bank_cap'], p['open_tac'], p['open_s'], p['def_tac'], p['def_range'], p['def_ata'], p['off_tac'], p['off_range'], p['off_ata'])
            lines.append('| %s | %.3f | %d-%d-%d | %s | %s | %.0f | %d | %s |' % (name, r['fit'], bw, rw, len(ok) - bw - rw, sm(-1), sm(1),
                                                                     rec['median_margin'] or 0, rec['red_crash'], key))
    (out / 'confirm_report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['search', 'confirm'])
    ap.add_argument('--out', default='runs/adv_f1')
    ap.add_argument('--gens', type=int, default=18)
    ap.add_argument('--pop', type=int, default=12)
    ap.add_argument('--sigma', type=float, default=.3)
    ap.add_argument('--seed0', type=int, default=5100000)
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--budget-min', type=float, default=600)
    ap.add_argument('--top', type=int, default=12)
    ap.add_argument('--n', type=int, default=24)
    ap.add_argument('--min-dist', type=float, default=.35)
    ap.add_argument('--blue', default='tuned2', help="tuned2 | tuned2w:<cap> | any rollout_bfm arm")
    a = ap.parse_args()
    (cmd_search if a.mode == 'search' else cmd_confirm)(a)


if __name__ == '__main__':
    main()
