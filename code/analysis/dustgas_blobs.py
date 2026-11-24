"""먼지·가스 잔차 덩어리 분류: 가장자리(플랫·감광 잔여) / 대상 천체 / 그 밖(검토 대상)."""
import json, glob, os, numpy as np
from astropy.io import fits
from astropy.wcs import WCS
import common as C
rows = []
for f in sorted(glob.glob(os.path.join(C.HERE, 'results', 'dustgas', '*.json'))):
    r = json.load(open(f)); sid = r['sid']
    h = fits.getheader(os.path.join(C.STACKS, sid, 'linear.fit')); w = WCS(h, naxis=2)
    nx, ny = h['NAXIS1'], h['NAXIS2']
    for key in ('dust_iris', 'dust_planck', 'halpha'):
        x = r.get(key)
        if not isinstance(x, dict):
            continue
        for b in x['blobs']:
            px, py = w.all_world2pix(b['ra'], b['dec'], 0)
            ex = min(px, nx - px) / nx; ey = min(py, ny - py) / ny
            cen = np.hypot(px / nx - 0.5, py / ny - 0.5)
            where = 'edge' if min(ex, ey) < 0.12 else ('center' if cen < 0.15 else 'field')
            rows.append(dict(sid=sid, map=key, where=where, x=float(px), y=float(py), **b))
json.dump(rows, open(os.path.join(C.HERE, 'results', 'dustgas_blobs.json'), 'w'), indent=0)
from collections import Counter
print(Counter(r['where'] for r in rows))
for r in rows:
    if r['where'] == 'field' and r['peak_sigma'] > 5:
        print(f"{r['sid'][:40]:40s} {r['map']:11s} {r['sign']} {r['ra']:.3f} {r['dec']:+.3f} 면적 {r['area_arcmin2']:.0f}′² 최대 {r['peak_sigma']:.1f}σ  px({r['x']:.0f},{r['y']:.0f})")
