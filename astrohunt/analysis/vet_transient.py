"""transient_candidates.json 후보 검증: 대상별 VSX 전체 시야 조회(캐시) → 변광 별·이번 세션 단독 후보 대조."""
import sys as _s, os as _o; _s.path.insert(0, _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))); import cfg
import os, json, numpy as np, requests, collections
import common as C
OUT = os.path.join(C.HERE, 'results', 'transient')
VC = os.path.join(C.HERE, 'cache_vsx'); os.makedirs(VC, exist_ok=True)
d = json.load(open(os.path.join(OUT, 'transient_candidates.json'), encoding='utf-8'))

def vsx_query(ra, dec, rad):
    """반경이 크면 서버 500 → 작은 원으로 쪼개 재귀 조회"""
    import time
    for att in range(3):
        try:
            r = requests.get('https://www.aavso.org/vsx/index.php', params=dict(view='api.list', ra=ra, dec=dec, radius=rad, format='json'), timeout=300)
            js = r.json()['VSXObjects']
            return js.get('VSXObject', []) if isinstance(js, dict) else []
        except Exception:
            if rad > 0.15:
                break
            time.sleep(20)
    if rad <= 0.15:
        raise RuntimeError(f'VSX 실패 {ra} {dec} {rad}')
    out, seen = [], set()
    h = rad / 2
    for dx in (-h, h):
        for dy in (-h, h):
            for o in vsx_query(ra + dx / np.cos(np.radians(dec)), dec + dy, h * 1.42):
                if o['OID'] not in seen:
                    seen.add(o['OID']); out.append(o)
    return out

def vsx_field(key, ra, dec, rad):
    fn = os.path.join(VC, f'{key}.json')
    if not os.path.exists(fn):
        json.dump(vsx_query(ra, dec, rad), open(fn, 'w'))
    o = json.load(open(fn))
    return (np.array([float(x['RA2000']) for x in o]), np.array([float(x['Declination2000']) for x in o]), o)

items = d['variables'] + [c for c in d['cands'] if c['kind'] == 'only_this_session' and not c['asteroid']]
groups = collections.defaultdict(list)
for it in items:
    groups[it['target']].append(it)
for t, L in groups.items():
    ra = np.array([x['ra'] for x in L]); de = np.array([x['dec'] for x in L])
    # 좌표 군집별(같은 대상 이름이라도 다른 시야일 수 있음)
    rem = list(range(len(L)))
    while rem:
        i0 = rem[0]
        s = np.hypot((ra[rem] - ra[i0]) * np.cos(np.radians(de[i0])), de[rem] - de[i0])
        grp = [rem[k] for k in np.where(s < 2.0)[0]]
        cra, cde = np.median(ra[grp]), np.median(de[grp])
        rad = float(np.max(np.hypot((ra[grp] - cra) * np.cos(np.radians(cde)), de[grp] - cde))) + 0.05
        key = f'{cra:.2f}_{cde:.2f}_{rad:.2f}'
        vr, vd, vo = vsx_field(key, cra, cde, rad)
        for g in grp:
            x = L[g]
            if len(vr):
                sep = np.hypot((vr - x['ra']) * np.cos(np.radians(x['dec'])), vd - x['dec']) * 3600
                k = np.where(sep < 6)[0]
                x['vsx'] = [(vo[j]['Name'], vo[j].get('VariabilityType', ''), vo[j].get('MaxMag', ''), vo[j].get('MinMag', ''), float(sep[j])) for j in k[np.argsort(sep[k])]]
            else:
                x['vsx'] = []
        print(f'{t} ({cra:.2f},{cde:.2f}) r={rad:.2f}: VSX {len(vr)}개, 항목 {len(grp)}개, 일치 {sum(bool(L[g]["vsx"]) for g in grp)}', flush=True)
        rem = [r for r in rem if r not in grp]
json.dump(d, open(os.path.join(OUT, 'transient_candidates.json'), 'w'), ensure_ascii=False, indent=0)
V = d['variables']
print('변광 별 VSX 일치:', sum(bool(v['vsx']) for v in V), '/', len(V))
C_ = [c for c in d['cands'] if c['kind'] == 'only_this_session' and not c['asteroid']]
print('단독 후보 VSX 일치:', sum(bool(c['vsx']) for c in C_), '/', len(C_))
