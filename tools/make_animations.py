"""영상용 애니메이션 만들기 (GIF + MP4).
 - 소행성/혜성 이동: 원본 프레임에서 하늘에 고정된 영역을 잘라 연속 재생
 - 변광성 깜빡이기: 두 세션 스택을 같은 밝기 기준(측광 영점)으로 맞춰 번갈아 보기
 - M51 섬광: 앞·뒤 프레임 비교
 - 한 장 vs 스택 비교
사용법: python make_animations.py [ast] [var] [flash] [stack]   (환경변수 HUNT_DIR = 분석 폴더)
영어 라벨: ANIM_LANG=en, 저장 폴더: ANIM_OUT=<폴더>"""
import os, sys, json, subprocess, numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from scipy.ndimage import map_coordinates, uniform_filter
from PIL import Image, ImageDraw, ImageFont
HUNT = os.environ.get('HUNT_DIR', r'C:\rasa_test\asteroid_hunt')
RAW = os.environ.get('RAW_DIR', r'h:/asiair/Autorun/Light')
sys.path.insert(0, os.path.join(HUNT, 'analysis'))
import common as C, transient as T
OUT = os.environ.get('ANIM_OUT') or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'animations')
EN = os.environ.get('ANIM_LANG', '').lower() == 'en'
def tr(ko, en): return en if EN else ko
os.makedirs(OUT, exist_ok=True)
try:
    FONT = ImageFont.truetype(r'C:\Windows\Fonts\malgun.ttf', 18)
except Exception:
    FONT = ImageFont.load_default()


def sky_grid(ra, dec, half, step):
    yy, xx = np.mgrid[-half:half + 1, -half:half + 1] * step / 3600.0
    return ra - xx / np.cos(np.radians(dec)), dec + yy      # 동쪽 왼쪽


def resample(img, w, ra, dec, half, step):
    """북쪽 위·동쪽 왼쪽 하늘 격자(1px = step″)로 다시 표본추출"""
    rr, dd = sky_grid(ra, dec, half, step)
    px, py = w.all_world2pix(rr.ravel(), dd.ravel(), 0, quiet=True)
    return map_coordinates(img, [py, px], order=1, mode='constant', cval=np.nan).reshape(rr.shape)[::-1]


def stretch(a, lo, hi, k=30):
    b = np.arcsinh(np.clip((np.nan_to_num(a, nan=lo) - lo) / (hi - lo), 0, 1) * k) / np.arcsinh(k)
    return (255 * b).astype(np.uint8)


def label(im, text, sub=None):
    im = im.convert('RGB'); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, im.width, 28], fill=(0, 0, 0)); d.text((6, 4), text, fill=(255, 255, 255), font=FONT)
    if sub:
        d.rectangle([0, im.height - 26, im.width, im.height], fill=(0, 0, 0))
        d.text((6, im.height - 24), sub, fill=(200, 200, 255), font=FONT)
    return im


def save(frames, name, ms):
    frames[0].save(os.path.join(OUT, name + '.gif'), save_all=True, append_images=frames[1:], duration=ms, loop=0)
    tmp = os.path.join(OUT, '_tmp'); os.makedirs(tmp, exist_ok=True)
    for i, f in enumerate(frames):
        f.save(os.path.join(tmp, f'{i:04d}.png'))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', f'{1000 / ms:.3f}', '-i', os.path.join(tmp, '%04d.png'),
                    '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', '30',
                    os.path.join(OUT, name + '.mp4')], check=False)
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    print('저장', name, len(frames), '프레임', flush=True)


def raw_frame(fn):
    with fits.open(fn) as hd:
        d = hd[0].data.astype(np.float32); h = hd[0].header
    return uniform_filter(d, 2), WCS(h), h      # 베이어 패턴 2x2 평균 → 휘도


def asteroid_anim(idx, name, half=110, maxf=60):
    t = json.load(open(os.path.join(HUNT, 'results', 'tracklets_classified.json'), encoding='utf-8'))[idx]
    files = t['files'][:maxf]
    ra, dec = t['ra_mid'], t['dec_mid']
    imgs, times, step = [], [], None
    for fn in files:
        d, w, h = raw_frame(fn)
        step = step or float(np.sqrt(abs(np.linalg.det(w.pixel_scale_matrix))) * 3600)
        imgs.append(resample(d, w, ra, dec, half, step)); times.append(h.get('DATE-OBS', '')[:19])
    # 프레임마다 하늘 배경을 빼고, 공통 밝기 폭(중앙 프레임 잡음 기준)으로 표시
    sig = [1.4826 * np.nanmedian(np.abs(a - np.nanmedian(a))) for a in imgs]
    s = float(np.median(sig))
    sz = (2 * (2 * half + 1),) * 2
    frames = [label(Image.fromarray(stretch(a - np.nanmedian(a), -1.5 * s, 80 * s)).resize(sz, Image.LANCZOS), f"{name}  ({t['target']})", f'{tm} UTC')
              for a, tm in zip(imgs, times)]
    save(frames, 'asteroid_' + name.split()[0].replace('/', '_'), 120 if len(frames) > 20 else 300)


def variable_blink(name, ra, dec, sa, sb, half=60, step=1.5):
    ims, labs = [], []
    for sid in (sa, sb):
        d, h, info = C.load_stack(sid); L = C.lum(d); k = T.load_cat(sid)
        a = resample(L, k['wcs'], ra, dec, half, step)
        a = (a - np.nanmedian(a)) * 10 ** (-0.4 * float(k['zp'])) * (step / float(k['scale'])) ** 2 * 1e9   # 같은 등급 기준
        ims.append(a); labs.append(sid[:10])
    s = 1.4826 * np.nanmedian(np.abs(ims[0] - np.nanmedian(ims[0])))
    pk = np.nanpercentile(np.concatenate([i.ravel() for i in ims]), 99.9)
    fr = []
    for a, lb in zip(ims, labs):
        im = Image.fromarray(stretch(a, -2 * s, pk)).resize((4 * half + 2,) * 2, Image.LANCZOS).convert('RGB')
        dr = ImageDraw.Draw(im); c = 2 * half + 1
        dr.line([c - 40, c, c - 18, c], fill=(255, 200, 0), width=2); dr.line([c, c - 40, c, c - 18], fill=(255, 200, 0), width=2)
        fr.append(label(im, name, tr(f'{lb} 스택', f'{lb} stack')))
    save(fr, 'variable_' + name.split()[0] + '_' + name.split()[1], 700)


def m51_flash():
    base = os.path.join(RAW, 'M 51')
    fl = sorted(f for f in os.listdir(base) if f.endswith('.fit') and '20260418-0' in f)
    sel = [f for f in fl if f.endswith(('_0018.fit', '_0019.fit', '_0020.fit'))]
    for nm, (x, y) in {'A': (1730, 1659), 'B': (1328, 1242)}.items():
        crops = []
        for f in sel:
            d, w, h = raw_frame(os.path.join(base, f))
            crops.append((d[y - 60:y + 61, x - 60:x + 61], f[-8:-4]))
        ref = crops[0][0]; lo = np.median(ref); s = 1.4826 * np.median(np.abs(ref - lo))
        fr = [label(Image.fromarray(stretch(a, lo - s, lo + 150 * s)[::-1]).resize((363, 363), Image.NEAREST), tr(f'M51 섬광 {nm}', f'M51 flash {nm}'), tr(f'프레임 {n} (5분 노출)', f'frame {n} (5-min exposure)'))
              for a, n in crops]
        save(fr, f'm51_flash_{nm}', 900)


def single_vs_stack(sid, rawdir, day, ra, dec, title, half=300):
    fn = sorted(os.path.join(rawdir, f) for f in os.listdir(rawdir) if f.endswith('.fit') and day in f)[0]
    d, w, h = raw_frame(fn)
    step = float(np.sqrt(abs(np.linalg.det(w.pixel_scale_matrix))) * 3600) * 1.5
    a = resample(d, w, ra, dec, half, step)
    D, hh, info = C.load_stack(sid); k = T.load_cat(sid)
    b = resample(C.lum(D), k['wcs'], ra, dec, half, step)
    out = []
    for img, lb in ((a, tr('한 장 (노출 1회)', 'single frame')), (b, tr(f"스택 ({info['n_registered']}장 합성)", f"stack of {info['n_registered']} frames"))):
        m = np.nanmedian(img); s = 1.4826 * np.nanmedian(np.abs(img - m))
        out.append(label(Image.fromarray(stretch(img, m - 2 * s, np.nanpercentile(img, 99.95))), title, lb))
    W = Image.new('RGB', (out[0].width * 2 + 10, out[0].height)); W.paste(out[0], (0, 0)); W.paste(out[1], (out[0].width + 10, 0))
    W.save(os.path.join(OUT, f'single_vs_stack_{title}.png'))
    save(out, f'single_vs_stack_{title}', 1200)


if __name__ == '__main__':
    job = sys.argv[1:] or ['ast', 'var', 'flash', 'stack']
    if 'ast' in job:
        asteroid_anim(144, '275 Sapientia')
        asteroid_anim(278, '1675 Simonida')
        asteroid_anim(292, '1008 La Paz')
        asteroid_anim(1, tr('C/2025 R3 PANSTARRS 혜성', 'C/2025 R3 PANSTARRS (comet)'), half=140)
    if 'var' in job:
        m42a, m42b = '2026-09-14_M_42_620mm_10s', '2026-10-08_M_42_620mm_10s'
        variable_blink(tr('TT Ori (오리온 젊은 별)', 'TT Ori (young star in Orion)'), 83.8197, -4.7624, m42a, m42b)
        variable_blink(tr('V808 Ori (오리온 젊은 별)', 'V808 Ori (young star in Orion)'), 83.9422, -5.1810, m42a, m42b)
        variable_blink(tr('AH Ori (오리온 젊은 별)', 'AH Ori (young star in Orion)'), 83.8572, -5.1637, m42a, m42b)
        variable_blink(tr('FN Cep (식쌍성)', 'FN Cep (eclipsing binary)'), 313.1844, 68.0962, '2026-06-27_NGC_7023_620mm_180s', '2026-08-07_NGC_7023_620mm_60s')
    if 'flash' in job:
        m51_flash()
    if 'stack' in job:
        single_vs_stack('2026-04-20_M_51_857mm_300s', os.path.join(RAW, 'M 51'), '20260420', 202.4696, 47.1952, 'M51')
