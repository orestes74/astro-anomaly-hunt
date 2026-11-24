"""shift-and-stack 후보 해석: WCS로 좌표 변환 → SkyBoT 알려진 천체와 대조 → 구간 간 연결 → 분류, 확인용 컷아웃.
사용법: python ssa_post.py <세션ID> [...]   (C:\\stackwork\\ssa_out\\<세션>.json, C:\\stackwork\\ssa\\<세션>.npz 필요)"""
import sys as _s, os as _o; _s.path.insert(0, _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))); import cfg
import os, sys, json, numpy as np, warnings
from datetime import datetime, timezone
from astropy.time import Time
from PIL import Image
import common as C
warnings.filterwarnings('ignore')
SSA_IN = cfg.SSA_IN; SSA_OUT = cfg.SSA_OUT
RES = os.path.join(C.HERE, 'results', 'ssa'); os.makedirs(RES, exist_ok=True)
B = 3   # 비닝

def b2f(x, y):  # 비닝 좌표 → 원본(0 기준) 픽셀
    return B * x + (B - 1) / 2, B * y + (B - 1) / 2

def cutout_ssa(cube, t, frames, x, y, vx, vy, half=20):
    """해당 속도로 맞춘 합 컷아웃과 정지 합(별 기준) 컷아웃"""
    tt = t[frames] - t[frames].mean()
    acc = np.zeros((2 * half + 1, 2 * half + 1), np.float32); sta = np.zeros_like(acc)
    for k, i in enumerate(frames):
        f = cube[i].astype(np.float32)
        xi, yi = int(round(x + vx * tt[k])), int(round(y + vy * tt[k]))
        a = f[max(yi - half, 0):yi + half + 1, max(xi - half, 0):xi + half + 1]
        if a.shape == acc.shape: acc += a - np.median(f)
        s = f[y - half:y + half + 1, x - half:x + half + 1]
        if s.shape == sta.shape: sta += s - np.median(f)
    return acc, sta

def to_png(arrs, path, scale=4):
    tiles = []
    for a in arrs:
        m, s = np.median(a), 1.4826 * np.median(np.abs(a - np.median(a))) + 1e-6
        b = np.clip((a - m) / s, -2, 12); b = np.arcsinh(b) ; b = (255 * (b - b.min()) / (b.max() - b.min() + 1e-9)).astype(np.uint8)
        tiles.append(np.kron(b, np.ones((scale, scale), np.uint8))); tiles.append(np.full((b.shape[0] * scale, 6), 128, np.uint8))
    Image.fromarray(np.hstack(tiles[:-1])).save(path)

def process(sid):
    res = json.load(open(os.path.join(SSA_OUT, sid + '.json')))
    d, h, info = C.load_stack(sid)
    w, err, nm = C.check_wcs(C.lum(d), h)
    z = np.load(os.path.join(SSA_IN, sid + '.npz')); cube = np.nan_to_num(z['cube'], nan=0, posinf=65504, neginf=0)
    t = np.array([datetime.fromisoformat(s[:26]).replace(tzinfo=timezone.utc).timestamp() / 3600 for s in z['dateobs']]) + z['exptime'] / 7200
    scale = res['scale_binned']
    ny, nx = d.shape[-2:]
    cen = w.pixel_to_world(nx / 2, ny / 2)
    rad = float(np.hypot(nx, ny) / 2 * scale / B / 3600)
    out = dict(sid=sid, wcs_err_px=err, chunks=[], known_in_field=[])
    allc = []
    for ch in res['chunks']:
        mjd = Time(datetime.fromtimestamp(ch['t_ref_unix_h'] * 3600, tz=timezone.utc)).mjd
        kn = C.skybot(cen.ra.deg, cen.dec.deg, mjd, rad) or []
        known = []
        for k in kn:
            cosd = np.cos(np.radians(k['dec']))
            ra1 = k['ra'] + k['dra'] / 3600 / cosd; de1 = k['dec'] + k['ddec'] / 3600   # 1시간 뒤
            X, Y = w.all_world2pix([k['ra'], ra1], [k['dec'], de1], 0, quiet=True)
            x, y = (X[0] - 1) / B, (Y[0] - 1) / B
            if 15 < x < res['W'] - 15 and 15 < y < res['H'] - 15:
                known.append(dict(name=(k['number'] + ' ' + k['name']).strip('- '), V=k['V'], x=x, y=y,
                                  vx=(X[1] - X[0]) / B, vy=(Y[1] - Y[0]) / B, detected=False, snr=None))
        mp = os.path.join(SSA_OUT, f"{sid}_c{ch['i']}_max.npz")
        best = np.load(mp)['best'].astype(np.float32) if os.path.exists(mp) else None
        for k in known:   # 강제 측정: 예상 위치 ±3px 안의 최대 S/N (속도 무관)
            xi, yi = int(round(k['x'])), int(round(k['y']))
            k['forced_snr'] = float(best[max(yi - 3, 0):yi + 4, max(xi - 3, 0):xi + 4].max()) if best is not None else None
        for c in ch['cands']:
            c['chunk'] = ch['i']; c['T_h'] = ch['T_h']; c['mjd'] = mjd
            ok_split = min(c['snr_first'], c['snr_second'], c['snr_even'], c['snr_odd']) >= 0.35 * c['snr']
            c['split_ok'] = bool(ok_split)
            c['known'] = None
            for k in known:
                if np.hypot(c['x'] - k['x'], c['y'] - k['y']) < 8 and np.hypot(c['vx'] - k['vx'], c['vy'] - k['vy']) < max(3 * ch['step_px_h'], 0.3 * np.hypot(k['vx'], k['vy'])):
                    c['known'] = k['name']
                    if not k['detected'] or c['snr'] > (k['snr'] or 0):
                        k['detected'] = True; k['snr'] = c['snr']
            allc.append(c)
        out['chunks'].append(dict(i=ch['i'], n=ch['n'], T_h=ch['T_h'], mjd=mjd, nv=ch['nv'], masked=ch['masked_frac'], known=known))
    # 구간 간 연결 (알려지지 않은 후보, S/N ≥ 5.5, 반반 검증 통과)
    unk = [c for c in allc if c['known'] is None and c['split_ok']]
    for c in unk:
        c['links'] = []
    for i, a in enumerate(unk):
        for b in unk[i + 1:]:
            if a['chunk'] == b['chunk']:
                continue
            dt = (b['mjd'] - a['mjd']) * 24
            px, py = a['x'] + a['vx'] * dt, a['y'] + a['vy'] * dt
            vtol = max(1.5, 0.25 * np.hypot(a['vx'], a['vy']))
            if np.hypot(px - b['x'], py - b['y']) < 5 + 0.5 * abs(dt) and np.hypot(a['vx'] - b['vx'], a['vy'] - b['vy']) < vtol:
                a['links'].append(b['chunk']); b['links'].append(a['chunk'])
    nchunks = len(res['chunks'])
    for c in allc:
        if c['known']:
            c['cls'] = 'known'
        elif not c['split_ok'] or c.get('static_sn', 0) > 3:
            c['cls'] = 'artifact'
        elif c.get('links'):
            c['cls'] = 'linked'            # 여러 구간에서 같은 경로 → 강한 후보
        elif c['snr'] >= 8.0 and nchunks == 1:
            c['cls'] = 'single_strong'     # 구간 1개뿐인 세션의 강한 후보 → 눈으로 확인
        else:
            c['cls'] = 'weak'
    # 컷아웃 (linked / single_strong / known 상위)
    rev = [c for c in allc if c['cls'] in ('linked', 'single_strong')] + sorted([c for c in allc if c['cls'] == 'known'], key=lambda c: -c['snr'])[:3]
    for j, c in enumerate(rev[:40]):
        ch = res['chunks'][c['chunk']]
        frames = [res['chunks'][c['chunk']]['frames'].index(f) if False else f for f in ch['frames']]
        idx = [list(np.argsort(t)).index(f) if False else f for f in frames]
        acc, sta = cutout_ssa(cube, t, np.array(sorted(ch['frames'], key=lambda f: t[f])), c['x'], c['y'], c['vx'], c['vy'])
        X, Y = b2f(c['x'], c['y']); sky = w.pixel_to_world(X, Y)
        c['ra'], c['dec'] = float(sky.ra.deg), float(sky.dec.deg)
        c['png'] = os.path.join(RES, f"{sid}_{c['cls']}_{j:02d}.png")
        to_png([acc, sta], c['png'])
    for c in allc:
        if 'ra' not in c:
            X, Y = b2f(c['x'], c['y']); sky = w.pixel_to_world(X, Y); c['ra'], c['dec'] = float(sky.ra.deg), float(sky.dec.deg)
        c['rate_arcsec_min'] = float(np.hypot(c['vx'], c['vy']) * scale / 60)
    out['cands'] = allc
    json.dump(out, open(os.path.join(RES, sid + '.json'), 'w'), ensure_ascii=False, indent=0)
    from collections import Counter
    cnt = Counter(c['cls'] for c in allc)
    kn_all = {k['name']: k for ch in out['chunks'] for k in ch['known']}
    det = {n: any(k2['detected'] for ch in out['chunks'] for k2 in ch['known'] if k2['name'] == n) for n in kn_all}
    print(f"{sid}: WCS {err:.1f}px, 구간 {nchunks}, 분류 {dict(cnt)}")
    for n, k in sorted(kn_all.items(), key=lambda a: a[1]['V']):
        if k['V'] < 20.5:
            fs = max([k2.get('forced_snr') or 0 for ch in out['chunks'] for k2 in ch['known'] if k2['name'] == n])
            print(f"   알려진 {n:28s} V={k['V']:5.2f}  {'검출' if det[n] else '-':4s} 예상위치 S/N {fs:5.1f}")
    return out

if __name__ == '__main__':
    for s in sys.argv[1:]:
        process(s)
