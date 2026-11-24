"""M51 0019: 측정 밝기(flash_phot.py) → 고도별 크기 추정.
- 궤적: 확산 반사 구(Lambert sphere), 반사율 0.2. 물체 등급은 각속도 ω에 달려 있으므로 원궤도 속도/거리로 ω를 추정.
- 섬광: 평면 거울 반사(글린트). 300초 적분 밝기 = 피크 밝기 × 섬광 시간 t_f → 거울 면적 × t_f 만 정해짐.
  별처럼 둥글려면 섬광 동안 2 px 이상 움직이면 안 됨 → t_f ≤ 2/ω → 최소 거울 면적."""
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.time import Time
from astropy.coordinates import EarthLocation, AltAz, SkyCoord, get_sun
import astropy.units as u

F = r'h:/asiair/Autorun/Light/M 51/Light_M 51_300.0s_Bin1_20260418-030615_16deg_0019.fit'
h = fits.getheader(F); w = WCS(h)
ZP = 25.996; EXP = 300.0; ZP1 = ZP - 2.5 * np.log10(EXP)     # 1초 영점
PIX = 0.873                                                   # "/px
M_SUN = -26.74 + 0.08                                         # 태양 G 등급(대략)
ALPHA = np.radians(0.2666)                                    # 태양 각반지름
STREAK = {'밝은 궤적': 1758.0, '희미한 궤적': 710.0}           # 1 px 길이당 ADU
FLASH = {'A': 10.73, 'B': 11.43}                              # 300초 적분 등가 G (A는 피크 포화 → 하한)
RHO_D, RHO_M = 0.2, 0.9
RE, GM = 6371.0, 398600.4418

t = Time(h['DATE-OBS']) + 150 * u.s
loc = EarthLocation(lon=h['SITELONG'] * u.deg, lat=h['SITELAT'] * u.deg, height=50 * u.m)
c = w.pixel_to_world(3124, 2088)
aa = c.transform_to(AltAz(obstime=t, location=loc))
el = aa.alt.rad
# 위상각용 벡터(지평 좌표: 동, 북, 천정)
def enu(alt, az): return np.array([np.cos(alt) * np.sin(az), np.cos(alt) * np.cos(az), np.sin(alt)])
los = enu(el, aa.az.rad)
sa = get_sun(t).transform_to(AltAz(obstime=t, location=loc))
sun = enu(sa.alt.rad, sa.az.rad)
print(f'시야 중심 고도 {np.degrees(el):.1f}°, 방위 {aa.az.deg:.1f}°, 태양 고도 {sa.alt.deg:.1f}°')

def lambert(phi):  # 구의 위상 함수 (phi=0 정면 조명)
    return 2 / (3 * np.pi ** 2) * ((np.pi - phi) * np.cos(phi) + np.sin(phi))

print('\n고도(km) 거리(km) ω(px/s) 위상각 | 궤적: 밝은/희미한 등급, 지름(m) | 섬광 A/B: 1초 등가 등급, t_f≤2/ω일 때 최소 거울 지름(m)')
for H in (1150, 1500, 2000, 5000, 10000, 20200, 35786):
    # LOS 위 고도 H까지 거리: |obs + d los| = RE + H, obs=(0,0,RE)
    b = RE * np.sin(el); d = -b + np.sqrt(b * b + (RE + H) ** 2 - RE ** 2)
    v = np.sqrt(GM / (RE + H))
    v_obs = 0.465 * np.cos(np.radians(h['SITELAT']))           # 관측자 자전 속도(대략)
    om = max(v - v_obs, 0.05) / d                               # rad/s (상한 근사: 시선에 수직으로 움직인다고 가정)
    om_px = np.degrees(om) * 3600 / PIX
    sat = np.array([0, 0, RE]) + d * los                       # 대략적 위치 (태양 방향은 무한원)
    to_obs = -los
    phi = np.arccos(np.clip(np.dot(sun, to_obs), -1, 1))       # 태양→위성→관측자 위상각 = 180° - (태양방향, 위성→관측자) 사이각...
    phi = np.pi - np.arccos(np.clip(np.dot(sun, -to_obs), -1, 1))
    row = f'{H:7.0f} {d:8.0f} {om_px:8.0f} {np.degrees(phi):6.0f}° |'
    for k, s in STREAK.items():
        m = ZP1 - 2.5 * np.log10(s * om_px)
        ratio = 10 ** (-0.4 * (m - M_SUN))
        A = ratio * (d * 1e3) ** 2 / (RHO_D * lambert(phi))   # 단면적 m²
        row += f' {m:5.1f}등 {2*np.sqrt(A/np.pi):5.1f}m'
    row += ' |'
    for k, m300 in FLASH.items():
        m1 = m300 - 2.5 * np.log10(EXP)                            # 1초 동안 지속했다면의 등급
        Et = 10 ** (-0.4 * (m1 - M_SUN))                           # (피크 플럭스비 × t_f)
        tf = 2 / om_px
        Am = Et / tf * np.pi * ALPHA ** 2 * (d * 1e3) ** 2 / RHO_M  # 거울 면적 m²
        row += f' {m1:4.1f}등 t_f≤{tf*1e3:5.0f}ms 거울≥{2*np.sqrt(Am/np.pi):5.2f}m'
    print(row)
