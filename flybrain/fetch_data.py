"""Download the FlyWire v783 connectome + neuron annotations into ./data (about 135 MB, resumable, checksummed).

  python fetch_data.py

Sources (pinned commits, so everybody gets the same bytes):
  * connectome edge list + neuron list : github.com/philshiu/Drosophila_brain_model   (MIT)  - Shiu et al. 2024, Nature
  * neuron annotations (cell types...) : github.com/flyconnectome/flywire_annotations        - Schlegel et al. 2024, Nature
Please cite those papers if you show results (see README).
"""
import hashlib, sys, urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent / 'data'
SHIU = 'https://raw.githubusercontent.com/philshiu/Drosophila_brain_model/91bdd1e7dcf193f3e7ca5a8933497fcef63b7960/'
ANN = 'https://raw.githubusercontent.com/flyconnectome/flywire_annotations/a83b2776d60d5764cef36b927f5f9679c16c47a2/supplemental_files/'
FILES = [
    ('Completeness_783.csv', SHIU + 'Completeness_783.csv', 'bbb847a4cc2caaa7a16349722d220c087317b946d148d4d592d94d250617a311'),
    ('Connectivity_783.parquet', SHIU + 'Connectivity_783.parquet', 'efeb23fb99098e9c390f6869969b2a121a2ee92c833cfc45ecb2c1d8e1af0347'),
    ('Supplemental_file1_neuron_annotations.tsv', ANN + 'Supplemental_file1_neuron_annotations.tsv', 'b214970b55d2fbe0853bba536fdcb9e28730f4eb7ab06f600491df795da683cd'),
]


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    DATA.mkdir(exist_ok=True)
    for name, url, digest in FILES:
        dst = DATA / name
        if dst.exists() and sha256(dst) == digest:
            print('ok      ', name); continue
        print('download', name, flush=True)
        tmp = dst.with_suffix(dst.suffix + '.part')
        with urllib.request.urlopen(url) as r, open(tmp, 'wb') as f:
            total = int(r.headers.get('Content-Length') or 0); got = 0
            while True:
                b = r.read(1 << 20)
                if not b: break
                f.write(b); got += len(b)
                if total: print('\r  %.0f%%' % (100 * got / total), end='', flush=True)
        print()
        if sha256(tmp) != digest:
            tmp.unlink(); sys.exit('checksum mismatch for ' + name)
        tmp.replace(dst)
        print('saved   ', name)
    print('all data ready in', DATA)


if __name__ == '__main__':
    main()
