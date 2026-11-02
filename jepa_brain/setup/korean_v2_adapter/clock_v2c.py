import math
import numpy as np

FT = .3048


class PolicyClock:
    """Korea V2c (2026-11-01): decide every 0.1 s of *flight* time, not every six packets.

    Elapsed time between two received packets = distance our own jet flew / its mean speed
    (packet: lat, lon, alt ft at 0:3, NED velocity ft/s at 15:18).  A lost, late or skipped packet
    therefore no longer makes the policy's clock (and the enemy acceleration / bank estimate) run slow.
    With every 60 Hz packet received this reproduces the old six-packet schedule (29/30 identical games).
    """
    def __init__(self, policy):
        self.policy = policy
        self.reset()

    def reset(self):
        self.policy.reset()
        self.previous = None
        self.t = 0.
        self.t_decision = None
        self.action = np.array([0., 0., 0., .8])

    def step(self, packet, started=True):
        o = np.asarray(packet, dtype=float)
        if not started:
            return self.action.copy()
        if self.previous is not None:
            p = self.previous
            if np.array_equal(p, o):
                return self.action.copy()
            dn = math.radians(o[0] - p[0]) * 6378137.
            de = math.radians(o[1] - p[1]) * 6378137. * math.cos(math.radians(p[0]))
            du = (o[2] - p[2]) * FT
            v = .5 * (np.linalg.norm(o[15:18]) + np.linalg.norm(p[15:18])) * FT
            dt = math.sqrt(dn * dn + de * de + du * du) / v if v > 1. else 1. / 60.
            self.t += min(max(dt, 0.), 1.)
        self.previous = o.copy()
        if self.t_decision is None or self.t - self.t_decision >= .1 - .5 / 60.:
            self.t_decision = self.t
            self.action = self.policy.command(o, self.t)
        return self.action.copy()
