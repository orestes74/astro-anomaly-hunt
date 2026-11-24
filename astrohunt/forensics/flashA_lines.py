"""섬광 A를 지나는 희미한 궤적 찾기: A를 지나는 모든 방향의 직선을 따라 밝기를 더해, 무작위 점에서 같은 계산을 한 분포와 비교.
검증: 같은 방법을 B에 적용해 희미한 궤적(수직)이 잡히는지 확인."""
import numpy as np
from astropy.io import fits
from scipy.ndimage import median_filter, map_coordinates

F = r'h:/asiair/Autorun/Light/M 51/Light_M 51_300.0s_Bin1_20260418-030615_16deg_0019.fit'
d = fits.getdata(F).astype(float); NY, NX = d.shape
b = d[:NY // 2 * 2, :NX // 2 * 2].reshape(NY // 2, 2, NX // 2, 2).sum((1, 3))   # 2x2 비닝 (Bayer 제거)
bg = median_filter(b, size=31)
r = b - bg
s = 1.4826 * np.median(np.abs(r - np.median(r)))
r[r > 5 * s] = 0          # 별·밝은 궤적 마스크 (희미한 궤적만 남김)
r[r < -5 * s] = 0
ANG = np.arange(0, 180, 0.25)
RAD = np.arange(-1400, 1400, 0.5)

def line_scores(x0, y0):
    out = []
    for a in ANG:
        t = np.radians(a)
        xs, ys = x0 + RAD * np.cos(t), y0 + RAD * np.sin(t)
        k = (np.abs(RAD) > 20) & (xs > 2) & (xs < b.shape[1] - 3) & (ys > 2) & (ys < b.shape[0] - 3)
        v = map_coordinates(r, [ys[k], xs[k]], order=1)
        out.append(v.mean() / s * np.sqrt(k.sum() / 2) if k.sum() > 400 else 0)   # 길이로 정규화한 유의도
    return np.array(out)

rng = np.random.default_rng(1)
rand = np.array([line_scores(*p) for p in zip(rng.uniform(300, b.shape[1] - 300, 40), rng.uniform(300, b.shape[0] - 300, 40))])
rmax = rand.max(1)
print(f'무작위 점 40개: 최대 유의도 중앙값 {np.median(rmax):.1f}, 90% {np.percentile(rmax, 90):.1f}, 최대 {rmax.max():.1f}')
for name, (x, y) in {'B (검증)': (1328.1, 1242.1), 'A': (1730.2, 1659.2)}.items():
    sc = line_scores(x / 2, y / 2)
    o = np.argsort(sc)[::-1]
    picks = []
    for i in o:
        if all(min(abs(ANG[i] - ANG[j]), 180 - abs(ANG[i] - ANG[j])) > 3 for j in picks):
            picks.append(i)
        if len(picks) == 4:
            break
    print(f'{name}: ' + ', '.join(f'{ANG[i]:.2f}° → {sc[i]:.1f}' for i in picks))
