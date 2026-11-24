"""단독 후보 강제측광: 다른 세션 같은 하늘 위치 구경 측광, 주변 별로 세션 간 밝기비 보정 → 실제로 없는지 판정."""
import sys as _s, os as _o; _s.path.insert(0, _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))); import cfg
import os, json, numpy as np, collections
from scipy.spatial import cKDTree
import transient as T, common as C
R = os.path.join(C.HERE, 'results', 'transient')
cache = {}
def get(sid):
    if sid not in cache:
        if len(cache) > 3: cache.pop(next(iter(cache)))
        d, h, info = C.load_stack(sid); k = T.load_cat(sid)
        cache[sid] = (C.lum(d), k['wcs'], k)
    return cache[sid]
def phot(sid, ra, dec, r_as=4.0):
    Lm, w, k = get(sid)
    x, y = w.all_world2pix(np.atleast_1d(ra), np.atleast_1d(dec), 0, quiet=True)
    r = r_as / k['scale']; out = []
    for xi, yi in zip(x, y):
        xi, yi = float(xi), float(yi); R2 = int(r * 4) + 2
        y0, x0 = int(yi) - R2, int(xi) - R2
        if y0 < 0 or x0 < 0 or y0 + 2 * R2 + 1 > Lm.shape[0] or x0 + 2 * R2 + 1 > Lm.shape[1]:
            out.append((np.nan, np.nan)); continue
        a = Lm[y0:y0 + 2 * R2 + 1, x0:x0 + 2 * R2 + 1]
        yy, xx = np.mgrid[y0:y0 + 2 * R2 + 1, x0:x0 + 2 * R2 + 1]
        dd = np.hypot(xx - xi, yy - yi)
        ann = a[(dd > 2 * r) & (dd < 3.5 * r)]
        bg = np.median(ann); sg = 1.4826 * np.median(np.abs(ann - bg))
        ap = dd <= r
        out.append((float((a[ap] - bg).sum()), float(sg * np.sqrt(ap.sum()))))
    return np.array(out)
def main():
    ok = json.load(open(os.path.join(R, 'only_ok.json'), encoding='utf-8'))
    res = []
    for o in ok:
        Lm, w, k = get(o['sid'])
        good = (k['snr'] > 30) & (k['snr'] < 500) & (k['gaia_d'] < 1.5) & (k['flag'] < 4)
        sep = np.hypot((k['ra'][good] - o['ra']) * np.cos(np.radians(o['dec'])), k['dec'][good] - o['dec'])
        nb = np.argsort(sep)[:25]
        rr, dd = k['ra'][good][nb], k['dec'][good][nb]
        f_this = phot(o['sid'], o['ra'], o['dec'])[0]
        ref_this = phot(o['sid'], rr, dd)
        verdict = []
        for x in o['others']:
            ref_o = phot(x['sid'], rr, dd)
            m = np.isfinite(ref_this[:, 0]) & np.isfinite(ref_o[:, 0]) & (ref_this[:, 0] > 0)
            if m.sum() < 5:
                verdict.append(dict(sid=x['sid'], state='nocal')); continue
            kk = float(np.median(ref_o[m, 0] / ref_this[m, 0]))
            fo, so = phot(x['sid'], o['ra'], o['dec'])[0]
            exp = kk * f_this[0]
            verdict.append(dict(sid=x['sid'], ratio=float(fo / exp) if exp > 0 else np.nan, exp_snr=float(exp / so) if so > 0 else np.nan, obs_snr=float(fo / so) if so > 0 else np.nan))
        o['forced'] = verdict
        st = [v for v in verdict if 'ratio' in v and v['exp_snr'] > 8]
        o['absent'] = bool(st) and all(v['ratio'] < 0.25 for v in st)
        o['present'] = any(v['ratio'] > 0.5 for v in st)
        res.append(o)
    json.dump(res, open(os.path.join(R, 'only_forced.json'), 'w'), ensure_ascii=False, indent=0)
    ab = [o for o in res if o['absent']]
    print('강제측광: 다른 세션에도 있음', sum(o['present'] for o in res), '/ 확실히 없음', len(ab), '/ 판정불가', len(res) - len(ab) - sum(o['present'] for o in res))
    print(collections.Counter(o['target'] for o in ab).most_common())
    for i, o in enumerate(res):
        if o['absent']:
            print(i, o['target'], o['sid'][:10], f"{o['ra']:.4f} {o['dec']:+.4f} m={o['mag']:.1f} snr={o['snr']:.0f}", [(v['sid'][:10], round(v['ratio'], 2), round(v['exp_snr'])) for v in o['forced'] if 'ratio' in v])


if __name__ == "__main__":
    main()
