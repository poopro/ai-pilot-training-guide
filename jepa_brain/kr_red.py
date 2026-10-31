"""External opponent (2026-10-28): the PPO pilots of the 1st-place team of the Korean "TOPGUN 2026 AI Pilot Challenge"
(github.com/idearendil/2026_AI_Pilot_Challenge-1st_Solution, final_team_models/*), flown as RED in our arena.

Their rules are close to ours (JSBSim F-16, guns only, 1 deg cone 500-3000 ft, 1000 ft deck; 200 s rounds; HP damage).
Policy: 214-D observation (their claude_code/my_observation.py, imported read-only from the model folder),
MLP tanh -> 4 x 21-bin argmax -> [roll, pitch, rudder, throttle] at 10 Hz (held 6 ticks).  Their stick convention
(roll +right, pitch +forward, rudder +right, throttle 0..1) = JSBSim fcs/*-cmd-norm = our command order.
Weights are read WITHOUT torch: a restricted unpickler that only rebuilds float tensors from the checkpoint zip.

kind 'kr:<model folder name>', e.g. kr:junhwa_final, kr:gylee_69k  (GRU models are not supported).
The adapter needs both jets' full state (their observation uses the target's attitude), so it reads the two JSBSim
models of the current Arena (dcsvet_pool registers it).
"""
import io, math, pickle, sys, zipfile
from pathlib import Path
import numpy as np

import os
# folder that holds the Korean team's model folders (git clone github.com/idearendil/2026_AI_Pilot_Challenge-1st_Solution):
# set KR_MODELS=<clone>/final_team_models, or clone it to ../ext/kr1 next to this folder
_cands = [os.environ.get('KR_MODELS', ''), str(Path(__file__).resolve().parent.parent / 'ext' / 'kr1' / 'final_team_models'),
          '/home/claude/ext/kr1/final_team_models']
KR_ROOT = Path(next((c for c in _cands if c and Path(c).is_dir()), _cands[1]))
FT = .3048
CURRENT = {'arena': None}


class _Restricted(pickle.Unpickler):
    def __init__(self, f, storages):
        super().__init__(f)
        self.storages = storages

    def find_class(self, module, name):
        if module == 'torch._utils' and name == '_rebuild_tensor_v2':
            return _rebuild
        if module == 'torch' and name in ('FloatStorage', 'DoubleStorage', 'LongStorage', 'IntStorage', 'BoolStorage'):
            return name
        if module == 'collections' and name == 'OrderedDict':
            import collections
            return collections.OrderedDict
        raise pickle.UnpicklingError('blocked %s.%s' % (module, name))

    def persistent_load(self, pid):
        typ, dtype, key, loc, numel = pid
        dt = {'FloatStorage': np.float32, 'DoubleStorage': np.float64, 'LongStorage': np.int64,
              'IntStorage': np.int32, 'BoolStorage': np.bool_}[dtype]
        return np.frombuffer(self.storages(key), dtype=dt)


def _rebuild(storage, offset, size, stride, requires_grad=None, hooks=None, metadata=None):
    if len(size) == 0:
        return storage[offset].copy()
    item = storage.itemsize
    return np.lib.stride_tricks.as_strided(storage[offset:], shape=tuple(size), strides=tuple(s * item for s in stride)).copy()


def load_checkpoint(path):
    z = zipfile.ZipFile(path)
    names = z.namelist()
    root = names[0].split('/')[0]
    data = z.read(root + '/data.pkl')
    return _Restricted(io.BytesIO(data), lambda k: z.read('%s/data/%s' % (root, k))).load()


class NumpyPolicy:
    def __init__(self, folder):
        ck = load_checkpoint(Path(folder) / 'model.pt')
        cfg, w = ck['cfg'], ck['model']
        if cfg.get('gru_last') or cfg.get('gru_all'):
            raise ValueError('GRU models not supported')
        self.W, self.b = [], []
        i = 0
        while 'actor_body.%d.weight' % i in w:
            self.W.append(np.asarray(w['actor_body.%d.weight' % i], np.float64).T)
            self.b.append(np.asarray(w['actor_body.%d.bias' % i], np.float64)); i += 2
        self.Wl = np.asarray(w['actor_logits.weight'], np.float64).T
        self.bl = np.asarray(w['actor_logits.bias'], np.float64)
        self.nb = int(cfg.get('num_bins', 21))
        norm = ck.get('norm')
        self.mean = np.asarray(norm['mean'], np.float64) if norm else None
        self.var = np.asarray(norm['var'], np.float64) if norm else None

    def act(self, obs):
        x = np.asarray(obs, np.float64)
        if self.mean is not None:
            x = np.clip((x - self.mean) / np.sqrt(self.var + 1e-8), -10, 10)
        for W, b in zip(self.W, self.b):
            x = np.tanh(x @ W + b)
        idx = (x @ self.Wl + self.bl).reshape(4, self.nb).argmax(-1)
        c = np.linspace(-1., 1., self.nb)[idx]
        c[3] = .5 * c[3] + .5
        return c


_OBS_MODS = {}


def _obs_state_class(folder):
    folder = str(folder)
    if folder not in _OBS_MODS:
        for p in (folder, folder + '/src'):
            if p not in sys.path:
                sys.path.insert(0, p)
        for m in [m for m in sys.modules if m == 'claude_code' or m.startswith('claude_code.') or m.startswith('dogfight') or m == 'GeoMathUtil']:
            del sys.modules[m]
        from claude_code.observation_contract import CUDAObservationState
        _OBS_MODS[folder] = CUDAObservationState
    return _OBS_MODS[folder]


def jet_state(fdm, origin):
    f = fdm.fdm
    lat, lon, h = f['position/lat-geod-deg'], f['position/long-gc-deg'], f['position/h-sl-meters']
    R = 6378137.
    n = math.radians(lat - origin[0]) * R
    e = math.radians(lon - origin[1]) * R * math.cos(math.radians(origin[0]))
    return np.array([n, e, -h, f['attitude/phi-deg'], f['attitude/theta-deg'], f['attitude/psi-deg'],
                     f['velocities/u-fps'] * FT, f['velocities/v-fps'] * FT, f['velocities/w-fps'] * FT], np.float64)


def _est_attitude(vn, ve, vd, prev, dt):
    """'Legal' enemy attitude: only velocity (+ its change) is known.  x_body = velocity direction (alpha = beta = 0);
    z_body = -specific force (lift direction), f = a - g.  Returns phi, theta, psi (deg) and the body velocity."""
    v = np.array([vn, ve, vd], float); sp = float(np.linalg.norm(v))
    x = v / max(sp, 1.)
    if prev is None:
        f = np.array([0., 0., -9.81])
    else:
        f = (v - prev) / dt - np.array([0., 0., 9.81])
    z = -f
    z = z - x * float(z @ x)
    if np.linalg.norm(z) < 1.:
        z = np.array([0., 0., 1.]) - x * x[2]
    z = z / max(np.linalg.norm(z), 1e-6)
    y = np.cross(z, x)
    theta = math.degrees(math.asin(float(np.clip(-x[2], -1, 1))))
    psi = math.degrees(math.atan2(x[1], x[0])) % 360.
    phi = math.degrees(math.atan2(float(y[2]), float(z[2])))
    return phi, theta, psi, sp


class KRRed:
    def __init__(self, kind, seed=0, side='red'):
        self.side = side
        self.legal = kind.startswith('krl:')
        self.prev_v = None
        name = kind.split(':', 1)[1]
        folder = KR_ROOT / name
        self.policy = NumpyPolicy(folder)
        self.obs = _obs_state_class(folder)()
        self.obs.reset()
        self.cmd = np.array([0., 0., 0., .8])
        self.origin = None

    def act(self, obs_red, tick):
        a = CURRENT['arena']
        mine, his = (a.fdm2, a.fdm1) if self.side == 'red' else (a.fdm1, a.fdm2)
        if tick % 6 == 0:
            if self.origin is None:
                f = mine.fdm
                self.origin = (f['position/lat-geod-deg'], f['position/long-gc-deg'])
            own, tgt = jet_state(mine, self.origin), jet_state(his, self.origin)
            if self.legal:      # the enemy's attitude is not given: estimate it from his velocity / acceleration only
                f = his.fdm
                vn, ve, vd = f['velocities/v-north-fps'] * FT, f['velocities/v-east-fps'] * FT, f['velocities/v-down-fps'] * FT
                phi, th, psi, sp = _est_attitude(vn, ve, vd, self.prev_v, .1)
                self.prev_v = np.array([vn, ve, vd])
                tgt = tgt.copy(); tgt[3], tgt[4], tgt[5] = phi, th, psi; tgt[6:9] = (sp, 0., 0.)
            o = self.obs.observation(own, tgt)
            self.cmd = self.policy.act(o)
            self.obs.record_command(self.cmd)
        return self.cmd.copy()


class KRBlue:
    """The same pilot flown as BLUE (arm 'kr:<m>' / 'krl:<m>' in dcsvet_pool.make_blue)."""
    def __init__(self, kind):
        self.inner = KRRed(kind, side='blue')
        self.t = 0
    def set_tactic(self, t):
        pass
    def act(self, observation, residual=None, started=True):
        c = self.inner.act(observation, self.t); self.t += 1
        return c, False
