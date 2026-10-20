"""Closed-loop test of simple hand-written tactic rules in your rollout_bfm harness (frozen repair_guide + shield v3 flies;
only the tactic choice differs), paired with base_t3 on the same seeds.

  python rule_test.py --arms lead_all,lead_near --opponents guide,lead,lag,mix,breaker,level --n 12 --seed0 950000 --workers 2 --out runs/rule01

Rules:  lead_all   = LEAD at every decision
        lead_near  = LEAD while range < --zone (3500 m), PURSUE otherwise
        lead_Rxxxx = LEAD while range < xxxx m
"""
import argparse, json, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for p in (str(ROOT / 'jepa_brain'), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)


class RulePolicy:
    needs_feat = False
    name = 'rule'

    def __init__(self, arm):
        self.arm = arm

    def reset(self, cfg):
        pass

    def decide(self, feat, ob, arena):
        from tactics import PURSUE, LEAD
        d = arena.geo['distance_m']
        if self.arm == 'lead_all':
            return LEAD
        if self.arm == 'lead_near':
            return LEAD if d < 3500. else PURSUE
        if self.arm.startswith('lead_R'):
            return LEAD if d < float(self.arm[6:]) else PURSUE
        raise ValueError(self.arm)


def _task(args):
    cfg, arm = args
    import rollout_bfm as RB
    orig = RB.make_arm

    def patched(name):
        if isinstance(name, str) and name.startswith('lead_'):
            p = RB.ShieldedTacticalPilot(shield=False)
            p.enable_shield(RB.TIGHT3)
            return p, RulePolicy(name)
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
    ap.add_argument('--arms', default='lead_all,lead_near')
    ap.add_argument('--opponents', default='guide,lead,lag,mix,breaker,level')
    ap.add_argument('--n', type=int, default=12)
    ap.add_argument('--seed0', type=int, default=950000)
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--max-ticks', type=int, default=18000)
    ap.add_argument('--with-base', action='store_true', help='also play base_t3 (needed for seeds that have no base rows yet)')
    ap.add_argument('--out', default='runs/rule01')
    a = ap.parse_args()
    import rollout
    arms = [x for x in a.arms.split(',') if x] + (['base_t3'] if a.with_base else [])
    tasks = [(dict(rollout.game_config(i, a.seed0, red, a.max_ticks), host_fidelity=True), arm)
             for arm in arms for red in a.opponents.split(',') for i in range(a.n)]
    out = HERE / a.out
    out.mkdir(parents=True, exist_ok=True)
    sink, t0, k = (out / 'results.jsonl').open('a', encoding='utf-8'), time.time(), 0
    import multiprocessing as mp
    with mp.get_context('spawn').Pool(a.workers, maxtasksperchild=8) as pool:
        for r in pool.imap_unordered(_task, tasks):
            k += 1
            sink.write(json.dumps(r, ensure_ascii=False) + '\n'); sink.flush()
            print('[%d/%d %.0fs] %s' % (k, len(tasks), time.time() - t0, r['error'][-300:] if 'error' in r else '%s/%s %s winner=%s margin %s atk %s/%s' % (r['policy'], r['red'], r['event'], r['winner'], r['margin'], r['atk_b'], r['atk_r'])), flush=True)
    sink.close()


if __name__ == '__main__':
    main()
