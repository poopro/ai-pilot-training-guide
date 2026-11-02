"""DCSVET in the JSBSim arena: cloned DCS AI as red opponent ('dcsvet' / 'dcsvet:<weights.npz>')
and as a blue arm (DcsVetPilot), plus a small evaluator.

  python dcsvet_pool.py eval --weights W.npz --blue tuned2 --red dcsvet --games 12 --seed 990000 --out runs/x.jsonl
  python dcsvet_pool.py eval --weights W.npz --blue dcsvet --red lag ...

Importing this module chains 'dcsvet' onto rollout.ScriptedRed (same pattern as pool2).
"""
import os, sys, json, time, argparse, math
from pathlib import Path
import numpy as np
import rollout
import rollout_bfm                      # installs sac / pool2 kinds first
import dcsvet_core as C
from dcsvet_bc import DcsVetPolicy

HERE = Path(__file__).resolve().parent
DEFAULT_W = Path(os.environ.get('DCSVET_W', str(HERE / 'dcsvet' / 'bc.npz')))
_POL = {}


def policy(path=None):
    p = str(path or DEFAULT_W)
    if p not in _POL:
        _POL[p] = DcsVetPolicy(p)
    return _POL[p]


class DcsVetPilot:
    """Cloned DCS AI: policy at 15 Hz -> lift-vector low-level at 60 Hz."""
    def __init__(self, weights=None, every=4, floor_m=1200., cas_floor=430., energy_cap=True, soft_alt=3000.):
        """cas_floor: DCS AI holds ~420-470 KCAS at full power (SFM); JSBSim cannot, so the speed channel keeps
        max power down to this CAS instead of copying the AI's 2 s speed change.
        energy_cap: limit commanded g below corner speed so the JSBSim jet does not bleed to a stall."""
        self.cas_floor = cas_floor
        self.soft_alt = soft_alt
        self.gov_ticks = 0
        self.energy_cap = energy_cap
        self.pol = policy(weights)
        self.low = C.LiftPilot(floor_m=floor_m)
        self.every = every
        self.tick = 0
        self.cmd = None
        self.shield_ticks = 0

    def set_tactic(self, t):
        pass

    def alt_governor(self, o, mu):
        """DCS AI spirals down to the sea (nose-low turns, lift vector below the horizon).
        Below soft_alt the lift vector may not point below the horizon; deeper down it is forced upward.
        Hard recovery (LiftPilot floor, ~1200 m / 6 s to floor) stays as the last line."""
        alt = o[2] * C.FT
        if alt >= self.soft_alt:
            return mu
        frac = float(np.clip((self.soft_alt - alt) / (self.soft_alt - self.low.floor), 0., 1.))
        lim = 90. - 45. * frac                        # 90 deg at soft_alt -> 45 deg at the floor
        self.gov_ticks += 1
        return float(np.clip(C.wrap180(mu), -lim, lim))

    def act(self, obs, residual=None, started=True):
        o = np.asarray(obs, dtype=np.float64)
        if self.cmd is None or self.tick % self.every == 0:
            mu, n, dcas = self.pol.predict(C.features(o))
            cas = o[12] * C.FPS_TO_KT
            if self.energy_cap:
                n = min(n, float(np.clip(3. + (cas - 250.) / 80. * 5.6, 3., 8.6)))
            mu = self.alt_governor(o, mu)
            self.cmd = (mu, n, max(cas + dcas, self.cas_floor))
        self.tick += 1
        out, guard = self.low.command(o, *self.cmd)
        if guard:
            self.shield_ticks += 1
        return out, guard


class DcsVetRed:
    def __init__(self, kind):
        w = kind.split(':', 1)[1] if ':' in kind else None
        self.pilot = DcsVetPilot(w)

    def act(self, obs, tick):
        return self.pilot.act(obs)[0]


_Prev = rollout.ScriptedRed


class ArmRed:
    """Any blue arm flown as the red jet: kind 'arm=<arm spec>', e.g. 'arm=tuned2' or 'arm=tuned2f:turn_cas=340'."""
    def __init__(self, kind):
        self.pilot, self.pol = make_blue(kind.split('=', 1)[1])

    def act(self, obs, tick):
        from opponents import DECISION_TICKS
        if self.pol is not None and tick % DECISION_TICKS == 0:
            self.pilot.set_tactic(int(self.pol.decide(None, obs, None)))
        return self.pilot.act(obs)[0]


class _WrapDV:
    def __init__(self, kind, seed):
        self.kind = kind
        if kind.startswith('kr:') or kind.startswith('krl:'):                 # external: Korean TOPGUN 2026 1st-place team PPO pilots (kr_red.py)
            from kr_red import KRRed
            self.inner = KRRed(kind, seed)
        elif kind.startswith('arm='):
            self.inner = ArmRed(kind)
        else:
            self.inner = DcsVetRed(kind) if kind.split(':')[0] == 'dcsvet' else _Prev(kind, seed)

    def act(self, obs, tick):
        return self.inner.act(obs, tick)


# 2026-10-28: remember the current Arena so reds that need the full state of both jets (kr:) can read it
import arena as _arena_mod
if not getattr(_arena_mod.Arena.__init__, '_registers', False):
    _orig_arena_init = _arena_mod.Arena.__init__

    def _arena_init(self, *a, **k):
        _orig_arena_init(self, *a, **k)
        import kr_red
        kr_red.CURRENT['arena'] = self
    _arena_init._registers = True
    _arena_mod.Arena.__init__ = _arena_init

if getattr(rollout.ScriptedRed, '__name__', '') != '_WrapDV':
    rollout.ScriptedRed = _WrapDV


class _RLKBlue:
    """Teammate's fine-tuned Korean-type pilot (team_pack RLPilot: official 26-D obs in, 4 controls out), 2026-11-01.
    arm 'rlk:<npz path>:<grid lin|aip>:<mode aip|kr>'; relative paths are looked up in ../ext_team."""
    def __init__(self, arm):
        import sys
        parts = arm.split(':')
        path, grid, mode = parts[1], (parts[2] if len(parts) > 2 else 'lin'), (parts[3] if len(parts) > 3 else 'aip')
        d = HERE.parent / 'ext_team'
        if str(d) not in sys.path:
            sys.path.insert(0, str(d))
        from rl_client import RLPilot
        p = Path(path) if Path(path).is_absolute() else d / path
        self.p = RLPilot(str(p), grid=grid, mode=mode)
        self.drop = float(parts[4]) if len(parts) > 4 else 0.          # optional packet-loss probability (2026-11-01)
        self.rng = np.random.default_rng(7)
        self.last = np.array([0., 0., 0., .8])

    def set_tactic(self, t):
        pass

    def act(self, observation, residual=None, started=True):
        if self.drop > 0 and self.rng.random() < self.drop:
            return self.last.copy(), False
        self.last = np.asarray(self.p.feed([float(x) for x in observation[:26]]), dtype=np.float64).copy()
        return self.last.copy(), False


class _KV2PkgBlue:
    """ChatGPT's Korea V2 deployment code (korean_v1.policy.KoreanV1 + clock.PolicyClock, packet-count clock) fed with the
    official 26-double packet, optionally dropping packets: arm 'kv2pkg:<drop prob>[:<seed>]' (2026-11-01, review item P1)."""
    def __init__(self, arm):
        import sys
        parts = arm.split(':')
        self.drop = float(parts[1]) if len(parts) > 1 else 0.
        self.rng = np.random.default_rng(int(parts[2]) if len(parts) > 2 else 0)
        d = HERE.parent / 'ext_kv1'
        if str(d) not in sys.path:
            sys.path.insert(0, str(d))
        from korean_v1.policy import KoreanV1
        if arm.startswith('kv2c:'):                                   # the patched deployment clock (korean_v2c)
            from korean_v1.clock_v2c import PolicyClock
        else:
            from korean_v1.clock import PolicyClock
        self.clock = PolicyClock(KoreanV1('gylee_20k'))
        self.act_ = np.array([0., 0., 0., .8])
        self.dropped = 0

    def set_tactic(self, t):
        pass

    def act(self, observation, residual=None, started=True):
        if self.drop > 0 and self.rng.random() < self.drop:
            self.dropped += 1
            return self.act_.copy(), False                       # packet lost: Host keeps the last command
        self.act_ = np.asarray(self.clock.step([float(x) for x in observation[:26]], True), dtype=np.float64)
        return self.act_.copy(), False


class _KV2FixBlue(_KV2PkgBlue):
    """Same deployment policy, but time = distance flown / speed between received packets (no packet counting);
    decide whenever >= 0.1 s of estimated time has passed.  arm 'kv2fix:<drop prob>[:<seed>]'."""
    def __init__(self, arm):
        super().__init__(arm)
        self.pol = self.clock.policy
        self.pol.reset()
        self.prev = None
        self.t = 0.
        self.t_dec = None

    def act(self, observation, residual=None, started=True):
        if self.drop > 0 and self.rng.random() < self.drop:
            self.dropped += 1
            return self.act_.copy(), False
        o = np.asarray([float(x) for x in observation[:26]])
        if self.prev is not None:
            p = self.prev
            dn = math.radians(o[0] - p[0]) * 6378137.
            de = math.radians(o[1] - p[1]) * 6378137. * math.cos(math.radians(p[0]))
            du = (o[2] - p[2]) * .3048
            v = .5 * (np.linalg.norm(o[15:18]) + np.linalg.norm(p[15:18])) * .3048
            if v > 1.:
                self.t += float(np.sqrt(dn * dn + de * de + du * du)) / v
            elif np.array_equal(o, p):
                return self.act_.copy(), False
        self.prev = o
        if self.t_dec is None or self.t - self.t_dec >= .1 - .5 / 60.:
            self.t_dec = self.t
            self.act_ = np.asarray(self.pol.command(o, self.t), dtype=np.float64)
        return self.act_.copy(), False


def make_blue(arm, weights=None):
    if arm.startswith('kv2fix:'):
        return _KV2FixBlue(arm), None
    if arm.startswith('kv2pkg:') or arm.startswith('kv2c:'):
        return _KV2PkgBlue(arm), None
    if arm.startswith('rlk:'):
        return _RLKBlue(arm), None
    if arm.startswith('kr:') or arm.startswith('krl:'):      # Korean PPO pilot as blue (2026-10-28)
        from kr_red import KRBlue
        return KRBlue(arm), None
    if arm == 'dcsvet':
        return DcsVetPilot(weights), None
    if arm == 'tuned2':
        params = json.loads((HERE / 'runs' / 'tune02' / 'best.json').read_text(encoding='utf-8'))['params']
        return rollout_bfm.make_arm({'params': params})
    if arm.split(':')[0] == 'jinksoft':         # milder: tighter cone, only very close, gentler pull, slower changes
        from jink import JinkPilot
        inner, pol = make_blue(arm.split(':', 1)[1], weights)
        return JinkPilot(inner, cone_deg=4., r_max=950., period_s=1.5, n=5.5), pol
    if arm.split(':')[0] == 'jink':             # defensive jink around any finisher arm: jink:<inner arm> (2026-10-28)
        from jink import JinkPilot
        inner, pol = make_blue(arm.split(':', 1)[1], weights)
        return JinkPilot(inner), pol
    if arm.split(':')[0] == 'fin4':             # tune4 result: fin4:<run dir> (best.json cfg; WidePilot base with its bank_cap), 2026-10-28
        from finisher import FinisherPilot
        import wide_pilot
        d = json.loads((HERE / arm.split(':', 1)[1] / 'best.json').read_text())['cfg']
        p = dict(wide_pilot.tuned2_params(), bank_cap=float(d['bank_cap']))
        cfg = dict(aa_max=180., enter_deg=180., exit_deg=180., enter_m=3000., exit_m=3500., turn_cas=340., n_cap=8., merge_off_m=400.)
        cfg.update({k: float(v) for k, v in d.items() if k != 'bank_cap'})
        return FinisherPilot(wide_pilot.WidePilot(p), cfg), None
    if arm.split(':')[0] == 'dcsv2frs':         # + collision shield for the far-range net (2026-10-28): dcsv2frs:<weights>
        from dcsvet_v2 import DcsV2Pilot
        cfg = dict(aa_max=180., enter_deg=180., exit_deg=180., enter_m=3000., exit_m=3500., turn_cas=340., n_cap=8., merge_off_m=400., rec_v2=1., v2_shield=1.)
        return DcsV2Pilot(arm.split(':', 1)[1], fin_cfg=cfg).fin, None
    if arm.split(':')[0] == 'dcsv2fr':          # same + finisher F4R and ground recovery v2 (2026-10-27): dcsv2fr:<weights>
        from dcsvet_v2 import DcsV2Pilot
        cfg = dict(aa_max=180., enter_deg=180., exit_deg=180., enter_m=3000., exit_m=3500., turn_cas=340., n_cap=8., merge_off_m=400., rec_v2=1.)
        return DcsV2Pilot(arm.split(':', 1)[1], fin_cfg=cfg).fin, None
    if arm.split(':')[0] == 'dcsv2f':           # DCS intent imitation (far) + finisher (close): dcsv2f:<weights>
        from dcsvet_v2 import DcsV2Pilot
        return DcsV2Pilot(arm.split(':', 1)[1]).fin, None
    if arm.split(':')[0] == 'tuned2f':          # tuned2 + close-range lift-vector finisher, e.g. tuned2f:k_ang=2.5:hold_m=450
        from finisher import FinisherPilot
        params = json.loads((HERE / 'runs' / 'tune02' / 'best.json').read_text(encoding='utf-8'))['params']
        base, pol = rollout_bfm.make_arm({'params': params})
        cfg = {kv.split('=')[0]: float(kv.split('=')[1]) for kv in arm.split(':')[1:]}
        return FinisherPilot(base, cfg), pol
    return rollout_bfm.make_arm(arm)


DIST = (3000, 6000, 9000)


def game_cfg(seed, i, max_ticks=18000):
    rng = np.random.default_rng(seed * 7919 + 13)
    return dict(seed=int(seed), distance_ft=DIST[i % 3], side=1 if (i // 3) % 2 == 0 else -1,
                altitude_ft=float(rng.uniform(10000, 20000)), max_ticks=max_ticks)


def play(cfg, blue, red_kind, weights=None, trace=False):
    from arena import Arena
    from opponents import DECISION_TICKS
    t0 = time.time()
    arena = Arena(cfg['seed'], cfg['distance_ft'], cfg['side'], cfg['altitude_ft'], host_fidelity=True)
    pilot, pol = make_blue(blue, weights)
    if pol is not None and hasattr(pol, 'reset'):
        pol.reset(cfg)
    if red_kind.split(':')[0] == 'dcsvet' and weights and ':' not in red_kind:
        red_kind = 'dcsvet:' + str(weights)
    red = rollout.ScriptedRed(red_kind, cfg['seed'] + 1)
    done = False
    tr = []
    min_agl = [1e9, 1e9]
    while not done and arena.tick < cfg['max_ticks']:
        ob = arena.obs_blue()
        if pol is not None and arena.tick % DECISION_TICKS == 0:
            pilot.set_tactic(int(pol.decide(None, ob, arena)))
        bcmd, _ = pilot.act(ob)
        orr = arena.obs_red()
        done = arena.step(bcmd, red.act(orr, arena.tick))
        min_agl[0] = min(min_agl[0], arena.agl_blue_m())
        min_agl[1] = min(min_agl[1], float(arena.fdm2.fdm['position/h-agl-ft']) * C.FT)
        if trace and arena.tick % 6 == 0:
            tr.append([arena.tick / 60.] + list(ob[[0, 1, 2]]) + list(orr[[0, 1, 2]]) + list(ob[3:6]) + list(orr[3:6]))
    snap = arena.judge.snapshot()
    ts = snap['total_score'] or snap['advantage']
    res = dict(seed=cfg['seed'], blue=blue, red=red_kind.split(':')[0], distance_ft=cfg['distance_ft'], side=cfg['side'],
               altitude_ft=round(cfg['altitude_ft']), event=snap['event'], winner=snap['winner'], ticks=snap['ticks'],
               atk_b=snap['attack_ticks'][0], atk_r=snap['attack_ticks'][1],
               pos_b=round(snap['position_sum'][0], 1), pos_r=round(snap['position_sum'][1], 1),
               overg_b=snap['over_g_ticks'][0], overg_r=snap['over_g_ticks'][1], margin=round(ts[0] - ts[1], 1),
               min_agl_b=round(min_agl[0]), min_agl_r=round(min_agl[1]), wall_s=round(time.time() - t0, 1))
    if trace:
        res['trace'] = tr
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd')
    ap.add_argument('--weights', default=None)
    ap.add_argument('--blue', default='tuned2')
    ap.add_argument('--red', default='dcsvet')
    ap.add_argument('--games', type=int, default=12)
    ap.add_argument('--seed', type=int, default=990000)
    ap.add_argument('--out', default=None)
    ap.add_argument('--workers', type=int, default=1)
    a = ap.parse_args()
    cfgs = [game_cfg(a.seed + i, i) for i in range(a.games)]
    args = [(c, a.blue, a.red, a.weights) for c in cfgs]
    if a.workers > 1:
        from multiprocessing import Pool
        with Pool(a.workers) as p:
            rs = p.starmap(play, args)
    else:
        rs = [play(*x) for x in args]
    W = sum(r['winner'] == 'blue' for r in rs); L = sum(r['winner'] == 'red' for r in rs)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        with open(a.out, 'a', encoding='utf-8') as f:
            for r in rs:
                f.write(json.dumps(r) + '\n')
    for r in rs:
        print(r['distance_ft'], r['side'], r['event'], r['winner'], 'atk', r['atk_b'], r['atk_r'], 'margin', r['margin'],
              'agl', r['min_agl_b'], r['min_agl_r'], 'overg', r['overg_b'], r['overg_r'])
    print('%s vs %s: W-L-D %d-%d-%d' % (a.blue, a.red, W, L, len(rs) - W - L))


if __name__ == '__main__':
    main()
