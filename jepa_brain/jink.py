"""Defensive jink (2026-10-28): when the enemy is behind us and his flight path points at us inside gun range, fly
irregular hard lift-vector changes so he cannot hold a 1 deg track for 3 s.  Otherwise the wrapped pilot flies.

arm 'jink:<inner arm>' (dcsvet_pool.make_blue), e.g. jink:fin4:runs/tune04_fin12d.  The inner pilot must be a
finisher.FinisherPilot (we fly the jink through its LiftPilot).  Pseudo-random but seeded -> games stay reproducible.
cfg: cone_deg (enemy velocity vs line to us), r_max, our_ata_min (we are not attacking him), period_s, n, seed.
"""
import math
import numpy as np


class JinkPilot:
    def __init__(self, inner, cone_deg=10., r_max=1300., r_min=120., our_ata_min=70., period_s=.8, n=7.5, seed=0):
        self.inner = inner
        self.c = dict(cone_deg=cone_deg, r_max=r_max, r_min=r_min, our_ata_min=our_ata_min, period_s=period_s, n=n)
        self.rng = np.random.default_rng(seed)
        self.jinking = False
        self.k = 0
        self.mu = 0.
        self.n_jink_ticks = 0

    def set_tactic(self, t):
        self.inner.set_tactic(t)

    @property
    def mode(self):
        return 'jink' if self.jinking else self.inner.mode

    def threat(self, o):
        g = self.inner.geometry(o)
        rel, v, ve, r = g['rel'], g['v'], g['ve'], g['r']
        if not (self.c['r_min'] < r < self.c['r_max']):
            return False
        if self.inner.collision_threat(g)[0]:          # collision avoidance always wins
            return False
        sv, se = float(np.linalg.norm(v)), float(np.linalg.norm(ve))
        if sv < 1. or se < 1.:
            return False
        his = math.degrees(math.acos(float(np.clip(np.dot(ve, -rel) / (se * r), -1., 1.))))   # his path vs line to us
        ours = math.degrees(math.acos(float(np.clip(np.dot(v, rel) / (sv * r), -1., 1.))))    # our path vs line to him
        return his < self.c['cone_deg'] and ours > self.c['our_ata_min']

    def act(self, observation, residual=None, started=True):
        if not started:
            return self.inner.act(observation, residual, started)
        o = np.asarray(observation, dtype=np.float64)
        th = self.threat(o)
        fin, low = self.inner, self.inner.low
        if th and not self.jinking:
            src = low.last if fin.active else getattr(fin.base, 'last', low.last)
            low.last = np.array(src, dtype=np.float64).copy()
            low.ni = 0.; low.si = 0.
            self.k = 0
        if not th and self.jinking:
            if not fin.active and hasattr(fin.base, 'last'):
                fin.base.last = low.last.copy()
        self.jinking = th
        if not th:
            return self.inner.act(observation, residual, started)
        per = max(1, int(self.c['period_s'] * 60))
        if self.k % per == 0:
            # new lift direction: mostly sideways / up, never straight down at low altitude
            self.mu = float(self.rng.choice([-1., 1.]) * self.rng.uniform(40., 140.))
            if o[2] * .3048 < 2500.:
                self.mu = float(np.clip(self.mu, -90., 90.))
        self.k += 1
        self.n_jink_ticks += 1
        cas = o[12] * 0.592484
        n = float(np.clip(3. + (cas - 250.) / 80. * 5.6, 3., self.c['n']))
        out, guard = low.command(o, self.mu, n, 420.)
        return out, guard
