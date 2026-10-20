"""Scripted red opponents that actually fly and (try to) shoot back."""
import numpy as np
from tactics import TacticalPilot, PURSUE, LEAD, LAG, BREAK_IN, BREAK_OUT, STRAIGHT

DECISION_TICKS = 20   # 3 Hz tactical decisions
KINDS = ('guide', 'lead', 'lag', 'mix', 'breaker', 'level')


class ScriptedRed:
    def __init__(self, kind, seed):
        if kind not in KINDS:
            raise ValueError('unknown opponent ' + kind)
        self.kind = kind
        self.rng = np.random.default_rng(seed)
        self.pilot = TacticalPilot()
        self.tactic = {'lead': LEAD, 'lag': LAG, 'level': STRAIGHT}.get(kind, PURSUE)
        self.until = int(self.rng.uniform(8, 14) * 60) if kind == 'breaker' else 0

    def _choose(self, tick):
        k = self.kind
        if k in ('guide', 'lead', 'lag', 'level'):
            return self.tactic
        if tick >= self.until:
            if k == 'mix':
                self.tactic = int(self.rng.choice([0, 0, 0, 1, 2, 3, 4, 5, 6]))
                self.until = tick + int(self.rng.uniform(2, 5) * 60)
            else:  # breaker
                if self.tactic in (BREAK_IN, BREAK_OUT):
                    self.tactic = PURSUE
                    self.until = tick + int(self.rng.uniform(8, 14) * 60)
                else:
                    self.tactic = int(self.rng.choice([BREAK_IN, BREAK_OUT]))
                    self.until = tick + int(self.rng.uniform(2, 3) * 60)
        return self.tactic

    def act(self, obs, tick):
        if tick % DECISION_TICKS == 0:
            self.pilot.set_tactic(self._choose(tick))
        return self.pilot.act(obs)[0]
