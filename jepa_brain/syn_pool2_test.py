"""Synthetic-observation check of pool2 maneuver opponents (no JSBSim)."""
import sys, math, numpy as np
sys.argv = [sys.argv[0]]
import importlib
LAT0, LON0 = 23.060552, 121.948555
R_E = 6378137.0; FT = .3048
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

import pool2
own = state(0, 0, 4500, 175, 0); en = state(0, 1800, 4500, 175, 180)
for kind in pool2.MANEUVER:
    r = pool2.build(kind, 123)
    cmds = []
    for t in range(0, 1200, 3):          # 20 s of ticks, sparse
        c = r.act(make_obs(own, en), t)
        assert np.isfinite(c).all() and np.shape(c) == (4,), (kind, c)
        cmds.append(c)
    cmds = np.array(cmds)
    print('%-9s ok  aileron[%.2f,%.2f] elev[%.2f,%.2f] thr[%.2f,%.2f]' % (kind, cmds[:,0].min(), cmds[:,0].max(), cmds[:,1].min(), cmds[:,1].max(), cmds[:,3].min(), cmds[:,3].max()))
for i in range(6):
    r = pool2.build('pp%d' % i, 1)
    c = r.act(make_obs(own, en), 0); assert np.isfinite(c).all()
print('pp0..5 ok')
# defender: enemy pointing at red at 1200 m -> should break (aileron large)
r = pool2.build('defender', 5)
own = state(0, 0, 4500, 175, 0); en = state(0, 1200, 4500, 175, 180)   # enemy abeam, heading opposite -> not pointing at us
for t in range(0, 60, 20): r.act(make_obs(own, en), t)
print('defender state (abeam)', r.state)
en = state(-1200, 0, 4500, 175, 0)   # enemy 1200 m directly behind us, flying toward us (psi 0 = north; we are at x=0, he at x=-1200 heading north)
r = pool2.build('defender', 5)
for t in range(0, 60, 20): r.act(make_obs(own, en), t)
print('defender state (tail-chaser)', r.state)
assert r.state == 'break'
print('SYN_POOL2 OK')
