"""M45 스택(2026-09-14, 30s x 116)을 반사 성운이 살아나도록 보정합니다. 원본은 읽기만 함.

1) 가장자리 자르기  2) 바깥쪽 하늘로 배경 기울기 제거  3) 어두운 배경 별들로 색 균형
4) 밝기(L)만 asinh로 늘리고, 색 비율(RGB/L)은 부드럽게 해서 채도를 올려 다시 입힘 (색이 빠지지 않음)
5) 약한 국소 대비, 노이즈 완화
실행: python m45.py [stretch] [sat]
"""
import os, sys
import numpy as np, cv2
from astropy.io import fits
from scipy.ndimage import gaussian_filter, maximum_filter
from PIL import Image

SRC = r'H:\ASIAIR\Stacks\2026-09-14_M_45_620mm_30s\linear.fit'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')
STRETCH = float(sys.argv[1]) if len(sys.argv) > 1 else 300
SAT = float(sys.argv[2]) if len(sys.argv) > 2 else 2.4
TAG = sys.argv[3] if len(sys.argv) > 3 else 'rich'

with fits.open(SRC, memmap=False) as h:
    d = h[0].data.astype(np.float32)
v = np.all(d != 0, axis=0)
rows = np.where(v.mean(1) > 0.995)[0]; cols = np.where(v.mean(0) > 0.995)[0]
d = d[:, rows[0] + 40:rows[-1] - 40, cols[0] + 40:cols[-1] - 40]
C, H, W = d.shape

# 2) 배경: 가장자리 고리 영역의 어두운 값으로 2차 다항식
ny, nx = 18, 27
ys = np.linspace(0, H, ny + 1).astype(int); xs = np.linspace(0, W, nx + 1).astype(int)
def design(x, y): return np.stack([x ** a * y ** b for a in range(3) for b in range(3 - a)], 1)
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); xx /= W; yy /= H
bg = []
for c in range(3):
    pts = []
    for i in range(ny):
        for j in range(nx):
            cx, cy = (xs[j] + xs[j + 1]) / 2 / W, (ys[i] + ys[i + 1]) / 2 / H
            if ((cx - .5) / .5) ** 2 + ((cy - .5) / .5) ** 2 < .55:   # 가운데(성운)는 빼기
                continue
            pts.append((cx, cy, np.percentile(d[c, ys[i]:ys[i + 1], xs[j]:xs[j + 1]], 20)))
    p = np.array(pts); keep = np.ones(len(p), bool)
    for _ in range(4):
        co, *_ = np.linalg.lstsq(design(p[keep, 0], p[keep, 1]), p[keep, 2], rcond=None)
        r = p[:, 2] - design(p[:, 0], p[:, 1]) @ co
        s = 1.4826 * np.median(np.abs(r[keep])) + 1e-9
        keep = np.abs(r) < 2.0 * s
    bg.append((design(xx.ravel(), yy.ravel()) @ co).reshape(H, W))
d = d - np.array(bg, np.float32)
del xx, yy, bg

# 3) 색 균형: 성운 밖의 어두운 배경 별(대부분 태양 비슷한 별) 평균을 흰색으로
L = d.mean(0)
noise = 1.4826 * np.median(np.abs(L[::7, ::7] - np.median(L[::7, ::7])))
pk = (L == maximum_filter(L, 9)) & (L > 30 * noise) & (L < 400 * noise)
yy0, xx0 = np.nonzero(pk)
sel = np.hypot((xx0 / W - .5) / .5, (yy0 / H - .5) / .5) > .6
flux = np.array([[d[c, y - 1:y + 2, x - 1:x + 2].sum() for c in range(3)] for y, x in zip(yy0[sel], xx0[sel]) if 2 < y < H - 3 and 2 < x < W - 3])
gain = np.median(flux[:, 1]) / np.median(flux, axis=0)
print('field-star gain', gain.round(3))

# 3b) Gaia 색 지수로 다시 맞추기 (PCC 방식): 태양형 별(BP-RP 0.82)이 하얗게 나오도록
import glob
from astropy.wcs import WCS
hdr = fits.getheader(SRC)
w = WCS(hdr, naxis=2)
cat = None
for f in glob.glob(r'C:\rasa_test\asteroid_hunt\analysis\cache\gaia_*.npz'):
    z_ = np.load(f)
    if len(z_['ra']) and abs(np.median(z_['ra']) - hdr['CRVAL1']) < 1.5 and abs(np.median(z_['dec']) - hdr['CRVAL2']) < 1.5:
        cat = z_ if cat is None else {k: np.concatenate([cat[k], z_[k]]) for k in ('ra', 'dec', 'g', 'bprp')}
if cat is not None:
    ok = (cat['g'] > 9.5) & (cat['g'] < 13.5) & np.isfinite(cat['bprp']) & (cat['bprp'] > .3) & (cat['bprp'] < 1.6)
    px, py = w.all_world2pix(cat['ra'][ok], cat['dec'][ok], 0)
    px -= cols[0] + 40; py -= rows[0] + 40; bprp = cat['bprp'][ok]
    yy_, xx_ = np.mgrid[-8:9, -8:9]; rr = np.hypot(xx_, yy_); ap = rr <= 4; ann = (rr >= 6) & (rr <= 8)
    rows_ = []
    for x, y, c_ in zip(px, py, bprp):
        xi, yi = int(round(x)), int(round(y))
        if 10 < xi < W - 10 and 10 < yi < H - 10:
            cut = d[:, yi - 8:yi + 9, xi - 8:xi + 9]
            f_ = np.array([(cut[k][ap] - np.median(cut[k][ann])).sum() for k in range(3)])
            if (f_ > 0).all() and cut.max() < 0.9 * d.max():
                rows_.append((c_, *f_))
    a = np.array(rows_)
    lr, lb = np.log(a[:, 1] / a[:, 2]), np.log(a[:, 3] / a[:, 2])          # R/G, B/G (로그) vs 색 지수
    keep = np.ones(len(a), bool)
    for _ in range(4):
        pr = np.polyfit(a[keep, 0], lr[keep], 1); pb = np.polyfit(a[keep, 0], lb[keep], 1)
        res = np.hypot(lr - np.polyval(pr, a[:, 0]), lb - np.polyval(pb, a[:, 0]))
        keep = res < 3 * 1.4826 * np.median(res[keep])
    sun = 0.82
    gain = np.array([np.exp(-np.polyval(pr, sun)), 1.0, np.exp(-np.polyval(pb, sun))])
    print('Gaia stars', int(keep.sum()), '/', len(a), 'gain', gain.round(3))
d *= gain[:, None, None]
sky = np.array([np.median(d[c, ::7, ::7]) for c in range(3)])
d -= sky[:, None, None]

# 4) 밝기와 색 분리
rgb = np.moveaxis(d, 0, -1); del d
L = rgb.mean(2)
noise = 1.4826 * np.median(np.abs(L[::7, ::7] - np.median(L[::7, ::7])))
Ls = L.copy()
det = L - gaussian_filter(L, 1.2)                                       # 배경 노이즈 완화(별·구조는 보호)
mix = .6 * (1 - np.clip(np.abs(det) / (4 * noise), 0, 1)) * (1 - np.clip(L / (40 * noise), 0, 1))
Ls = L * (1 - mix) + gaussian_filter(L, 1.2) * mix
white = float(np.percentile(Ls, 99.97))
black = -1.5 * noise
z = np.arcsinh(np.maximum(Ls - black, 0) / (white - black) * STRETCH) / np.arcsinh(STRETCH)
z = np.clip(z, 0, 1)
knee = .82; z = np.where(z <= knee, z, knee + (1 - knee) * (1 - np.exp(-(z - knee) / (1 - knee))))
# 약한 국소 대비 (성운 결)
z16 = np.uint16(np.clip(z, 0, 1) * 65535)
cl = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(8, 12)).apply(z16).astype(np.float32) / 65535
z = z * .7 + cl * .3

ratio = rgb / np.maximum(L, noise * 0.5)[..., None]
wgt = np.clip(L / (3 * noise), 0, 1)                                     # 신호 없는 곳은 무채색
ratio = 1 + (ratio - 1) * wgt[..., None]
ratio = np.stack([gaussian_filter(ratio[..., c], 2.5) for c in range(3)], 2)   # 색 노이즈 완화
ratio = 1 + (ratio - 1) * SAT
core = np.clip((z - .72) / .2, 0, 1) * .65                               # 밝은 별 중심은 색을 덜어 하얗게
ratio = 1 + (ratio - 1) * (1 - core)[..., None]
out = z[..., None] * ratio
m = out.max(2, keepdims=True)                                            # 넘치는 색은 밝기 유지하며 눌러 줌
out = np.where(m > 1, z[..., None] + (out - z[..., None]) * np.clip((1 - z[..., None]) / np.maximum(m - z[..., None], 1e-6), 0, 1), out)
out = np.clip(out, 0, 1)
GLOW = float(os.environ.get('GLOW', 0))
if GLOW:                                                                # 성운이 빛나 보이도록 번지는 빛(screen 합성)
    neb = out * (1 - np.clip((z - .6) / .3, 0, 1))[..., None]           # 별 중심은 빼고 성운만
    g = np.stack([gaussian_filter(neb[..., c], 18) + gaussian_filter(neb[..., c], 60) for c in range(3)], 2) * .5
    out = 1 - (1 - out) * (1 - np.clip(g * GLOW, 0, 1))
out = out[::-1]                                                          # FITS 아래→위

os.makedirs(OUT, exist_ok=True)
im = Image.fromarray(np.uint8(np.round(out * 255)))
im.save(os.path.join(OUT, f'M45_{TAG}.jpg'), quality=95)
im.thumbnail((1400, 1400)); im.save(os.path.join(OUT, f'M45_{TAG}_preview.jpg'), quality=90)
print('saved', TAG)
