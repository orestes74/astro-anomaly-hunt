"""스택 대상 시야별 Gaia DR3(G<20.8) 미리 받기 (중심이 0.3° 안인 세션은 한 시야로)."""
import json, numpy as np, pandas as pd, warnings
from concurrent.futures import ThreadPoolExecutor
from astropy.io import fits
from astropy.wcs import WCS
import common as C
warnings.filterwarnings('ignore')
S = pd.read_pickle(r'C:\rasa_test\asteroid_hunt\stack\inventory\sessions.pkl'); S = S[S.do_stack]
fields = []
for r in S.itertuples():
    for f in r.files:
        h = fits.getheader(f)
        if 'CD1_1' in h:
            w = WCS(h); c = w.pixel_to_world(h['NAXIS1'] / 2, h['NAXIS2'] / 2)
            rad = np.hypot(h['NAXIS1'], h['NAXIS2']) / 2 * np.sqrt(abs(np.linalg.det(w.pixel_scale_matrix))) * 1.08
            fields.append((r.sid, c.ra.deg, c.dec.deg, rad)); break
F = []
for sid, ra, de, rad in fields:
    for g in F:
        if np.hypot((ra - g['ra']) * np.cos(np.radians(de)), de - g['dec']) < 0.3:
            g['sids'].append(sid); g['rad'] = max(g['rad'], rad + np.hypot((ra - g['ra']) * np.cos(np.radians(de)), de - g['dec'])); break
    else:
        F.append(dict(ra=ra, dec=de, rad=rad, sids=[sid]))
json.dump(F, open(C.os.path.join(C.HERE, 'fields.json'), 'w'), indent=0)
print(f'세션 {len(fields)}개 → 시야 {len(F)}개', flush=True)

def go(g):
    import time; t = time.time()
    ra, de, gg, _ = C.gaia(round(g['ra'], 3), round(g['dec'], 3), round(g['rad'], 3), 20.8)
    print(f"시야 {g['ra']:.2f},{g['dec']:.2f} r={g['rad']:.2f}°: {len(ra)}개, {time.time()-t:.0f}s ({g['sids'][0]})", flush=True)
with ThreadPoolExecutor(2) as ex:
    list(ex.map(go, F))
