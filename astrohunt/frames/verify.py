"""Stage 3: classify tracklets against known solar-system objects (IMCCE SkyBoT) and make cutouts.

Only sequence centre coordinates + epoch are sent to SkyBoT. FITS stay read-only.
Output: results/report.csv, results/cutouts/*.png
"""
import sys as _s, os as _o; _s.path.insert(0, _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))); import cfg
import json, os, csv, time, hashlib
import numpy as np
import warnings
warnings.filterwarnings('ignore')
from astropy.coordinates import SkyCoord
from astropy.time import Time
import astropy.units as u

HERE = cfg.WORK
OUT = cfg.FRAME_RESULTS
CUT = os.path.join(OUT, 'cutouts')
SKYCACHE = cfg.SKYBOT_CACHE


def skybot(ra, dec, mjd, rad_deg):
    from astroquery.imcce import Skybot
    key = hashlib.md5(f'{ra:.3f}{dec:.3f}{mjd:.4f}{rad_deg:.2f}'.encode()).hexdigest()
    fn = os.path.join(SKYCACHE, key + '.json')
    if os.path.exists(fn):
        return json.load(open(fn))
    rows = []
    for attempt in range(3):
        try:
            # 지구 중심('500') 기준 조회: 관측지 시차는 대조 반경보다 훨씬 작음
            r = Skybot.cone_search(SkyCoord(ra * u.deg, dec * u.deg), rad_deg * u.deg,
                                   Time(mjd, format='mjd'), location='500', cache=False)
            for x in r:
                rows.append(dict(name=str(x['Name']), number=str(x['Number']), type=str(x['Type']),
                                 ra=float(x['RA'].to(u.deg).value) if hasattr(x['RA'], 'to') else float(x['RA']),
                                 dec=float(x['DEC'].to(u.deg).value) if hasattr(x['DEC'], 'to') else float(x['DEC']),
                                 V=float(x['V'].value if hasattr(x['V'], 'value') else x['V']),
                                 dra=float(x['RA_rate'].to(u.arcsec / u.hour).value),
                                 ddec=float(x['DEC_rate'].to(u.arcsec / u.hour).value)))
            break
        except RuntimeError as e:  # "No solar system object was found"
            if 'No solar system object' in str(e):
                break
            time.sleep(3)
        except Exception:
            time.sleep(3)
    else:
        return None
    os.makedirs(SKYCACHE, exist_ok=True)
    json.dump(rows, open(fn, 'w'))
    return rows


def cutouts(t, fn, half=40):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from astropy.io import fits
    idx = np.linspace(0, t['n'] - 1, min(6, t['n'])).round().astype(int)
    fig, axs = plt.subplots(1, len(idx), figsize=(2.2 * len(idx), 2.5))
    for ax, i in zip(np.atleast_1d(axs), idx):
        d = fits.getdata(t['files'][i]).astype(np.float32)
        sp = d[0::2, 0::2] + d[0::2, 1::2] + d[1::2, 0::2] + d[1::2, 1::2]
        cx, cy = int(round((t['xs'][i] - 0.5) / 2)), int(round((t['ys'][i] - 0.5) / 2))
        c = sp[max(0, cy - half):cy + half, max(0, cx - half):cx + half]
        med = np.median(c); mad = np.median(np.abs(c - med)) * 1.48 + 1
        ax.imshow(np.arcsinh((c - med) / (3 * mad)), cmap='gray', origin='lower', vmin=-0.5, vmax=4)
        ax.plot([half], [half], 'o', mfc='none', mec='r', ms=14)
        ax.set_title(os.path.basename(t['files'][i])[-25:-4], fontsize=6)
        ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle(f"{t['target']}  {t['rate_arcsec_min']:.2f}\"/min  n={t['n']}  {t.get('class','')} {t.get('known_name','')}", fontsize=8)
    fig.tight_layout()
    fig.savefig(fn, dpi=110)
    plt.close(fig)


def main():
    os.makedirs(CUT, exist_ok=True)
    tr = json.load(open(os.path.join(OUT, 'tracklets.json'), encoding='utf-8'))
    seqinfo = {}
    for i, t in enumerate(tr):
        tid = f'T{i:03d}'
        t['id'] = tid
        if 'C2025' in t['target'] or 'comet' in t['target'].lower():
            pass
        # one SkyBoT query per sequence (centre, mid epoch)
        key = t['seq_start']
        if key not in seqinfo:
            same = [u_ for u_ in tr if u_['seq_start'] == key]
            ra = np.mean([u_['ra_mid'] for u_ in same]); dec = np.mean([u_['dec_mid'] for u_ in same])
            mjd = np.mean([u_['mjd_mid'] for u_ in same])
            seqinfo[key] = (ra, dec, mjd, skybot(ra, dec, mjd, 1.2))
        ra0, dec0, mjd0, rows = seqinfo[key]
        t['known_name'] = ''; t['known_V'] = ''; t['known_sep'] = ''
        if rows is None:
            t['class'] = 'skybot-failed'
        else:
            best = None
            dt = (t['mjd_mid'] - mjd0) * 24
            for r in rows:
                kra = r['ra'] + r['dra'] * dt / 3600 / np.cos(np.radians(r['dec']))
                kde = r['dec'] + r['ddec'] * dt / 3600
                s = SkyCoord(kra * u.deg, kde * u.deg).separation(SkyCoord(t['ra_mid'] * u.deg, t['dec_mid'] * u.deg)).arcsec
                krate = np.hypot(r['dra'], r['ddec']) / 60
                if best is None or s < best[0]:
                    best = (s, r, krate)
            if best and best[0] < 30 and abs(best[2] - t['rate_arcsec_min']) < 0.3 * best[2] + 0.1:
                t['class'] = 'known'
                t['known_name'] = (best[1]['number'] + ' ' + best[1]['name']).strip('- ')
                t['known_V'] = best[1]['V']; t['known_sep'] = round(best[0], 1)
            else:
                t['class'] = 'unidentified'
                if best:
                    t['known_sep'] = round(best[0], 1); t['known_name'] = '(nearest) ' + best[1]['name']
        print(tid, t['target'][:20], t['class'], t['known_name'], t['known_V'], t['known_sep'], flush=True)
        try:
            cutouts(t, os.path.join(CUT, f"{tid}_{t['class']}_{t['target'].replace(' ', '_')}.png"))
        except Exception as e:
            print('cutout fail', tid, e)
    keys = ['id', 'class', 'target', 'known_name', 'known_V', 'known_sep', 'n', 'n_span', 'frac', 'rate_arcsec_min',
            'disp_arcsec', 'rms_arcsec', 'snr_hint', 'ra_mid', 'dec_mid', 'mjd_mid', 'seq_start']
    with open(os.path.join(OUT, 'report.csv'), 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, keys, extrasaction='ignore'); w.writeheader()
        for t in tr:
            t2 = dict(t); t2['utc_mid'] = Time(t['mjd_mid'], format='mjd').isot
            w.writerow(t2)
    json.dump(tr, open(os.path.join(OUT, 'tracklets_classified.json'), 'w', encoding='utf-8'), indent=1)


if __name__ == '__main__':
    main()
