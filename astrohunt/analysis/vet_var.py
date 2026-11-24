"""세션 간 밝기 변화 별 강제측광 재검증 (주변 별 25개로 상대 보정, 이웃 오염·노이즈 고려)."""
import sys as _s, os as _o; _s.path.insert(0, _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))); import cfg
import os, json, numpy as np, collections
import transient as T, common as C
from vet_forced import phot, get
R = os.path.join(C.HERE, 'results', 'transient')
V = json.load(open(os.path.join(R, 'transient_candidates.json'), encoding='utf-8'))['variables']
out = []
V.sort(key=lambda v: (v['sid_a'], v['sid_b']))
for v in V:
    Lm, w, k = get(v['sid_a'])
    good = (k['snr'] > 30) & (k['snr'] < 500) & (k['gaia_d'] < 1.5) & (k['flag'] < 4)
    sep_all = np.hypot((k['ra'] - v['ra']) * np.cos(np.radians(v['dec'])), k['dec'] - v['dec']) * 3600
    crowd = int(((sep_all > 1.5) & (sep_all < 10)).sum())
    sep = sep_all[good]; nb = np.argsort(sep)[1:26]
    rr, dd = k['ra'][good][nb], k['dec'][good][nb]
    fa = phot(v['sid_a'], np.r_[v['ra'], rr], np.r_[v['dec'], dd])
    fb = phot(v['sid_b'], np.r_[v['ra'], rr], np.r_[v['dec'], dd])
    m = np.isfinite(fa[1:, 0]) & np.isfinite(fb[1:, 0]) & (fa[1:, 0] > 0) & (fb[1:, 0] > 0)
    if m.sum() < 8 or not (fa[0, 0] > 0 and fb[0, 0] > 0):
        v.update(fdm=None); out.append(v); continue
    rn = -2.5 * np.log10(fb[1:, 0][m] / fa[1:, 0][m]); zp = np.median(rn); sc = 1.4826 * np.median(np.abs(rn - zp))
    dm = -2.5 * np.log10(fb[0, 0] / fa[0, 0]) - zp
    err = 1.0857 * np.hypot(fa[0, 1] / fa[0, 0], fb[0, 1] / fb[0, 0])
    v.update(fdm=float(dm), fsig=float(abs(dm) / np.hypot(err, sc)), nb_scatter=float(sc), crowd=crowd)
    out.append(v)
json.dump(out, open(os.path.join(R, 'var_forced.json'), 'w'), ensure_ascii=False, indent=0)
keep = [v for v in out if v.get('fdm') is not None and abs(v['fdm']) > 0.4 and v['fsig'] > 6 and v['crowd'] == 0 and v['nb_scatter'] < 0.1]
print('변광 후보', len(out), '→ 강제측광 재확인(|Δm|>0.4, >6σ, 이웃 없음, 보정 산포<0.1)', len(keep))
print(collections.Counter(v['target'] for v in keep).most_common())
json.dump(keep, open(os.path.join(R, 'var_keep.json'), 'w'), ensure_ascii=False, indent=0)
