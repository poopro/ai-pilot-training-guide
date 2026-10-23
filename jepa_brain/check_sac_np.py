"""Check sac_np.SacNumpy against stable-baselines3 predict (deterministic) on random observations."""
import glob, sys
import numpy as np
import sac_np

path = sys.argv[1] if len(sys.argv) > 1 else glob.glob('../2026*/*/*/AirCombat_Train_Test/model/jsbsim_sac_25600000_steps.zip')[0]
a = sac_np.SacNumpy(path)
from stable_baselines3 import SAC
m = SAC.load(path, device='cpu')
rng = np.random.default_rng(3)
worst = 0.
for _ in range(500):
    x = rng.normal(0, .5, 20)
    worst = max(worst, float(np.abs(m.predict(x, deterministic=True)[0] - a.predict(x)).max()))
print('max abs diff vs SB3 over 500 random observations:', worst)
