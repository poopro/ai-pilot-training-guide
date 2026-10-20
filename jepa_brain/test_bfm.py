"""Numeric sanity tests (no JSBSim needed): synthetic observations + a point-mass closed loop."""
import math, time, sys
import numpy as np
import bfm
from bfm import FT, R_E, G0, _advance, _commands, UserPilot, MilPolicy

LAT0, LON0 = 23.060552, 121.948555
import json
KW = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}

def ll(x, y):
    return LAT0 + math.degrees(x / R_E), LON0 + math.degrees(y / (R_E * math.cos(math.radians(LAT0))))

def make_obs(own, en, cr=.79):
    o = np.zeros(26)
    def vel(S):
        c = math.cos(S['gam'])
        return np.array([S['V'] * c * math.cos(S['psi']), S['V'] * c * math.sin(S['psi']), -S['V'] * math.sin(S['gam'])]) / FT
    o[0], o[1] = ll(own['x'], own['y']); o[2] = own['h'] / FT
    o[3] = math.degrees(own['phi']); o[4] = math.degrees(own['gam']) + 3.; o[5] = math.degrees(own['psi']) % 360
    o[6:9] = vel(own); o[12] = own['V'] * cr / FT; o[13] = own['V'] / FT; o[14] = 1.; o[15] = own['V'] / FT; o[18] = 3.
    o[20], o[21] = ll(en['x'], en['y']); o[22] = en['h'] / FT; o[23:26] = vel(en)
    return o

def state(x, y, h, V, psi_deg, gam=0., phi=0.):
    return dict(x=float(x), y=float(y), h=float(h), V=float(V), psi=math.radians(psi_deg), gam=gam, phi=phi)

def arr(S):
    return {k: np.array([v]) for k, v in S.items()}

# ---- 1. UserPilot on synthetic obs
own = state(0, 0, 4500, 220, 0); en = state(0, 1800, 4500, 220, 180)
p = UserPilot(shield=True)
for k in range(5):
    cmd, g = p.act(make_obs(own, en))
assert np.isfinite(cmd).all() and cmd.shape == (4,), cmd
print('U cmd', np.round(cmd, 3))
# overshoot -> zoom
own = state(0, 0, 4500, 220, 0); en = state(-300, 50, 4500, 200, 0)   # enemy behind us
p = UserPilot()
p.act(make_obs(own, en)); assert p.zoom_left > 0, 'zoom should trigger when enemy is behind'
print('zoom trigger OK')
# shield on collision course
from bfm import shield_targets, DEFAULT_SHIELD
own = state(0, 0, 4500, 220, 0); en = state(700, 0, 4500, 220, 180)
r = shield_targets(make_obs(own, en), 30., 5., 300., DEFAULT_SHIELD)
assert r[3] and r[0] == 0.; print('shield head-on OK', r)
en = state(700, 400, 4500, 220, 180)
assert not shield_targets(make_obs(own, en), 30., 5., 300., DEFAULT_SHIELD)[3]; print('shield no-trigger OK')

# ---- 2. MilPolicy timing + decision
m = MilPolicy(**KW)
own = state(0, 0, 4500, 220, 0); en = state(0, 1800, 4500, 220, 180)
t0 = time.time(); a = m.decide(None, make_obs(own, en), None); dt = time.time() - t0
print('first decision', a, 'q', np.round(m.last_q), 'ms %.1f' % (dt * 1000))
ms = []
for _ in range(10):
    t0 = time.time(); m.decide(None, make_obs(own, en), None); ms.append((time.time() - t0) * 1000)
print('plan ms mean %.1f max %.1f' % (np.mean(ms), np.max(ms)))
assert np.isfinite(m.last_q).any()

# ---- 3. closed loop in the point-mass world: blue (policy) vs red (hypothesis behaviour)
def play(blue_mode, red_tac, seed, secs=60, dist=1800):
    rng = np.random.default_rng(seed)
    B = arr(state(0, 0, 4500, 220, 0)); R = arr(state(0, dist, 4500, 220, 180))
    pol = MilPolicy(**KW) if blue_mode == 'mil' else None
    cur = 0; sa = ea = 0.; pa_b = pa_r = 0.; mind = 1e9; minh = 1e9
    for i in range(int(secs * 5)):          # dt = .2
        ob = make_obs({k: v[0] for k, v in B.items()}, {k: v[0] for k, v in R.items()})
        if pol is not None and i % 2 == 0:  # ~2.5 Hz decisions
            cur = pol.decide(None, ob, None)
        tb = np.array([cur]); tr = np.array([red_tac])
        cb = _commands(B, R, tb, .79); cr_ = _commands(R, B, tr, .79)
        _advance(B, cb[0], cb[1], cb[2], cb[3], .2); _advance(R, cr_[0], cr_[1], cr_[2], cr_[3], .2)
        dx, dy, dz = R['x'] - B['x'], R['y'] - B['y'], R['h'] - B['h']
        d = float(np.sqrt(dx**2 + dy**2 + dz**2)); mind = min(mind, d); minh = min(minh, float(B['h'][0]))
        n = lambda S: np.array([math.cos(S['gam'][0]) * math.cos(S['psi'][0]), math.cos(S['gam'][0]) * math.sin(S['psi'][0]), math.sin(S['gam'][0])])
        los = np.array([dx[0], dy[0], dz[0]]) / d
        ab = math.degrees(math.acos(np.clip(np.dot(n(B), los), -1, 1))); ae = math.degrees(math.acos(np.clip(-np.dot(n(R), los), -1, 1)))
        if 152.4 <= d <= 914.4:
            sa += .2 * (ab <= 3.); ea += .2 * (ae <= 3.)
        if d < 15: break
    return sa, ea, mind, minh

for red_tac, nm in [(bfm.PURSUE, 'pursue'), (bfm.LEAD, 'lead'), (bfm.H_STRAIGHT, 'straight'), (bfm.H_BL, 'breakL')]:
    for mode in ('fixed', 'mil'):
        res = [play(mode, red_tac, s, 40) for s in range(1)]
        print('%-8s %-5s  atk(s) mine/theirs %.1f/%.1f  minD %.0f  minH %.0f' % (nm, mode, np.mean([r[0] for r in res]), np.mean([r[1] for r in res]), min(r[2] for r in res), min(r[3] for r in res)))
print('TEST_BFM OK')
