"""단독 후보 국소 검증: 후보 주변(3') 밝은 별들의 Gaia 거리 중앙값 = 국소 좌표 오차. 큰 곳은 좌표 오류 가짜."""
import sys as _s, os as _o; _s.path.insert(0, _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))); import cfg
import os, json, numpy as np, collections
from scipy.spatial import cKDTree
import transient as T, common as C
d = json.load(open(os.path.join(C.HERE, 'results', 'transient', 'transient_candidates.json'), encoding='utf-8'))
cs = [c for c in d['cands'] if c['kind'] == 'only_this_session' and not c['asteroid']]
cache = {}
out = []
for c in cs:
    if c['sid'] not in cache:
        k = T.load_cat(c['sid']); good = (k['snr'] > 30) & (k['flag'] < 4)
        xyz = np.c_[np.cos(np.radians(k['dec'][good])) * np.cos(np.radians(k['ra'][good])), np.cos(np.radians(k['dec'][good])) * np.sin(np.radians(k['ra'][good])), np.sin(np.radians(k['dec'][good]))]
        cache[c['sid']] = (cKDTree(xyz), k['gaia_d'][good], k['scale'])
    tr, gd, sc = cache[c['sid']]
    p = [np.cos(np.radians(c['dec'])) * np.cos(np.radians(c['ra'])), np.cos(np.radians(c['dec'])) * np.sin(np.radians(c['ra'])), np.sin(np.radians(c['dec']))]
    ii = tr.query_ball_point(p, np.radians(3 / 60))
    loc = float(np.median(gd[ii])) if len(ii) >= 5 else np.nan
    frac = float(np.mean(gd[ii] > 4)) if len(ii) >= 5 else np.nan
    out.append(dict(c, loc_gaia_d=loc, loc_frac4=frac, n_nb=len(ii)))
json.dump(out, open(os.path.join(C.HERE, 'results', 'transient', 'only_local.json'), 'w'), ensure_ascii=False, indent=0)
ok = [o for o in out if o['loc_gaia_d'] < 1.5 and o['loc_frac4'] < 0.1]
print('단독 후보', len(out), '→ 국소 좌표 양호', len(ok))
print(collections.Counter(o['target'] for o in ok).most_common())
for o in sorted(ok, key=lambda o: -o['snr'])[:40]:
    print(f"{o['target']:20s} {o['sid'][:10]} {o['ra']:9.4f} {o['dec']:+8.4f} m={o['mag']:.1f} snr={o['snr']:.0f} gd={o['gaia_d']:.1f} loc={o['loc_gaia_d']:.2f} others={[(x['sid'][:10], round(x['lim5'],1)) for x in o['others']]}")
