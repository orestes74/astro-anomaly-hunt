"""h:\\asiair\\Autorun 의 Light/Flat/Dark FITS 헤더 목록 (원본은 읽기만)."""
import sys as _s, os as _o; _s.path.insert(0, _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))); import cfg
import os, re, glob, numpy as np, pandas as pd, warnings
from concurrent.futures import ThreadPoolExecutor
from astropy.io import fits
from astropy.time import Time
warnings.filterwarnings('ignore')
ROOT = cfg.RAW
OUT = cfg.INVENTORY
os.makedirs(OUT, exist_ok=True)
HDR = ('DATE-OBS', 'EXPTIME', 'GAIN', 'OFFSET', 'CCD-TEMP', 'SET-TEMP', 'FOCALLEN', 'NAXIS1', 'NAXIS2', 'BAYERPAT',
       'XPIXSZ', 'XBINNING', 'INSTRUME', 'TELESCOP', 'FILTER', 'IMAGETYP', 'OBJECT', 'RA', 'DEC', 'CRVAL1', 'CRVAL2')
# 폴더가 비어도 이 열 이름으로 저장 (다음 단계가 열 이름으로 읽음)
COLS = ['path', 'folder', *HDR, 'angle_fn', 'scale', 'rot', 'parity', 'mjd', 'local', 'night', 'in_window', 'error']

def one(path):
    try:
        h = fits.getheader(path)
    except Exception as e:
        return dict(path=path, error=str(e)[:80])
    r = dict(path=path, folder=os.path.basename(os.path.dirname(path)))
    for k in HDR:
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
        lt = cfg.local_dt(t)   # 현지 시각
        r['local'] = lt.strftime('%Y-%m-%d %H:%M:%S')
        # 밤 구분: 18:00~다음날 06:00 → 저녁 날짜로 이름. 그 밖 시간은 별도 표시
        hh = lt.hour + lt.minute / 60
        if hh >= cfg.NIGHT_START:
            r['night'] = lt.strftime('%Y-%m-%d'); r['in_window'] = True
        elif hh < cfg.NIGHT_END:
            r['night'] = (lt - pd.Timedelta(days=1)).strftime('%Y-%m-%d'); r['in_window'] = True
        else:
            r['night'] = (lt - pd.Timedelta(days=1)).strftime('%Y-%m-%d') if hh < 12 else lt.strftime('%Y-%m-%d')
            r['in_window'] = False
    return r

for kind in ('Light', 'Flat', 'Dark'):
    files = sorted(glob.glob(f'{ROOT}/{kind}/**/*.fit', recursive=True)) + sorted(glob.glob(f'{ROOT}/{kind}/**/*.fits', recursive=True))
    old_csv = f'{OUT}/{kind.lower()}.csv'
    old = pd.read_csv(old_csv) if os.path.exists(old_csv) else pd.DataFrame(columns=['path'])
    if 'error' in old:
        old = old[old.error.isna()]
    known = set(old.path)
    new = [f for f in files if f not in known]
    with ThreadPoolExecutor(16) as ex:
        rows = list(ex.map(one, new))
    df = pd.concat([old[old.path.isin(set(files))], pd.DataFrame(rows)], ignore_index=True)
    if not len(df):
        df = pd.DataFrame(columns=COLS)
    print(kind, '새 파일', len(new), end=' / ')
    df.to_csv(f'{OUT}/{kind.lower()}.csv', index=False, encoding='utf-8-sig')
    print(kind, len(df), 'errors', df.get('error', pd.Series(dtype=str)).notna().sum())
