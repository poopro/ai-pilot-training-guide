"""Build the interactive fly-brain viewer (single HTML file, three.js from cdnjs).

  python make_viewer.py --replay cache\\g600001_lead.npz --out viewer.html          # recorded game, fly watched open-loop
  python make_viewer.py --replay runs\\watch\\activity\\fly_700000_mix.npz --out viewer.html   # live arena game (fly_eval --record)

The .npz must hold the sparse spikes (sp_idx, sp_cnt, sp_ptr) and feats; tactic or acts for the strip.
"""
import argparse, base64, json
from pathlib import Path
import numpy as np
from flybrain.connectome import Connectome
from flybrain.pilot import Encoder

FEAT_NAMES = ['距離', '接近速度', '機鼻偏角', '方位角', '仰角', '敵機相位', '橫向交叉', '滾轉 sin', '滾轉 cos', '俯仰 sin', '俯仰 cos',
              '攻角 α', '側滑 β', 'G 值', '空速', '高度', '相對高度', '敵機速度', '垂直速度', '滾轉率 p', '俯仰率 q', '偏航率 r',
              '攻擊累積', '時鐘', '1° 鎖定', '有效距離內', '偏角<5°']
TACTICS = ['純追', '超前', '滯後', '向內急轉', '向外急轉', '高 yo-yo', '低 yo-yo', '脫離']
ENEMY = [0, 1, 2, 3, 4, 5, 6, 16, 17]
OWN = [7, 8, 9, 10, 11, 12, 13, 14, 15, 18, 19, 20, 21]
STATE = [22, 23, 24, 25, 26]


def b64(a):
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode('ascii')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--replay', required=True)
    ap.add_argument('--out', default='viewer.html')
    ap.add_argument('--fragment', default=None, help='also write the body-less fragment (for publishing as a web page)')
    ap.add_argument('--stats', default='cache/enc_stats.npz')
    ap.add_argument('--k', type=int, default=20)
    ap.add_argument('--window-ms', type=float, default=80.0)
    ap.add_argument('--subtitle', default='')
    ap.add_argument('--footer', default='')
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--max-frames', type=int, default=0)
    a = ap.parse_args()
    here = Path(__file__).resolve().parent
    z = np.load(a.replay)
    T = len(z['feats'])
    if a.max_frames: T = min(T, a.max_frames)
    ptr = z['sp_ptr'][:T + 1].astype(np.uint32)
    sidx = z['sp_idx'][:ptr[-1]].astype(np.uint32)
    scnt = np.minimum(z['sp_cnt'][:ptr[-1]], 255).astype(np.uint8)
    feats = z['feats'][:T].astype(np.float32)
    tac = (z['tactic'] if 'tactic' in z.files else z['acts'])[:T].astype(np.uint8)
    if 'enc_mu' in z.files:
        mu, sd = z['enc_mu'], z['enc_sd']
    else:
        st = np.load(a.stats); mu, sd = st['mu'], st['sd']
    zz = np.clip((feats - mu) / sd / 2.5, -1, 1)
    C = Connectome()
    A = C.ann
    P = C.positions().copy()
    P -= np.nanmedian(P, 0)
    P[:, 1] *= -1                                    # dorsal up
    P = np.nan_to_num(P)
    scale = np.percentile(np.abs(P), 99.7)
    Q = np.clip(P / scale * 32767, -32767, 32767).astype(np.int16)
    sc = A['super_class'].to_numpy()
    cls = np.zeros(C.n, np.uint8)
    cls[sc == 'optic'] = 1
    cls[sc == 'sensory'] = 2
    cls[np.isin(sc, ['visual_projection', 'visual_centrifugal'])] = 3
    cls[(sc == 'sensory') & (A['cell_class'].to_numpy() == 'visual')] = 6      # photoreceptors: outside the brain, never driven, hidden
    cls[(np.abs(P / scale) > 1.0).any(1)] = 6
    cls[sc == 'descending'] = 4
    cls[np.isin(sc, ['ascending', 'sensory_ascending'])] = 5
    dn = C.select(super_class='descending')
    lab = [('%s·%s' % (A['cell_type'].iat[i] or 'DN?', {'left': 'L', 'right': 'R'}.get(A['side'].iat[i], 'C')))[:14] for i in dn]
    enc = Encoder(C, k=a.k)
    data = dict(n=int(C.n), T=int(T), k=a.k, dt=20 / 60.0, windowMs=a.window_ms, windowS=a.window_ms / 1000.0, nDN=int(len(dn)),
                pos=b64(Q.reshape(-1)), cls=b64(cls), inp=b64(enc.flat_idx.astype(np.uint32)), dn=b64(dn.astype(np.uint32)),
                dnLabel=lab, ptr=b64(ptr), sidx=b64(sidx), scnt=b64(scnt), feat=b64(feats.reshape(-1)),
                z=b64(np.round(zz * 100).astype(np.int8).reshape(-1)), tactic=b64(tac),
                featNames=FEAT_NAMES, tacticNames=TACTICS, groupEnemy=ENEMY, groupOwn=OWN, groupState=STATE,
                subtitle=a.subtitle, footer=a.footer, startAt=a.start)
    tpl = (here / 'viewer_template.html').read_text(encoding='utf-8')
    frag = tpl.replace('/*__DATA__*/', 'const DATA = ' + json.dumps(data, ensure_ascii=False) + ';')
    doc = '<!doctype html>\n<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>\n' + frag + '\n</body></html>\n'
    Path(a.out).write_text(doc, encoding='utf-8')
    if a.fragment:
        Path(a.fragment).write_text(frag, encoding='utf-8')
    print('wrote', a.out, '%.1f MB' % (len(doc) / 1e6), '| frames', T, '| spikes/frame mean %.0f' % np.diff(ptr).mean())


if __name__ == '__main__':
    main()
