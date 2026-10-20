"""Derive portable/player_fighter_opt.py from YOUR portable/player_fighter.py (nothing of yours is modified): the only change is that the
pilot comes from fighter_opt.build (which falls back to fighter.build for every profile it does not know).

  python make_player_fighter_opt.py  [path/to/player_fighter.py]
Then copy fighter_opt.py + player_fighter_opt.py next to fighter.py and start the player with  --profile opt_ridge:tuned   (or network.json 'profile')."""
import sys, difflib
from pathlib import Path
src_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / 'portable' / 'player_fighter.py'
src = src_path.read_text(encoding='utf-8')
old = 'from fighter import build as build_pilot'
assert src.count(old) == 1, 'unexpected player_fighter.py'
new = src.replace(old, 'from fighter_opt import build as build_pilot').replace('(fighter.py；無SAC)', '(fighter_opt.py；無SAC)')
out = src_path.with_name('player_fighter_opt.py')
out.write_text(new, encoding='utf-8')
compile(new, str(out), 'exec')
print(''.join(difflib.unified_diff(src.splitlines(True), new.splitlines(True), 'player_fighter.py', 'player_fighter_opt.py', n=0)))
