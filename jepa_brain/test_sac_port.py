"""Linux-side check: our port == organizer's player1_Loadmodel.get_state / process_joystick_action.
Stubs stable_baselines3 so the official file can be imported without it."""
import sys, types, importlib.util
import numpy as np
sys.modules['stable_baselines3'] = types.SimpleNamespace(SAC=None)
from common import BASE
spec = importlib.util.spec_from_file_location('official_player', str(BASE.parent / '..' / '..' / 'x'))  # placeholder, replaced below
import glob
cands = glob.glob(str(BASE / 'player1_Loadmodel.py'))
assert cands, 'player1_Loadmodel.py not found'
spec = importlib.util.spec_from_file_location('official_player', cands[0])
off = importlib.util.module_from_spec(spec); spec.loader.exec_module(off)
from sac_red import OfficialSacPlayer

rng = np.random.default_rng(3)
def fake(step):
    o = np.zeros(26)
    o[0], o[1], o[2] = 23.06 + 1e-4 * step, 121.95 + 2e-5 * step, 15000 + 100 * np.sin(step / 40)
    o[3], o[4], o[5] = 30 * np.sin(step / 30), 4 * np.cos(step / 50), (step * 0.7) % 360
    o[6:9] = [550 * np.cos(np.radians(o[5])), 550 * np.sin(np.radians(o[5])), 3 * np.sin(step / 20)]
    o[9:12] = rng.normal(0, .05, 3); o[12], o[13] = 575, 600; o[14] = 1 + .3 * np.sin(step / 11)
    o[15:18] = [570, 4, 6]; o[18], o[19] = 4, .5
    o[20], o[21], o[22] = 23.06 + 1e-3 * np.cos(step / 90), 121.95 + 1e-3 * np.sin(step / 90), 15200
    o[23:26] = [-550, 20, 0]
    return o.astype(np.float32)

mine = OfficialSacPlayer()
off.last_actual_action = np.array([0, 0, 0, 0.8]); off.prev_distance_m = None
worst_s = worst_a = 0.
for step in range(500):
    o = fake(step)
    s_off, s_me = off.get_state(o), mine.get_state(o)
    worst_s = max(worst_s, float(np.max(np.abs(s_off - s_me))))
    act = rng.uniform(-1, 1, 4); act[3] = rng.uniform(0, 1)
    a_off = off.process_joystick_action(act, o); a_me = mine.process_joystick_action(act, o)
    worst_a = max(worst_a, float(np.max(np.abs(a_off - a_me))))
print('state max diff', worst_s, ' action max diff', worst_a)
assert worst_s == 0.0 and worst_a == 0.0
print('PORT OK')
