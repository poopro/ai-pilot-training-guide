import numpy as np

class PolicyClock:
    """One observation every six started, nonduplicate 60Hz packets."""
    def __init__(self,policy):
        self.policy=policy
        self.reset()

    def reset(self):
        self.policy.reset()
        self.tick=0
        self.previous=None
        self.action=np.array([0.,0.,0.,.8])

    def step(self,packet,started=True):
        o=np.asarray(packet,dtype=float)
        if not started: return self.action.copy()
        if self.previous is not None and np.array_equal(self.previous,o): return self.action.copy()
        if self.tick%6==0: self.action=self.policy.command(o,self.tick/60.)
        self.previous=o.copy()
        self.tick+=1
        return self.action.copy()
