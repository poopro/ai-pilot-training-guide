"""Game runner: data collection, paired evaluation and smoke test.

  python rollout.py smoke
  python rollout.py collect --games 300 --workers 3 --out runs/collect01 [--model brain.pt]
  python rollout.py eval --n 12 --workers 3 --out runs/eval01 --model brain.pt --opponents guide,lead,lag,mix,breaker,level
"""
import argparse, json, math, os, sys, time, traceback
from collections import deque
from pathlib import Path
import numpy as np
from common import HERE
from tactics import TacticalPilot, PURSUE, LEAD, LAG, BREAK_IN, BREAK_OUT, HIGH_YOYO, LOW_YOYO, EXTEND, N_TACTICS, NAMES
from opponents import ScriptedRed, DECISION_TICKS, KINDS
from feats import features, make_token, window_from_tokens, N_ACT

DISTANCES = (3000, 6000, 9000)
GAMMA = 0.95


def game_config(index, seed0, red, max_ticks):
    seed = int(seed0 + index)
    rng = np.random.default_rng(seed * 7919 + 13)
    return dict(seed=seed, distance_ft=DISTANCES[index % 3], side=1 if (index // 3) % 2 == 0 else -1,
                altitude_ft=float(rng.uniform(10000, 20000)), red=red, max_ticks=int(max_ticks))


class FixedPolicy:
    name = 'baseline'
    def __init__(self, tactic=PURSUE): self.t = tactic
    def reset(self, cfg): pass
    def decide(self, feat, ob, arena): return self.t


class ExplorePolicy:
    name = 'explore'
    def reset(self, cfg):
        self.rng = np.random.default_rng(cfg['seed'] + 99)
        self.eps = float(self.rng.choice([.15, .4, .8]))
        self.hold = 0; self.cur = PURSUE
    def decide(self, feat, ob, arena):
        if self.hold > 0:
            self.hold -= 1
            return self.cur
        if self.rng.random() < self.eps:
            p = np.array([.1, .15, .15, .12, .1, .13, .12, .13])
            if ob[2] * .3048 < 2500:
                p[[LOW_YOYO, BREAK_IN, BREAK_OUT]] = 0
            p = p / p.sum()
            self.cur = int(self.rng.choice(N_ACT, p=p))
            self.hold = int(self.rng.integers(1, 5)) - 1
        else:
            self.cur = PURSUE
        return self.cur


class BrainPolicy:
    name = 'brain'
    def __init__(self, brain, **kw):
        self.brain = brain; self.kw = kw
    def reset(self, cfg):
        self.tokens = []; self.prev = None; self.cur = PURSUE
    def decide(self, feat, ob, arena):
        self.tokens.append(make_token(feat, self.prev))
        window = window_from_tokens(self.tokens)
        agl = ob[2] * .3048
        mask = np.ones(N_ACT, dtype=bool)
        if agl < 2500:
            mask[LOW_YOYO] = False
        if agl < 1800:
            mask[[BREAK_IN, BREAK_OUT, HIGH_YOYO, LOW_YOYO]] = False
        a, _ = self.brain.plan(window, mask, self.cur, **self.kw)
        self.prev = a; self.cur = a
        return a


_BRAIN_CACHE = {}
def get_policy(spec):
    kind = spec['type']
    if kind == 'baseline': return FixedPolicy(spec.get('tactic', PURSUE))
    if kind == 'explore': return ExplorePolicy()
    if kind == 'brain':
        path = spec['model']
        if path not in _BRAIN_CACHE:
            from brain import load_brain
            _BRAIN_CACHE[path] = load_brain(path)
        return BrainPolicy(_BRAIN_CACHE[path], **spec.get('plan', {}))
    raise ValueError(kind)


def build_labels(snaps, mins, terminal):
    S = np.asarray(snaps, dtype=np.float64)
    T = len(S) - 1
    d = S[1:] - S[:-1]
    r = (10000. * (d[:, 0] - d[:, 1]) / 60. - 100. * (d[:, 4] - d[:, 5]) / 60. + (d[:, 2] - d[:, 3])) / 10000.
    if T > 0:
        r[-1] += terminal
    hit = np.array([min(max((S[min(t + 9, T), 1] - S[t, 1]) / 180., 0.), 1.) for t in range(T)])
    mins = np.asarray(mins, dtype=np.float64)
    low = np.array([float(mins[t:t + 15].min() < 1000.) for t in range(T)])
    return r.astype(np.float32), hit.astype(np.float32), low.astype(np.float32)


def play_game(cfg, policy_spec, out_data=None):
    from arena import Arena
    t0 = time.time()
    arena = Arena(cfg['seed'], cfg['distance_ft'], cfg['side'], cfg['altitude_ft'], host_fidelity=cfg.get('host_fidelity', True))
    pilot = TacticalPilot()
    red = ScriptedRed(cfg['red'], cfg['seed'] + 1)
    policy = get_policy(policy_spec)
    policy.reset(cfg)
    feats, acts, snaps, mins = [], [], [arena.counters()], []
    imin = 1e9
    hist = np.zeros(N_ACT, dtype=int)
    done = False
    while not done and arena.tick < cfg['max_ticks']:
        ob = arena.obs_blue()
        if arena.tick % DECISION_TICKS == 0:
            if arena.tick > 0:
                snaps.append(arena.counters()); mins.append(imin)
            imin = 1e9
            feat = features(ob, arena.judge.attack[0], arena.tick)
            tac = int(policy.decide(feat, ob, arena))
            feats.append(feat); acts.append(tac); hist[tac] += 1
            pilot.set_tactic(tac)
        bcmd, _ = pilot.act(ob)
        done = arena.step(bcmd, red.act(arena.obs_red(), arena.tick))
        imin = min(imin, arena.agl_blue_m())
    snaps.append(arena.counters()); mins.append(imin)
    if not done:
        # time limit reached without the judge declaring timeout (shortened smoke games)
        pass
    snap = arena.judge.snapshot()
    terminal = 0.
    if snap['winner'] == 'blue': terminal += 3.
    elif snap['winner'] == 'red': terminal -= 3.
    ks = snap['kill_score']
    if ks is not None: terminal += (ks[0] - ks[1]) / 10000.
    r, hit, low = build_labels(snaps, mins, terminal)
    G = np.zeros_like(r); run = 0.
    for t in range(len(r) - 1, -1, -1):
        run = r[t] + GAMMA * run; G[t] = run
    ts = snap['total_score'] or snap['advantage']
    res = dict(seed=cfg['seed'], red=cfg['red'], distance_ft=cfg['distance_ft'], side=cfg['side'],
               altitude_ft=round(cfg['altitude_ft'], 1), policy=policy.name, event=snap['event'], winner=snap['winner'],
               ticks=snap['ticks'], atk_b=snap['attack_ticks'][0], atk_r=snap['attack_ticks'][1],
               pos_b=round(snap['position_sum'][0], 1), pos_r=round(snap['position_sum'][1], 1),
               overg_b=snap['over_g_ticks'][0], margin=round(ts[0] - ts[1], 1), min_agl_m=round(float(min(mins)), 1),
               tactics=hist.tolist(), wall_s=round(time.time() - t0, 1),
               fidelity=arena.fidelity_applied, ticks_per_s=round(snap['ticks'] / max(time.time() - t0, 1e-9), 0))
    if out_data is not None:
        Path(out_data).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(out_data, feats=np.asarray(feats, np.float32), acts=np.asarray(acts, np.int64),
                            rewards=r, risk_hit=hit, risk_low=low, returns=G)
    return res


def _task(args):
    cfg, spec, out_data = args
    try:
        return play_game(cfg, spec, out_data)
    except Exception:
        return dict(seed=cfg['seed'], red=cfg['red'], policy=spec['type'], error=traceback.format_exc())


def run_tasks(tasks, workers, out_dir):
    import multiprocessing as mp
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    sink = (out_dir / 'results.jsonl').open('a', encoding='utf-8')
    def handle(res):
        results.append(res)
        sink.write(json.dumps(res, ensure_ascii=False) + '\n'); sink.flush()
        tag = res.get('error', '')[-300:] if 'error' in res else '%s/%s %s winner=%s atk %s/%s' % (res['policy'], res['red'], res['event'], res['winner'], res['atk_b'], res['atk_r'])
        print('[%d/%d] %s' % (len(results), len(tasks), tag), flush=True)
    if workers <= 1:
        for t in tasks: handle(_task(t))
    else:
        ctx = mp.get_context('spawn')
        with ctx.Pool(workers, maxtasksperchild=6) as pool:
            for res in pool.imap_unordered(_task, tasks):
                handle(res)
    sink.close()
    return results


def summarize(results):
    rows = {}
    for r in results:
        if 'error' in r: continue
        rows.setdefault((r['red'], r['policy']), []).append(r)
    print('\n%-8s %-9s %3s %4s %4s %4s %5s %5s %7s %9s' % ('opp', 'policy', 'n', 'win', 'loss', 'draw', 'atkB', 'atkR', 'margin', 'minAGLm'))
    for (red, pol), rs in sorted(rows.items()):
        w = sum(r['winner'] == 'blue' for r in rs); l = sum(r['winner'] == 'red' for r in rs)
        print('%-8s %-9s %3d %4d %4d %4d %5.0f %5.0f %7.0f %9.0f' % (red, pol, len(rs), w, l, len(rs) - w - l,
              np.mean([r['atk_b'] for r in rs]), np.mean([r['atk_r'] for r in rs]),
              np.mean([r['margin'] for r in rs]), min(r['min_agl_m'] for r in rs)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['smoke', 'collect', 'eval'])
    ap.add_argument('--games', type=int, default=60)
    ap.add_argument('--n', type=int, default=12, help='eval games per opponent (same seeds for every arm)')
    ap.add_argument('--workers', type=int, default=3)
    ap.add_argument('--out', default='runs/run')
    ap.add_argument('--seed0', type=int, default=500000)
    ap.add_argument('--model', default=None)
    ap.add_argument('--opponents', default=','.join(KINDS))
    ap.add_argument('--max-ticks', type=int, default=18000)
    ap.add_argument('--no-fidelity', action='store_true')
    a = ap.parse_args()
    out = HERE / a.out
    fid = not a.no_fidelity
    if a.mode == 'smoke':
        t0 = time.time()
        cfg = dict(game_config(0, 1, 'mix', 1800), host_fidelity=fid)
        res = play_game(cfg, {'type': 'explore'}, out_data=out / 'smoke.npz')
        print(json.dumps(res, ensure_ascii=False, indent=1))
        d = np.load(out / 'smoke.npz')
        print('decisions', len(d['acts']), 'feat shape', d['feats'].shape, 'reward sum %.3f' % d['rewards'].sum())
        print('SMOKE OK in %.1fs' % (time.time() - t0))
        return
    opps = [o for o in a.opponents.split(',') if o]
    if a.mode == 'collect':
        spec = {'type': 'explore'} if not a.model else {'type': 'brain', 'model': str(HERE / a.model)}
        tasks = []
        for i in range(a.games):
            red = opps[i % len(opps)]
            cfg = dict(game_config(i, a.seed0, red, a.max_ticks), host_fidelity=fid)
            tasks.append((cfg, spec, str(out / 'data' / ('g%d_%s.npz' % (cfg['seed'], red)))))
        res = run_tasks(tasks, a.workers, out)
        summarize(res)
    else:
        arms = [{'type': 'baseline'}]
        if a.model: arms.append({'type': 'brain', 'model': str(HERE / a.model)})
        tasks = []
        for red in opps:
            for i in range(a.n):
                for spec in arms:
                    cfg = dict(game_config(i, a.seed0, red, a.max_ticks), host_fidelity=fid)
                    tasks.append((cfg, spec, None))
        res = run_tasks(tasks, a.workers, out)
        summarize(res)


if __name__ == '__main__':
    main()
