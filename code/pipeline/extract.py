"""Stage 1: per-frame source extraction (read-only on FITS).

Each Light frame -> 2x2 superpixel luminance -> SEP detection -> RA/Dec via frame WCS.
Writes one small .npz catalog per frame into cache/ (skips frames already done).
"""
import glob, os, sys, time, traceback
import numpy as np
from multiprocessing import Pool

ROOT = 'h:/asiair/Autorun/Light'
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')


def cache_name(path):
    rel = os.path.relpath(path, ROOT).replace('\\', '/').replace('/', '__').replace(' ', '_')
    return os.path.join(CACHE, rel + '.npz')


def process(path):
    out = cache_name(path)
    if os.path.exists(out):
        return 'skip'
    try:
        import sep
        from astropy.io import fits
        from astropy.wcs import WCS
        from astropy.time import Time
        import warnings
        warnings.filterwarnings('ignore')
        with fits.open(path, memmap=False) as hd:
            h = hd[0].header
            d = hd[0].data.astype(np.float32)
        H, W = d.shape
        H2, W2 = H // 2 * 2, W // 2 * 2
        d = d[:H2, :W2]
        sp = (d[0::2, 0::2] + d[0::2, 1::2] + d[1::2, 0::2] + d[1::2, 1::2])
        sp = np.ascontiguousarray(sp)
        bkg = sep.Background(sp, bw=64, bh=64)
        sub = sp - bkg.back()
        rms = bkg.globalrms
        sep.set_extract_pixstack(2_000_000)
        sep.set_sub_object_limit(4096)
        objs = sep.extract(sub, 5.0, err=bkg.rms(), minarea=4, deblend_cont=0.005)
        # full-res 0-based pixel coords (superpixel i spans full pixels 2i, 2i+1)
        xf = 2 * objs['x'] + 0.5
        yf = 2 * objs['y'] + 0.5
        w = WCS(h)
        ra, dec = w.all_pix2world(xf, yf, 0)
        exp = float(h.get('EXPTIME', h.get('EXPOSURE', 0)))
        t0 = Time(h['DATE-OBS'], format='isot', scale='utc')
        mjd_mid = t0.mjd + exp / 2 / 86400
        satur = 4 * (65535 - 200)  # superpixel sum near saturation
        np.savez_compressed(
            out,
            path=path, mjd=mjd_mid, exptime=exp, W=W, H=H,
            focallen=float(h.get('FOCALLEN', 0)), rms=rms,
            back=float(np.median(bkg.back())),
            x=xf.astype(np.float32), y=yf.astype(np.float32),
            ra=ra, dec=dec,
            flux=objs['flux'].astype(np.float32), peak=objs['peak'].astype(np.float32),
            a=objs['a'].astype(np.float32), b=objs['b'].astype(np.float32),
            theta=objs['theta'].astype(np.float32), npix=objs['npix'].astype(np.int32),
            flag=objs['flag'].astype(np.int16),
            sat=(objs['peak'] + bkg.back()[objs['y'].astype(int).clip(0, H2 // 2 - 1),
                                           objs['x'].astype(int).clip(0, W2 // 2 - 1)] > satur * 0.95),
        )
        return 'ok'
    except Exception:
        return 'ERR ' + path + '\n' + traceback.format_exc()


if __name__ == '__main__':
    os.makedirs(CACHE, exist_ok=True)
    files = sorted(glob.glob(os.path.join(ROOT, '*', '*.fit')))
    if len(sys.argv) > 1:
        files = [f for f in files if any(k in f for k in sys.argv[1:])]
    print(len(files), 'frames', flush=True)
    t = time.time()
    n = 0
    with Pool(6) as p:
        for r in p.imap_unordered(process, files, chunksize=2):
            n += 1
            if r.startswith('ERR'):
                print(r, flush=True)
            if n % 100 == 0:
                el = time.time() - t
                print(f'{n}/{len(files)}  {el/60:.1f} min  eta {(len(files)-n)*el/n/60:.1f} min', flush=True)
    print('done', (time.time() - t) / 60, 'min')
