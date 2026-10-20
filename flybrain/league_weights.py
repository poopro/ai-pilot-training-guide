"""Which enemies are worth training against?  (prioritised sampling from measured win rates)

  python league_weights.py runs\\base.json runs\\fly01\\results.jsonl --policy baseline --games 200

Reads results written by rollout.py / fly_eval.py (.json list or .jsonl), computes the win rate of --policy against each
opponent, and splits the next --games between opponents in proportion to (1 - win_rate + floor) ** power:
  * opponents you already beat 10/10 teach little -> they keep only --min-share (so you still notice regressions)
  * the rest is split in proportion to (1 - win_rate + floor) ** power, i.e. the opponents you lose to most
"""
import argparse, json, collections
from pathlib import Path


def load(paths):
    rows = []
    for p in paths:
        t = Path(p).read_text(encoding='utf-8')
        rows += json.loads(t) if t.lstrip().startswith('[') else [json.loads(l) for l in t.splitlines() if l.strip()]
    return [r for r in rows if 'error' not in r]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('results', nargs='+')
    ap.add_argument('--policy', default='baseline')
    ap.add_argument('--games', type=int, default=200)
    ap.add_argument('--power', type=float, default=2.0)
    ap.add_argument('--floor', type=float, default=0.05)
    ap.add_argument('--min-share', type=float, default=0.05, help='every opponent keeps at least this share of the games')
    a = ap.parse_args()
    rows = [r for r in load(a.results) if r['policy'] == a.policy]
    by = collections.defaultdict(list)
    for r in rows:
        by[r['red']].append(r['winner'] == 'blue')
    wr = {k: sum(v) / len(v) for k, v in by.items()}
    w = {k: (1 - wr[k] + a.floor) ** a.power for k in wr}
    tot = sum(w.values())
    share = {k: a.min_share + (1 - a.min_share * len(w)) * v / tot for k, v in w.items()}
    print('%-8s %5s %8s %8s %7s' % ('opponent', 'n', 'win_rate', 'share', 'games'))
    for k in sorted(wr, key=lambda k: wr[k]):
        print('%-8s %5d %8.2f %7.0f%% %7d' % (k, len(by[k]), wr[k], 100 * share[k], round(share[k] * a.games)))


if __name__ == '__main__':
    main()
