"""먼지·가스층 비교: 스택(별 제거·비닝·평탄화) vs 전천 지도 (IRAS/IRIS 100µm, Planck 857GHz = 먼지, H-Alpha Comp = 가스).
같은 다항식 평탄화를 양쪽에 적용한 뒤 상관을 보고, 전천 지도로 설명되지 않는 구조(잔차 4σ 이상 덩어리)를 찾음.
사용법: python dustgas.py [세션...|--best]  (--best: 대상마다 가장 깊은 스택 1개)"""
import sys as _s, os as _o; _s.path.insert(0, _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))); import cfg
import os, sys, json, glob, hashlib, numpy as np, warnings
import astropy.units as u
from astropy.io import fits
from astropy.wcs import WCS
from scipy.ndimage import gaussian_filter, map_coordinates, binary_dilation, label
from PIL import Image
import common as C
warnings.filterwarnings('ignore')
OUT = os.path.join(C.HERE, 'results', 'dustgas'); os.makedirs(OUT, exist_ok=True)
BLK = 16
SURV = {'IRIS 100': 'dust_iris', 'Planck 857 I': 'dust_planck', 'H-Alpha Comp': 'halpha'}

def survey(ra, dec, wdeg, hdeg, name):
    key = hashlib.md5(f'{name}{ra:.3f}{dec:.3f}{wdeg:.2f}{hdeg:.2f}'.encode()).hexdigest()
    fn = os.path.join(C.CACHE, f'sv_{key}.fits')
    if not os.path.exists(fn):
        from astroquery.skyview import SkyView
        im = SkyView.get_images(position=f'{ra} {dec}', coordinates='J2000', survey=[name], pixels=200,
                                width=wdeg * u.deg, height=hdeg * u.deg)[0]
        im.writeto(fn, overwrite=True)
    with fits.open(fn) as hd:
        return hd[0].data.astype(np.float32), WCS(hd[0].header)

def poly_detrend(img, mask, deg=2):
    ny, nx = img.shape
    yy, xx = np.mgrid[0:ny, 0:nx] / np.array([ny, nx])[:, None, None]
    terms = [xx ** i * yy ** j for i in range(deg + 1) for j in range(deg + 1 - i)]
    A = np.stack([t[mask] for t in terms], 1)
    good = mask & np.isfinite(img)
    A = np.stack([t[good] for t in terms], 1); b = img[good]
    for _ in range(3):   # 시그마 클리핑
        coef, *_ = np.linalg.lstsq(A, b, rcond=None)
        r = b - A @ coef; s = 1.4826 * np.median(np.abs(r))
        k = np.abs(r) < 3 * s
        A, b = A[k], b[k]
    model = sum(c * t for c, t in zip(coef, terms))
    return img - model

def coarse(sid):
    """별 마스크 후 BLKxBLK 블록 중앙값 → (3, ny, nx), 비닝 WCS"""
    d, h, info = C.load_stack(sid)
    L = C.lum(d)
    w, err, nm = C.check_wcs(L, h)
    # 별만 가리기: 2x2 비닝 후 32px(≈80") 배경을 뺀 고역 영상에서 3σ 넘는 조밀한 광원 → 팽창. 넓은 성운은 남김.
    import sep
    H2, W2 = L.shape[0] // 2, L.shape[1] // 2
    L2 = np.ascontiguousarray(L[:H2 * 2, :W2 * 2].reshape(H2, 2, W2, 2).mean((1, 3)))
    bk = sep.Background(L2, bw=32, bh=32, fw=3, fh=3)
    hp = L2 - bk.back()
    s_ = 1.4826 * np.median(np.abs(hp - np.median(hp)))
    m2 = binary_dilation(hp > 3 * s_, iterations=3)
    gra, gde, gg, _ = C.gaia(*[round(v, 3) for v in (w.pixel_to_world(W2, H2).ra.deg, w.pixel_to_world(W2, H2).dec.deg)],
                             round(float(np.hypot(*L.shape) / 2 * np.sqrt(abs(np.linalg.det(w.pixel_scale_matrix)))) * 1.05, 3), 15.5)
    bx, by = w.all_world2pix(gra[gg < 9], gde[gg < 9], 0, quiet=True)
    yy2, xx2 = np.ogrid[0:H2, 0:W2]
    for x_, y_, g_ in zip(bx / 2, by / 2, gg[gg < 9]):
        r_ = 15 + 4 * (9 - g_) ** 1.8
        if -r_ < x_ < W2 + r_ and -r_ < y_ < H2 + r_:
            y0, y1, x0, x1 = int(max(y_ - r_, 0)), int(min(y_ + r_ + 1, H2)), int(max(x_ - r_, 0)), int(min(x_ + r_ + 1, W2))
            m2[y0:y1, x0:x1] |= (yy2[y0:y1] - y_) ** 2 + (xx2[:, x0:x1] - x_) ** 2 < r_ ** 2
    mask = np.repeat(np.repeat(m2, 2, 0), 2, 1)
    mask = np.pad(mask, ((0, L.shape[0] - mask.shape[0]), (0, L.shape[1] - mask.shape[1])), constant_values=True)
    ny, nx = L.shape[0] // BLK, L.shape[1] // BLK
    out = np.empty((3, ny, nx), np.float32)
    for c in range(3):
        a = d[c, :ny * BLK, :nx * BLK].copy(); a[mask[:ny * BLK, :nx * BLK]] = np.nan
        out[c] = np.nanmedian(a.reshape(ny, BLK, nx, BLK).transpose(0, 2, 1, 3).reshape(ny, nx, -1), axis=2)
    frac_masked = mask.mean()
    wb = w.deepcopy()
    wb.wcs.crpix = (w.wcs.crpix - 0.5) / BLK + 0.5
    if w.wcs.has_cd():
        wb.wcs.cd = w.wcs.cd * BLK
    else:
        wb.wcs.cdelt = w.wcs.cdelt * BLK
    wb.sip = None
    return out, wb, info, frac_masked, L.shape

def to_grid(img_s, w_s, wb, shape):
    ny, nx = shape
    yy, xx = np.mgrid[0:ny, 0:nx]
    sky = wb.pixel_to_world(xx.ravel(), yy.ravel())
    sx, sy = w_s.world_to_pixel(sky)
    return map_coordinates(img_s, [sy.reshape(shape), sx.reshape(shape)], order=1, mode='nearest')

def norm8(a, lo=1, hi=99):
    f = np.isfinite(a)
    p0, p1 = np.percentile(a[f], [lo, hi]) if f.any() else (0, 1)
    return (255 * np.clip((np.nan_to_num(a, nan=p0) - p0) / (p1 - p0 + 1e-9), 0, 1)).astype(np.uint8)[::-1]

def analyse(sid):
    rgb, wb, info, fm, shp = coarse(sid)
    ny, nx = rgb.shape[1:]
    pix = float(np.sqrt(abs(np.linalg.det(wb.pixel_scale_matrix))) * 60)   # 비닝 픽셀 크기(′)
    cen = wb.pixel_to_world(nx / 2, ny / 2)
    wdeg, hdeg = nx * pix / 60 * 1.15, ny * pix / 60 * 1.15
    lum = rgb.sum(0)
    valid = np.isfinite(lum)
    # Hα(빨강 초과): R - k·G, k는 화면 중앙값 비
    k = np.nanmedian(rgb[0]) / np.nanmedian(rgb[1])
    rex = rgb[0] - k * rgb[1]
    sm = 5.0 / pix / 2.355   # 5′ 해상도로 맞춤
    def prep(a):
        a = np.where(np.isfinite(a), a, np.nanmedian(a))
        a = gaussian_filter(a, sm)
        return poly_detrend(a, valid, 2)
    ours = dict(lum=prep(lum), rex=prep(rex))
    res = dict(sid=sid, target=info['target'], flat=info['flat'] != 'none', n=info['n_registered'], exptime=info['exptime'],
               pix_arcmin=pix, masked=float(fm))
    maps = {}
    for sname, key in SURV.items():
        try:
            s_img, s_w = survey(cen.ra.deg, cen.dec.deg, wdeg, hdeg, sname)
        except Exception as e:
            res[key] = f'fail {e}'; continue
        g = to_grid(s_img, s_w, wb, (ny, nx))
        g = poly_detrend(gaussian_filter(g, max(sm * 0.3, 0.5)), valid, 2)
        maps[key] = g
        o = ours['rex'] if key == 'halpha' else ours['lum']
        f = valid & np.isfinite(g)
        r = float(np.corrcoef(o[f], g[f])[0, 1])
        slope = float(np.polyfit(g[f], o[f], 1)[0])
        resid = o - slope * g
        rs = 1.4826 * np.median(np.abs(resid[f] - np.median(resid[f])))
        z = (resid - np.median(resid[f])) / rs
        blobs = []
        for sgn in (1, -1):
            lab, nl = label((sgn * z > 4) & f)
            for i in range(1, nl + 1):
                m = lab == i
                if m.sum() < 6:
                    continue
                yy, xx = np.nonzero(m)
                sky = wb.pixel_to_world(xx.mean(), yy.mean())
                blobs.append(dict(sign='+' if sgn > 0 else '-', ra=float(sky.ra.deg), dec=float(sky.dec.deg),
                                  area_arcmin2=float(m.sum() * pix ** 2), peak_sigma=float(np.abs(z[m]).max())))
        res[key] = dict(r=r, slope=slope, resid_sigma=float(rs), blobs=blobs)
        maps[key + '_z'] = z
    json.dump(res, open(os.path.join(OUT, sid + '.json'), 'w'), ensure_ascii=False, indent=0)
    # 그림: 위 = 우리 휘도 / IRIS / Planck / 먼지 잔차,  아래 = 우리 빨강초과 / Hα / Hα 잔차 / 컬러 미리보기
    blank = np.zeros((ny, nx), np.uint8)
    col = np.stack([norm8(prep(rgb[c])) for c in range(3)], -1)
    top = [norm8(ours['lum']), norm8(maps.get('dust_iris', np.zeros((ny, nx)))), norm8(maps.get('dust_planck', np.zeros((ny, nx)))),
           norm8(np.clip(maps.get('dust_iris_z', np.zeros((ny, nx))), -6, 6), 0, 100)]
    bot = [norm8(ours['rex']), norm8(maps.get('halpha', np.zeros((ny, nx)))), norm8(np.clip(maps.get('halpha_z', np.zeros((ny, nx))), -6, 6), 0, 100), blank]
    g8 = lambda a: np.stack([a] * 3, -1)
    row1 = np.hstack([g8(a) for a in top]); row2 = np.hstack([g8(a) for a in bot[:3]] + [col])
    Image.fromarray(np.vstack([row1, row2])).save(os.path.join(OUT, sid + '.png'))
    di, dp, ha = res.get('dust_iris'), res.get('dust_planck'), res.get('halpha')
    f = lambda x: f"r={x['r']:+.2f} 잔차덩어리 {len(x['blobs'])}" if isinstance(x, dict) else str(x)
    print(f"{sid}: 먼지(IRIS) {f(di)} | 먼지(Planck) {f(dp)} | Hα {f(ha)} | 플랫 {'O' if res['flat'] else 'X'}", flush=True)

if __name__ == '__main__':
    ids = sys.argv[1:]
    if '--best' in ids:
        infos = [json.load(open(p, encoding='utf-8')) for p in glob.glob(os.path.join(C.STACKS, '*', 'info.json'))]
        best = {}
        for i in infos:
            if i['flat'] == 'none':   # 플랫 없는 스택은 주변 감광 무늬 때문에 희미한 퍼진 빛 분석 불가
                continue
            sc = i['n_registered'] * i['exptime'] * (2 if i['flat'] != 'none' else 1)
            if i['target'] not in best or sc > best[i['target']][0]:
                best[i['target']] = (sc, i['sid'])
        ids = [v[1] for v in best.values()]
    for s in ids:
        if os.path.exists(os.path.join(OUT, s + '.json')):
            continue
        try:
            analyse(s)
        except Exception as e:
            import traceback; print(f'{s}: 실패 {e}', traceback.format_exc()[-400:], flush=True)
