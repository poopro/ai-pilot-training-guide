"""Does portable/fighter_opt.py (single file, numpy only) fly the SAME games as the harness tactician?  Plays identical games with
  popt:<profile>   -> fighter_opt.build(profile) drives blue alone (no external policy)
  fly_t3 / fly_tuned  -> harness: FlyArm (flybrain/options.py) + ShieldedTacticalPilot / TunedTactical
and compares event / winner / margin / position scores / attack ticks game by game (the tactic histogram only exists for the harness arm).

  python portable_equiv.py --pairs popt:opt_ridge=fly_t3@ro/opt_b1_frozen.feat.npz,popt:opt_ridge:tuned=fly_tuned@ro/opt_b1_frozen.feat.npz \
        --opponents guide,lead --n 2 --seed0 1020000
"""
import argparse, json, sys, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for p in (str(ROOT / 'jepa_brain'), str(HERE), str(HERE / 'portable'), str(ROOT / 'campaign_2026' / 'repair_v1')):
    if p not in sys.path:
        sys.path.insert(0, p)


def _task(args):
    cfg, arm, spec = args
    import fly_bfm, rollout_bfm as RB
    fly_bfm._install_flyred()
    orig = RB.make_arm

    def patched(name):
        if isinstance(name, str) and name.startswith('popt:'):
            import fighter_opt
            return fighter_opt.build(name[5:]), None
        if isinstance(name, str) and name.startswith('fly_t3'):
            p = RB.ShieldedTacticalPilot(shield=False); p.enable_shield(RB.TIGHT3)
            return p, fly_bfm.FlyArm(spec)
        if name == 'fly_tuned':
            return fly_bfm.make_tuned_tactical(), fly_bfm.FlyArm(spec)
        return orig(name)
    RB.make_arm = patched
    try:
        r = RB.play_game(cfg, arm)
        r['spec'] = spec.get('opt')
        return r
    except Exception:
        return dict(seed=cfg['seed'], red=cfg['red'], policy=arm, error=traceback.format_exc())
    finally:
        RB.make_arm = orig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pairs', required=True, help='comma list  popt:<profile>=<harness arm>@<readout>')
    ap.add_argument('--opponents', default='guide,lead')
    ap.add_argument('--n', type=int, default=2)
    ap.add_argument('--seed0', type=int, default=1020000)
    ap.add_argument('--workers', type=int, default=2)
    a = ap.parse_args()
    import rollout, multiprocessing as mp
    jobs = []
    for pr in a.pairs.split(','):
        port, rest = pr.split('=', 1)
        arm, ro = rest.split('@')
        spec = dict(opt=str(Path(ro).resolve()), prune_cache=None, backend=None, hold=None, zone=None, tau=None, cooldown=3, only=None)
        for red in a.opponents.split(','):
            for i in range(a.n):
                cfg = dict(rollout.game_config(i, a.seed0, red, 18000), host_fidelity=True)
                jobs.append((cfg, port, spec)); jobs.append((cfg, arm, spec))
    res = {}
    with mp.get_context('spawn').Pool(a.workers, maxtasksperchild=6) as pool:
        for r in pool.imap_unordered(_task, jobs):
            if 'error' in r:
                print('ERROR', r['error'][-500:]); continue
            res[(r['policy'], r['red'], r['seed'], r['spec'])] = r
            print('.', end='', flush=True)
    print()
    bad = 0
    for pr in a.pairs.split(','):
        port, rest = pr.split('=', 1)
        arm, ro = rest.split('@')
        rp = str(Path(ro).resolve())
        for red in a.opponents.split(','):
            for i in range(a.n):
                seed = rollout.game_config(i, a.seed0, red, 18000)['seed']
                x, y = res.get((port, red, seed, rp)), res.get((arm, red, seed, rp))
                if not x or not y:
                    print('missing', port, red, seed); bad += 1; continue
                same = (x['event'], x['winner'], x['margin'], x['pos_b'], x['pos_r'], x['atk_b'], x['atk_r']) == (y['event'], y['winner'], y['margin'], y['pos_b'], y['pos_r'], y['atk_b'], y['atk_r'])
                bad += not same
                print('%-22s %-8s %d  %s | portable %s %s %8.1f nonPURSUE ticks %s | harness %s %s %8.1f %s' % (port, red, seed, 'SAME' if same else 'DIFF', x['event'], x['winner'], x['margin'], x['def_ticks'], y['event'], y['winner'], y['margin'], y['tactics']))
    print('games differing:', bad)


if __name__ == '__main__':
    main()
