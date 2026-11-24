"""국소 좌표 양호한 단독 후보 잘라보기: [이 세션 | 다른 세션들] 한 줄씩."""
import sys as _s, os as _o; _s.path.insert(0, _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))); import cfg
import os, json, numpy as np
from PIL import Image, ImageDraw
import transient as T, common as C
R = os.path.join(C.HERE, 'results', 'transient')
L = json.load(open(os.path.join(R, 'only_local.json'), encoding='utf-8'))
ok = sorted([o for o in L if o['loc_gaia_d'] < 1.5 and o['loc_frac4'] < 0.1], key=lambda o: (o['target'], -o['snr']))
cache = {}
def img(sid):
    if sid not in cache:
        if len(cache) > 3: cache.pop(next(iter(cache)))
        d, h, info = C.load_stack(sid); cache[sid] = (C.lum(d), T.load_cat(sid)['wcs'])
    return cache[sid]
def cut(sid, ra, dec, half=24, step=2.0):
    """북쪽 위·동쪽 왼쪽, 1px=step″ 하늘 격자로 재표본"""
    from scipy.ndimage import map_coordinates
    Lm, w = img(sid)
    yy, xx = np.mgrid[-half:half + 1, -half:half + 1] * step / 3600.0
    de = dec + yy; rr = ra - xx / np.cos(np.radians(dec))
    px, py = w.all_world2pix(rr.ravel(), de.ravel(), 0, quiet=True)
    a = map_coordinates(Lm, [py, px], order=1, mode='constant', cval=np.nan).reshape(yy.shape)
    f = np.isfinite(a); m = np.median(a[f]) if f.any() else 0; s = 1.4826 * np.median(np.abs(a[f] - m)) + 1e-6 if f.any() else 1
    b = np.arcsinh(np.clip((np.nan_to_num(a, nan=m) - m) / s, -3, 300) / 3)
    b = (255 * (b - b.min()) / (b.max() - b.min() + 1e-9)).astype(np.uint8)[::-1]
    return Image.fromarray(b).resize((98, 98), Image.NEAREST)
rows = []
for i, o in enumerate(ok):
    sids = [o['sid']] + [x['sid'] for x in o['others']][:3]
    row = Image.new('RGB', (110 + 100 * 4, 112), (40, 40, 40)); dr = ImageDraw.Draw(row)
    dr.text((2, 2), f"#{i} {o['target'][:10]}", fill=(255, 255, 0)); dr.text((2, 16), f"{o['sid'][:10]}", fill=(255, 255, 255))
    dr.text((2, 30), f"m={o['mag']:.1f} s={o['snr']:.0f}", fill=(255, 255, 255)); dr.text((2, 44), f"{o['ra']:.4f}", fill=(200, 200, 200)); dr.text((2, 58), f"{o['dec']:+.4f}", fill=(200, 200, 200))
    for k, s in enumerate(sids):
        row.paste(cut(s, o['ra'], o['dec']).convert('RGB'), (110 + 100 * k, 2))
        ImageDraw.Draw(row).text((112 + 100 * k, 100), s[:10] if k else 'THIS', fill=(0, 255, 0) if not k else (180, 180, 255))
    rows.append(row)
for p in range(0, len(rows), 24):
    pg = rows[p:p + 24]; W = Image.new('RGB', (2 * pg[0].width, 112 * ((len(pg) + 1) // 2)))
    for j, r in enumerate(pg):
        W.paste(r, ((j % 2) * r.width, 112 * (j // 2)))
    W.save(os.path.join(R, f'only_montage_{p // 24}.png'))
json.dump(ok, open(os.path.join(R, 'only_ok.json'), 'w'), ensure_ascii=False, indent=0)
print(len(ok), 'rows')
