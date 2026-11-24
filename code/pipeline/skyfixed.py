"""Sky-fixed test using each frame's own WCS (no registration): is there a source at the
track's FIRST sky position in its LAST frame (and vice versa)? -> stationary object, false mover."""
import json, numpy as np
from extract import cache_name
tr = json.load(open('results/tracklets_classified.json', encoding='utf-8'))
def src_at(f, ra, dec, r=2.5):
    c = np.load(cache_name(f))
    d = np.hypot((c['ra'] - ra) * np.cos(np.radians(dec)), c['dec'] - dec) * 3600
    return bool(np.nanmin(d) < r)
def radec(f, i):
    c = np.load(cache_name(f)); k = np.argmin(np.hypot(c['x'] - xs[i], c['y'] - ys[i])); return c['ra'][k], c['dec'][k]
for t in tr:
    import re
    rot = [re.search(r'_(\d+)deg', f).group(1) for f in t['files']]
    keep = [i for i in range(len(rot)) if rot[i] == rot[0]]
    t['spans_flip'] = len(keep) < len(rot)
    xs = [t['xs'][i] for i in keep]; ys = [t['ys'][i] for i in keep]; fs = [t['files'][i] for i in keep]
    ra0, de0 = radec(fs[0], 0); ra1, de1 = radec(fs[-1], -1)
    sep = np.hypot((ra1 - ra0) * np.cos(np.radians(de0)), de1 - de0) * 3600
    stat = src_at(fs[-1], ra0, de0) and src_at(fs[0], ra1, de1)
    t['raw_sky_disp_arcsec'] = round(float(sep), 1); t['stationary_raw'] = stat
    if t['class'].startswith('unidentified') or t['class'].startswith('false'):
        t['class'] = 'false(stationary)' if stat or sep < 4 or len(keep) < 4 else 'unidentified'
    print(t['id'], t['target'][:12], t['class'], t['known_name'], 'raw disp', round(sep, 1), 'stationary', stat, 'flip', t['spans_flip'])
json.dump(tr, open('results/tracklets_classified.json', 'w', encoding='utf-8'), indent=1)
