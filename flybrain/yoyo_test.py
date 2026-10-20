"""Does a COMMITTED high yo-yo help?  A small, honest test of the idea "when the fight stalls, go up in the z axis".

The tactician is a hand-written rule, not learned: when the other aircraft is close (range < --trig-range), we are closing
on it and our nose is more than --min-ata degrees off the line of sight, fly HIGH_YOYO for --hold decisions (1 decision =
20 ticks = 0.33 s), then PURSUE again; at most one yo-yo per --cooldown decisions.  The flying itself is exactly
base_t3's (frozen repair_guide controller + collision shield v3), so any difference comes from the yo-yo alone.

  python yoyo_test.py --holds 3,9,15 --opponents lag,lead,guide --n 12 --seed0 950000 --workers 2 --out runs/yoyo01

Prints, for every variant, win-loss against base_t3 on the SAME seeds (read from --base-results, default the val_dn_g99 run).
"""
import argparse, json, sys, time, traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
JEPA = ROOT / 'jepa_brain'
for p in (str(JEPA), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)


class YoyoPolicy:
    needs_feat = False
    name = 'yoyo'

    def __init__(self, hold=6, trig_range=1800., min_ata=30., cooldown=30, tactic=None):
        from tactics import HIGH_YOYO
        self.hold, self.trig, self.min_ata, self.cooldown = int(hold), float(trig_range), float(min_ata), int(cooldown)
        self.tactic = HIGH_YOYO if tactic is None else int(tactic)

    def reset(self, cfg):
        self.left, self.cool, self.prev_d, self.n_yoyo = 0, 0, None, 0

    def decide(self, feat, ob, arena):
        from tactics import PURSUE
        g = arena.geo
        d, ata = g['distance_m'], g['blue_angle_deg']
        closing = self.prev_d is not None and d < self.prev_d
        self.prev_d = d
        if self.left > 0:
            self.left -= 1
            return self.tactic
        if self.cool > 0:
            self.cool -= 1
        elif d < self.trig and closing and ata > self.min_ata:
            self.left, self.cool = self.hold - 1, self.cooldown
            self.n_yoyo += 1
            return self.tactic
        return PURSUE


def _task(args):
    cfg, arm, spec = args
    import rollout_bfm as RB
    orig = RB.make_arm

    def patched(name):
        if isinstance(name, str) and name.startswith('yoyo'):
            p = RB.ShieldedTacticalPilot(shield=False)
            p.enable_shield(RB.TIGHT3)
            return p, YoyoPolicy(**spec)
        return orig(name)
    RB.make_arm = patched
    try:
        r = RB.play_game(cfg, arm)
        return r
    except Exception:
        return dict(seed=cfg['seed'], red=cfg['red'], policy=arm, error=traceback.format_exc())
    finally:
        RB.make_arm = orig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--holds', default='3,9,15', help='comma list: yo-yo length in decisions (3 = 1 s)')
    ap.add_argument('--trig-range', type=float, default=1800.)
    ap.add_argument('--min-ata', type=float, default=30.)
    ap.add_argument('--cooldown', type=int, default=30)
    ap.add_argument('--n', type=int, default=12)
    ap.add_argument('--seed0', type=int, default=950000)
    ap.add_argument('--opponents', default='lag,lead,guide')
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--max-ticks', type=int, default=18000)
    ap.add_argument('--base-results', default='runs/val_dn_g99/results.jsonl', help='jsonl that contains base_t3 rows for the same seeds')
    ap.add_argument('--out', default='runs/yoyo01')
    a = ap.parse_args()
    import rollout
    holds = [int(x) for x in a.holds.split(',')]
    tasks = []
    for h in holds:
        spec = dict(hold=h, trig_range=a.trig_range, min_ata=a.min_ata, cooldown=a.cooldown)
        for red in a.opponents.split(','):
            for i in range(a.n):
                tasks.append((dict(rollout.game_config(i, a.seed0, red, a.max_ticks), host_fidelity=True), 'yoyo_h%d' % h, spec))
    out = HERE / a.out
    out.mkdir(parents=True, exist_ok=True)
    sink, t0, results = (out / 'results.jsonl').open('a', encoding='utf-8'), time.time(), []

    def handle(r):
        results.append(r)
        sink.write(json.dumps(r, ensure_ascii=False) + '\n'); sink.flush()
        print('[%d/%d %.0fs] %s' % (len(results), len(tasks), time.time() - t0,
                                    r['error'][-300:] if 'error' in r else '%s/%s %s winner=%s margin %s atk %s/%s' % (r['policy'], r['red'], r['event'], r['winner'], r['margin'], r['atk_b'], r['atk_r'])), flush=True)
    import multiprocessing as mp
    with mp.get_context('spawn').Pool(a.workers, maxtasksperchild=8) as pool:
        for r in pool.imap_unordered(_task, tasks):
            handle(r)
    sink.close()
    summarize(results, HERE / a.base_results, a.opponents.split(','))


def summarize(results, base_path, opps):
    base = {}
    for l in open(base_path, encoding='utf-8'):
        r = json.loads(l)
        if 'error' not in r and r['policy'] == 'base_t3':
            base[(r['red'], r['seed'])] = r
    arms = sorted({r['policy'] for r in results if 'error' not in r}, key=lambda s: int(s.split('h')[-1]))
    print('\n%-10s %-7s %-9s %-9s %-12s %-12s' % ('arm', 'opp', 'win-loss', 'base', 'atk ticks b/r', 'mean margin (arm | base)'))
    for arm in arms:
        tw = tl = bw = bl = ow = ob = 0
        for red in opps:
            rs = [r for r in results if r['policy'] == arm and r['red'] == red and 'error' not in r]
            bs = [base[(r['red'], r['seed'])] for r in rs if (r['red'], r['seed']) in base]
            if not rs:
                continue
            w = sum(r['winner'] == 'blue' for r in rs); l = len(rs) - w
            bw_ = sum(b['winner'] == 'blue' for b in bs); bl_ = len(bs) - bw_
            tw += w; tl += l; bw += bw_; bl += bl_
            for r in rs:
                b = base.get((r['red'], r['seed']))
                if b is not None:
                    ow += int(r['winner'] == 'blue' and b['winner'] != 'blue'); ob += int(b['winner'] == 'blue' and r['winner'] != 'blue')
            print('%-10s %-7s %2d-%-2d     %2d-%-2d     %4d/%-4d     %7.0f | %7.0f' % (
                arm, red, w, l, bw_, bl_, sum(r['atk_b'] for r in rs), sum(r['atk_r'] for r in rs),
                sum(r['margin'] for r in rs) / len(rs), sum(b['margin'] for b in bs) / max(len(bs), 1)))
        print('%-10s TOTAL   %2d-%-2d     %2d-%-2d     only-arm-wins %d, only-base-wins %d\n' % (arm, tw, tl, bw, bl, ow, ob))


if __name__ == '__main__':
    main()
