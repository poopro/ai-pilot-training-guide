"""Pure-numpy SAC actor loaded straight from a stable-baselines3 zip (no torch needed), 2026-10-23.

Reads policy.pth inside the SB3 zip (torch's zip/pickle format) with a restricted unpickler that rebuilds
tensors as numpy arrays, and reproduces SB3's SAC actor for the official train.py architecture
(MlpPolicy, net_arch [256, 256], Tanh, no gSDE):
    latent = tanh(W1 x + b1) -> tanh(W2 . + b2);  mean = Wmu latent + bmu;  log_std = clip(Wls latent + bls, -20, 2)
    deterministic action = tanh(mean);  stochastic = tanh(mean + std * N(0,1))
then rescales from [-1, 1] to the action-space bounds like SB3 predict(). Observation is clipped to the
observation-space bounds is NOT done by SB3 for Box spaces, so it is not done here either.
Use: actor = SacNumpy(path); a = actor.predict(state20, deterministic=True)
"""
import io
import json
import pickle
import zipfile
import numpy as np

_DT = {'FloatStorage': np.float32, 'DoubleStorage': np.float64, 'HalfStorage': np.float16,
       'LongStorage': np.int64, 'IntStorage': np.int32, 'BoolStorage': np.bool_}


class _Unpickler(pickle.Unpickler):
    def __init__(self, f, zf, prefix):
        super().__init__(f)
        self.zf, self.prefix = zf, prefix

    def find_class(self, module, name):
        if module == 'torch._utils' and name == '_rebuild_tensor_v2':
            return self._rebuild
        if module == 'torch' and name.endswith('Storage'):
            return name
        if module == 'collections' and name == 'OrderedDict':
            import collections
            return collections.OrderedDict
        if module == 'torch._utils' and name == '_rebuild_parameter':
            return lambda data, requires_grad, hooks: data
        raise pickle.UnpicklingError('blocked: %s.%s' % (module, name))

    def persistent_load(self, pid):
        _, storage_type, key, _loc, numel = pid
        dt = _DT[storage_type if isinstance(storage_type, str) else storage_type.__name__]
        raw = self.zf.read('%sdata/%s' % (self.prefix, key))
        return np.frombuffer(raw, dtype=dt)[:numel]

    @staticmethod
    def _rebuild(storage, offset, size, stride, requires_grad=False, hooks=None, metadata=None):
        if len(size) == 0:
            return np.array(storage[offset])
        return np.lib.stride_tricks.as_strided(storage[offset:], shape=tuple(size),
                                               strides=tuple(s * storage.itemsize for s in stride)).copy()


def load_state_dict(pth_bytes):
    zf = zipfile.ZipFile(io.BytesIO(pth_bytes))
    pkl = [n for n in zf.namelist() if n.endswith('data.pkl')][0]
    prefix = pkl[:-len('data.pkl')]
    return _Unpickler(io.BytesIO(zf.read(pkl)), zf, prefix).load()


class SacNumpy:
    def __init__(self, path):
        z = zipfile.ZipFile(str(path))
        sd = load_state_dict(z.read('policy.pth'))
        data = json.loads(z.read('data'))
        if data.get('use_sde') or data.get('policy_kwargs', {}).get('use_sde'):
            raise ValueError('gSDE policies are not supported')
        g = lambda k: np.asarray(sd[k], dtype=np.float64)
        self.W = [(g('actor.latent_pi.0.weight'), g('actor.latent_pi.0.bias')),
                  (g('actor.latent_pi.2.weight'), g('actor.latent_pi.2.bias'))]
        self.Wmu, self.bmu = g('actor.mu.weight'), g('actor.mu.bias')
        self.Wls, self.bls = g('actor.log_std.weight'), g('actor.log_std.bias')
        # action-space bounds from the official env (Box low/high); read from the saved space when possible
        self.low = np.array([-1., -1., 0., 0.])
        self.high = np.array([1., 1., 1e-17, 1.])
        self.rng = np.random.default_rng(0)

    def dist(self, obs):
        h = np.asarray(obs, dtype=np.float64)
        for W, b in self.W:
            h = np.tanh(W @ h + b)
        mean = self.Wmu @ h + self.bmu
        log_std = np.clip(self.Wls @ h + self.bls, -20., 2.)
        return mean, log_std

    def predict(self, obs, deterministic=True, rng=None):
        mean, log_std = self.dist(obs)
        if deterministic:
            a = np.tanh(mean)
        else:
            r = rng if rng is not None else self.rng
            a = np.tanh(mean + np.exp(log_std) * r.standard_normal(mean.shape))
        return (self.low + .5 * (a + 1.) * (self.high - self.low)).astype(np.float32)
