import sys, math, numpy as np
sys.argv=[sys.argv[0]]
exec(open('syn_pool2_test.py',encoding='utf-8').read().split('import pool2')[0])
import bfm
from tactics import TacticalPilot
# 1. ParamPilot defaults still identical to the frozen pursuit
own = state(0, 0, 4500, 175, 20); en = state(900, 400, 4600, 170, 200)
a = bfm.ParamPilot(); b = TacticalPilot()
for k in range(30):
    ca, _ = a.act(make_obs(own, en)); cb, _ = b.act(make_obs(own, en))
assert np.max(np.abs(ca-cb)) == 0.0, (ca, cb)
print('ParamPilot default == frozen PURSUE (max diff 0.0)')
# 2. tail-chase: enemy 800 m behind and pointing at us
own = state(0, 0, 4500, 150, 0); en = state(-800, 0, 4500, 175, 0)
d = bfm.DefPilot(defense={'mode': 'break'})
cmds = [d.act(make_obs(own, en))[0] for k in range(200)]
print('tail-chase: entries', d.n_def_entries, 'def ticks', d.n_def_ticks, 'aileron max', round(max(abs(c[0]) for c in cmds), 2))
assert d.n_def_entries >= 1 and d.n_def_ticks > 60
# 3. normal pursuit: enemy ahead
own = state(0, 0, 4500, 175, 0); en = state(900, 0, 4500, 150, 0)
d = bfm.DefPilot(defense={'mode': 'break'})
for k in range(200): d.act(make_obs(own, en))
print('pursuit (enemy ahead): entries', d.n_def_entries); assert d.n_def_entries == 0
# 4. head-on pass: enemy flying away behind after the pass -> no threat
own = state(0, 0, 4500, 175, 0); en = state(-800, 0, 4500, 175, 180)
d = bfm.DefPilot(defense={'mode': 'break'})
for k in range(200): d.act(make_obs(own, en))
print('after pass (enemy moving away): entries', d.n_def_entries); assert d.n_def_entries == 0
# 5. every mode runs
for m in ('break', 'out', 'extend', 'hy', 'ly', 'none'):
    own = state(0, 0, 4500, 150, 0); en = state(-800, 0, 4500, 175, 0)
    d = bfm.DefPilot(defense={'mode': m}, params={'turn_cap': 380.})
    for k in range(200): c = d.act(make_obs(own, en))[0]; assert np.isfinite(c).all()
    print(m, 'ok entries', d.n_def_entries)
print('SYN_DEF OK')
