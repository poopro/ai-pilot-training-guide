"""Counterfactual tactic labels by BRANCHING a running game (os.fork).

Why: the offline Monte-Carlo returns used before cannot tell which tactic caused what (R^2 ~ 0, see README 5/6.6).  Here, at a
decision tick of a game flown by the roll-in policy (default: your base_t3 = frozen repair_guide + shield v3 + PURSUE), the whole
simulator process is forked once per option.  Option a = "fly tactic a for --hold decisions (20 ticks each), then PURSUE again"
until --horizon ticks have passed.  The label of option a at that state is the change of the judge's advantage
(blue minus red: 10000*attack_ticks/60 - 100*over_g_ticks/60 + position index sum) over the horizon, plus/minus TERM when the
branch ends decisively (kill, crash, collision).  Every option sees exactly the same state, opponent and random seed, so
differences between options are caused by the option - this is the signal the random-exploration data did not have.

  python branch_labels.py --opponents guide,lag,lead --n 2 --seed0 800000 --workers 2 --out labels/pilot
  python branch_labels.py --check ...        # also verifies that the PURSUE branch reproduces the parent's own future exactly

Output per game: labels/g<seed>_<opp>.npz with feats (all decisions of the roll-in game), lab_dec (decision index of each
labelled state), lab_delta / lab_term [m, 9] (columns 0-7 = tactics, column 8 = null: PURSUE nudged by 0.002 aileron once), lab_range / lab_ata / lab_rata.

Linux / macOS only (os.fork).  Nothing under jepa_brain/ or campaign_2026/ is modified.
"""
import argparse, json, os, sys, time, traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
JEPA = ROOT / 'jepa_brain'
for p in (str(JEPA), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

TERM = 3000.0          # added to a branch's label when it ends decisively (blue win +, red win -)
DEC = 20               # ticks per decision (3 Hz)
NULL = 8               # option id 8 = PURSUE with a tiny aileron nudge on the first tick: measures how much the label moves by chaos alone


def _branch_child(arena, pilot, red, tick0, opt, hold, horizon, wfd):
    """runs in the forked child: fly option `opt`, report the advantage change, exit"""
    try:
        import numpy as np
        from tactics import PURSUE
        adv = arena.judge.advantages()
        d0, a0, g0 = adv[0] - adv[1], list(arena.judge.attack), list(arena.judge.over_g)
        done = False
        while not done and arena.tick < tick0 + horizon:
            ob = arena.obs_blue()
            if arena.tick % DEC == 0:
                pilot.set_tactic(PURSUE if opt == NULL else (opt if (arena.tick - tick0) // DEC < hold else PURSUE))
            bcmd, _ = pilot.act(ob)
            if opt == NULL and arena.tick == tick0:
                bcmd = np.asarray(bcmd, dtype=float) + np.array([0.002, 0., 0., 0.])
            done = arena.step(bcmd, red.act(arena.obs_red(), arena.tick))
        snap = arena.judge.snapshot()
        adv = arena.judge.advantages()
        term = 0.0
        if done:
            term = TERM if snap['winner'] == 'blue' else (-TERM if snap['winner'] == 'red' else 0.0)
        out = dict(delta=adv[0] - adv[1] - d0, term=term, event=snap['event'], winner=snap['winner'], ticks=arena.tick - tick0,
                   atk_b=arena.judge.attack[0] - a0[0], atk_r=arena.judge.attack[1] - a0[1],
                   overg=arena.judge.over_g[0] - g0[0])
    except Exception:
        out = dict(error=traceback.format_exc()[-500:])
    os.write(wfd, json.dumps(out).encode())
    os.close(wfd)
    os._exit(0)


def branch(arena, pilot, red, tick0, opts, hold, horizon):
    """fork one child per option (one after the other), return a list of result dicts"""
    res = []
    sys.stdout.flush(); sys.stderr.flush()
    for opt in opts:
        r, w = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(r)
            _branch_child(arena, pilot, red, tick0, opt, hold, horizon, w)
        os.close(w)
        chunks = []
        while True:
            b = os.read(r, 65536)
            if not b:
                break
            chunks.append(b)
        os.close(r)
        os.waitpid(pid, 0)
        d = json.loads(b''.join(chunks).decode())
        if 'error' in d:
            raise RuntimeError('branch child failed: ' + d['error'])
        res.append(d)
    return res


def make_rollin(a, cfg):
    """None = always PURSUE (= base_t3).  Other roll-in policies (for DAgger rounds) are built here."""
    if a.rollin == 'pursue':
        return None
    if a.rollin == 'opt':                       # DAgger round: states visited by a learned option policy (fly_bfm.FlyArm)
        import fly_bfm
        spec = dict(readout=None, opt=str(Path(a.opt).resolve()), hold=None, zone=None, tau=a.tau, cooldown=3, only=None,
                    prune_cache=str(Path(a.prune_cache).resolve()) if a.prune_cache else None, backend=a.backend, dt=1.0)
        return fly_bfm.FlyArm(spec)
    raise ValueError('unknown roll-in ' + a.rollin)


def label_game(cfg, a):
    import numpy as np
    import rollout
    import rollout_bfm as RB
    from arena import Arena
    from feats import features
    from tactics import PURSUE, N_TACTICS

    t0 = time.time()
    arena = Arena(cfg['seed'], cfg['distance_ft'], cfg['side'], cfg['altitude_ft'], host_fidelity=True)
    if getattr(a, 'pilot', 'base_t3') == 'tuned':        # labels relative to YOUR tuned pursuit (runs/tune01/best.json) + shield v3
        import fly_bfm
        pilot = fly_bfm.make_tuned_tactical()
    else:
        pilot = RB.ShieldedTacticalPilot(shield=False)
        pilot.enable_shield(RB.TIGHT3)
    if str(cfg['red']).startswith('flyred:'):             # self-play labels: the red side flies a fly-style option tactician
        import fly_bfm
        fly_bfm._install_flyred()
    red = rollout.ScriptedRed(cfg['red'], cfg['seed'] + 1)
    rollin = make_rollin(a, cfg)
    if rollin is not None:
        rollin.reset(cfg)
    rng = np.random.default_rng(cfg['seed'] + 4242)
    sub = [int(x) for x in a.options.split(',')] if a.options else list(range(N_TACTICS))
    opts = sub + ([] if a.no_null else [NULL])
    n_opt = len(opts)
    near_off, far_off = int(rng.integers(a.near_stride)), int(rng.integers(a.far_stride))
    n_near = n_far = 0
    feats, rows, checks = [], [], []
    done = False
    while not done and arena.tick < cfg['max_ticks']:
        ob = arena.obs_blue()
        if arena.tick % DEC == 0:
            dec = arena.tick // DEC
            feat = features(ob, arena.judge.attack[0], arena.tick)
            feats.append(feat)
            g = arena.geo
            if g['distance_m'] < a.zone:
                n_near += 1
                take = (n_near + near_off) % a.near_stride == 0
            else:
                n_far += 1
                take = (n_far + far_off) % a.far_stride == 0
            if take and dec >= 1 and arena.tick + a.horizon <= cfg['max_ticks'] and len(rows) < a.max_states:
                adv = arena.judge.advantages()
                if a.check:
                    checks.append((arena.tick + a.horizon, adv[0] - adv[1], len(rows)))
                res = branch(arena, pilot, red, arena.tick, opts, a.hold, a.horizon)
                rows.append(dict(dec=dec, range=g['distance_m'], ata=g['blue_angle_deg'], rata=g['red_angle_deg'], res=res))
            tac = PURSUE if rollin is None else int(rollin.decide(feat, ob, arena))
            pilot.set_tactic(tac)
        bcmd, _ = pilot.act(ob)
        done = arena.step(bcmd, red.act(arena.obs_red(), arena.tick))
        if a.check:                                   # the parent's own PURSUE future must equal the PURSUE branch
            for tgt, d0, k in [c for c in checks if c[0] == arena.tick]:
                adv = arena.judge.advantages()
                rows[k]['parent_delta'] = adv[0] - adv[1] - d0
    m = len(rows)
    delta = np.array([[r['delta'] for r in row['res']] for row in rows], np.float32).reshape(m, n_opt)
    term = np.array([[r['term'] for r in row['res']] for row in rows], np.float32).reshape(m, n_opt)
    atk = np.array([[[r['atk_b'], r['atk_r']] for r in row['res']] for row in rows], np.int16).reshape(m, n_opt, 2)
    overg = np.array([[r['overg'] for r in row['res']] for row in rows], np.int16).reshape(m, n_opt)
    if a.options:                                   # un-labelled tactics: filled with a clearly bad advantage (-300 = the training clip)
        full_cols = list(range(N_TACTICS)) + ([] if a.no_null else [NULL])
        n_full = len(full_cols)
        d2 = np.full((m, n_full), -300.0, np.float32); t2 = np.zeros((m, n_full), np.float32)
        k2 = np.zeros((m, n_full, 2), np.int16); g2 = np.zeros((m, n_full), np.int16)
        for j, o in enumerate(opts):
            c = full_cols.index(o)
            d2[:, c], t2[:, c], k2[:, c], g2[:, c] = delta[:, j], term[:, j], atk[:, j], overg[:, j]
        # the PURSUE column (0) is the reference; if it was not requested the file is useless, so force it
        assert 0 in opts, '--options must include 0 (PURSUE)'
        delta, term, atk, overg = d2, t2, k2, g2
    out = dict(feats=np.asarray(feats, np.float32), lab_dec=np.array([r['dec'] for r in rows], np.int32),
               lab_range=np.array([r['range'] for r in rows], np.float32), lab_ata=np.array([r['ata'] for r in rows], np.float32),
               lab_rata=np.array([r['rata'] for r in rows], np.float32), lab_delta=delta, lab_term=term, lab_atk=atk, lab_overg=overg)
    info = dict(seed=cfg['seed'], red=cfg['red'], states=m, near=int(sum(r['range'] < a.zone for r in rows)),
                wall_s=round(time.time() - t0, 1), snapshot=arena.judge.snapshot()['event'])
    if a.check:
        errs = [abs(r['parent_delta'] - r['res'][0]['delta']) for r in rows if 'parent_delta' in r]
        info['check_max_abs_err'] = float(max(errs)) if errs else None
        info['check_n'] = len(errs)
    redname = str(cfg['red'])
    if redname.startswith('flyred:'):                     # file name of a self-play opponent: sp-<head file stem>
        redname = 'sp-' + Path(redname[len('flyred:'):].replace('\\', '/')).stem.replace('_', '-').replace('.', '-')
    out_path = Path(a.out) / ('g%d_%s.npz' % (cfg['seed'], redname))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_path, **out)
    return info


def _task(args):
    cfg, a = args
    try:
        return label_game(cfg, a)
    except Exception:
        return dict(seed=cfg['seed'], red=cfg['red'], error=traceback.format_exc()[-800:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--opponents', default='guide,lag,lead')
    ap.add_argument('--n', type=int, default=2, help='games per opponent')
    ap.add_argument('--seed0', type=int, default=800000)
    ap.add_argument('--first', type=int, default=0, help='first game index (use to add more games later without repeating seeds)')
    ap.add_argument('--hold', type=int, default=6, help='option length in decisions (6 = 2 s)')
    ap.add_argument('--horizon', type=int, default=900, help='ticks to look ahead (900 = 15 s)')
    ap.add_argument('--zone', type=float, default=3500., help='range (m) below which a state counts as "near"')
    ap.add_argument('--near-stride', type=int, default=6, help='label every k-th near decision')
    ap.add_argument('--far-stride', type=int, default=30, help='label every k-th far decision')
    ap.add_argument('--max-states', type=int, default=80)
    ap.add_argument('--rollin', default='pursue', help='pursue | opt (needs --opt, --prune-cache)')
    ap.add_argument('--opt', default=None); ap.add_argument('--tau', type=float, default=None)
    ap.add_argument('--prune-cache', default=None); ap.add_argument('--backend', default='numba')
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--max-ticks', type=int, default=18000)
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--options', default='', help='comma list of tactic ids to label (must include 0); the others are filled with -300. Default: all 8')
    ap.add_argument('--no-null', action='store_true', help='skip the chaos-noise control option (saves 11%% of the time)')
    ap.add_argument('--pilot', default='base_t3', help='base_t3 | tuned: the pursuit law whose PURSUE branch is the reference')
    ap.add_argument('--out', default='labels/pilot')
    a = ap.parse_args()
    import rollout
    tasks = [(dict(rollout.game_config(i, a.seed0, red, a.max_ticks), host_fidelity=True), a)
             for red in a.opponents.split(',') for i in range(a.first, a.first + a.n)]
    t0 = time.time()
    done = 0

    def handle(r):
        nonlocal done
        done += 1
        print('[%d/%d %.0fs] %s' % (done, len(tasks), time.time() - t0, json.dumps(r, ensure_ascii=False)), flush=True)
    if a.workers <= 1:
        for t in tasks:
            handle(_task(t))
    else:
        import multiprocessing as mp
        with mp.get_context('spawn').Pool(a.workers, maxtasksperchild=2) as pool:
            for r in pool.imap_unordered(_task, tasks):
                handle(r)


if __name__ == '__main__':
    main()
