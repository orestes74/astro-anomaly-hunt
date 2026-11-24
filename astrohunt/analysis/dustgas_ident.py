"""시야 안쪽(field) 잔차 덩어리 ≥5σ를 알려진 천체(NED)·밝은 별(Gaia G<7)과 대조."""
import sys as _s, os as _o; _s.path.insert(0, _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))); import cfg
import json, os, numpy as np, warnings, time
import astropy.units as u
from astropy.coordinates import SkyCoord
from astroquery.ipac.ned import Ned
import common as C
warnings.filterwarnings('ignore')
rows = json.load(open(os.path.join(C.HERE, 'results', 'dustgas_blobs.json')))
SKIP = {'XrayS', 'IrS', 'RadioS', 'UvS', 'VisS', '*', 'UvES', 'Other', 'G_Lens', 'GClstr', 'GGroup', 'QSO', 'EmLS', 'MCld', '*Cl', '!*'}
cache = {}
out = []
for r in rows:
    if r['where'] != 'field' or r['peak_sigma'] < 5:
        continue
    k = (round(r['ra'], 2), round(r['dec'], 2))
    rad = max(3.0, np.sqrt(r['area_arcmin2'] / np.pi) + 2)
    if k not in cache:
        names = []
        for a in range(3):
            try:
                t = Ned.query_region(SkyCoord(r['ra'], r['dec'], unit='deg'), radius=rad * u.arcmin)
                t = t[[str(x) not in SKIP for x in t['Type']]]
                # 큰 천체 우선: 이름이 짧은 M/NGC/IC/LBN/LDN/Sh2/vdB 등
                pri = [n for n in t['Object Name'] if str(n).split()[0].upper() in ('MESSIER', 'NGC', 'IC', 'LBN', 'LDN', 'SH2', 'SH', 'VDB', 'UGC', 'B', 'BARNARD', 'GN', 'RCW', 'CED')]
                names = list(dict.fromkeys(pri))[:4] or [f"{n}({ty})" for n, ty in zip(t['Object Name'][:3], t['Type'][:3])]
                break
            except Exception as e:
                time.sleep(3)
        gra, gde, gg, _ = C.gaia(round(r['ra'], 2), round(r['dec'], 2), 0.25, 9.0)
        s = SkyCoord(gra * u.deg, gde * u.deg).separation(SkyCoord(r['ra'] * u.deg, r['dec'] * u.deg)).arcmin
        bright = [f"G{g:.1f}@{d:.1f}′" for g, d in sorted(zip(gg, s)) if d < 6 + 3 * (9 - g)][:2]
        cache[k] = (names, bright)
    names, bright = cache[k]
    r['ned'] = names; r['bright'] = bright
    r['verdict'] = 'known_object' if names else ('bright_star_halo' if bright else 'UNEXPLAINED')
    out.append(r)
    print(f"{r['sid'][:36]:36s} {r['map']:11s} {r['sign']} {r['ra']:.3f} {r['dec']:+.3f} {r['peak_sigma']:5.1f}σ {r['area_arcmin2']:5.0f}′² → {r['verdict']:16s} {names[:3]} {bright}", flush=True)
json.dump(out, open(os.path.join(C.HERE, 'results', 'dustgas_ident.json'), 'w'), ensure_ascii=False, indent=0)
