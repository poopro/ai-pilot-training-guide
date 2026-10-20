"""Host ACMI 回合分析(Tacview ACMI 2.2,Host 端輸出)。
用法: python acmi_analyze.py <output_acmi 資料夾或單一 .acmi 檔>
P1 = 我方(藍),P2 = 內建/對手(紅)。ACMI 高度單位為公尺,T=經度|緯度|高度|roll|pitch|yaw。
擊殺判定近似:機鼻與視線夾角 <= 1°、三維距離 500–3000 ft,累積 180 幀。
注意:機鼻角在 1° 邊緣附近很敏感,本腳本重建的結束幀與 Host 實際結束幀可能差數十幀。"""
import sys, re, glob, math, os
import numpy as np
FT = 3.28084
def load(fn):
    t, A, B, cur = [], [], [], None
    for line in open(fn, encoding='utf-8'):
        line = line.strip()
        if line.startswith('#'):
            cur = float(line[1:]); t.append(cur); A.append(None); B.append(None); continue
        m = re.match(r'^([12]),T=(.*)$', line)
        if m and cur is not None:
            v = [float(x) for x in m.group(2).split('|')]
            (A if m.group(1) == '1' else B)[-1] = v
    return np.array(t), np.array(A, float), np.array(B, float)
def analyze(fn):
    t, A, B = load(fn)
    phi = math.radians(A[0, 1])
    mlat = 111132.92 - 559.82*math.cos(2*phi) + 1.175*math.cos(4*phi)
    mlon = 111412.84*math.cos(phi) - 93.5*math.cos(3*phi)
    xyz = lambda P: np.stack([(P[:, 0]-A[0, 0])*mlon, (P[:, 1]-A[0, 1])*mlat, P[:, 2]], 1)
    a, b = xyz(A), xyz(B)
    def nose(P):
        y, p = np.radians(P[:, 5]), np.radians(P[:, 4])
        return np.stack([np.sin(y)*np.cos(p), np.cos(y)*np.cos(p), np.sin(p)], 1)
    d = b - a; dist = np.linalg.norm(d, axis=1); dft = dist*FT
    angA = np.degrees(np.arccos(np.clip((nose(A)*d).sum(1)/dist, -1, 1)))
    angB = np.degrees(np.arccos(np.clip((nose(B)*-d).sum(1)/dist, -1, 1)))
    inr = (dft >= 500) & (dft <= 3000)
    cA = np.cumsum((angA <= 1) & inr); cB = np.cumsum((angB <= 1) & inr)
    dt = np.diff(t); k = 6
    def g(P):
        v = np.diff(xyz(P), axis=0)/dt[:, None]
        out = [np.linalg.norm((v[i]-v[i-k])/dt[i-k:i].sum() + [0, 0, 9.80665])/9.80665 for i in range(k, len(v))]
        return np.array(out)
    gA, gB = g(A), g(B)
    hd = math.radians(A[0, 5]); u = (math.sin(hd), math.cos(hd))
    side = 'P2在左' if (u[0]*d[0, 1]-u[1]*d[0, 0]) > 0 else 'P2在右'
    return dict(檔案=os.path.basename(fn), 回合秒=round(float(t[-1]), 1), 初始距離ft=round(float(dft[0])), 側=side,
        最小間距m=round(float(dist.min())), 結束距離ft=round(float(dft[-1])), 最低高度m_我=round(float(A[:, 2].min())),
        結束機鼻夾角_我=round(float(angA[-1]), 2), 結束機鼻夾角_對=round(float(angB[-1]), 1),
        錐內累積幀_我=int(cA[-1]), 錐內累積幀_對=int(cB[-1]), 最大G_我=round(float(gA.max()), 2),
        最大G_對=round(float(gB.max()), 2), 最大滾轉_我=round(float(np.abs(A[:, 3]).max())))
if __name__ == '__main__':
    p = sys.argv[1] if len(sys.argv) > 1 else '.'
    files = [p] if p.endswith('.acmi') else sorted(glob.glob(os.path.join(p, '*.acmi')))
    for f in files:
        for k, v in analyze(f).items(): print(f'{k}: {v}')
        print()
