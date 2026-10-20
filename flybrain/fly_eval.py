"""Closed-loop test of the fly brain in YOUR arena (jepa_brain.rollout.play_game), paired against PURSUE.

  python fly_eval.py --readout readout.npz --n 6 --device cuda --workers 1 --out runs\\fly01
  python fly_eval.py --passive --n 1 --opponents mix --record --out runs\\watch      # the fly only WATCHES (PURSUE flies)

Same seeds / distances / sides / altitudes for both arms (same as jepa_brain/rollout.py eval), so the table is a
paired comparison.  Nothing under jepa_brain/, campaign_2026/ or the official folder is modified.
"""
import argparse, json, sys, time, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JEPA = ROOT / 'jepa_brain'
for p in (str(JEPA), str(Path(__file__).resolve().parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

_STATE = {}


def _fly_policy(spec):
    import numpy as np
    from flybrain.pilot import FlyBrain, FlyPolicy, Readout
    key = (spec['device'], spec.get('readout'), spec.get('prune_cache'))
    if key not in _STATE:
        brain = FlyBrain(device=spec['device'], dt_ms=spec.get('dt', 1.0), window_ms=spec.get('window_ms', 80.0))
        if spec.get('prune_cache'):
            from flybrain.prune import keep_from_cache
            brain.prune(keep_from_cache(spec['prune_cache'])[0])
        ro = Readout.load(spec['readout']) if spec.get('readout') else None
        _STATE[key] = (brain, ro)
    brain, ro = _STATE[key]
    pol = FlyPolicy(brain, ro, mode='passive' if spec.get('passive') or ro is None else 'q',
                    margin=spec.get('margin', 0.01), record=spec.get('record', False))
    pol.record_dir = spec.get('record_dir')
    return pol


def _task(args):
    import numpy as np
    import rollout
    cfg, spec, out_data = args
    orig = rollout.get_policy
    holder = {}

    def patched(s):
        if s['type'] == 'fly':
            holder['p'] = _fly_policy(s)
            return holder['p']
        return orig(s)
    rollout.get_policy = patched
    try:
        res = rollout.play_game(cfg, spec, out_data)
        p = holder.get('p')
        if p is not None and p.record and p.record_dir and p.log:
            Path(p.record_dir).mkdir(parents=True, exist_ok=True)
            lens = [len(l['sparse'][0]) for l in p.log]
            np.savez_compressed(Path(p.record_dir) / ('fly_%d_%s.npz' % (cfg['seed'], cfg['red'])),
                                dn=np.stack([l['dn'] for l in p.log]), tactic=np.array([l['tactic'] for l in p.log]),
                                feats=np.stack([l['feat'] for l in p.log]), enc_mu=p.brain.enc.mu, enc_sd=p.brain.enc.sd,
                                sp_idx=np.concatenate([l['sparse'][0] for l in p.log]),
                                sp_cnt=np.concatenate([l['sparse'][1] for l in p.log]),
                                sp_ptr=np.concatenate([[0], np.cumsum(lens)]), cfg=json.dumps(cfg))
        return res
    except Exception:
        return dict(seed=cfg['seed'], red=cfg['red'], policy=spec['type'], error=traceback.format_exc())
    finally:
        rollout.get_policy = orig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--readout', default=None)
    ap.add_argument('--prune-cache', default=None, help='simulate only neurons that spiked in the games of this cache dir (faster; see README)')
    ap.add_argument('--passive', action='store_true', help='fly watches only; PURSUE is flown')
    ap.add_argument('--record', action='store_true', help='save the fly-brain activity of every fly game (for the viewer)')
    ap.add_argument('--n', type=int, default=6, help='games per opponent (same seeds for both arms)')
    ap.add_argument('--opponents', default='guide,lead,lag,mix,breaker,level')
    ap.add_argument('--workers', type=int, default=1)
    ap.add_argument('--dt', type=float, default=1.0, help='brain time step in ms; use the SAME value as replay.py (default 1.0) or the read-out sees different statistics')
    ap.add_argument('--device', default='cpu')
    ap.add_argument('--seed0', type=int, default=700000, help='use seeds that were NOT in the training games (collect01 used 600000+)')
    ap.add_argument('--max-ticks', type=int, default=18000)
    ap.add_argument('--no-baseline', action='store_true')
    ap.add_argument('--out', default='runs/fly')
    a = ap.parse_args()
    import rollout
    out = Path(__file__).resolve().parent / a.out
    spec = dict(type='fly', device=a.device, readout=str(Path(a.readout).resolve()) if a.readout else None,
                passive=a.passive, record=a.record, record_dir=str(out / 'activity'),
                dt=a.dt, prune_cache=str(Path(a.prune_cache).resolve()) if a.prune_cache else None)
    arms = ([] if a.no_baseline else [{'type': 'baseline'}]) + [spec]
    tasks = []
    for red in [o for o in a.opponents.split(',') if o]:
        for i in range(a.n):
            for s in arms:
                cfg = dict(rollout.game_config(i, a.seed0, red, a.max_ticks), host_fidelity=True)
                tasks.append((cfg, s, None))
    out.mkdir(parents=True, exist_ok=True)
    results = []
    sink = (out / 'results.jsonl').open('a', encoding='utf-8')

    def handle(r):
        results.append(r)
        sink.write(json.dumps(r, ensure_ascii=False) + '\n'); sink.flush()
        tag = r['error'][-300:] if 'error' in r else '%s/%s %s winner=%s atk %s/%s' % (r['policy'], r['red'], r['event'], r['winner'], r['atk_b'], r['atk_r'])
        print('[%d/%d] %s' % (len(results), len(tasks), tag), flush=True)
    t0 = time.time()
    if a.workers <= 1:
        for t in tasks:
            handle(_task(t))
    else:
        import multiprocessing as mp
        with mp.get_context('spawn').Pool(a.workers, maxtasksperchild=6) as pool:
            for r in pool.imap_unordered(_task, tasks):
                handle(r)
    sink.close()
    rollout.summarize(results)
    print('done in %.0f s -> %s' % (time.time() - t0, out))


if __name__ == '__main__':
    main()
