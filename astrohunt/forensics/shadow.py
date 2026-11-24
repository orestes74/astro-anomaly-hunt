"""M51 0019 섬광: 시선 방향에서 위성이 햇빛을 받으려면 몇 km 이상이어야 하는지 (원통형 지구 그림자 근사)"""
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.time import Time, TimeDelta
from astropy.coordinates import EarthLocation, SkyCoord, AltAz, get_sun, GCRS, ITRS, CartesianRepresentation
import astropy.units as u
f = r'h:/asiair/Autorun/Light/M 51/Light_M 51_300.0s_Bin1_20260418-030615_16deg_0019.fit'
h = fits.getheader(f); w = WCS(h)
loc = EarthLocation(lon=h['SITELONG']*u.deg, lat=h['SITELAT']*u.deg, height=50*u.m)
t0 = Time(h['DATE-OBS'], scale='utc')
RE = 6371.0
for name, (x, y) in {'A': (1730, 1659), 'B': (1328, 1242)}.items():
    ra, dec = w.all_pix2world(x, y, 0)
    print(f'섬광 {name}: RA {float(ra):.3f} Dec {float(dec):+.3f}')
    for dt in (0, 150, 300):
        t = t0 + TimeDelta(dt, format='sec')
        aa = SkyCoord(ra=float(ra)*u.deg, dec=float(dec)*u.deg).transform_to(AltAz(obstime=t, location=loc))
        sun = get_sun(t)
        saa = sun.transform_to(AltAz(obstime=t, location=loc))
        # ITRS vectors (km)
        obs = np.array(loc.get_itrs(t).cartesian.xyz.to(u.km).value)
        s_itrs = sun.transform_to(ITRS(obstime=t)).cartesian.xyz.value; s_hat = s_itrs/np.linalg.norm(s_itrs)
        # line of sight unit vector in ITRS from alt/az
        alt, az = aa.alt.rad, aa.az.rad
        lat, lon = np.radians(h['SITELAT']), np.radians(h['SITELONG'])
        e = np.array([-np.sin(lon), np.cos(lon), 0]); n = np.array([-np.sin(lat)*np.cos(lon), -np.sin(lat)*np.sin(lon), np.cos(lat)])
        up = np.array([np.cos(lat)*np.cos(lon), np.cos(lat)*np.sin(lon), np.sin(lat)])
        los = np.cos(alt)*(np.sin(az)*e + np.cos(az)*n) + np.sin(alt)*up
        hit = None
        for r in np.arange(1, 60000, 1.0):
            p = obs + r*los
            along = p @ s_hat; perp = np.linalg.norm(p - along*s_hat)
            if along > 0 or perp > RE:   # 햇빛 받음
                hit = (r, np.linalg.norm(p) - RE); break
        print(f'  +{dt:3d}s 고도 {aa.alt.deg:5.1f}° 방위 {aa.az.deg:5.1f}°  태양고도 {saa.alt.deg:6.1f}°  '
              f'햇빛 받는 최소: 거리 {hit[0]:.0f} km, 지표 높이 {hit[1]:.0f} km')
