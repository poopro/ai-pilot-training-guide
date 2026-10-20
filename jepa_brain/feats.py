"""Legal-information features (OWN20+ENEMY6 observation + own counters only)."""
import math
import numpy as np
from combat_v3.interface import geometry_from_observation

FEAT_DIM = 27
N_ACT = 8
WINDOW = 4
TOKEN_DIM = FEAT_DIM + N_ACT


def _wrap(a):
    return (a + 180.) % 360. - 180.


def features(o, atk_ticks, tick):
    g = geometry_from_observation(o)
    phi, theta = math.radians(o[3]), math.radians(o[4])
    ev, ov = o[23:26], o[6:9]
    cross = _wrap(math.degrees(math.atan2(ev[1], ev[0])) - math.degrees(math.atan2(ov[1], ov[0]))) / 180.
    d_ft = g['distance_m'] / .3048
    in_band = 500. <= d_ft <= 3000.
    ba = g['blue_angle_deg']
    c = np.clip
    f = [min(g['distance_m'] / 5000., 3.), c(g['closing_mps'] / 340., -3, 3), ba / 180., g['blue_az_deg'] / 180.,
         g['blue_el_deg'] / 90., g['aspect_proxy_deg'] / 180., cross,
         math.sin(phi), math.cos(phi), math.sin(theta), math.cos(theta),
         c(o[18] / 30., -3, 3), c(o[19] / 10., -3, 3), c(o[14] / 9., -2, 2),
         o[12] / 1.6878098571011957 / 400., o[2] * .3048 / 6000.,
         c((o[22] - o[2]) * .3048 / 3000., -3, 3), float(np.linalg.norm(ev)) / 1.6878098571011957 / 400.,
         c(o[8] * .3048 / 100., -3, 3), c(o[9] / 3., -1, 1), c(o[10] / 3., -1, 1), c(o[11] / 3., -1, 1),
         atk_ticks / 180., tick / 18000., float(in_band and ba <= 1.), float(in_band), float(ba <= 5.)]
    return np.asarray(f, dtype=np.float32)


def make_token(feat, prev_action):
    onehot = np.zeros(N_ACT, dtype=np.float32)
    if prev_action is not None:
        onehot[int(prev_action)] = 1.
    return np.concatenate([feat, onehot])


def window_from_tokens(tokens):
    """Last WINDOW tokens, left-padded by repeating the first token."""
    tail = tokens[-WINDOW:]
    if len(tail) < WINDOW:
        tail = [tail[0]] * (WINDOW - len(tail)) + list(tail)
    return np.concatenate(tail).astype(np.float32)
