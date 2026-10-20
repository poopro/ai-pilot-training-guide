"""PURSUE must reproduce the frozen RepairController exactly (numpy only, no JSBSim)."""
import numpy as np
from common import repair, SETTINGS
from tactics import TacticalPilot, PURSUE, N_TACTICS, NAMES

rng = np.random.default_rng(1)
base = repair.RepairController(SETTINGS)
mine = TacticalPilot()
mine.set_tactic(PURSUE)

def fake_obs(step):
    o = np.zeros(26)
    o[0], o[1] = 23.06 + 0.0002 * step * 0.1, 121.95
    o[2] = 15000 + 200 * np.sin(step / 50)
    o[3] = 30 * np.sin(step / 40); o[4] = 3 * np.cos(step / 70); o[5] = (step * 0.3) % 360
    o[6:9] = [340 * 1.69 * np.cos(np.radians(o[5])), 340 * 1.69 * np.sin(np.radians(o[5])), 5 * np.sin(step / 33)]
    o[9:12] = rng.normal(0, 0.05, 3)
    o[12] = 340 * 1.69; o[13] = 360 * 1.69; o[14] = 1 + 0.5 * np.sin(step / 25)
    o[15:18] = [o[12], 3, 5]; o[18] = 4 + np.sin(step / 30); o[19] = 0.5
    o[20] = 23.06 + 0.02 * np.cos(step / 200); o[21] = 121.95 + 0.02 * np.sin(step / 200)
    o[22] = 15000 + 300 * np.sin(step / 90)
    o[23:26] = [-340 * 1.69 * np.cos(np.radians(o[5])), -340 * 1.69 * np.sin(np.radians(o[5])), 0]
    return o

worst = 0.
for step in range(600):
    o = fake_obs(step)
    a, ga = base.act(o)
    b, gb = mine.act(o)
    worst = max(worst, float(np.max(np.abs(a - b))))
    assert ga == gb, ('guard flag differs', step)
print('PURSUE equivalence max abs diff =', worst)
assert worst == 0.0, 'PURSUE is not identical to RepairController'

for t in range(N_TACTICS):
    p = TacticalPilot(); p.set_tactic(t)
    for step in range(120):
        cmd, _ = p.act(fake_obs(step))
        assert np.all(np.isfinite(cmd)) and cmd.shape == (4,)
    print('tactic %d %-10s ok  last_cmd=%s' % (t, NAMES[t], np.round(cmd, 3)))
print('ALL OK')
