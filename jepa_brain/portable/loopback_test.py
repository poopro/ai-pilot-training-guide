"""UDP loopback: fake Host <-> tools/player_fighter.py  vs.  direct fighter.build(profile) on the same observations.
  python portable/loopback_test.py <extracted package dir> [profile ...]
Checks: 208-byte OBS in, 30-byte PLAYER_CMD out, state 1 (first 60 obs) then 2, INIT obs do not advance the controller,
duplicate obs keep the previous command, and every command equals the in-process reference (float32 tolerance)."""
import socket, struct, subprocess, sys, os, time, math, json
from pathlib import Path
import numpy as np
PKG = Path(sys.argv[1]).resolve()
args_ = sys.argv[2:]; RESUME = '--resume' in args_; profiles = [x for x in args_ if x != '--resume'] or ['tuned2', 'tuned', 'base_t3', 'tuned_open:9']
LAT0, LON0, R_E, FT = 23.060552, 121.948555, 6378137.0, .3048
def ll(x, y): return LAT0 + math.degrees(x / R_E), LON0 + math.degrees(y / (R_E * math.cos(math.radians(LAT0))))
def obs(own, en):
    o = np.zeros(26)
    def vel(S): return np.array([S[3] * math.cos(S[4]), S[3] * math.sin(S[4]), 0.]) / FT
    o[0], o[1] = ll(own[0], own[1]); o[2] = own[2] / FT; o[4] = 3.; o[5] = math.degrees(own[4]) % 360
    o[6:9] = vel(own); o[12] = own[3] * .79 / FT; o[13] = o[15] = own[3] / FT; o[14] = 1.; o[18] = 3.
    o[20], o[21] = ll(en[0], en[1]); o[22] = en[2] / FT; o[23:26] = vel(en)
    return o
def sequence(kind):
    side = -1 if kind == 'left' else 1
    own = [0., 0., 4500., 175., 0.]
    en = {'left': [0., -1829., 4500., 175., math.pi], 'right': [0., 1829., 4500., 175., math.pi], 'headon': [2200., 20., 4500., 175., math.pi]}[kind]
    seq = [obs(own, en)] * 70                       # INIT: identical observations, position never changes
    for k in range(300):
        for S in (own, en):
            S[0] += S[3] * math.cos(S[4]) / 60.; S[1] += S[3] * math.sin(S[4]) / 60.
        seq.append(obs(own, en))
        if k % 50 == 25: seq.append(seq[-1].copy())  # a duplicate observation
    return seq
sys.path[:0] = [str(PKG / 'policy'), str(PKG / 'tools')]
import fighter
class RoundState:                                    # same logic as the official player
    def __init__(self): self.anchor = None; self.count = 0; self.started = False; self.previous = None
    def observe(self, o):
        if self.anchor is None: self.anchor = o[[0, 1]].copy()
        self.count += 1
        if np.any(np.abs(o[[0, 1]] - self.anchor) > 1e-10): self.started = True
        dup = self.previous is not None and np.array_equal(o, self.previous)
        self.previous = o.copy()
        return (2 if self.count > 60 else 1), self.started, dup
def reference(profile, seq, resume=False):
    c = fighter.build(profile); rs = RoundState(); rs.count = 61 if resume else 0; act = np.array([0., 0., 0., .8]); out = []
    for o in seq:
        st, started, dup = rs.observe(o)
        if not dup or not started: act, _ = c.act(o, np.zeros(4, dtype=np.float32), started)
        a = np.clip(np.asarray(act, float), [-1, -1, -1, 0], [1, 1, 1, 1])
        out.append((np.float32(a), st))
    return out
ok = True
for pi, profile in enumerate(profiles):
    for kind in (('left', 'headon') if profile not in ('tuned', 'tuned2') else ('left', 'right')):
        seq = sequence(kind); ref = reference(profile, seq, RESUME)
        lport, hport = 18200 + 2 * pi, 18201 + 2 * pi
        (PKG / 'net_test.json').write_text(json.dumps(dict(listen_ip='127.0.0.1', listen_port=lport, host_ip='127.0.0.1', host_port=hport, max_hz=60)))
        host = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); host.bind(('127.0.0.1', hport)); host.settimeout(2.)
        env = dict(os.environ, PYTHONPATH=str(PKG / 'policy') + os.pathsep + str(PKG / 'tools'))
        pl = subprocess.Popen([sys.executable, '-B', str(PKG / 'tools' / 'player_fighter.py'), '--network', str(PKG / 'net_test.json'), '--profile', profile] + (['--resume'] if RESUME else []), cwd=str(PKG), env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        time.sleep(1.5)
        worst = 0.; bad_state = 0; got = 0
        for k, o in enumerate(seq):
            host.sendto(struct.pack('<26d', *o), ('127.0.0.1', lport))
            try:
                data, _ = host.recvfrom(256)
            except socket.timeout:
                print('TIMEOUT at', k); ok = False; break
            assert len(data) == 30, len(data)
            *a, st, tag = struct.unpack('<fffff10s', data)
            assert tag == b'PLAYER_CMD', tag
            worst = max(worst, float(np.max(np.abs(np.array(a, dtype=np.float32) - ref[k][0]))))
            bad_state += int(int(st) != ref[k][1]); got += 1
            time.sleep(1 / 45)
        pl.terminate()
        try: pl.wait(3)
        except Exception: pl.kill()
        host.close()
        good = got == len(seq) and worst <= 1e-6 and bad_state == 0
        ok &= good
        print('%-14s %-7s packets %d/%d  max|cmd-ref| = %.2g  state mismatches = %d  -> %s' % (profile, kind, got, len(seq), worst, bad_state, 'PASS' if good else 'FAIL'))
print('LOOPBACK', 'ALL PASS' if ok else 'FAILED')
sys.exit(0 if ok else 1)
