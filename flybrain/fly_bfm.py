"""Closed-loop test of the fly brain inside YOUR newest harness (jepa_brain/rollout_bfm.py): the fly picks the tactic,
the frozen repair_guide pursuit + collision shield v3 (TIGHT3) flies - exactly like the 'brain_t3' arm, with the JEPA brain
replaced by the fly.  The reference arm is your own `base_t3` on the same seeds.

  python fly_bfm.py --readout readout.npz --prune-cache cache --n 24 --opponents guide,lead,lag,mix,breaker,level ^
         --workers 2 --out runs\\fly_bfm01                     (arms: fly_t3 and base_t3, paired on identical games)
  python fly_bfm.py --readout readout.npz --prune-cache cache --arms fly_t3 --pursue-bonus 0.3 --n 24 --out runs\\fly_bfm02

Nothing under jepa_brain/ or campaign_2026/ is modified (rollout_bfm.make_arm is patched in memory).
"""
import argparse, json, sys, time, traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
JEPA = ROOT / 'jepa_brain'
for p in (str(JEPA), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

_STATE = {}


class FlyArm:
    """tactician with the same interface as rollout_bfm.BrainArm"""
    needs_feat = True
    name = 'fly'

    def __init__(self, spec):
        from flybrain.pilot import FlyBrain, FlyPolicy, Readout
        if str(spec.get('opt') or '').startswith('random'):      # information-free control, e.g.  --opt random:0.15
            from flybrain.options import RandomOptionPolicy
            self.inner = RandomOptionPolicy(p=float(spec['opt'].partition(':')[2] or 0.15), hold=spec.get('hold') or 6, zone=spec.get('zone') or 3500.)
            return
        if spec.get('opt'):                      # option tactician trained on branch labels (train_branch.py): flybrain/options.py
            from flybrain.options import load_readout, FlyOptionPolicy
            ro = load_readout(spec['opt'])
            m = ro.meta
            kw = dict(hold=spec.get('hold') or m.get('hold', 6), zone=spec.get('zone') or m.get('zone', 3500.),
                      tau=m.get('tau', 0.) if spec.get('tau') is None else spec['tau'], cooldown=spec.get('cooldown', 3), only=spec.get('only'))
            if m.get('kind') == 'feat':
                self.inner = FlyOptionPolicy(None, ro, mode='feat', **kw)
                return
            key = (spec['opt'], spec.get('prune_cache'), spec.get('backend'), spec.get('dt'))
            if key not in _STATE:
                if spec.get('prune_cache'):
                    from flybrain.pilot import load_brain
                    brain = load_brain(spec['prune_cache'], backend=spec.get('backend', 'auto'))
                else:
                    brain = FlyBrain(device='cpu', dt_ms=spec.get('dt', 1.0), window_ms=spec.get('window_ms', 80.0))
                    if spec.get('backend') == 'numba':
                        brain.use_numba()
                _STATE[key] = brain
            self.inner = FlyOptionPolicy(_STATE[key], ro, mode='dn', **kw)
            return
        if spec.get('feat'):                     # control: raw-feature read-out, no brain
            self.inner = FlyPolicy(None, Readout.load(spec['readout']), mode='feat', margin=spec.get('margin', 0.01),
                                   pursue_bonus=spec.get('pursue_bonus', 0.0))
            return
        key = (spec['readout'], spec.get('prune_cache'), spec.get('backend'), spec.get('dt'))
        if key not in _STATE:
            brain = FlyBrain(device='cpu', dt_ms=spec.get('dt', 1.0), window_ms=spec.get('window_ms', 80.0))
            if spec.get('prune_cache'):
                from flybrain.prune import keep_from_cache
                brain.prune(keep_from_cache(spec['prune_cache'])[0], backend=spec.get('backend', 'auto'))
            elif spec.get('backend') == 'numba':
                brain.use_numba()
            _STATE[key] = (brain, Readout.load(spec['readout']))
        brain, ro = _STATE[key]
        self.inner = FlyPolicy(brain, ro, mode='passive' if spec.get('passive') else 'q',
                               margin=spec.get('margin', 0.01), pursue_bonus=spec.get('pursue_bonus', 0.0))

    def reset(self, cfg):
        self.inner.reset(cfg)

    def decide(self, feat, ob, arena):
        return self.inner.decide(feat, ob, arena)


class FlyRed:
    """Red flies the same option tactician as blue (frozen controller + shield v3 + a readout without a shared brain:
    ridge-on-features or MLP head) -> fly-vs-fly self play.  opponent name:  flyred:<path to readout .npz>"""

    def __init__(self, path, seed):
        import rollout_bfm as RB
        self.pilot = RB.ShieldedTacticalPilot(shield=False)
        self.pilot.enable_shield(RB.TIGHT3)
        self.arm = FlyArm(dict(opt=path, prune_cache=None, backend=None))
        self.arm.reset(dict(seed=seed))

    def act(self, obs, tick):
        if tick % 20 == 0:
            from feats import features
            from combat_v3.interface import geometry_from_observation
            geo = geometry_from_observation(obs)

            class _A:
                pass
            ar = _A(); ar.geo = geo
            self.pilot.set_tactic(int(self.arm.decide(features(obs, 0, tick), obs, ar)))
        return self.pilot.act(obs)[0]


def _install_flyred():
    import rollout
    if getattr(rollout.ScriptedRed, '_flyred', False):
        return
    Prev = rollout.ScriptedRed

    class _W:
        _flyred = True

        def __init__(self, kind, seed):
            self.inner = FlyRed(kind[len('flyred:'):], seed) if str(kind).startswith('flyred:') else Prev(kind, seed)

        def act(self, obs, tick):
            return self.inner.act(obs, tick)
    rollout.ScriptedRed = _W


def make_tuned_tactical():
    """tuned pursuit (ParamPilot with runs/tune01/best.json) for PURSUE; every other tactic is the frozen TacticalPilot code (as in
    bfm.DefPilot / portable.OpenPilot).  Shield v3 on top."""
    import json as _j
    import rollout_bfm as RB
    import bfm, tactics
    best = _j.loads((JEPA / 'runs' / 'tune01' / 'best.json').read_text(encoding='utf-8'))['params']

    class TunedTactical(bfm.ParamPilot):
        def act(self, observation, residual=None, started=True):
            if started and self.tactic != tactics.PURSUE:
                return tactics.TacticalPilot.act(self, observation)
            return super().act(observation, residual, started)
    return TunedTactical(best, shield=RB.TIGHT3)


def _task(args):
    cfg, arm, spec = args
    import rollout_bfm as RB
    _install_flyred()
    orig = RB.make_arm

    def patched(name):
        if isinstance(name, str) and name.startswith('fly_t3'):
            p = RB.ShieldedTacticalPilot(shield=False)
            p.enable_shield(RB.TIGHT3)
            return p, FlyArm(spec)
        if name == 'fly_tuned':                  # same tactician on top of YOUR tuned pursuit (runs/tune01/best.json) + shield v3
            return make_tuned_tactical(), FlyArm(spec)
        return orig(name)
    RB.make_arm = patched
    try:
        return RB.play_game(cfg, arm)
    except Exception:
        return dict(seed=cfg['seed'], red=cfg['red'], policy=arm, error=traceback.format_exc())
    finally:
        RB.make_arm = orig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--readout', default=None, help='Q readout from train_q.py (not needed with --opt)')
    ap.add_argument('--opt', default=None, help='option readout from train_branch.py (committed tactics, PURSUE by default); the .feat.npz file is the raw-feature control')
    ap.add_argument('--hold', type=int, default=None); ap.add_argument('--zone', type=float, default=None)
    ap.add_argument('--tau', type=float, default=None); ap.add_argument('--cooldown', type=int, default=3)
    ap.add_argument('--only', default=None, help='comma list of tactic ids the option policy may use, e.g. 1 = LEAD only')
    ap.add_argument('--prune-cache', default=None)
    ap.add_argument('--backend', default='auto', help='numba | torch | auto (used with --prune-cache; without it torch runs the full brain)')
    ap.add_argument('--arms', default='fly_t3,base_t3')
    ap.add_argument('--n', type=int, default=24)
    ap.add_argument('--seed0', type=int, default=910000, help='must differ from the training games (collect01 used 600000+)')
    ap.add_argument('--opponents', default='guide,lead,lag,mix,breaker,level')
    ap.add_argument('--workers', type=int, default=1)
    ap.add_argument('--margin', type=float, default=0.01, help='switch tactic only if Q(best) - Q(current) exceeds this')
    ap.add_argument('--pursue-bonus', type=float, default=0.0, help='added to Q(PURSUE): positive = more conservative')
    ap.add_argument('--feat', action='store_true', help='--readout is a raw-feature read-out (train_q.py --out-feat): control arm without the brain')
    ap.add_argument('--passive', action='store_true', help='fly only watches (always PURSUE); a plumbing check')
    ap.add_argument('--dt', type=float, default=1.0)
    ap.add_argument('--max-ticks', type=int, default=18000)
    ap.add_argument('--out', default='runs/fly_bfm')
    ap.add_argument('--resume', action='store_true', help='skip games already in <out>/results.jsonl (after a crash / restart)')
    a = ap.parse_args()
    import rollout
    if not a.readout and not a.opt:
        ap.error('one of --readout / --opt is required')
    spec = dict(readout=str(Path(a.readout).resolve()) if a.readout else None, opt=(a.opt if str(a.opt).startswith('random') else str(Path(a.opt).resolve())) if a.opt else None,
                hold=a.hold, zone=a.zone, tau=a.tau, cooldown=a.cooldown, only=[int(x) for x in a.only.split(',')] if a.only else None,
                prune_cache=str(Path(a.prune_cache).resolve()) if a.prune_cache else None,
                backend=a.backend, margin=a.margin, pursue_bonus=a.pursue_bonus, passive=a.passive, feat=a.feat, dt=a.dt)
    arms = [x for x in a.arms.split(',') if x]
    tasks = [(dict(rollout.game_config(i, a.seed0, red, a.max_ticks), host_fidelity=True), arm, spec)
             for red in a.opponents.split(',') for i in range(a.n) for arm in arms]
    out = HERE / a.out
    out.mkdir(parents=True, exist_ok=True)
    if a.resume and (out / 'results.jsonl').exists():
        done = set()
        for l in (out / 'results.jsonl').read_text(encoding='utf-8').splitlines():
            try:
                r = json.loads(l)
            except ValueError:
                continue
            if 'error' not in r:
                done.add((r['red'], r['seed'], r['policy']))
        tasks = [t for t in tasks if (t[0]['red'], t[0]['seed'], t[1]) not in done]
        print('resume: %d games already done, %d to go' % (len(done), len(tasks)), flush=True)
    (out / 'spec.json').write_text(json.dumps(dict(spec, arms=arms, n=a.n, seed0=a.seed0)), encoding='utf-8')
    results, sink, t0 = [], (out / 'results.jsonl').open('a', encoding='utf-8'), time.time()

    def handle(r):
        results.append(r)
        sink.write(json.dumps(r, ensure_ascii=False) + '\n'); sink.flush()
        tag = r['error'][-300:] if 'error' in r else '%s/%s %s winner=%s margin %s' % (r['policy'], r['red'], r['event'], r['winner'], r['margin'])
        print('[%d/%d %.0fs] %s' % (len(results), len(tasks), time.time() - t0, tag), flush=True)
    if a.workers <= 1:
        for t in tasks:
            handle(_task(t))
    else:
        import multiprocessing as mp
        with mp.get_context('spawn').Pool(a.workers, maxtasksperchild=8) as pool:
            for r in pool.imap_unordered(_task, tasks):
                handle(r)
    sink.close()
    rollout.summarize(results)


if __name__ == '__main__':
    main()
