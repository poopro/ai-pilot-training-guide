"""One-shot DCSVET pipeline: all recordings -> dataset -> BC model -> league check.

  python dcsvet_run.py                       (uses Saved Games\\DCS\\Logs\\dcsvet\\*.csv and dcs.log*)
  python dcsvet_run.py --skill Excellent     (only fights logged with that skill; default: all)
Outputs in jepa_brain/dcsvet/: data.npz, bc.npz, report.json, eval.jsonl
"""
import os, sys, glob, json, zipfile, argparse, io
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / 'dcsvet'


def dcs_dir():
    cands = [Path(os.environ.get('USERPROFILE', '')) / 'Saved Games' / 'DCS', Path.home() / 'Saved Games' / 'DCS',
             Path.home() / 'mnt' / 'DCS']
    for c in cands:
        if (c / 'Logs').exists():
            return c
    raise SystemExit('DCS Saved Games folder not found')


def collect_logs(d):
    """dcs.log plus rotated dcs.log-*.zip (DCSVET lines only) -> one text file."""
    lines = []
    for z in sorted(glob.glob(str(d / 'Logs' / 'dcs.log-*.zip'))):
        try:
            with zipfile.ZipFile(z) as zf:
                for n in zf.namelist():
                    lines += [l for l in io.TextIOWrapper(zf.open(n), encoding='utf-8', errors='replace') if 'DCSVET|' in l]
        except Exception:
            pass
    p = d / 'Logs' / 'dcs.log'
    if p.exists():
        lines += [l for l in open(p, encoding='utf-8', errors='replace') if 'DCSVET|' in l]
    OUT.mkdir(exist_ok=True)
    f = OUT / 'dcsvet_lines.log'
    f.write_text(''.join(lines), encoding='utf-8')
    return str(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skill', default=None)
    ap.add_argument('--epochs', type=int, default=40)
    ap.add_argument('--games', type=int, default=24)
    ap.add_argument('--workers', type=int, default=2)
    a = ap.parse_args()
    d = dcs_dir()
    recs = sorted(glob.glob(str(d / 'Logs' / 'dcsvet' / 'rec_*.csv')))
    log = collect_logs(d)
    print('recordings', len(recs), 'log', log)
    import dcsvet_data, dcsvet_bc
    X, Y, rows = dcsvet_data.main([str(OUT / 'data_all.npz')] + recs + ['--log', log])
    data = OUT / 'data_all.npz'
    if a.skill:
        z = np.load(data, allow_pickle=True)
        keep_f = {r['fid'] for r in rows if r.get('skill') == a.skill}
        m = np.isin(z['fid'], list(keep_f))
        data = OUT / ('data_%s.npz' % a.skill)
        np.savez_compressed(data, X=z['X'][m], Y=z['Y'][m], fid=z['fid'][m], t=z['t'][m],
                            rows=json.dumps([r for r in rows if r['fid'] in keep_f]))
    rep = dcsvet_bc.train(str(data), str(OUT / 'bc.npz'), epochs=a.epochs)
    (OUT / 'report.json').write_text(json.dumps(dict(bc=rep, fights=len({(r['rec'], r['seed'], r['idx']) for r in rows})), indent=1))
    import subprocess
    for blue, red in (('tuned2', 'dcsvet'), ('dcsvet', 'lag'), ('dcsvet', 'guide')):
        subprocess.run([sys.executable, str(HERE / 'dcsvet_pool.py'), 'eval', '--weights', str(OUT / 'bc.npz'), '--blue', blue,
                        '--red', red, '--games', str(a.games), '--workers', str(a.workers), '--out', str(OUT / 'eval.jsonl')])


if __name__ == '__main__':
    main()
