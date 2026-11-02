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

KR_ROOT = Path('/home/claude/ext/kr1/final_team_models')
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


class KRRed:
    def __init__(self, kind, seed=0):
        name = kind.split(':', 1)[1]
        folder = KR_ROOT / name
        self.policy = NumpyPolicy(folder)
        self.obs = _obs_state_class(folder)()
        self.obs.reset()
        self.cmd = np.array([0., 0., 0., .8])
        self.origin = None

    def act(self, obs_red, tick):
        a = CURRENT['arena']
        if tick % 6 == 0:
            if self.origin is None:
                f = a.fdm2.fdm
                self.origin = (f['position/lat-geod-deg'], f['position/long-gc-deg'])
            own, tgt = jet_state(a.fdm2, self.origin), jet_state(a.fdm1, self.origin)
            o = self.obs.observation(own, tgt)
            self.cmd = self.policy.act(o)
            self.obs.record_command(self.cmd)
        return self.cmd.copy()
