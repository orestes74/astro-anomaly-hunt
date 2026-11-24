"""M51 0019: 섬광 A/B와 수직 궤적 2개의 밝기 측정 (Gaia G로 영점 보정, OSC 원시 Bayer 전체 합 = 넓은 백색광)."""
import numpy as np, warnings
from astropy.io import fits
from astropy.wcs import WCS
import requests, io
from astropy.table import Table
import astropy.units as u
from astropy.coordinates import SkyCoord
warnings.filterwarnings('ignore')

F = r'h:/asiair/Autorun/Light/M 51/Light_M 51_300.0s_Bin1_20260418-030615_16deg_0019.fit'
d = fits.getdata(F).astype(float); h = fits.getheader(F); w = WCS(h); NY, NX = d.shape
EXP = h['EXPTIME']
yy, xx = np.mgrid[-30:31, -30:31]; rr = np.hypot(xx, yy)

def phot(x, y, r=10):
    xi, yi = int(round(x)), int(round(y))
    cut = d[yi - 30:yi + 31, xi - 30:xi + 31]
    if cut.shape != rr.shape:
        return np.nan, np.nan
    bg = np.median(cut[(rr > 18) & (rr < 28)])
    return float((cut[rr <= r] - bg).sum()), float(cut[rr <= 4].max())

# Gaia DR3 별로 영점
c = w.pixel_to_world(NX / 2, NY / 2)
q = (f"SELECT ra, dec, phot_g_mean_mag AS Gmag, bp_rp FROM gaiadr3.gaia_source WHERE phot_g_mean_mag BETWEEN 9 AND 14.5 "
     f"AND CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {c.ra.deg:.5f}, {c.dec.deg:.5f}, 0.85)) = 1")
rq = requests.post('https://gea.esac.esa.int/tap-server/tap/sync', data=dict(REQUEST='doQuery', LANG='ADQL', FORMAT='csv', QUERY=q), timeout=120)
rq.raise_for_status()
g = Table.read(rq.text.splitlines(), format='csv')
g.rename_columns(['ra', 'dec', 'gmag', 'bp_rp'] if 'gmag' in g.colnames else ['ra','dec','Gmag','bp_rp'], ['RA_ICRS', 'DE_ICRS', 'Gmag', 'BP-RP'])
gx, gy = w.world_to_pixel(SkyCoord(g['RA_ICRS'], g['DE_ICRS'], unit='deg'))
zp, col = [], []
for X, Y, G, br in zip(gx, gy, g['Gmag'], g['BP-RP']):
    if 60 < X < NX - 60 and 60 < Y < NY - 60:
        f, pk = phot(X, Y)
        if f > 0 and pk < 55000:
            zp.append(G + 2.5 * np.log10(f)); col.append(br)
zp = np.array(zp); ZP = np.median(zp)
print(f'영점: Gaia 별 {len(zp)}개, ZP(300초 합) = {ZP:.3f} ± {1.4826*np.median(np.abs(zp-ZP)):.3f} mag')

# 섬광 반경별 (곡선 수렴 확인)
for name, (x, y) in {'A': (1730.2, 1659.2), 'B': (1328.1, 1242.1)}.items():
    fl = [phot(x, y, r)[0] for r in (6, 10, 14)]
    m = ZP - 2.5 * np.log10(fl[1])
    print(f'섬광 {name}: 플럭스(r=6/10/14) {fl[0]:.0f}/{fl[1]:.0f}/{fl[2]:.0f} ADU, 피크 {phot(x,y)[1]:.0f}  →  300초 동안 별 등가 G = {m:.2f}')

# 수직 궤적: 행마다 가로로 잘라 단위 길이당 플럭스
print()
for name, x0 in (('밝은 궤적', 1000), ('희미한 궤적', 1330)):
    per = []
    for y in range(100, NY - 100, 7):
        row = d[y, x0 - 60:x0 + 61]
        j = int(np.argmax(row[40:81])) + 40   # 궤적 중심(±20px)
        bg = np.median(np.r_[row[:25], row[-25:]])
        s = (row[j - 8:j + 9] - bg).sum()
        per.append((y, x0 - 60 + j, s))
    per = np.array(per)
    s = np.median(per[:, 2])
    m_len = ZP - 2.5 * np.log10(s)   # 길이 1px당 등가 등급
    print(f'{name}: x≈{np.median(per[:,1]):.0f}, 1 px 길이당 플럭스 {s:.0f} ADU (행 {len(per)}개 중앙값)  → 1 px당 G = {m_len:.2f}')
    print(f'   물체 등급 = {m_len:.2f} - 2.5 log10(ω·{EXP:.0f}) ... ω[px/s]가 각속도일 때. 예: ω=100 → {m_len - 2.5*np.log10(100*EXP)+2.5*np.log10(EXP):.2f}')
    for om in (50, 100, 300, 1000):
        # 물체 등급 m: 플럭스율 f = 10^(-0.4(m - ZPs)), ZPs = ZP - 2.5log(EXP) (1초 영점). 1px 지나는 시간 1/ω → 1px 플럭스 = f/ω
        ZPs = ZP - 2.5 * np.log10(EXP)
        mo = ZPs - 2.5 * np.log10(s * om)
        print(f'   ω={om:5d} px/s ({om*0.873/3600:.3f}°/s) → 물체 등급 G ≈ {mo:.2f}')
