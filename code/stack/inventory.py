"""h:\\asiair\\Autorun 의 Light/Flat/Dark FITS 헤더 목록 (원본은 읽기만)."""
import os, re, glob, numpy as np, pandas as pd, warnings
from concurrent.futures import ThreadPoolExecutor
from astropy.io import fits
from astropy.time import Time
warnings.filterwarnings('ignore')
ROOT = r'h:/asiair/Autorun'
OUT = os.path.join(os.path.dirname(__file__), 'inventory')
os.makedirs(OUT, exist_ok=True)

def one(path):
    try:
        h = fits.getheader(path)
    except Exception as e:
        return dict(path=path, error=str(e)[:80])
    r = dict(path=path, folder=os.path.basename(os.path.dirname(path)))
    for k in ('DATE-OBS', 'EXPTIME', 'GAIN', 'OFFSET', 'CCD-TEMP', 'SET-TEMP', 'FOCALLEN', 'NAXIS1', 'NAXIS2', 'BAYERPAT',
              'XPIXSZ', 'XBINNING', 'INSTRUME', 'TELESCOP', 'FILTER', 'IMAGETYP', 'OBJECT', 'RA', 'DEC', 'CRVAL1', 'CRVAL2'):
        r[k] = h.get(k)
    m = re.search(r'_(\d+)deg_', os.path.basename(path)); r['angle_fn'] = int(m.group(1)) if m else None
    if 'CD1_1' in h:
        cd = np.array([[h['CD1_1'], h.get('CD1_2', 0)], [h.get('CD2_1', 0), h['CD2_2']]])
        r['scale'] = float(np.sqrt(abs(np.linalg.det(cd))) * 3600)
        r['rot'] = float(np.degrees(np.arctan2(cd[1, 0], cd[1, 1])))
        r['parity'] = float(np.sign(np.linalg.det(cd)))
    if r['DATE-OBS']:
        t = Time(r['DATE-OBS'], scale='utc')
        r['mjd'] = t.mjd
        lt = (t + 9 / 24).datetime   # KST
        r['local'] = lt.strftime('%Y-%m-%d %H:%M:%S')
        # 밤 구분: 18:00~다음날 06:00 → 저녁 날짜로 이름. 그 밖 시간은 별도 표시
        hh = lt.hour + lt.minute / 60
        if hh >= 18:
            r['night'] = lt.strftime('%Y-%m-%d'); r['in_window'] = True
        elif hh < 6:
            r['night'] = (lt - pd.Timedelta(days=1)).strftime('%Y-%m-%d'); r['in_window'] = True
        else:
            r['night'] = (lt - pd.Timedelta(days=1)).strftime('%Y-%m-%d') if hh < 12 else lt.strftime('%Y-%m-%d')
            r['in_window'] = False
    return r

for kind in ('Light', 'Flat', 'Dark'):
    files = sorted(glob.glob(f'{ROOT}/{kind}/**/*.fit', recursive=True)) + sorted(glob.glob(f'{ROOT}/{kind}/**/*.fits', recursive=True))
    with ThreadPoolExecutor(16) as ex:
        rows = list(ex.map(one, files))
    df = pd.DataFrame(rows)
    df.to_csv(f'{OUT}/{kind.lower()}.csv', index=False, encoding='utf-8-sig')
    print(kind, len(df), 'errors', df.get('error', pd.Series(dtype=str)).notna().sum())
