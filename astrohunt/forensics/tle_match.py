"""M51 0019 섬광 A/B를 2026-04-16~17 TLE와 대조.
노출 시간(300초) 동안 모든 위성을 0.5초 간격으로 전파해 화면 안을 지나간 것, 섬광 위치에 가장 가까이 온 것, 햇빛을 받았는지를 계산."""
import sys, numpy as np
from collections import defaultdict
from astropy.io import fits
from astropy.wcs import WCS
from astropy.time import Time
from astropy.coordinates import get_sun, GCRS
import astropy.units as u
from skyfield.api import load, wgs84, EarthSatellite

F = r'h:/asiair/Autorun/Light/M 51/Light_M 51_300.0s_Bin1_20260418-030615_16deg_0019.fit'
TLE = r'tle/tle_20260417.txt'
FLASH = {'A': (1730.2, 1659.2), 'B': (1328.1, 1242.1)}
RE = 6371.0

h = fits.getheader(F); w = WCS(h)
NX, NY = h['NAXIS1'], h['NAXIS2']
t0 = Time(h['DATE-OBS'], scale='utc'); exp = h['EXPTIME']
ts = load.timescale()
secs = np.arange(-10, exp + 10.01, 0.5)
tt = ts.from_astropy(t0 + secs * u.s)
site = wgs84.latlon(h['SITELAT'], h['SITELONG'], elevation_m=50)

# 태양 방향 (GCRS, 노출 중간) — 5분 동안 변화 무시
sun = get_sun(t0 + exp / 2 * u.s).transform_to(GCRS(obstime=t0 + exp / 2 * u.s)).cartesian.xyz.value
s_hat = sun / np.linalg.norm(sun)

# TLE 읽기: 위성 번호별로 노출 시각에 가장 가까운 epoch 하나
lines = open(TLE, encoding='utf-8', errors='replace').read().splitlines()
best = {}
tmid = (t0 + exp / 2 * u.s).jd
for i in range(0, len(lines) - 2, 3):
    n, l1, l2 = lines[i], lines[i + 1], lines[i + 2]
    if not (l1.startswith('1 ') and l2.startswith('2 ')):
        continue
    num = l1[2:7].strip().lstrip('0')
    yy, doy = int(l1[18:20]), float(l1[20:32])
    ep = Time(f'20{yy:02d}:001:00:00:00', format='yday', scale='utc').jd + doy - 1
    d = abs(ep - tmid)
    if num not in best or d < best[num][0]:
        best[num] = (d, n[2:].strip() if n.startswith('0 ') else n.strip(), l1, l2)
print(f'TLE {len(lines)//3}개, 위성 {len(best)}개, 노출 시작 {t0.isot} UTC', flush=True)

rows = []
for k, (age, name, l1, l2) in enumerate(best.values()):
    try:
        sat = EarthSatellite(l1, l2, name, ts)
        topo = (sat - site).at(tt)
        ra, dec, dist = topo.radec()
        alt = topo.altaz()[0].degrees
    except Exception:
        continue
    if np.all(alt < 0) or np.any(~np.isfinite(dist.km)):
        continue
    ra_d, de_d = ra._degrees, dec.degrees
    c0r, c0d = np.radians(h['CRVAL1']), np.radians(h['CRVAL2'])
    sep = np.degrees(np.arccos(np.clip(np.sin(np.radians(de_d)) * np.sin(c0d) + np.cos(np.radians(de_d)) * np.cos(c0d) * np.cos(np.radians(ra_d) - c0r), -1, 1)))
    if not (sep < 3).any():
        continue
    x = np.full(len(secs), np.nan); y = np.full(len(secs), np.nan)
    ok = sep < 3
    x[ok], y[ok] = w.all_world2pix(ra_d[ok], de_d[ok], 0, quiet=True)
    inside = (x > 0) & (x < NX) & (y > 0) & (y < NY) & (secs >= 0) & (secs <= exp)
    near = (x > -NX) & (x < 2 * NX) & (y > -NY) & (y < 2 * NY)
    if not near.any():
        continue
    p = sat.at(tt).position.km.T  # GCRS
    along = p @ s_hat
    perp = np.linalg.norm(p - np.outer(along, s_hat), axis=1)
    lit = (along > 0) | (perp > RE)
    hgt = np.linalg.norm(p, axis=1) - RE
    r = dict(num=l1[2:7].strip(), name=name, age_d=age, inside=inside.any(),
             lit_inside=(inside & lit).any(), alt_km=float(np.median(hgt)), dist_km=float(np.median(dist.km)))
    for f, (fx, fy) in FLASH.items():
        dd = np.hypot(x - fx, y - fy); dd[(secs < 0) | (secs > exp) | ~np.isfinite(dd)] = np.inf
        j = int(np.argmin(dd))
        r[f'{f}_px'] = float(dd[j]); r[f'{f}_t'] = float(secs[j]); r[f'{f}_lit'] = bool(lit[j])
        r[f'{f}_rate'] = float(np.hypot(*(np.gradient(x)[j], np.gradient(y)[j])) / 0.5)  # px/s
    if inside.any():
        xi, yi = x[inside], y[inside]
        r['enter'] = (round(float(xi[0])), round(float(yi[0])), float(secs[inside][0]))
        r['exit'] = (round(float(xi[-1])), round(float(yi[-1])), float(secs[inside][-1]))
        r['angle'] = float(np.degrees(np.arctan2(yi[-1] - yi[0], xi[-1] - xi[0])))
    rows.append(r)
    if k % 2000 == 0:
        print(f'  {k}/{len(best)}', flush=True)

print('\n== 노출 중 화면 안을 지나간 위성 ==')
for r in sorted(rows, key=lambda r: r.get('enter', (0, 0, 1e9))[2]):
    if r['inside']:
        print(f"{r['num']:>6} {r['name'][:24]:24} 높이 {r['alt_km']:7.0f} km 거리 {r['dist_km']:7.0f} km  "
              f"햇빛 {'O' if r['lit_inside'] else 'X'}  진입 {r['enter']} 이탈 {r['exit']} 각도 {r['angle']:.1f}°  "
              f"A {r['A_px']:.0f}px B {r['B_px']:.0f}px  TLE나이 {r['age_d']:.2f}d")
for f in FLASH:
    print(f'\n== 섬광 {f}에 가장 가까이 온 위성 (노출 중) ==')
    for r in sorted(rows, key=lambda r: r[f'{f}_px'])[:12]:
        print(f"{r['num']:>6} {r['name'][:24]:24} {r[f'{f}_px']:8.0f} px  t=+{r[f'{f}_t']:5.1f}s  "
              f"햇빛 {'O' if r[f'{f}_lit'] else 'X'}  속도 {r[f'{f}_rate']:7.0f} px/s  높이 {r['alt_km']:7.0f} km  TLE나이 {r['age_d']:.2f}d")
