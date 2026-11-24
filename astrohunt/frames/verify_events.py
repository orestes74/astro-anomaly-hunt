"""Stage 3b: image-based vetting of single-frame flashes + streak summary.

flash classes:
  cosmic/hot  - full-res size sigma < 1.3 px (sharper than any star PSF)
  on-streak   - lies on the line of a streak in the same frame (satellite flare / trail piece)
  extended    - much larger than stars (nebula knot / halo / reflection)
  flash-candidate - star-like PSF, only in this frame, not on a streak
"""
import sys as _s, os as _o; _s.path.insert(0, _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))); import cfg
import json, os, glob, csv
import numpy as np
import warnings
warnings.filterwarnings('ignore')
from astropy.io import fits
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = cfg.WORK
OUT = cfg.FRAME_RESULTS
CUT = os.path.join(OUT, 'flash_cutouts')


def moments(d, x, y, hw=10):
    x, y = int(round(x)), int(round(y))
    big = d[max(0, y - 40):y + 40, max(0, x - 40):x + 40]
    bg = np.median(big)
    if y - hw < 0 or x - hw < 0 or y + hw + 1 > d.shape[0] or x + hw + 1 > d.shape[1]:
        return np.nan, np.nan, np.nan
    c = d[y - hw:y + hw + 1, x - hw:x + hw + 1] - bg
    # recentre on the brightest 3x3 sum
    yy, xx = np.mgrid[-hw:hw + 1, -hw:hw + 1]
    w = c.clip(0)
    w[w < 0.1 * w.max()] = 0
    t = w.sum() + 1e-9
    mx, my = (w * xx).sum() / t, (w * yy).sum() / t
    sx = np.sqrt((w * (xx - mx) ** 2).sum() / t); sy = np.sqrt((w * (yy - my) ** 2).sum() / t)
    return float(sx), float(sy), float(c.max())


def phot(d, x, y, r=4, r1=8, r2=14):
    """superpixel aperture flux and brightest-superpixel fraction (Bayer-neutral)"""
    if not (np.isfinite(x) and np.isfinite(y)):
        return np.nan, np.nan
    cx, cy = int((x - 0.5) / 2), int((y - 0.5) / 2)
    y0, x0 = 2 * (cy - r2), 2 * (cx - r2)
    if y0 < 0 or x0 < 0 or y0 + 4 * r2 + 2 > d.shape[0] or x0 + 4 * r2 + 2 > d.shape[1]:
        return np.nan, np.nan
    c = d[y0:y0 + 4 * r2 + 2, x0:x0 + 4 * r2 + 2]
    s = c[0::2, 0::2] + c[0::2, 1::2] + c[1::2, 0::2] + c[1::2, 1::2]
    yy, xx = np.mgrid[:s.shape[0], :s.shape[1]] - r2
    rr = np.hypot(xx, yy)
    bg = np.median(s[(rr > r1) & (rr < r2)])
    ap = (s - bg)[rr <= r]
    f = float(ap.sum())
    return f, float(ap.max() / f) if f > 0 else np.nan


def star_sigma(d, cat):
    # median moment size of moderately bright stars from the frame's catalogue
    idx = np.argsort(-cat['peak'])
    sel = [k for k in idx if not cat['sat'][k] and cat['a'][k] > 0.9][20:60]
    vals = []
    for k in sel:
        sx, sy, _ = moments(d, cat['x'][k], cat['y'][k])
        if np.isfinite(sx):
            vals.append((sx + sy) / 2)
    return float(np.median(vals)) if vals else np.nan


def on_streak(e, streaks):
    for s in streaks:
        th = np.radians(s['angle_deg'])
        ux, uy = np.cos(th), np.sin(th)
        dx, dy = e['x'] - s['x'], e['y'] - s['y']
        if abs(-uy * dx + ux * dy) < 25:
            return True
    return False


def main():
    os.makedirs(CUT, exist_ok=True)
    ev = json.load(open(os.path.join(OUT, 'events.json'), encoding='utf-8'))
    streaks = [e for e in ev if e['kind'] == 'streak']
    flashes = [e for e in ev if e['kind'] == 'flash']
    sbf = {}
    for s in streaks:
        sbf.setdefault(s['file'], []).append(s)
    from extract import cache_name
    out = []
    for n, e in enumerate(flashes):
        d = fits.getdata(e['file']).astype(np.float32)
        cat = np.load(cache_name(e['file']))
        sx, sy, pk = moments(d, e['x'], e['y'])
        ss = star_sigma(d, cat)
        e['sigma_px'] = round((sx + sy) / 2, 2); e['star_sigma_px'] = round(ss, 2)
        e['elong'] = round(max(sx, sy) / max(min(sx, sy), 1e-3), 2)
        f0, pf = phot(d, e['x'], e['y'])
        idx = np.argsort(-cat['peak'])
        spf = [phot(d, cat['x'][k], cat['y'][k])[1] for k in idx[20:80] if not cat['sat'][k]]
        spf = float(np.nanmedian(spf)) if spf else np.nan
        e['peakfrac'] = round(pf, 3); e['star_peakfrac'] = round(spf, 3)
        # same sky spot in neighbouring frames
        from astropy.wcs import WCS
        fs_all = sorted(glob.glob(os.path.dirname(e['file']) + '/*.fit'))
        ii = fs_all.index(e['file'])
        ra, dec = WCS(fits.getheader(e['file'])).all_pix2world(e['x'], e['y'], 0)
        nb = []
        for j in (ii - 1, ii + 1):
            if 0 <= j < len(fs_all):
                xj, yj = WCS(fits.getheader(fs_all[j])).all_world2pix(ra, dec, 0)
                nb.append(phot(fits.getdata(fs_all[j]).astype(np.float32), float(xj), float(yj))[0])
        e['nb_flux_ratio'] = round(max(nb) / f0, 3) if nb and f0 > 0 else None
        # short flashes are legitimately sharper than long-exposure stars (no seeing/guiding blur);
        # cosmic rays / hot pixels are far sharper still
        if (e['sigma_px'] < 1.3 or not np.isfinite(pf) or pf > 0.25
                or (np.isfinite(spf) and pf > 3.0 * spf)):
            e['class'] = 'cosmic/hot'
        elif e['nb_flux_ratio'] is None or e['nb_flux_ratio'] > 0.3:
            e['class'] = 'persistent(not-transient)'
        elif on_streak(e, sbf.get(e['file'], [])):
            e['class'] = 'on-streak'
        elif np.isfinite(ss) and e['sigma_px'] > 2.5 * ss:
            e['class'] = 'extended'
        elif e['elong'] > 1.8:
            e['class'] = 'short-trail'
        else:
            e['class'] = 'flash-candidate'
        out.append(e)
        if e['class'] in ('flash-candidate', 'short-trail'):
            fs = sorted(glob.glob(os.path.dirname(e['file']) + '/*.fit'))
            i = fs.index(e['file'])
            fig, axs = plt.subplots(1, 3, figsize=(7, 2.6))
            for ax, j in zip(axs, (i - 1, i, i + 1)):
                ax.set_xticks([]); ax.set_yticks([])
                if 0 <= j < len(fs):
                    dd = d if j == i else fits.getdata(fs[j]).astype(np.float32)
                    x, y = int(e['x']), int(e['y'])
                    c = dd[max(0, y - 50):y + 50, max(0, x - 50):x + 50]
                    m = np.median(c); s = np.median(abs(c - m)) * 1.48 + 1
                    ax.imshow(np.arcsinh((c - m) / (3 * s)), cmap='gray', origin='lower', vmin=-.5, vmax=5)
                    ax.set_title(os.path.basename(fs[j])[-26:-4], fontsize=6)
            fig.suptitle(f"{e['target']} {e['class']} sigma={e['sigma_px']} (stars {e['star_sigma_px']}) snr={e['snr']:.0f}", fontsize=8)
            fig.tight_layout()
            fig.savefig(os.path.join(CUT, f"F{n:03d}_{e['class']}_{e['target'].replace(' ', '_')}.png"), dpi=90)
            plt.close(fig)
            e['cutout'] = f"F{n:03d}"
        if n % 25 == 0:
            print(n, len(flashes), flush=True)
    keys = ['cutout', 'class', 'target', 'file', 'x', 'y', 'snr', 'sigma_px', 'star_sigma_px', 'elong', 'peakfrac', 'star_peakfrac', 'nb_flux_ratio', 'mjd']
    with open(os.path.join(OUT, 'flashes.csv'), 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, keys, extrasaction='ignore'); w.writeheader(); w.writerows(out)
    with open(os.path.join(OUT, 'streaks.csv'), 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, ['target', 'file', 'mjd', 'x', 'y', 'angle_deg', 'length_px', 'pieces', 'snr'], extrasaction='ignore')
        w.writeheader(); w.writerows(streaks)
    import collections
    print(collections.Counter(e['class'] for e in out))


if __name__ == '__main__':
    main()
