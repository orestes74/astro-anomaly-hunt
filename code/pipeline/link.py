"""Stage 2: find moving objects (asteroid-like tracklets) per observing sequence.

sequence = same target folder, same focal length, no gap > 2 h.
1. stationary sources: detected at the same sky spot in >= 50% of frames that cover it
2. sensor artifacts: candidates recurring at the same sensor x,y in >= 3 frames
3. link remaining candidates into straight constant-rate tracks (>= 4 frames)
Output: results/tracklets.csv, results/sequences.csv, results/tracklets.json
"""
import glob, os, json, sys, collections
import numpy as np
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'cache')
OUT = os.path.join(HERE, 'results')
ARCSEC = np.pi / 180 / 3600

MIN_PTS = 5
VMAX = 10.0          # arcsec / min upper bound for linking
MAX_SEED_GAP = 4     # seed pairs from frames at most this many apart


def load():
    cats = []
    for f in sorted(glob.glob(os.path.join(CACHE, '*.npz'))):
        z = np.load(f, allow_pickle=False)
        d = {k: z[k] for k in z.files}
        d['path'] = str(d['path'])
        d['target'] = os.path.basename(os.path.dirname(d['path']))
        for k in ('mjd', 'exptime', 'W', 'H', 'focallen', 'rms', 'back'):
            d[k] = float(d[k])
        cats.append(d)
    return cats


def sequences(cats):
    by = collections.defaultdict(list)
    for c in cats:
        by[c['target']].append(c)
    seqs = []
    for tgt, cs in by.items():
        cs.sort(key=lambda c: c['mjd'])
        def ctr(c):
            ok = np.isfinite(c['ra'])
            return (np.median(c['ra'][ok]), np.median(c['dec'][ok])) if ok.sum() > 10 else (np.nan, np.nan)
        def moved(a, b):
            (r1, d1), (r2, d2) = ctr(a), ctr(b)
            if not np.isfinite(r1 + r2):
                return True
            dra = ((r1 - r2 + 180) % 360 - 180) * np.cos(np.radians(d1))
            return np.hypot(dra, d1 - d2) > 0.15
        cur = [cs[0]]
        for c in cs[1:]:
            if ((c['mjd'] - cur[-1]['mjd']) * 24 > 2 or abs(c['focallen'] - cur[-1]['focallen']) > 30
                    or moved(cur[0], c)):
                seqs.append(cur); cur = [c]
            else:
                cur.append(c)
        seqs.append(cur)
    return seqs


def tangent(ra, dec, ra0, dec0):
    ra, dec = np.radians(ra), np.radians(dec)
    ra0, dec0 = np.radians(ra0), np.radians(dec0)
    cosc = np.sin(dec0) * np.sin(dec) + np.cos(dec0) * np.cos(dec) * np.cos(ra - ra0)
    xi = np.cos(dec) * np.sin(ra - ra0) / cosc
    eta = (np.cos(dec0) * np.sin(dec) - np.sin(dec0) * np.cos(dec) * np.cos(ra - ra0)) / cosc
    return xi / ARCSEC, eta / ARCSEC


def untangent(xi, eta, ra0, dec0):
    xi, eta = xi * ARCSEC, eta * ARCSEC
    ra0, dec0 = np.radians(ra0), np.radians(dec0)
    rho = np.hypot(xi, eta)
    c = np.arctan(rho)
    with np.errstate(invalid='ignore', divide='ignore'):
        dec = np.arcsin(np.cos(c) * np.sin(dec0) + np.where(rho > 0, eta * np.sin(c) * np.cos(dec0) / rho, 0))
        ra = ra0 + np.arctan2(xi * np.sin(c), rho * np.cos(dec0) * np.cos(c) - eta * np.sin(dec0) * np.sin(c))
    return np.degrees(ra) % 360, np.degrees(dec)


def footprint_poly(c, ra0, dec0, margin=40):
    """frame footprint corners in tangent arcsec, via linear interpolation of detections' x,y->xi,eta"""
    x, y = c['x'], c['y']
    xi, eta = tangent(c['ra'], c['dec'], ra0, dec0)
    if len(x) < 10:
        return None
    A = np.c_[np.ones_like(x), x, y, x * y, x * x, y * y]
    px, *_ = np.linalg.lstsq(A, xi, rcond=None)
    py, *_ = np.linalg.lstsq(A, eta, rcond=None)
    m = margin
    cx = np.array([m, c['W'] - m, c['W'] - m, m], float)
    cy = np.array([m, m, c['H'] - m, c['H'] - m], float)
    B = np.c_[np.ones(4), cx, cy, cx * cy, cx * cx, cy * cy]
    return np.c_[B @ px, B @ py], (px, py)


def inside(poly, P):
    pos = np.ones(len(P), bool); neg = np.ones(len(P), bool)
    for i in range(4):
        a, b = poly[i], poly[(i + 1) % 4]
        cr = (b[0] - a[0]) * (P[:, 1] - a[1]) - (b[1] - a[1]) * (P[:, 0] - a[0])
        pos &= cr >= 0; neg &= cr <= 0
    return pos | neg


def transient_events(seq, P, F, X, Y, A, B, TH, PK, FL, SAT, cnt, cand, edge, R):
    """single-frame events: streaks (satellite / aircraft / meteor) and point flashes (glints etc.)"""
    ev = []
    fr_t = np.array([c['mjd'] for c in seq])
    # --- streaks: long elongated pieces (a in superpixels), merged per frame by angle + collinearity
    longp = np.where((A >= 5) & (A / np.maximum(B, 1e-3) >= 4) & (cnt <= 2))[0]
    byf = collections.defaultdict(list)
    for k in longp:
        byf[F[k]].append(k)
    for f, ks in byf.items():
        ks = sorted(ks, key=lambda k: -A[k])
        groups = []
        for k in ks:
            for g in groups:
                k0 = g[0]
                dth = abs(((TH[k] - TH[k0]) + np.pi / 2) % np.pi - np.pi / 2)
                # perpendicular distance of piece centre from the line of the group's main piece
                ux, uy = np.cos(TH[k0]), np.sin(TH[k0])
                dx, dy = X[k] - X[k0], Y[k] - Y[k0]
                perp = abs(-uy * dx + ux * dy)
                if dth < np.radians(4) and perp < 12:
                    g.append(k); break
            else:
                groups.append([k])
        for g in groups:
            g = np.array(g)
            length = 4 * A[g].sum()   # full-res px (2*a superpix -> *2)
            ev.append(dict(kind='streak', frame=int(f), file=seq[f]['path'], mjd=float(fr_t[f]),
                           x=float(X[g[0]]), y=float(Y[g[0]]), angle_deg=round(float(np.degrees(TH[g[0]])), 1),
                           length_px=round(float(length), 0), pieces=int(len(g)),
                           flux=float(FL[g].sum()), snr=float(PK[g].max() / seq[f]['rms'])))
    # --- flashes: point source in one frame only, not near anything in adjacent frames
    rmsf = np.array([c['rms'] for c in seq])
    medb = {f: np.median(B[(F == f) & (cnt >= 3)]) if np.any((F == f) & (cnt >= 3)) else 1.0 for f in range(len(seq))}
    conc = {}
    for f in range(len(seq)):
        m = (F == f) & (cnt >= 3) & ~SAT & (PK / rmsf[f] > 25) & (PK / rmsf[f] < 1000)
        conc[f] = np.median(PK[m] / FL[m]) if m.sum() > 5 else 1.0
    fl = np.where((cnt == 1) & ~edge & ~SAT & (A / np.maximum(B, 1e-3) < 2.5))[0]
    fl = fl[PK[fl] / rmsf[F[fl]] > 25]
    if len(fl):
        trees = {}
        for k in fl:
            f = F[k]
            if B[k] < 0.8 or A[k] > 4 or PK[k] / max(FL[k], 1) > 0.5:
                continue  # sharper than stars -> cosmic ray / hot pixel
            ok = True
            for g in (f - 1, f + 1):
                if 0 <= g < len(seq):
                    if g not in trees:
                        trees[g] = cKDTree(P[F == g])
                    rad = min(VMAX * abs(fr_t[g] - fr_t[f]) * 1440 + R, 120)
                    if trees[g].query_ball_point(P[k], rad, return_length=True) > 0:
                        ok = False; break
                    mg = F == g
                    if np.any(np.hypot(X[mg] - X[k], Y[mg] - Y[k]) < 15):
                        ok = False; break  # something at the same sensor spot (bad WCS / hot pixel)
                else:
                    ok = False; break  # need both neighbours to call it a flash
            if ok:
                ev.append(dict(kind='flash', frame=int(f), file=seq[f]['path'], mjd=float(fr_t[f]),
                               x=float(X[k]), y=float(Y[k]), angle_deg=None, length_px=None, pieces=1,
                               flux=float(FL[k]), snr=float(PK[k] / rmsf[f]),
                               a=float(A[k]), b=float(B[k]), medb=float(medb[f]), conc=float(PK[k] / max(FL[k], 1)), conc_star=float(conc[f])))
    for e in ev:
        e['target'] = seq[0]['target']; e['seq_start'] = seq[0]['path']
    return ev


def analyse(seq):
    N = len(seq)
    tgt = seq[0]['target']
    pixscale = 206.265 * 3.76 / seq[0]['focallen']  # arcsec / full pixel
    R = max(2.5, 2.2 * pixscale)                    # arcsec: same-spot radius
    ra0 = np.nanmedian([np.nanmedian(c["ra"]) for c in seq])
    dec0 = np.nanmedian([np.nanmedian(c["dec"]) for c in seq])
    info = dict(target=tgt, start=seq[0]['path'], n_frames=N, exptime=seq[0]['exptime'],
                mjd0=seq[0]['mjd'], mjd1=seq[-1]['mjd'], focallen=seq[0]['focallen'],
                pixscale=round(pixscale, 3), ra0=ra0, dec0=dec0)
    if N < MIN_PTS:
        info['note'] = 'too few frames'
        return info, []

    # gather detections
    F, T, XI, ETA, X, Y, FL, A, B, PK, SAT, TH = [], [], [], [], [], [], [], [], [], [], [], []
    polys = []
    iref = int(np.argmax([len(c['x']) for c in seq]))
    cr = seq[iref]
    rxi, reta = tangent(cr['ra'], cr['dec'], ra0, dec0)
    rsel = np.isfinite(rxi) & ~cr['sat']
    rsel &= cr['flux'] >= np.sort(cr['flux'][rsel])[-min(800, rsel.sum())]
    rtree = cKDTree(np.c_[rxi[rsel], reta[rsel]])
    resid = []
    for i, c in enumerate(seq):
        xi, eta = tangent(c['ra'], c['dec'], ra0, dec0)
        # re-register to reference frame (removes per-frame WCS errors)
        good = np.isfinite(xi) & ~c['sat']
        if i != iref and good.sum() > 30 and not os.environ.get('NOREG'):
            fsel = good & (c['flux'] >= np.sort(c['flux'][good])[-min(800, good.sum())])
            src = np.c_[xi[fsel], eta[fsel]]
            design = lambda q: np.c_[np.ones(len(q)), q[:, 0], q[:, 1], q[:, 0] ** 2, q[:, 0] * q[:, 1], q[:, 1] ** 2]
            Msrc = design(src)
            coef_x = coef_y = None
            pred = src
            for rad in (15.0, 4.0, 2.0):
                d, j = rtree.query(pred, distance_upper_bound=rad)
                m = np.isfinite(d)
                if m.sum() < 12:
                    break
                tgt_xy = rtree.data[j[m]]
                coef_x, *_ = np.linalg.lstsq(Msrc[m], tgt_xy[:, 0] - src[m, 0], rcond=None)
                coef_y, *_ = np.linalg.lstsq(Msrc[m], tgt_xy[:, 1] - src[m, 1], rcond=None)
                pred = src + np.c_[Msrc @ coef_x, Msrc @ coef_y]
                rr = np.hypot(*(pred[m] - tgt_xy).T)
            if coef_x is not None:
                resid.append(float(np.median(rr)))
                allp = np.c_[np.ones_like(xi), xi, eta, xi ** 2, xi * eta, eta ** 2]
                xi, eta = xi + allp @ coef_x, eta + allp @ coef_y
        n = len(xi)
        F.append(np.full(n, i)); T.append(np.full(n, c['mjd'])); XI.append(xi); ETA.append(eta)
        X.append(c['x']); Y.append(c['y']); FL.append(c['flux']); A.append(c['a']); B.append(c['b'])
        PK.append(c['peak']); SAT.append(c['sat']); TH.append(c['theta'])
        fp = footprint_poly(c, ra0, dec0)
        polys.append(fp[0] if fp else None)
    F = np.concatenate(F); T = np.concatenate(T); XI = np.concatenate(XI); ETA = np.concatenate(ETA)
    X = np.concatenate(X); Y = np.concatenate(Y); FL = np.concatenate(FL); A = np.concatenate(A)
    B = np.concatenate(B); PK = np.concatenate(PK); SAT = np.concatenate(SAT); TH = np.concatenate(TH)
    P = np.c_[XI, ETA]
    ok = np.isfinite(P).all(1)
    F, T, XI, ETA, X, Y, FL, A, B, PK, SAT, TH = [v[ok] for v in (F, T, XI, ETA, X, Y, FL, A, B, PK, SAT, TH)]
    P = P[ok]
    W, H = seq[0]['W'], seq[0]['H']
    info['reg_resid_med'] = round(float(np.median(resid)), 2) if resid else None

    tree = cKDTree(P)
    cnt = tree.query_ball_point(P, R, return_length=True)
    # coverage for low-count points
    low = np.where(cnt < 0.5 * N)[0]
    cover = np.full(len(P), N)
    if len(low):
        cv = np.zeros(len(low), int)
        for poly in polys:
            if poly is not None:
                cv += inside(poly, P[low])
        cover[low] = np.maximum(cv, 1)
    stationary = cnt >= np.maximum(3, 0.5 * cover)
    # faint stars detected only sometimes: neighbours at the same spot spread over a long time
    dur = max((seq[-1]['mjd'] - seq[0]['mjd']), 1e-6)
    lowi = np.where(~stationary & (cnt >= 2))[0]
    if len(lowi):
        nbs = tree.query_ball_point(P[lowi], R)
        span = np.array([T[nb].max() - T[nb].min() for nb in nbs])
        stationary[lowi[span >= 0.4 * dur]] = True

    edge = (X < 40) | (Y < 40) | (X > W - 40) | (Y > H - 40)
    elong = (A / np.maximum(B, 1e-3)) > 3.5
    cand = (~stationary) & (~edge) & (~SAT) & (~elong) & (B > 0.45)
    # sensor artifacts: same sensor x,y among candidates (and anything) in >= 3 frames
    st = cKDTree(np.c_[X, Y])
    ci = np.where(cand)[0]
    snb = st.query_ball_point(np.c_[X[ci], Y[ci]], 1.5)
    # hot pixel / sensor artifact: same sensor spot over a long time (a slow mover only lingers briefly)
    sspan = np.array([(T[nb].max() - T[nb].min()) if len(nb) >= 3 else 0.0 for nb in snb])
    cand[ci[sspan >= 0.4 * dur]] = False
    ci = np.where(cand)[0]
    info['n_det'] = int(len(P)); info['n_cand'] = int(len(ci))
    info['n_trail_pieces'] = int((elong & ~edge & ~stationary).sum())
    info['_events'] = transient_events(seq, P, F, X, Y, A, B, TH, PK, FL, SAT, cnt, cand, edge, R)
    if len(ci) < MIN_PTS:
        return info, []

    fr_t = np.array([c['mjd'] for c in seq])
    # candidates per frame
    per = collections.defaultdict(list)
    for k in ci:
        per[F[k]].append(k)
    per = {f: np.array(v) for f, v in per.items()}
    ftrees = {f: cKDTree(P[v]) for f, v in per.items()}
    used = np.zeros(len(P), bool)
    tracks = []
    frames_sorted = sorted(per)
    tol = max(1.5 * R, 3.0)
    # limit pathological fields
    if len(ci) > 60000:
        info['note'] = f'too many candidates ({len(ci)}), skipped linking'
        return info, []
    for ia, fa in enumerate(frames_sorted):
        for fb in frames_sorted[ia + 1: ia + 1 + MAX_SEED_GAP]:
            dt_min = (fr_t[fb] - fr_t[fa]) * 1440
            if dt_min <= 0:
                continue
            rad = VMAX * dt_min + R
            for ka in per[fa]:
                if used[ka]:
                    continue
                for jb in ftrees[fb].query_ball_point(P[ka], rad):
                    kb = per[fb][jb]
                    if used[kb] or used[ka]:
                        continue
                    v = (P[kb] - P[ka]) / dt_min  # arcsec/min
                    sp = np.hypot(*v)
                    if sp * dt_min < 0.8 * R and sp < 0.05:
                        continue
                    dtm = (fr_t - fr_t[fa]) * 1440
                    pred = P[ka] + np.outer(dtm, v)
                    # quick check: need a 3rd point in nearby frames before full scan
                    ib = frames_sorted.index(fb)
                    near = frames_sorted[max(0, ia - 4):ia] + frames_sorted[ib + 1: ib + 5]
                    if not any(np.isfinite(ftrees[f].query(pred[f], distance_upper_bound=tol)[0]) for f in near):
                        continue
                    hits = {}
                    for f in frames_sorted:
                        dd, jj = ftrees[f].query(pred[f], distance_upper_bound=tol)
                        if np.isfinite(dd):
                            k = per[f][jj]
                            if not used[k]:
                                hits[f] = k
                    if len(hits) < MIN_PTS:
                        continue
                    ks = np.array(list(hits.values()))
                    tt = (T[ks] - T[ks].mean()) * 1440
                    M = np.c_[np.ones_like(tt), tt]
                    cx, *_ = np.linalg.lstsq(M, P[ks, 0], rcond=None)
                    cy, *_ = np.linalg.lstsq(M, P[ks, 1], rcond=None)
                    res = np.hypot(P[ks, 0] - M @ cx, P[ks, 1] - M @ cy)
                    good = res < max(1.5 * R, 3.0)
                    ks, tt, res = ks[good], tt[good], res[good]
                    if len(ks) < MIN_PTS:
                        continue
                    fs = F[ks]
                    span = np.where((fr_t >= T[ks].min() - 1e-9) & (fr_t <= T[ks].max() + 1e-9))[0]
                    # frames in span whose footprint contains the predicted position
                    frac = len(ks) / max(len(span), 1)
                    rate = np.hypot(cx[1], cy[1])
                    disp = rate * (tt.max() - tt.min())
                    if frac < 0.6 or disp < 3 * R or np.sqrt(np.mean(res ** 2)) > max(1.0, pixscale):
                        continue
                    used[ks] = True
                    ra_m, dec_m = untangent(cx[0], cy[0], ra0, dec0)
                    tracks.append(dict(
                        target=tgt, n=int(len(ks)), n_span=int(len(span)), frac=round(frac, 2),
                        rate_arcsec_min=round(rate, 3), disp_arcsec=round(disp, 1),
                        rms_arcsec=round(float(np.sqrt(np.mean(res ** 2))), 2),
                        mjd_mid=float(T[ks].mean()), ra_mid=float(ra_m), dec_mid=float(dec_m),
                        v_xi=float(cx[1]), v_eta=float(cy[1]),
                        flux_med=float(np.median(FL[ks])), peak_med=float(np.median(PK[ks])),
                        snr_hint=float(np.median(PK[ks]) / seq[0]['rms']),
                        frames=[int(f) for f in fs], xs=[float(v) for v in X[ks]], ys=[float(v) for v in Y[ks]],
                        mjds=[float(v) for v in T[ks]],
                        files=[seq[f]['path'] for f in fs],
                        seq_start=seq[0]['path'],
                    ))
    return info, tracks


def main():
    os.makedirs(OUT, exist_ok=True)
    cats = load()
    seqs = sequences(cats)
    print(len(cats), 'frames,', len(seqs), 'sequences', flush=True)
    infos, alltr, allev = [], [], []
    for s in seqs:
        info, tr = analyse(s)
        info['n_tracks'] = len(tr)
        allev += info.pop('_events', [])
        infos.append(info); alltr += tr
        print(f"{info['target'][:28]:28s} N={info['n_frames']:4d} cand={info.get('n_cand','-')!s:>6} tracks={len(tr)} {info.get('note','')}", flush=True)
    import csv
    with open(os.path.join(OUT, 'sequences.csv'), 'w', newline='', encoding='utf-8') as fh:
        keys = sorted({k for i in infos for k in i})
        w = csv.DictWriter(fh, keys); w.writeheader(); w.writerows(infos)
    with open(os.path.join(OUT, 'tracklets.json'), 'w', encoding='utf-8') as fh:
        json.dump(alltr, fh, indent=1)
    with open(os.path.join(OUT, 'events.json'), 'w', encoding='utf-8') as fh:
        json.dump(allev, fh, indent=1)
    print('total tracklets', len(alltr), 'streaks', sum(e['kind'] == 'streak' for e in allev),
          'flashes', sum(e['kind'] == 'flash' for e in allev))


if __name__ == '__main__':
    main()
