"""기밀 위성 비공식 TLE(McCants classfd.tle, epoch 2026-11)로 M51 0019 대조.
epoch가 7개월 뒤라 궤도 위의 '위치'(언제 어디 있었는지)는 믿을 수 없습니다. 그러나 궤도면(J2 세차 포함)은 꽤 정확하므로,
노출 중 각 위성의 '궤도 고리'가 시야를 지나가는지, 지나간다면 방향·햇빛 여부가 사진 속 궤적과 맞는지 봅니다.
관측자도 노출 300초 동안 지구 자전으로 ~140 km 움직이므로(저궤도에서는 시차 수 도), 관측 시각을 10초 간격으로 훑습니다.
TLE 받는 법: python get_tle.py classified  (최신본만 공개되어 지난 날짜 판은 없음 → 위치가 아니라 궤도면만 비교)
사용법: python tle_plane.py [TLE 파일]"""
import sys
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.time import Time
from astropy.coordinates import get_sun, GCRS
import astropy.units as u
from skyfield.api import load, wgs84, EarthSatellite

F = r'h:/asiair/Autorun/Light/M 51/Light_M 51_300.0s_Bin1_20260418-030615_16deg_0019.fit'
TLE = sys.argv[1] if len(sys.argv) > 1 else r'tle/classfd/classfd.tle'
FLASH = {'A': (1730.2, 1659.2), 'B': (1328.1, 1242.1)}
RE = 6371.0

h = fits.getheader(F); w = WCS(h); NX, NY = h['NAXIS1'], h['NAXIS2']
c0r, c0d = np.radians(h['CRVAL1']), np.radians(h['CRVAL2'])
ts = load.timescale()
t0 = Time(h['DATE-OBS'], scale='utc'); EXP = h['EXPTIME']
tm = t0 + EXP / 2 * u.s
site = wgs84.latlon(h['SITELAT'], h['SITELONG'], elevation_m=50)
TOBS = np.arange(0, EXP + 0.1, 10)
OBS = site.at(ts.from_astropy(t0 + TOBS * u.s)).position.km.T
sun = get_sun(tm).transform_to(GCRS(obstime=tm)).cartesian.xyz.value; s_hat = sun / np.linalg.norm(sun)

L = [l.rstrip() for l in open(TLE, errors='replace')]
sats = []
for i, l in enumerate(L):
    if l.startswith('1 ') and i + 1 < len(L) and L[i + 1].startswith('2 '):
        name = L[i - 1].strip() if i > 0 and not L[i - 1].startswith(('1 ', '2 ')) else l[2:7]
        sats.append((name.removeprefix('0 '), l, L[i + 1]))
print(f'{TLE}: {len(sats)}개, 노출 {t0.isot} UTC + {EXP:.0f}초')

out, minsep_all = [], {}
for name, l1, l2 in sats:
    try:
        s = EarthSatellite(l1, l2, name, ts)
        P = 2 * np.pi / s.model.no_kozai   # 분
        if P > 200:   # 고궤도: 시야 근처에서 거의 정지 → 긴 궤적이 될 수 없음
            continue
        tau = np.arange(-P / 2, P / 2, 2 / 60)   # 궤도 한 바퀴, 2초 간격 (= 가능한 모든 위상)
        p = s.at(ts.from_astropy(tm + tau * u.min)).position.km.T
    except Exception:
        continue
    if not np.all(np.isfinite(p)):
        continue
    recs = []
    for to, obs in zip(TOBS, OBS):
        v = p - obs
        d = np.linalg.norm(v, axis=1)
        ra = np.arctan2(v[:, 1], v[:, 0]); de = np.arcsin(v[:, 2] / d)
        sep = np.degrees(np.arccos(np.clip(np.sin(de) * np.sin(c0d) + np.cos(de) * np.cos(c0d) * np.cos(ra - c0r), -1, 1)))
        minsep_all[name] = min(float(sep.min()), minsep_all.get(name, 999))
        k = np.where(sep < 3)[0]
        if len(k) < 2:
            continue
        x, y = w.all_world2pix(np.degrees(ra[k]) % 360, np.degrees(de[k]), 0, quiet=True)
        j = int(np.argmin(np.abs(y - NY / 2)))
        j1 = max(j - 1, 0); j2 = j1 + 1
        pj = p[k[j]]
        a = pj @ s_hat
        lit = bool(a > 0 or np.linalg.norm(pj - a * s_hat) > RE)
        recs.append(dict(t=to, minsep=float(sep.min()), x_mid=float(x[j]), lit=lit,
                         angle=float(np.degrees(np.arctan2(y[j2] - y[j1], x[j2] - x[j1]))),
                         hgt=float(np.linalg.norm(pj) - RE), dist=float(d[k[j]]),
                         A=float(np.min(np.hypot(x - FLASH['A'][0], y - FLASH['A'][1]))),
                         B=float(np.min(np.hypot(x - FLASH['B'][0], y - FLASH['B'][1])))))
    if recs:
        out.append(dict(name=name, num=l1[2:7], epoch=l1[18:32], inc=float(l2[8:16]), recs=recs))

print('\n== 노출 중(0~300초) 궤도 고리가 시야 3° 안을 지나는 위성 ==')
print('  x_mid: 사진 가운데 높이(y=2088)에서 고리의 x 위치 (첫→끝 관측 시각). 각도: 진행 방향, 수직이면 ±90°')
print('  사진 속 궤적: x≈1000(밝음), x≈1330(희미함, B 위), 둘 다 각도 −89°')
for r in sorted(out, key=lambda r: min(q['minsep'] for q in r['recs'])):
    R = r['recs']
    print(f"{r['name'][:22]:22} {r['num']} ep {r['epoch'][:5]} i={r['inc']:5.1f} 높이 {np.median([q['hgt'] for q in R]):5.0f} km "
          f"거리 {np.median([q['dist'] for q in R]):5.0f} km  x_mid {R[0]['x_mid']:6.0f}→{R[-1]['x_mid']:6.0f} "
          f"(t={R[0]['t']:.0f}~{R[-1]['t']:.0f}s) 각도 {np.median([q['angle'] for q in R]):6.1f}°  "
          f"햇빛 {sum(q['lit'] for q in R)}/{len(R)}  A {min(q['A'] for q in R):5.0f}px B {min(q['B'] for q in R):5.0f}px")
print('\n== NOSS·USA(StarShield 제외) 계열: 노출 중 시야 중심과의 최소 이격 ==')
for n, v in sorted(minsep_all.items(), key=lambda a: a[1]):
    if 'NOSS' in n or (n.startswith('USA') and 'StarSh' not in n):
        print(f'{n:24} {v:6.1f}°')
