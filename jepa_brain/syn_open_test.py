import sys, math, numpy as np
sys.argv=[sys.argv[0]]
exec(open('syn_pool2_test.py',encoding='utf-8').read().split('import pool2')[0])
import rollout_open as ro
from tactics import BREAK_OUT
# enemy abeam on the LEFT (side -1): north-heading own, enemy to the west
own = state(0, 0, 4500, 175, 0); en_left = state(0, -914, 4500, 175, 180); en_right = state(0, 914, 4500, 175, 180)
for en, name in ((en_left, 'left'), (en_right, 'right')):
    p = ro.OpenPilot(tactic=BREAK_OUT, secs=2., only_side=-1)
    for k in range(240): p.act(make_obs(own, en))
    print(name, 'side', p.side, 'opening ticks used', p.n_def_ticks)
    assert (p.n_def_ticks == 120) == (name == 'left')
a, pol = ro.make_arm('topen:out:6:side=-1:turn_cap=350')
print(type(a).__name__, a.o_tactic, a.o_ticks, a.only_side, a.p['turn_cap'])
a, pol = ro.make_arm('tuned'); print(type(a).__name__)
print('SYN_OPEN OK')
