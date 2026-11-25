"""
grid_paths.py - minimum-cost paths (Dijkstra) on a 3D cost grid, 26-neighbourhood.

Replaces skimage.graph.MCP_Geometric, whose compiled module (_mcp.pyd) can be blocked by Windows Smart App Control.
Same definition of the cost of a route:

    step(a, b) = |a - b| * (cost(a) + cost(b)) / 2        |a - b| = 1, sqrt(2) or sqrt(3) cells

Cells with an infinite (or NaN) cost cannot be entered. Two backends give identical results:
  - "csgraph": scipy.sparse.csgraph.dijkstra on the graph of the passable cells (fast, ~1-2 s per run);
  - "numpy": repeated relaxation over the 26 neighbour shifts until nothing changes (no compiled code beyond
    NumPy itself; slower, used only if the SciPy module cannot be loaded).

Usage (same as MCP_Geometric):
    m = GridMCP(cost)
    cum, _ = m.find_costs([start_index, ...])      # cumulative cost from the nearest start to every cell (inf = unreachable)
    path = m.traceback(end_index)                  # [start, ..., end] as index tuples
"""
import itertools
import numpy as np

try:
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra as _dijkstra
    BACKEND = "csgraph"
except ImportError:                                               # e.g. blocked by Smart App Control
    BACKEND = "numpy"

OFFSETS = [o for o in itertools.product((-1, 0, 1), repeat=3) if o != (0, 0, 0)]
HALF = [o for o in OFFSETS if o > (0, 0, 0)]                      # one of each +/- pair (13 offsets)


def _pairs(shape, o):
    """Slices a, b such that cell a + o = cell b, for offset o."""
    a = tuple(slice(max(-d, 0), n - max(d, 0)) for d, n in zip(o, shape))
    b = tuple(slice(max(d, 0), n - max(-d, 0)) for d, n in zip(o, shape))
    return a, b


class GridMCP:
    def __init__(self, cost, backend=None):
        cost = np.asarray(cost, float)
        self.cost = np.where(np.isfinite(cost), cost, np.inf)
        self.shape = self.cost.shape
        self.backend = backend or BACKEND
        self.cum = self._pred = None

    # ------------------------------------------------------------------ public API (as MCP_Geometric)
    def find_costs(self, starts):
        starts = [tuple(int(v) for v in s) for s in starts]
        if self.backend == "csgraph": self._run_csgraph(starts)
        else: self._run_numpy(starts)
        return self.cum, None

    def traceback(self, end):
        end = tuple(int(v) for v in end)
        if not np.isfinite(self.cum[end]): raise ValueError(f"no route to {end}")
        path, cur = [end], end
        for _ in range(int(np.prod(self.shape))):
            prev = self._prev(cur)
            if prev is None: break
            path.append(prev); cur = prev
        return path[::-1]

    # ------------------------------------------------------------------ scipy.sparse.csgraph backend
    def _run_csgraph(self, starts):
        c, sh = self.cost, self.shape
        free = np.isfinite(c)
        ids = np.full(sh, -1, np.int64); ids[free] = np.arange(free.sum())
        rows, cols, w = [], [], []
        for o in HALF:
            a, b = _pairs(sh, o)
            ok = free[a] & free[b]
            if not ok.any(): continue
            rows.append(ids[a][ok]); cols.append(ids[b][ok])
            w.append(np.sqrt(sum(d * d for d in o)) * (c[a][ok] + c[b][ok]) / 2)
        n = int(free.sum())
        cum = np.full(sh, np.inf); self._pred_ids, self._ids = None, ids
        src = [ids[s] for s in starts if 0 <= ids[s]]
        if not rows or not src:                                   # nothing passable: only the starts themselves
            for s in starts: cum[s] = 0.0
            self.cum, self._pred_ids, self._cells = cum, np.full(n, -9999), np.argwhere(free)
            return
        w = np.concatenate(w)
        w = np.maximum(w, 1e-12)                                  # csgraph drops explicit zero-weight edges
        g = coo_matrix((w, (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsr()
        dist, pred, _ = _dijkstra(g, directed=False, indices=src, return_predecessors=True, min_only=True)
        cum[free] = dist
        for s in starts:
            if ids[s] < 0: cum[s] = 0.0                           # a start on an impassable cell: reached, nothing else
        self.cum, self._pred_ids, self._cells = cum, pred, np.argwhere(free)

    # ------------------------------------------------------------------ NumPy relaxation backend
    def _run_numpy(self, starts):
        c, sh = self.cost, self.shape
        cum = np.full(sh, np.inf)
        for s in starts: cum[s] = 0.0
        step = np.full(sh, -1, np.int8)                           # index into OFFSETS of the step that reached the cell
        edges = []                                                # per offset: cost of entering cell b from b - o
        for k, o in enumerate(OFFSETS):
            a, b = _pairs(sh, o)
            edges.append((k, a, b, np.sqrt(sum(d * d for d in o)) * (c[a] + c[b]) / 2))
        while True:
            changed = False
            for k, a, b, w in edges:
                cand = cum[a] + w
                better = cand < cum[b]
                if better.any():
                    cum[b] = np.where(better, cand, cum[b])
                    step[b] = np.where(better, k, step[b])
                    changed = True
            if not changed: break
        self.cum, self._step = cum, step

    # ------------------------------------------------------------------ one step back towards the start
    def _prev(self, cur):
        if self.backend == "csgraph":
            i = self._ids[cur]
            if i < 0: return None
            p = self._pred_ids[i]
            return None if p < 0 else tuple(int(v) for v in self._cells[p])
        k = self._step[cur]
        if k < 0: return None
        o = OFFSETS[k]
        return tuple(int(x - d) for x, d in zip(cur, o))
