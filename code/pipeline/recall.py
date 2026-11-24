"""Stage 4: recall check - which known objects (SkyBoT) inside each sequence footprint did we detect?"""
import csv, json, os
import numpy as np
import warnings
warnings.filterwarnings('ignore')
from verify import skybot, OUT

seqs = list(csv.DictReader(open(os.path.join(OUT, 'sequences.csv'), encoding='utf-8')))
tr = json.load(open(os.path.join(OUT, 'tracklets_classified.json'), encoding='utf-8'))
found = {(t['seq_start'], t['known_name']) for t in tr if t['class'] == 'known'}
rows = []
for s in seqs:
    N = int(s['n_frames'])
    if N < 5 or 'note' in s and s['note']:
        continue
    ra, dec = float(s['ra0']), float(s['dec0'])
    mjd = (float(s['mjd0']) + float(s['mjd1'])) / 2
    fl = float(s['focallen'])
    hw = 6248 * 3.76 / fl * 206.265 / 3600 / 2 * 0.95   # half width deg
    hh = 4176 * 3.76 / fl * 206.265 / 3600 / 2 * 0.95
    k = skybot(ra, dec, mjd, float(np.hypot(hw, hh)))
    if not k:
        continue
    from astropy.io import fits
    from astropy.wcs import WCS
    w = WCS(fits.getheader(s['start']))
    for r in k:
        # position at first frame epoch, then through the first frame's own WCS
        dt = (float(s['mjd0']) - mjd) * 24
        kra = r['ra'] + r['dra'] * dt / 3600 / np.cos(np.radians(r['dec'])); kde = r['dec'] + r['ddec'] * dt / 3600
        px, py = w.all_world2pix(kra, kde, 0)
        if not (60 < px < 6248 - 60 and 60 < py < 4176 - 60):
            continue
        name = (r['number'] + ' ' + r['name']).strip('- ')
        rows.append(dict(target=s['target'], seq_start=s['start'], n_frames=N, exptime=s['exptime'],
                         name=name, type=r['type'], V=r['V'],
                         rate=round(np.hypot(r['dra'], r['ddec']) / 60, 3),
                         detected=(s['start'], name) in found))
rows.sort(key=lambda r: r['V'])
with open(os.path.join(OUT, 'recall.csv'), 'w', newline='', encoding='utf-8-sig') as fh:
    w = csv.DictWriter(fh, list(rows[0].keys())); w.writeheader(); w.writerows(rows)
for r in rows:
    if r['V'] < 19.5:
        print(f"{r['V']:5.1f} {'DET' if r['detected'] else '---'} {r['name'][:28]:28s} {r['rate']:.2f}\"/min {r['target'][:22]:22s} N={r['n_frames']} exp={r['exptime']}")
