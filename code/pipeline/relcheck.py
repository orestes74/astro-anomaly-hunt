"""Motion relative to neighbouring stars in sensor pixels (immune to WCS / registration errors)."""
import json, numpy as np, os
from scipy.spatial import cKDTree
from extract import cache_name
tr = json.load(open('results/tracklets_classified.json', encoding='utf-8'))
for t in tr:
    offs = []
    ref = None
    for f, x, y in zip(t['files'], t['xs'], t['ys']):
        c = np.load(cache_name(f))
        bright = (c['peak'] > 20 * c['rms']) & ~c['sat']
        P = np.c_[c['x'][bright], c['y'][bright]]
        if ref is None:
            d = np.hypot(P[:, 0] - x, P[:, 1] - y)
            ref = P[(d > 15) & (d < 300)] - [x, y]   # neighbour star offsets in first frame
            ref = ref[np.argsort(np.hypot(*ref.T))[:12]]
            offs.append(0.0); continue
        # where are those neighbours now (same rotation assumed; skip flipped frames)
        tree = cKDTree(P)
        if len(ref) == 0:
            offs.append(0.0); continue
        # assume the object is static relative to the stars: are the first-frame neighbours at the same offsets now?
        dd, _ = tree.query(np.c_[x, y] + ref, distance_upper_bound=3)
        best = float(np.isfinite(dd).mean())
        offs.append(best)
    # fraction of neighbour stars found at the SAME offsets around the object in later frames
    stat_frac = float(np.mean(offs[1:])) if len(offs) > 1 else 0
    t['static_vs_stars'] = round(stat_frac, 2)
    if t['class'] == 'unidentified' and stat_frac > 0.5:
        t['class'] = 'false(static-vs-stars)'
    print(t['id'], t['target'][:12], t['class'], t['known_name'], 'static_frac', round(stat_frac, 2))
json.dump(tr, open('results/tracklets_classified.json', 'w', encoding='utf-8'), indent=1)
