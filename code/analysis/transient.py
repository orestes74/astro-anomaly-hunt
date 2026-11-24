"""신성·초신성·변광성 탐색.
1단계(스택별): 검출 → 측광(Gaia G로 영점) → Gaia 대응 여부 → 카탈로그 저장
2단계(후보):  (a) Gaia에 없는 별 모양 점광원  (b) 같은 대상 다른 세션과 비교(새로 나타남/사라짐/밝기 변화)
              알려진 소행성(SkyBoT)·변광성(VSX) 대조, 같은 세션 앞/뒤 절반 프레임에도 있는지 확인
사용법: python transient.py catalog [세션...|--all]  /  python transient.py compare"""
import os, sys, json, glob, numpy as np, pandas as pd, warnings, requests
from astropy.coordinates import SkyCoord
from astropy.wcs import WCS
from astropy.time import Time
import astropy.units as u
from scipy.spatial import cKDTree
from PIL import Image
import sep, common as C
warnings.filterwarnings('ignore')
OUT = os.path.join(C.HERE, 'results', 'transient'); os.makedirs(OUT, exist_ok=True)
CAT = os.path.join(OUT, 'catalogs'); os.makedirs(CAT, exist_ok=True)
FIELDS = json.load(open(os.path.join(C.HERE, 'fields.json')))

def field_gaia(sid):
    for g in FIELDS:
        if sid in g['sids']:
            return C.gaia(round(g['ra'], 3), round(g['dec'], 3), round(g['rad'], 3), 20.8)
    raise KeyError(sid)

def catalog(sid):
    fn = os.path.join(CAT, sid + '.npz')
    if os.path.exists(fn):
        return
    d, h, info = C.load_stack(sid)
    img = np.ascontiguousarray(C.lum(d)); del d
    w, werr, nm = C.check_wcs(img, h)
    obj, sub, bkg = C.detect(img, 4.0, 5)
    rms = bkg.globalrms
    hlr, _ = sep.flux_radius(sub, obj['x'], obj['y'], 6 * obj['a'], 0.5, subpix=5)
    good = (obj['flag'] < 4) & (obj['peak'] < 0.8 * np.nanmax(img))
    fw = np.median(hlr[good & (obj['peak'] > 30 * rms) & (obj['peak'] < 0.3 * np.nanmax(img))]) * 2
    ra_ = 1.5 * fw
    flux, ferr, _ = sep.sum_circle(sub, obj['x'], obj['y'], ra_, err=rms, subpix=5)
    gra, gde, gg, gbr = field_gaia(sid)
    gx, gy = w.all_world2pix(gra, gde, 0, quiet=True)
    inside = (gx > -10) & (gx < img.shape[1] + 10) & (gy > -10) & (gy < img.shape[0] + 10)
    gx, gy, gg, gra, gde = gx[inside], gy[inside], gg[inside], gra[inside], gde[inside]
    tg = cKDTree(np.c_[gx, gy])
    scale = float(np.sqrt(abs(np.linalg.det(w.pixel_scale_matrix))) * 3600)
    rmatch = max(2.5, 3.0 / scale)
    dd, ii = tg.query(np.c_[obj['x'], obj['y']], distance_upper_bound=4.0 / scale + 2)
    has = np.isfinite(dd)
    snr = flux / np.maximum(ferr, 1e-6)
    m_inst = -2.5 * np.log10(np.clip(flux, 1e-6, None))
    zsel = has & (dd < rmatch) & good & (snr > 50) & (gg[np.minimum(ii, len(gg) - 1)] > 11) & (gg[np.minimum(ii, len(gg) - 1)] < 17)
    zp = np.median(gg[ii[zsel]] - m_inst[zsel]) if zsel.sum() > 20 else np.nan
    zps = 1.4826 * np.median(np.abs(gg[ii[zsel]] - m_inst[zsel] - zp)) if zsel.sum() > 20 else np.nan
    mag = m_inst + zp
    lim5 = zp - 2.5 * np.log10(5 * rms * np.sqrt(np.pi) * ra_)
    sky = w.pixel_to_world(obj['x'], obj['y'])
    # 밝은 별(G<10) 위치: 주변 헤일로·스파이크 제외용
    bright = np.c_[gx[gg < 10], gy[gg < 10]], gg[gg < 10]
    np.savez(fn, x=obj['x'], y=obj['y'], ra=sky.ra.deg, dec=sky.dec.deg, mag=mag, snr=snr, hlr=hlr, a=obj['a'], b=obj['b'],
             peak=obj['peak'], flag=obj['flag'], gaia_d=np.where(has, dd * scale, np.inf), gaia_g=np.where(has, gg[np.minimum(ii, len(gg) - 1)], np.nan),
             zp=zp, zp_sig=zps, lim5=lim5, fwhm=fw, scale=scale, wcs_err=werr, rms=rms, satur=float(np.nanmax(img)),
             bright_xy=bright[0], bright_g=bright[1], shape=np.array(img.shape),
             wcs_hdr=np.array(w.to_header(relax=True).tostring()))
    print(f'{sid}: 검출 {len(obj)}, Gaia 일치 {np.sum(has & (dd < rmatch))}, ZP {zp:.2f}±{zps:.2f}, 5σ 한계 {lim5:.2f}, FWHM {fw*scale:.1f}"', flush=True)

def load_cat(sid):
    z = np.load(os.path.join(CAT, sid + '.npz'))
    c = {k: z[k] for k in z.files}
    c['wcs'] = WCS(fits_header(str(c['wcs_hdr'])))
    return c

def fits_header(s):
    from astropy.io.fits import Header
    return Header.fromstring(s)

def vsx(ra, dec, rad_deg=0.003):
    try:
        r = requests.get('https://www.aavso.org/vsx/index.php', params=dict(view='api.list', ra=ra, dec=dec, radius=rad_deg, format='json'), timeout=60)
        js = r.json().get('VSXObjects', {})
        objs = js.get('VSXObject', []) if isinstance(js, dict) else []
        return [(o['Name'], o.get('VariabilityType', ''), o.get('MaxMag', ''), o.get('MinMag', '')) for o in objs]
    except Exception:
        return None

def cutout(sid, ra, dec, half=40):
    d, h, info = C.load_stack(sid)
    c = load_cat(sid); w = c['wcs']
    x, y = w.all_world2pix(ra, dec, 0); x, y = int(round(float(x))), int(round(float(y)))
    L = C.lum(d)
    a = L[max(y - half, 0):y + half + 1, max(x - half, 0):x + half + 1]
    if a.size == 0:
        return np.zeros((2 * half + 1, 2 * half + 1))
    m = np.median(a); s = 1.4826 * np.median(np.abs(a - m)) + 1e-6
    b = np.arcsinh(np.clip((a - m) / s, -3, 200) / 3)
    return (255 * (b - b.min()) / (b.max() - b.min() + 1e-9)).astype(np.uint8)[::-1]

def compare():
    sids = [os.path.basename(f)[:-4] for f in sorted(glob.glob(os.path.join(CAT, '*.npz')))]
    infos = {s: json.load(open(os.path.join(C.STACKS, s, 'info.json'), encoding='utf-8')) for s in sids}
    cats = {s: load_cat(s) for s in sids}
    cands = []
    for s in sids:
        c = cats[s]; info = infos[s]
        if not np.isfinite(c['zp']):
            continue
        H, W = c['shape']
        star = (c['snr'] > 30) & (c['flag'] < 4) & (c['gaia_d'] < 2.5 * c['scale'])
        hlr0 = np.median(c['hlr'][star]); el = c['a'] / np.maximum(c['b'], 1e-3)
        sel = ((c['gaia_d'] > 4.0) & (c['snr'] >= 10) & (c['mag'] < c['lim5'] - 0.5) & (c['flag'] < 4)
               & (c['hlr'] > 0.7 * hlr0) & (c['hlr'] < 1.5 * hlr0) & (el < 1.5) & (c['peak'] < 0.8 * c['satur'])
               & (c['x'] > 60) & (c['x'] < W - 60) & (c['y'] > 60) & (c['y'] < H - 60))
        if len(c['bright_g']):
            tb = cKDTree(c['bright_xy'])
            dd, ii = tb.query(np.c_[c['x'], c['y']])
            rad = (40 + 20 * np.clip(10 - c['bright_g'][np.minimum(ii, len(c['bright_g']) - 1)], 0, 10)) / c['scale']
            sel &= dd > rad
        for j in np.where(sel)[0]:
            cands.append(dict(sid=s, target=info['target'], ra=float(c['ra'][j]), dec=float(c['dec'][j]), mag=float(c['mag'][j]),
                              snr=float(c['snr'][j]), gaia_d=float(c['gaia_d'][j]), lim5=float(c['lim5']), kind='no_gaia'))
    print(f'Gaia에 없는 별 모양 점광원(1차): {len(cands)}개', flush=True)
    # 같은 대상 다른 세션에서 같은 자리 확인
    by_t = {}
    for s in sids:
        by_t.setdefault(infos[s]['target'], []).append(s)
    for cd in cands:
        others = []
        for s2 in by_t[cd['target']]:
            if s2 == cd['sid']:
                continue
            c2 = cats[s2]; w2 = c2['wcs']
            x2, y2 = w2.all_world2pix(cd['ra'], cd['dec'], 0, quiet=True)
            H2, W2 = c2['shape']
            if not (20 < x2 < W2 - 20 and 20 < y2 < H2 - 20):
                continue
            t2 = cKDTree(np.c_[c2['x'], c2['y']])
            dd, ii = t2.query([float(x2), float(y2)], distance_upper_bound=3.0 / c2['scale'] + 1.5)
            others.append(dict(sid=s2, lim5=float(c2['lim5']), found=bool(np.isfinite(dd)), mag=float(c2['mag'][ii]) if np.isfinite(dd) else None))
        cd['others'] = others
        deep = [o for o in others if o['lim5'] > cd['mag'] + 0.7]
        if deep and not any(o['found'] for o in deep):
            cd['kind'] = 'only_this_session'      # 다른 세션(충분히 깊은)에는 없음 → 일시 천체 후보
        elif any(o['found'] for o in others):
            cd['kind'] = 'persistent_no_gaia'     # 여러 세션에 꾸준히 있음 → 목록에 없는 고정 천체(은하 내 성단·HII 등)
    # 알려진 소행성 제외: 세션마다 시야 전체를 한 번 조회
    kn_by = {}
    for sid in {cd['sid'] for cd in cands if cd['kind'] != 'persistent_no_gaia'}:
        info = infos[sid]; c = cats[sid]; H, W = c['shape']
        t_mid = Time(pd.Timestamp(info['t_first']).tz_localize('Asia/Seoul').tz_convert('UTC').to_pydatetime()).mjd +                 (pd.Timestamp(info['t_last']) - pd.Timestamp(info['t_first'])).total_seconds() / 86400 / 2
        cen = c['wcs'].pixel_to_world(W / 2, H / 2)
        rad = float(np.hypot(W, H) / 2 * c['scale'] / 3600 * 1.05)
        kn_by[sid] = C.skybot(round(cen.ra.deg, 3), round(cen.dec.deg, 3), t_mid, rad) or []
    for cd in cands:
        kn = kn_by.get(cd['sid'], [])
        # 세션 동안 움직인 거리만큼 허용(스택에서는 궤적 중앙에 남음)
        cd['asteroid'] = [k['name'] for k in kn if np.hypot((k['ra'] - cd['ra']) * np.cos(np.radians(cd['dec'])), k['dec'] - cd['dec']) * 3600 < 15 + 0.5 * np.hypot(k['dra'], k['ddec']) * 2]
    # 변광성: 같은 대상 두 세션의 Gaia 일치 별 등급 비교
    var = []
    for t, ss in by_t.items():
        for i, a in enumerate(ss):
            for b in ss[i + 1:]:
                ca, cb = cats[a], cats[b]
                if not (np.isfinite(ca['zp']) and np.isfinite(cb['zp'])):
                    continue
                ma = (ca['gaia_d'] < 2.5 * ca['scale']) & (ca['snr'] > 20) & (ca['peak'] < 0.8 * ca['satur'])
                mb = (cb['gaia_d'] < 2.5 * cb['scale']) & (cb['snr'] > 20) & (cb['peak'] < 0.8 * cb['satur'])
                A = SkyCoord(ca['ra'][ma] * u.deg, ca['dec'][ma] * u.deg); Bc = SkyCoord(cb['ra'][mb] * u.deg, cb['dec'][mb] * u.deg)
                if len(A) < 50 or len(Bc) < 50:
                    continue
                idx, d2, _ = A.match_to_catalog_sky(Bc)
                ok = d2.arcsec < 2.5
                dm = cb['mag'][mb][idx[ok]] - ca['mag'][ma][ok]
                dm -= np.median(dm)
                err = np.hypot(1.0857 / ca['snr'][ma][ok], 1.0857 / cb['snr'][mb][idx[ok]])
                scat = 1.4826 * np.median(np.abs(dm))
                sig = np.abs(dm) / np.hypot(err, scat)
                for j in np.where((np.abs(dm) > 0.4) & (sig > 6))[0]:
                    var.append(dict(target=t, sid_a=a, sid_b=b, ra=float(ca['ra'][ma][ok][j]), dec=float(ca['dec'][ma][ok][j]),
                                    mag_a=float(ca['mag'][ma][ok][j]), mag_b=float(cb['mag'][mb][idx[ok]][j]), dmag=float(dm[j]), sig=float(sig[j])))
    print(f'세션 간 밝기 변화 별(|Δm|>0.4, >6σ): {len(var)}개', flush=True)
    # VSX 대조 (후보 + 변광 별)
    for cd in cands:
        if cd['kind'] == 'only_this_session' and not cd['asteroid']:
            cd['vsx'] = vsx(cd['ra'], cd['dec'])
    for v in var:
        v['vsx'] = vsx(v['ra'], v['dec'])
    json.dump(dict(cands=cands, variables=var), open(os.path.join(OUT, 'transient_candidates.json'), 'w'), ensure_ascii=False, indent=0)
    from collections import Counter
    print('후보 분류:', Counter(c['kind'] for c in cands), ' 소행성 일치', sum(bool(c['asteroid']) for c in cands))
    print('변광 별 중 VSX 등록:', sum(bool(v['vsx']) for v in var), '/', len(var))

if __name__ == '__main__':
    if sys.argv[1] == 'catalog':
        ids = [os.path.basename(p) for p in glob.glob(os.path.join(C.STACKS, '*')) if os.path.exists(os.path.join(p, 'info.json'))] if '--all' in sys.argv else sys.argv[2:]
        for s in ids:
            if '--cached' in sys.argv:
                import hashlib
                g = next((g for g in FIELDS if s in g['sids']), None)
                if g is None:
                    continue
                key = hashlib.md5(f"{round(g['ra'],3):.3f}{round(g['dec'],3):.3f}{round(g['rad'],3):.3f}{20.8}".encode()).hexdigest()
                if not os.path.exists(os.path.join(C.CACHE, f'gaia_{key}.npz')):
                    continue
            try:
                catalog(s)
            except Exception as e:
                print(f'{s}: 실패 {e}', flush=True)
    elif sys.argv[1] == 'compare':
        compare()
