"""FlyWire (v783) connectome + annotations loader.

Data files (see fetch_data.py):
  data/Completeness_783.csv                    neuron list (138,639 neurons, index = FlyWire root_id)
  data/Connectivity_783.parquet                15.1 M neuron->neuron edges (signed synapse count)
  data/Supplemental_file1_neuron_annotations.tsv   super_class / cell_type / side / soma xyz ... (optional)

The edge list is the same file used by Shiu et al. 2024 (Nature, "A Drosophila computational brain
model reveals sensorimotor processing"): column 'Excitatory x Connectivity' = (#synapses) * (+1 for
excitatory transmitters, -1 for inhibitory).  We store it presynaptic-major (CSR) so that a spike can
be propagated by looking only at the rows of the neurons that actually fired (event driven).
"""
from pathlib import Path
import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / 'data'


class Connectome:
    def __init__(self, data_dir=None, annotations=True, verbose=True):
        d = Path(data_dir) if data_dir else DATA
        comp = pd.read_csv(d / 'Completeness_783.csv', index_col=0)
        self.root_ids = comp.index.values.astype(np.int64)
        self.n = len(self.root_ids)
        con = pd.read_parquet(d / 'Connectivity_783.parquet',
                              columns=['Presynaptic_Index', 'Postsynaptic_Index', 'Excitatory x Connectivity'])
        pre = con['Presynaptic_Index'].to_numpy(np.int64)
        order = np.argsort(pre, kind='stable')
        self.post = con['Postsynaptic_Index'].to_numpy(np.int32)[order]
        self.wcount = con['Excitatory x Connectivity'].to_numpy(np.int16)[order]   # signed #synapses
        self.indptr = np.zeros(self.n + 1, dtype=np.int64)
        np.cumsum(np.bincount(pre, minlength=self.n), out=self.indptr[1:])
        del con, pre, order
        self.ann = None
        f = d / 'Supplemental_file1_neuron_annotations.tsv'
        if annotations and f.exists():
            self.ann = self._load_annotations(f)
        if verbose:
            print('[connectome] %d neurons, %d edges%s' % (self.n, len(self.post),
                  ', annotations OK' if self.ann is not None else ', NO annotations'))

    def _load_annotations(self, f):
        cols = ['root_id', 'pos_x', 'pos_y', 'pos_z', 'soma_x', 'soma_y', 'soma_z', 'flow', 'super_class',
                'cell_class', 'cell_sub_class', 'cell_type', 'top_nt', 'side']
        a = pd.read_csv(f, sep='\t', usecols=cols, low_memory=False).drop_duplicates('root_id').set_index('root_id')
        a = a.reindex(self.root_ids)
        # soma position if known, else an anchor point on the neuron; 4x4x40 nm voxels -> micrometres
        for ax, scale in (('x', 0.004), ('y', 0.004), ('z', 0.04)):
            a['u' + ax] = a['soma_' + ax].fillna(a['pos_' + ax]) * scale
        for c in ('flow', 'super_class', 'cell_class', 'cell_sub_class', 'cell_type', 'top_nt', 'side'):
            a[c] = a[c].fillna('')
        a = a.reset_index()
        return a

    # ---- neuron selection helpers (indices into 0..n-1) ----
    def select(self, **kw):
        """select(super_class='descending', side='left') ; values may be str / list / callable"""
        assert self.ann is not None, 'annotations not loaded'
        m = np.ones(self.n, dtype=bool)
        for k, v in kw.items():
            col = self.ann[k]
            if callable(v):
                m &= col.map(v).to_numpy(bool)
            elif isinstance(v, (list, tuple, set)):
                m &= col.isin(list(v)).to_numpy()
            else:
                m &= (col == v).to_numpy()
        return np.flatnonzero(m)

    def positions(self):
        a = self.ann
        return np.stack([a['ux'].to_numpy(), a['uy'].to_numpy(), a['uz'].to_numpy()], 1).astype(np.float32)

    def influence(self, hops=3, cache=True):
        """Backward 'drive fraction' from each neuron to the descending neurons over up to `hops` excitatory hops.
        (How much of the DNs' input budget a spike of this neuron can reach.)  Cached in data/influence.npy."""
        f = DATA / 'influence.npy'
        if cache and f.exists():
            v = np.load(f)
            if len(v) == self.n:
                return v
        import scipy.sparse as sp
        pre = np.repeat(np.arange(self.n), np.diff(self.indptr))
        w = self.wcount.astype(np.float32)
        pos = w > 0
        Wp = sp.csr_matrix((w[pos], (pre[pos], self.post[pos])), shape=(self.n, self.n))
        tot_in = np.asarray(sp.csr_matrix((np.abs(w), (pre, self.post)), shape=(self.n, self.n)).sum(0)).ravel() + 1.0
        Wn = Wp @ sp.diags(1.0 / tot_in)
        d = np.zeros(self.n, np.float32)
        d[self.select(super_class='descending')] = 1
        v, tot = d, np.zeros(self.n, np.float32)
        for _ in range(hops):
            v = Wn @ v
            tot += v
        tot = tot.astype(np.float32)
        if cache:
            np.save(f, tot)
        return tot
