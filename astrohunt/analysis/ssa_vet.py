"""유의 후보 눈 검사용 그림: [정지 하늘 | 속도로 맞춘 잔차 합 | 시간 4등분 잔차(정지 좌표)]"""
import sys as _s, os as _o; _s.path.insert(0, _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))); import cfg
import json, os, sys, numpy as np
from datetime import datetime, timezone
from PIL import Image
import ssa_post as P
sig = json.load(open(os.path.join(P.RES, '..', 'ssa_significant.json')))
OUT = os.path.join(P.RES, '..', 'ssa_vet'); os.makedirs(OUT, exist_ok=True)
H = 24
def norm(a, lo=None, hi=None):
    m = np.median(a); s = 1.4826 * np.median(np.abs(a - m)) + 1e-6
    b = np.arcsinh(np.clip((a - m) / s, -3, 15)); b = (255 * (b - b.min()) / (np.ptp(b) + 1e-9)).astype(np.uint8)
    return np.kron(b, np.ones((4, 4), np.uint8))
cache = {}
rows = []
for j, c in enumerate(sig):
    sid = c['sid']
    if os.path.exists(os.path.join(OUT, f"{sid[:30]}_c{c['chunk']}_{int(c['x'])}_{int(c['y'])}.png")) or not os.path.exists(os.path.join(P.SSA_IN, sid + '.npz')):
        continue   # 이미 만든 그림, 또는 임시 파일이 지워진 예전 세션
    if sid not in cache:
        cache.clear()
        z = np.load(os.path.join(P.SSA_IN, sid + '.npz'))
        t = np.array([datetime.fromisoformat(s[:26]).replace(tzinfo=timezone.utc).timestamp() / 3600 for s in z['dateobs']]) + z['exptime'] / 7200
        cache[sid] = (z['cube'], t, json.load(open(os.path.join(P.SSA_OUT, sid + '.json'))))
    cube, t, res = cache[sid]
    ch = res['chunks'][c['chunk']]; fr = np.array(sorted(ch['frames'], key=lambda f: t[f]))
    tt = t[fr] - t[fr].mean()
    x0, y0 = int(round(c['x'])), int(round(c['y']))
    R = int(H + abs(c['vx']) * np.abs(tt).max() + abs(c['vy']) * np.abs(tt).max() + 2)
    ys, xs = slice(max(y0 - R, 0), y0 + R + 1), slice(max(x0 - R, 0), x0 + R + 1)
    st = np.stack([np.nan_to_num(cube[i][ys, xs].astype(np.float32), posinf=6e4) for i in fr])
    st -= np.median(st.reshape(len(fr), -1), 1)[:, None, None]
    stat = np.median(st, 0); res_ = st - stat
    oy, ox = y0 - ys.start, x0 - xs.start
    acc = np.zeros((2 * H + 1, 2 * H + 1), np.float32)
    for k in range(len(fr)):
        yi, xi = int(round(oy + c['vy'] * tt[k])), int(round(ox + c['vx'] * tt[k]))
        a = res_[k, yi - H:yi + H + 1, xi - H:xi + H + 1]
        if a.shape == acc.shape: acc += a
    cs = lambda a: a[oy - H:oy + H + 1, ox - H:ox + H + 1]
    q = np.array_split(np.arange(len(fr)), 4)
    try:
        tiles = [norm(cs(stat)), norm(acc)] + [norm(cs(res_[qq].sum(0))) for qq in q]
    except ValueError:
        print(j, 'edge skip'); continue
    if any(tl.shape != tiles[0].shape for tl in tiles):
        continue
    sep = np.full((tiles[0].shape[0], 6), 128, np.uint8)
    img = np.hstack(sum([[tl, sep] for tl in tiles], [])[:-1])
    fn = os.path.join(OUT, f"{sid[:30]}_c{c['chunk']}_{int(c['x'])}_{int(c['y'])}.png"); Image.fromarray(img).save(fn)
    print(j, fn, flush=True)
