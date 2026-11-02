# Stream-thin a DCSVET rec CSV to ~15 Hz per unit; bucket whole fights (100 fight-idx per file) into gzip files.
import sys, gzip, os
src, outdir, prefix = sys.argv[1], sys.argv[2], sys.argv[3]
min_dt = float(sys.argv[4]) if len(sys.argv) > 4 else 0.06
os.makedirs(outdir, exist_ok=True)
last = {}; outs = {}
n_in = n_out = 0
with open(src, 'r', encoding='utf-8', errors='replace') as fi:
    head = fi.readline()
    for line in fi:
        n_in += 1
        p = line.split(',', 3)
        if len(p) < 4: continue
        try: t = float(p[0])
        except ValueError: continue
        k = p[2]
        lt = last.get(k)
        if lt is not None and t - lt < min_dt: continue
        last[k] = t
        q = k.split('_')
        try: b = int(q[3]) // 100
        except (IndexError, ValueError): b = 9999
        fo = outs.get(b)
        if fo is None:
            fo = gzip.open(os.path.join(outdir, '%s_b%04d.csv.gz' % (prefix, b)), 'wt', compresslevel=3)
            fo.write(head); outs[b] = fo
        fo.write(line); n_out += 1
for fo in outs.values(): fo.close()
print('in', n_in, 'out', n_out, 'files', len(outs))
