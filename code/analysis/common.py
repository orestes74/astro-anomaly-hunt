"""분석 공통: 스택 읽기, Gaia 조회(캐시), WCS 검증·보정, SkyBoT."""
import os, json, hashlib, io, time, warnings, numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
import astropy.units as u
warnings.filterwarnings('ignore')
HERE = os.path.dirname(os.path.abspath(__file__))
STACKS = r'H:\asiair\Stacks'
CACHE = os.path.join(HERE, 'cache'); os.makedirs(CACHE, exist_ok=True)

def load_stack(sid):
    path = os.path.join(STACKS, sid, 'linear.fit')
    with fits.open(path, memmap=False) as hd:
        d = hd[0].data.astype(np.float32); h = hd[0].header
    info = json.load(open(os.path.join(STACKS, sid, 'info.json'), encoding='utf-8'))
    return d, h, info

def lum(d):
    return d.sum(0) if d.ndim == 3 else d

def gaia(ra, dec, radius, gmax=18.0):
    key = hashlib.md5(f'{ra:.3f}{dec:.3f}{radius:.3f}{gmax}'.encode()).hexdigest()
    fn = os.path.join(CACHE, f'gaia_{key}.npz')
    if os.path.exists(fn):
        z = np.load(fn); return z['ra'], z['dec'], z['g'], z['bprp']
    if gmax <= 20.8:   # 이미 받은 깊은 시야 목록(G<20.8)이 이 원을 덮으면 잘라 씀
        fj = os.path.join(HERE, 'fields.json')
        if os.path.exists(fj):
            for g in json.load(open(fj)):
                d = SkyCoord(ra * u.deg, dec * u.deg).separation(SkyCoord(g['ra'] * u.deg, g['dec'] * u.deg)).deg
                k2 = hashlib.md5(f"{round(g['ra'],3):.3f}{round(g['dec'],3):.3f}{round(g['rad'],3):.3f}{20.8}".encode()).hexdigest()
                f2 = os.path.join(CACHE, f'gaia_{k2}.npz')
                if d + radius <= round(g['rad'], 3) * 1.15 and os.path.exists(f2):
                    z = np.load(f2)
                    sep_ = SkyCoord(z['ra'] * u.deg, z['dec'] * u.deg).separation(SkyCoord(ra * u.deg, dec * u.deg)).deg
                    m = (sep_ < radius) & (z['g'] < gmax)
                    return z['ra'][m], z['dec'][m], z['g'][m], z['bprp'][m]
    if gmax > 17:   # 깊은 조회: 동기 조회가 5만 행에서 잘리므로 칸으로 나눠 받고, 가득 차면 다시 4등분
        import requests
        def cell(r0, r1, d0, d1, depth=0):
            q = (f"SELECT ra, dec, phot_g_mean_mag, bp_rp FROM gaiadr3.gaia_source WHERE phot_g_mean_mag < {gmax} "
                 f"AND ra BETWEEN {r0:.6f} AND {r1:.6f} AND dec BETWEEN {d0:.6f} AND {d1:.6f}")
            for k in range(4):
                try:
                    r = requests.post('https://gea.esac.esa.int/tap-server/tap/sync',
                                      data=dict(REQUEST='doQuery', LANG='ADQL', FORMAT='csv', QUERY=q), timeout=600)
                    r.raise_for_status(); break
                except Exception:
                    time.sleep(15)
            else:
                raise RuntimeError('Gaia 조회 실패')
            a_ = np.genfromtxt(io.StringIO(r.text), delimiter=',', skip_header=1, filling_values=np.nan).reshape(-1, 4)
            if len(a_) >= 49999 and depth < 5:
                rm, dm = (r0 + r1) / 2, (d0 + d1) / 2
                return np.vstack([cell(x0, x1, y0, y1, depth + 1) for x0, x1 in ((r0, rm), (rm, r1)) for y0, y1 in ((d0, dm), (dm, d1))])
            return a_
        cosd = max(np.cos(np.radians(min(abs(dec) + radius, 89))), 0.05)
        dr = radius / cosd
        nr = max(1, int(np.ceil(2 * dr / 0.5))); nd = max(1, int(np.ceil(2 * radius / 0.5)))
        rs = np.linspace(ra - dr, ra + dr, nr + 1); ds = np.linspace(dec - radius, dec + radius, nd + 1)
        parts = [cell(rs[i], rs[i + 1], ds[j], ds[j + 1]) for i in range(nr) for j in range(nd)]
        a = np.vstack(parts)
        sep_ = SkyCoord(a[:, 0] * u.deg, a[:, 1] * u.deg).separation(SkyCoord(ra * u.deg, dec * u.deg)).deg
        a = a[sep_ < radius]
        np.savez(fn, ra=a[:, 0], dec=a[:, 1], g=a[:, 2], bprp=a[:, 3])
        return a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    import requests
    q = (f"SELECT ra, dec, phot_g_mean_mag, bp_rp FROM gaiadr3.gaia_source WHERE phot_g_mean_mag < {gmax} "
         f"AND CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra:.5f}, {dec:.5f}, {radius:.4f})) = 1")
    for k in range(4):
        try:
            r = requests.post('https://gea.esac.esa.int/tap-server/tap/sync',
                              data=dict(REQUEST='doQuery', LANG='ADQL', FORMAT='csv', QUERY=q), timeout=300)
            r.raise_for_status(); break
        except Exception:
            time.sleep(10)
    else:
        raise RuntimeError('Gaia 조회 실패')
    a = np.genfromtxt(io.StringIO(r.text), delimiter=',', skip_header=1, filling_values=np.nan)
    a = a.reshape(-1, 4)
    np.savez(fn, ra=a[:, 0], dec=a[:, 1], g=a[:, 2], bprp=a[:, 3])
    return a[:, 0], a[:, 1], a[:, 2], a[:, 3]

def detect(img, thresh=5.0, minarea=5):
    import sep
    img = np.ascontiguousarray(img, dtype=np.float32)
    bkg = sep.Background(img, bw=128, bh=128)
    sub = img - bkg.back()
    sep.set_extract_pixstack(3_000_000); sep.set_sub_object_limit(4096)
    obj = sep.extract(sub, thresh, err=bkg.globalrms, minarea=minarea)
    return obj, sub, bkg

def check_wcs(img, h, gmax=15.5):
    """스택 WCS로 Gaia 별을 투영해 검출 별과 맞춤 → (WCS, 중앙 오차 px, 일치 수). 필요하면 이동 보정."""
    w = WCS(h, naxis=2)
    ny, nx = img.shape
    c = w.pixel_to_world(nx / 2, ny / 2)
    rad = float(np.hypot(nx, ny) / 2 * np.sqrt(abs(np.linalg.det(w.pixel_scale_matrix)))) * 1.05
    gra, gde, gg, _ = gaia(c.ra.deg, c.dec.deg, rad, gmax)
    obj, _, _ = detect(img, 10)
    obj = obj[(obj['flag'] == 0)]
    gx, gy = w.all_world2pix(gra, gde, 0, quiet=True)
    from scipy.spatial import cKDTree
    t = cKDTree(np.c_[obj['x'], obj['y']])
    dd, ii = t.query(np.c_[gx, gy], distance_upper_bound=15)
    ok = np.isfinite(dd)
    if ok.sum() < 10:
        return w, np.nan, int(ok.sum())
    dx = np.median(obj['x'][ii[ok]] - gx[ok]); dy = np.median(obj['y'][ii[ok]] - gy[ok])
    if np.hypot(dx, dy) > 0.5:   # 평행 이동 보정
        w.wcs.crpix = w.wcs.crpix + [dx, dy]
        gx, gy = w.all_world2pix(gra, gde, 0, quiet=True)
        dd, ii = t.query(np.c_[gx, gy], distance_upper_bound=6); ok = np.isfinite(dd)
    return w, float(np.median(dd[ok])), int(ok.sum())

def skybot(ra, dec, mjd, rad_deg):
    from astroquery.imcce import Skybot
    from astropy.time import Time
    key = hashlib.md5(f'{ra:.3f}{dec:.3f}{mjd:.4f}{rad_deg:.2f}'.encode()).hexdigest()
    fn = os.path.join(CACHE, f'skybot_{key}.json')
    if os.path.exists(fn):
        return json.load(open(fn))
    rows = []
    for attempt in range(3):
        try:
            r = Skybot.cone_search(SkyCoord(ra * u.deg, dec * u.deg), rad_deg * u.deg, Time(mjd, format='mjd'), location='500', cache=False)
            for x in r:
                rows.append(dict(name=str(x['Name']), number=str(x['Number']), type=str(x['Type']),
                                 ra=float(x['RA'].to(u.deg).value), dec=float(x['DEC'].to(u.deg).value),
                                 V=float(x['V'].value if hasattr(x['V'], 'value') else x['V']),
                                 dra=float(x['RA_rate'].to(u.arcsec / u.hour).value),
                                 ddec=float(x['DEC_rate'].to(u.arcsec / u.hour).value)))
            break
        except RuntimeError as e:
            if 'No solar system object' in str(e):
                break
            time.sleep(3)
        except Exception:
            time.sleep(3)
    else:
        return None
    json.dump(rows, open(fn, 'w'))
    return rows
