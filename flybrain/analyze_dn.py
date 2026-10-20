"""Which descending neurons (DN) follow which flight feature?  (open-loop replay cache -> Spearman-like correlation)

  python analyze_dn.py --cache cache --top 5

For every one of the 27 features it lists the DNs whose per-decision activity correlates most with it.
This is descriptive only: it shows what the fixed wiring + our encoder make of each input, not what is 'useful'.
"""
import argparse, glob, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from flybrain.connectome import Connectome
from flybrain.pilot import FlyBrain


def rank(x):
    from scipy.stats import rankdata       # average ranks: rare-spike DNs and 0/1 flags are mostly ties
    return rankdata(x, axis=0).astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', default='cache')
    ap.add_argument('--top', type=int, default=5)
    ap.add_argument('--out', default='dn_feature_corr.md')
    a = ap.parse_args()
    names = ['距離', '接近速度', '機鼻偏角', '方位角', '仰角', '敵機相位', '橫向交叉', '滾轉 sin', '滾轉 cos', '俯仰 sin', '俯仰 cos',
             '攻角 α', '側滑 β', 'G 值', '空速', '高度', '垂直速度', '敵機高度', '敵機速度', '滾轉率 p', '俯仰率 q', '偏航率 r',
             '攻擊累積', '時鐘', '1° 鎖定', '有效攻擊距離內', '偏角<5°']
    try:
        from make_viewer import FEAT_NAMES as names
    except Exception:
        pass
    C = Connectome()
    dn_ids = C.select(super_class='descending')
    lab = [str(C.ann['cell_type'].iloc[i]) + '·' + str(C.ann['side'].iloc[i])[:1].upper() for i in dn_ids]
    files = sorted(glob.glob(str(Path(a.cache) / 'g*.npz')))
    DN = np.concatenate([FlyBrain.dn_features(np.load(f)['dn']) for f in files])
    F = np.concatenate([np.load(f)['feats'] for f in files])
    keep = (DN.std(0) > 1e-6) & ((DN > DN.min(0)).mean(0) > 0.02)      # DN must be active in >2% of decisions
    kf = F.std(0) > 1e-6
    Rd, Rf = rank(DN), rank(F)
    Rd = (Rd - Rd.mean(0)) / np.maximum(Rd.std(0), 1e-6); Rf = (Rf - Rf.mean(0)) / np.maximum(Rf.std(0), 1e-6)
    cor = Rd.T @ Rf / len(DN)                        # (n_dn, 27)
    cor[~keep] = 0; cor[:, ~kf] = 0
    lines = ['# DN 與特徵的相關（%d 個決策、%d 場）' % (len(DN), len(files)), '',
             '每個特徵列出相關係數（Spearman）絕對值最大的下行神經元。只是描述固定連線加上我們的編碼會產生什麼，不代表「有用」。', '']
    for j in range(F.shape[1]):
        if not kf[j]:
            lines.append('- **%s**：資料中幾乎沒有變化，略過' % (names[j] if j < len(names) else 'f%d' % j)); continue
        o = np.argsort(-np.abs(cor[:, j]))[:a.top]
        nm = names[j] if j < len(names) else 'f%d' % j
        lines.append(('- **%s**：' % nm) + '、'.join('%s (%+.2f)' % (lab[i], cor[i, j]) for i in o))
    Path(a.out).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines)); print('DN active in >2%% of decisions: %d / %d' % (keep.sum(), len(keep)))


if __name__ == '__main__':
    main()
