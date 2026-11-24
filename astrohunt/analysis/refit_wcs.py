"""카탈로그 WCS를 Gaia 별로 다시 맞춤(SIP 3차 왜곡) → ra/dec/gaia_d/gaia_g 다시 계산해 카탈로그 갱신."""
import sys as _s, os as _o; _s.path.insert(0, _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))); import cfg
import os, sys, glob, numpy as np, warnings
from astropy.coordinates import SkyCoord
import astropy.units as u
from astropy.wcs.utils import fit_wcs_from_points
from scipy.spatial import cKDTree
import transient as T
warnings.filterwarnings('ignore')
for fn in sorted(glob.glob(os.path.join(T.CAT, '*.npz'))):
    sid = os.path.basename(fn)[:-4]
    z = dict(np.load(fn))
    if 'refit' in z:
        continue
    c = T.load_cat(sid); w = c['wcs']; H, W = c['shape']
    gra, gde, gg, _ = T.field_gaia(sid)
    sel = (gg < 18.5)
    gra, gde, gg2 = gra[sel], gde[sel], gg[sel]
    ok = (c['snr'] > 20) & (c['flag'] < 4) & (c['peak'] < 0.8 * c['satur'])
    x, y = c['x'][ok], c['y'][ok]
    for it, rad in enumerate((12, 5, 3)):
        gx, gy = w.all_world2pix(gra, gde, 0, quiet=True)
        t = cKDTree(np.c_[gx, gy]); dd, ii = t.query(np.c_[x, y], distance_upper_bound=rad)
        m = np.isfinite(dd)
        if m.sum() < 30:
            break
        w = fit_wcs_from_points((x[m], y[m]), SkyCoord(gra[ii[m]] * u.deg, gde[ii[m]] * u.deg), projection='TAN', sip_degree=3)
    gx, gy = w.all_world2pix(gra, gde, 0, quiet=True)
    t = cKDTree(np.c_[gx, gy]); scale = float(c['scale'])
    dd, ii = t.query(np.c_[c['x'], c['y']], distance_upper_bound=4.0 / scale + 2)
    has = np.isfinite(dd)
    # 전 목록(G<20.8)으로 가장 가까운 별 거리
    gx2, gy2 = w.all_world2pix(*T.field_gaia(sid)[:2], 0, quiet=True); gall = T.field_gaia(sid)[2]
    t2 = cKDTree(np.c_[gx2, gy2]); d2, i2 = t2.query(np.c_[c['x'], c['y']], distance_upper_bound=10 / scale)
    sky = w.pixel_to_world(c['x'], c['y'])
    z.update(ra=sky.ra.deg, dec=sky.dec.deg, gaia_d=np.where(np.isfinite(d2), d2 * scale, np.inf),
             gaia_g=np.where(np.isfinite(d2), gall[np.minimum(i2, len(gall) - 1)], np.nan),
             wcs_hdr=np.array(w.to_header(relax=True).tostring()), refit=1)
    np.savez(fn, **z)
    b = ok & np.isfinite(d2)
    r = np.hypot(c['x'] - W / 2, c['y'] - H / 2) / np.hypot(W / 2, H / 2)
    out = (ok & (r > 0.7))
    print(f"{sid}: 맞춘 별 {m.sum()}, 중앙 오차 {np.median(d2[b]) * scale:.2f}\", 바깥(r>0.7) 미일치 {np.mean(~np.isfinite(d2[out]) | (d2[out] * scale > 4)):.2f}", flush=True)
