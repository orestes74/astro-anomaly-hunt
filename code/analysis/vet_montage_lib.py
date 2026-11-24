"""국소 좌표 양호한 단독 후보 잘라보기: [이 세션 | 다른 세션들] 한 줄씩."""
import os, json, numpy as np
from PIL import Image, ImageDraw
import transient as T, common as C
R = os.path.join(C.HERE, 'results', 'transient')
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
