import unittest
import numpy as np
from gate import make_gated_controller

class Base:
    def __init__(self,*a,**kw): self.telemetry={}; self.seen=None
    def act(self,obs,residual=None,started=True):
        self.seen=(obs,residual,started)
        return np.zeros(4) if residual is None else residual,False

Gated=make_gated_controller(Base,lambda obs: {'distance_m':obs[0],'blue_angle_deg':obs[1]})

class GateTests(unittest.TestCase):
    def test_far_and_boundary_use_guide(self):
        for distance in [1100.,5000.]:
            c=Gated(); c.act([distance,90],[.5,-.5,.1,1.])
            self.assertIsNone(c.seen[1]); self.assertEqual(c.blocked_ticks,1)
    def test_near_preserves_frozen_action(self):
        action=np.array([.3,-.2,.8,1.]); c=Gated()
        output,_=c.act([1099.,179.],action)
        self.assertIs(c.seen[1],action); np.testing.assert_array_equal(output,action)
    def test_guide_remains_none(self):
        c=Gated(); c.act([100.,0.],None)
        self.assertIsNone(c.seen[1]); self.assertEqual(c.gate_ticks,0)
    def test_not_started_does_not_read_geometry(self):
        c=Gated(); c.act(None,[0,0,0,0],started=False)
        self.assertFalse(c.seen[2]); self.assertEqual(c.gate_ticks,0)
    def test_counters_follow_boundary_crossing(self):
        c=Gated()
        for d in [1200,1000,1099,1100]: c.act([d,0.],[1,1,1,1])
        self.assertEqual(c.gate_ticks,4); self.assertEqual(c.blocked_ticks,2)
        self.assertEqual(c.telemetry['gate_fraction_blocked'],.5)
    def test_nonfinite_or_bad_shape_rejected(self):
        for action in [[1,2],[0,0,float('nan'),0]]:
            with self.assertRaises(ValueError): Gated().act([1000,0],action)

if __name__=='__main__': unittest.main()
