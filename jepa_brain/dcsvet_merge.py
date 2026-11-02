"""Merge per-bucket dcsvet_data npz files; optional perspective filter.
python dcsvet_merge.py OUT.npz --filter ace|all|winners IN1.npz IN2.npz ..."""
import sys, json
import numpy as np


def keep_row(r, mode):
    if mode == 'all':
        return True
    if mode == 'ace':
        return r.get('skill') == 'Excellent'
    if mode == 'winners':
        return r.get('result') == 'win'
    if mode == 'ace_nodraw':
        return r.get('skill') == 'Excellent' and r.get('result') != 'draw'
    raise ValueError(mode)


def main(argv):
    out = argv[0]
    mode = 'all'
    files = []
    i = 1
    while i < len(argv):
        if argv[i] == '--filter':
            mode = argv[i + 1]; i += 2
        else:
            files.append(argv[i]); i += 1
    Xs, Ys, F, T, rows = [], [], [], [], []
    for f in files:
        d = np.load(f, allow_pickle=True)
        rr = json.loads(str(d['rows']))
        fid = d['fid']
        tag = f.split('/')[-1].replace('.npz', '')
        remap = {}
        for r in rr:
            if keep_row(r, mode):
                nr = dict(r, rec=tag + ':' + str(r['rec']), fid=len(rows))
                remap[r['fid']] = nr['fid']
                rows.append(nr)
        m = np.array([int(x) in remap for x in fid], bool)
        Xs.append(d['X'][m]); Ys.append(d['Y'][m]); T.append(d['t'][m])
        F.append(np.array([remap[int(x)] for x in fid[m]], np.int32))
    X, Y = np.concatenate(Xs), np.concatenate(Ys)
    np.savez(out, X=X, Y=Y, fid=np.concatenate(F), t=np.concatenate(T), rows=json.dumps(rows))
    print(mode, 'samples', len(X), 'perspectives', len(rows))


if __name__ == '__main__':
    main(sys.argv[1:])
