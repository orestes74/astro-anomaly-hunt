"""구간별 잡음 꼬리로 유의 수준 정하기: 최대 S/N 지도의 국소 최대값 분포(지수 꼬리)를 맞춰,
구간당 거짓 경보 기대 0.05개가 되는 S/N을 문턱으로 삼고 후보를 다시 분류."""
import json, glob, os, numpy as np
from scipy.ndimage import maximum_filter
import ssa_post as P
out = []
for f in sorted(glob.glob(os.path.join(P.RES, '*.json'))):
    r = json.load(open(f)); sid = r['sid']
    thr = {}
    for ch in r['chunks']:
        mp = os.path.join(P.SSA_OUT, f"{sid}_c{ch['i']}_max.npz")
        if not os.path.exists(mp):
            continue
        b = np.load(mp)['best'].astype(np.float32)
        b[:12] = b[-12:] = -50; b[:, :12] = b[:, -12:] = -50
        lm = (b == maximum_filter(b, 9)) & (b > 4.0)
        v = np.sort(b[lm])[::-1]
        if len(v) < 50:
            thr[ch['i']] = 8.0; continue
        tail = v[:min(300, len(v) // 2)]           # 꼬리 상위 → 지수 기울기
        s0 = tail[-1]; lam = 1.0 / max(np.mean(tail - s0), 1e-3)
        n0 = len(tail)
        thr[ch['i']] = float(max(s0 + np.log(n0 / 0.05) / lam, 7.0))   # N(>s)=0.05
    for c in r['cands']:
        t = thr.get(c['chunk'], 99)
        c['thr'] = t
        if c['cls'] in ('single_strong', 'linked', 'weak') and c['snr'] >= t and c['split_ok'] and c.get('static_sn', 0) <= 3:
            out.append(dict(sid=sid, chunk=c['chunk'], snr=c['snr'], thr=t, cls=c['cls'], ra=c['ra'], dec=c['dec'], x=c['x'], y=c['y'],
                            vx=c['vx'], vy=c['vy'], rate=c['rate_arcsec_min'], mjd=c['mjd'], png=c.get('png')))
    r['thr'] = thr
    json.dump(r, open(f, 'w'), ensure_ascii=False, indent=0)
json.dump(out, open(os.path.join(P.RES, '..', 'ssa_significant.json'), 'w'), indent=0)
print(len(out))
for o in sorted(out, key=lambda o: -(o['snr'] - o['thr'])):
    print(f"{o['sid'][:38]:38s} c{o['chunk']} S/N {o['snr']:.1f} (문턱 {o['thr']:.1f}) {o['cls']:13s} {o['ra']:.4f} {o['dec']:+.4f} {o['rate']:.2f}\"/min")
