"""장면별 1920x1080 정지 화면(카드, 도식, 직접 찍어 넣을 자리, 이미지 배치)을 만듭니다.
실행: python build_visuals.py   (Pillow, matplotlib 필요)
"""
import os, sys, json, textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle, Polygon, Wedge

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
from scenes import SCENES

OUT = os.path.join(HERE, 'out', 'frames'); os.makedirs(OUT, exist_ok=True)
W, H = 1920, 1080
BG = (9, 13, 26); GOLD = (232, 194, 122); FG = (236, 238, 245); DIM = (150, 160, 185); ORANGE = (255, 140, 40)
F = r'C:\Windows\Fonts'
def font(name, size): return ImageFont.truetype(os.path.join(F, name), size)
TITLE, BODY, MONO = 'georgia.ttf', 'segoeui.ttf', 'consola.ttf'

def bg_gradient():
    y = np.linspace(0, 1, H)[:, None, None]
    top, bot = np.array([16, 22, 44]), np.array(BG)
    arr = (top * (1 - y) + bot * y) * np.ones((1, W, 1))
    return Image.fromarray(arr.astype(np.uint8))

def fit(img, w, h, cover=False):
    s = (max if cover else min)(w / img.width, h / img.height)
    return img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)

def centered(draw, y, text, f, fill):
    for line in text.split('\n'):
        tw = draw.textlength(line, font=f)
        draw.text(((W - tw) / 2, y), line, font=f, fill=fill)
        y += f.size * 1.35
    return y

def place_image(path, pad=0):
    """이미지를 검은 화면 가운데에 2배 해상도로 배치 (ffmpeg에서 천천히 확대할 여유)."""
    im = Image.open(os.path.join(REPO, path)).convert('RGB')
    if path.endswith('M51_섬광_일직선.png'):        # 한글 제목을 영어로 덮어쓰기
        d = ImageDraw.Draw(im); d.rectangle([0, 0, im.width, 50], fill='white')
        f1, f2 = font(BODY, 17), font(BODY, 16)
        t = 'M51 frame 0019: three points on one straight line (red dashed)'
        d.text(((im.width - d.textlength(t, font=f1)) / 2, 3), t, font=f1, fill='black')
        for cx, t in ((207, 'Flash B'), (605, 'Flash A'), (1002, 'Trail C')):
            d.text((cx - d.textlength(t, font=f2) / 2, 27), t, font=f2, fill='black')
    canvas = Image.new('RGB', (W * 2, H * 2), (0, 0, 0))
    if os.path.isabs(path) or 'build/assets/' in path or 'build/photos/' in path:            # 직접 보정한 사진: 화면을 꽉 채우도록 가운데를 잘라 냄
        f = fit(im, W * 2, H * 2, cover=True)
        x0, y0 = (f.width - W * 2) // 2, (f.height - H * 2) // 2
        return f.crop((x0, y0, x0 + W * 2, y0 + H * 2))
    f = fit(im, W * 2 - pad * 2, H * 2 - pad * 2)
    canvas.paste(f, ((W * 2 - f.width) // 2, (H * 2 - f.height) // 2))
    return canvas

def card(title, body):
    im = bg_gradient(); d = ImageDraw.Draw(im)
    big = title.replace('.', '').replace(',', '').isdigit()
    tf = font(TITLE, 230 if big else 84)
    n = title.count('\n') + 1
    bl = [l for l in body.split('\n') if l] if body else []
    bf = font(BODY, 44)
    total = tf.size * 1.35 * n + (40 + bf.size * 1.5 * len(bl) if bl else 0)
    y = (H - total) / 2
    y = centered(d, y, title, tf, GOLD if big else FG)
    if bl:
        y += 40
        for line in bl:
            tw = d.textlength(line, font=bf); d.text(((W - tw) / 2, y), line, font=bf, fill=DIM); y += bf.size * 1.5
    return im

def placeholder(desc, bgpath):
    im = fit(Image.open(os.path.join(REPO, bgpath)).convert('RGB'), W, H, cover=True)
    im = im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H))
    im = ImageEnhance.Brightness(im.filter(ImageFilter.GaussianBlur(6))).enhance(0.35)
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = 360, 300, W - 360, H - 300
    for i in range(x0, x1, 40): d.line([(i, y0), (min(i + 22, x1), y0)], fill=ORANGE, width=5); d.line([(i, y1), (min(i + 22, x1), y1)], fill=ORANGE, width=5)
    for j in range(y0, y1, 40): d.line([(x0, j), (x0, min(j + 22, y1))], fill=ORANGE, width=5); d.line([(x1, j), (x1, min(j + 22, y1))], fill=ORANGE, width=5)
    y = centered(d, y0 + 110, 'YOUR FOOTAGE HERE', font(BODY.replace('ui', 'uib'), 64), ORANGE)
    lines = textwrap.wrap(desc, 48)
    centered(d, y + 30, '\n'.join(lines), font(BODY, 44), FG)
    return im

def cardimg(title, body, bgpath):
    im = fit(Image.open(os.path.join(REPO, bgpath)).convert('RGB'), W, H, cover=True)
    im = im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H))
    im = ImageEnhance.Brightness(im.filter(ImageFilter.GaussianBlur(3))).enhance(0.32)
    d = ImageDraw.Draw(im)
    y = centered(d, 430, title, font(TITLE, 72), FG)
    centered(d, y + 30, body, font(BODY, 44), GOLD)
    return im

def scroll_canvas(path):
    """폴더 목록 캡처: 목록 부분만 잘라 키우고, 세로로 긴 그림을 만듦 (assemble에서 위→아래 스크롤)"""
    im = Image.open(os.path.join(REPO, path)).convert('RGB')
    im = im.crop((0, 0, 760, im.height))
    w = 1240; im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    canvas = Image.new('RGB', (W, max(im.height, H)), (42, 42, 42))
    canvas.paste(im, ((W - w) // 2, 0))
    return canvas

def video_bg(label):
    im = bg_gradient(); d = ImageDraw.Draw(im)
    if label:
        f = font(TITLE, 54); tw = d.textlength(label, font=f)
        d.text(((W - tw) / 2, 50), label, font=f, fill=GOLD)
    return im

# ---------- matplotlib 도식 ----------
def mpl_fig():
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=np.array(BG) / 255)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 192); ax.set_ylim(0, 108); ax.axis('off')
    return fig, ax

def save_fig(fig, path):
    fig.savefig(path, facecolor=fig.get_facecolor()); plt.close(fig)

gold, fg, dim = np.array(GOLD) / 255, np.array(FG) / 255, np.array(DIM) / 255

def gen_sessions(path):
    fig, ax = mpl_fig()
    ax.text(96, 96, 'One target folder  →  separate sessions', ha='center', fontsize=40, color=fg)
    groups = [('Night 1', '700 mm', '0°', 9, '#5b8def'), ('Night 1', '700 mm', '90°', 6, '#46b3a0'),
              ('Night 2', '700 mm', '0°', 8, '#e8c27a'), ('Night 3', '620 mm', '0°', 10, '#d96c8a')]
    x = 14
    for i, (night, scope, rot, n, c) in enumerate(groups):
        x0 = x
        for k in range(n):
            ax.add_patch(Rectangle((x, 62), 3.2, 12, color=c)); x += 4.2
        ax.text((x0 + x - 1) / 2, 56, f'{night}\n{scope}\nrotation {rot}', ha='center', va='top', fontsize=20, color=dim, linespacing=1.4)
        ax.annotate('', xy=(x0, 80), xytext=(x - 1, 80), arrowprops=dict(arrowstyle='-', color=c, lw=3))
        ax.text((x0 + x - 1) / 2, 82, f'Session {"ABCD"[i]}', ha='center', fontsize=26, color=c)
        x += 7
    ax.text(96, 18, 'New session when the night, telescope, camera rotation (>5°), exposure or gain changes, or after a gap of 2+ hours.\n'
            'Flats are taken from the same night, same telescope, same rotation.', ha='center', fontsize=22, color=fg, linespacing=1.6)
    ax.text(96, 6, 'Nearly a year of imaging  →  89 sessions  →  76 stacks', ha='center', fontsize=28, color=gold)
    save_fig(fig, path)

def gen_pipeline(path):
    fig, ax = mpl_fig()
    ax.text(96, 97, 'astrohunt: one command, the whole pipeline', ha='center', fontsize=40, color=fg, family='Georgia')
    ax.add_patch(FancyBboxPatch((40, 79), 112, 8, boxstyle='round,pad=0.6', fc='#05070d', ec=dim, lw=1.5))
    ax.text(43, 83, '$ python astrohunt.py', va='center', fontsize=28, color='#7ee787', family='Consolas')
    def box(x, y, w, h, t, c=fg):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.8', fc=(1, 1, 1, 0.05), ec=c, lw=2))
        ax.text(x + w / 2, y + h / 2, t, ha='center', va='center', fontsize=20, color=c, linespacing=1.4)
    def arrow(x0, y0, x1, y1): ax.annotate('', xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle='->', color=dim, lw=2))
    box(6, 50, 22, 12, 'Raw photos\n(read only)')
    box(36, 50, 26, 12, 'Sort into sessions\n+ same-night flats')
    box(70, 50, 22, 12, 'Stack\n(Siril)')
    box(36, 22, 26, 12, 'Frame by frame:\nmoving objects, flashes')
    arrow(28.8, 56, 35.2, 56); arrow(62.8, 56, 69.2, 56); arrow(17, 49.2, 35.2, 28)
    outs = [('Faint asteroids\n(GPU shift-and-stack)', 64), ('New & variable stars\n(Gaia · VSX)', 48), ('Dust & gas\n(IRAS · Planck · Hα)', 32)]
    for t, y in outs:
        box(104, y, 32, 10, t, gold); arrow(92.8, 56, 103.2, y + 5)
    box(150, 38, 34, 14, 'Report\n+ list to check by eye', gold)
    for _, y in outs: arrow(136.8, y + 5, 149.2, 45)
    arrow(62.8, 28, 149.2, 42)
    ax.text(96, 8, 'Only new photos are processed  ·  temporary files are cleaned up  ·  code is open on GitHub', ha='center', fontsize=22, color=dim)
    save_fig(fig, path)

def gen_review(path):
    fig, ax = mpl_fig()
    ax.text(96, 95, 'REPORT_auto.md  —  "Check by eye"', ha='center', fontsize=40, color=fg, family='Georgia')
    rows = [('Kind', 'Session / target', 'Note', 'Image')]
    try:
        sig = json.load(open(os.path.join(REPO, 'data', 'ssa_significant.json'), encoding='utf-8'))
        for c in sig[:5]:
            rows.append(('shift-and-stack', c['sid'][:28], f"S/N {c['snr']:.1f}, {c['rate']:.2f}\"/min", '[view]'))
    except Exception:
        pass
    rows.append(('flash', '2026-04-17  M 51', 'single frame, 2 dots', '[view]'))
    xs = [12, 52, 112, 170]; y = 80
    for r, row in enumerate(rows):
        for x, cell in zip(xs, row):
            ax.text(x, y, cell, fontsize=24, color=gold if r == 0 else fg, family='Consolas', va='center')
        if r == 0: ax.plot([10, 182], [y - 4, y - 4], color=dim, lw=1.5)
        y -= 9
    ax.text(96, 6, 'The program filters.  People decide.', ha='center', fontsize=30, color=gold)
    save_fig(fig, path)

def gen_shadow(path):
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=np.array(BG) / 255)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_aspect('equal'); ax.axis('off')
    R = 6371.0
    ax.set_xlim(-11000, 13500); ax.set_ylim(-1500, 12300)
    ax.add_patch(Rectangle((0, -R), 14000, 2 * R, color='#000000', alpha=0.55, zorder=1))       # 그림자(원통 근사)
    ax.add_patch(Circle((0, 0), R, color='#1f4f8f', zorder=2))
    ax.add_patch(Wedge((0, 0), R, 90, 270, color='#e8c27a', alpha=0.18, zorder=3))
    for yy in (9500, 6000, 2500):
        ax.annotate('', xy=(-7200, yy), xytext=(-10500, yy), arrowprops=dict(arrowstyle='->', color=gold, lw=3))
    ax.text(-10500, 10300, 'Sunlight', color=gold, fontsize=30)
    ax.text(8200, 2500, "Earth's shadow", color=dim, fontsize=30)
    n = np.array([0.515, 0.857]); O = R * n                                  # 태양 고도 −31°인 관측자
    P = np.array([np.sqrt((R + 1120) ** 2 - R ** 2), R])                     # 시선이 그림자를 벗어나는 점
    for r_alt, lab, c in ((R + 420, 'Space station  ~420 km', '#9aa4b8'), (R + 550, 'Starlink  ~550 km', '#9aa4b8'), (R + 1120, '1,120 km', gold)):
        ax.add_patch(Circle((0, 0), r_alt, fill=False, ls='--', lw=1.5 if r_alt < R + 1000 else 2.5, ec=c, zorder=4))
    d = (P - O) / np.linalg.norm(P - O); Q = O + d * 9000
    ax.plot([O[0], Q[0]], [O[1], Q[1]], color='#7ee787', lw=3, zorder=5)
    ax.plot(*O, 'o', color='white', ms=12, zorder=6); ax.text(O[0] - 300, O[1] - 1900, 'Observer\nSun 31° below horizon', color=fg, fontsize=22, ha='right', zorder=6)
    ax.plot(*P, '*', color=gold, ms=30, zorder=7); ax.text(P[0] + 700, P[1] + 150, 'Sunlit only above\n1,120 km', color=gold, fontsize=26, zorder=7)
    ax.text(Q[0] - 600, Q[1] + 300, 'toward M51', color='#7ee787', fontsize=24)
    ax.text(-1500, -900, 'Earth', color=fg, fontsize=28, zorder=6)
    ax.text(-10800, 11500, 'Who could reflect sunlight at 3 a.m.?', color=fg, fontsize=38, family='Georgia')
    ax.text(8200, 1200, 'ISS (~420 km), Starlink (~550 km):\nalready in the shadow', color='#9aa4b8', fontsize=22, linespacing=1.5)
    save_fig(fig, path)

GEN = {'sessions': gen_sessions, 'pipeline': gen_pipeline, 'review': gen_review, 'shadow': gen_shadow}

def quote_frames(lines, bgpath, i):
    base = fit(Image.open(os.path.join(REPO, bgpath)).convert('RGB'), W, H, cover=True)
    base = base.crop(((base.width - W) // 2, (base.height - H) // 2, (base.width - W) // 2 + W, (base.height - H) // 2 + H))
    base = ImageEnhance.Brightness(base).enhance(0.45)
    shown = [k for k, l in enumerate(lines) if l]
    paths = []
    for step, upto in enumerate(shown):
        im = base.copy(); d = ImageDraw.Draw(im)
        y = 170
        for k, l in enumerate(lines):
            if not l: y += 40; continue
            f = font('georgiai.ttf' if k == len(lines) - 1 else TITLE, 44 if k == len(lines) - 1 else 52)
            if k <= upto:
                tw = d.textlength(l, font=f)
                d.text(((W - tw) / 2, y), ('—  ' + l) if k == len(lines) - 1 else l, font=f, fill=GOLD if k == len(lines) - 1 else FG)
            y += 82
        p = os.path.join(OUT, f'{i:02d}_q{step}.png'); im.save(p); paths.append(p)
    return paths

def label_for(path):
    b = os.path.basename(path).rsplit('.', 1)[0]
    names = {'single_vs_stack_M51': 'One frame  vs  stacked', 'asteroid_1675': '1675 Simonida', 'asteroid_1008': '1008 La Paz',
             'asteroid_275': '275 Sapientia', 'asteroid_C_2025': 'Comet C/2025 R3 (PANSTARRS)', 'variable_TT_Ori': 'TT Orionis',
             'variable_V808_Ori': 'V808 Orionis', 'variable_FN_Cep': 'FN Cephei', 'm51_flash_A': 'M51  ·  2026-04-18 03:01 KST',
             'm51_flash_B': 'Before  ·  during  ·  after'}
    return names.get(b, '')

manifest = []
for i, (sec, vis, lines) in enumerate(SCENES):
    kind = vis[0]; item = {'i': i, 'sec': sec, 'kind': kind}
    p = os.path.join(OUT, f'{i:02d}.png')
    if kind == 'img':
        place_image(vis[1]).save(p, quality=95); item['frame'] = p
    elif kind == 'card':
        card(vis[1], vis[2]).save(p); item['frame'] = p
    elif kind == 'ph':
        placeholder(vis[1], vis[2]).save(p); item['frame'] = p
    elif kind == 'gen':
        GEN[vis[1]](p); item['frame'] = p
    elif kind == 'cardimg':
        cardimg(vis[1], vis[2], vis[3]).save(p); item['frame'] = p
    elif kind == 'scroll':
        scroll_canvas(vis[1]).save(p); item['frame'] = p
    elif kind == 'vid':
        video_bg(label_for(vis[1])).save(p); item['frame'] = p; item['video'] = os.path.join(REPO, vis[1])
    elif kind == 'quote':
        item['frames'] = quote_frames(vis[1], vis[2], i)
    elif kind == 'pan':          # 화면은 assemble.py가 원본 사진에서 바로 렌더링
        item['photo'] = os.path.join(REPO, vis[1]); item['keys'] = vis[2]
    elif kind == 'skip':
        pass
    elif kind == 'motion':
        item['motion'] = os.path.join(HERE, 'out', 'motion', f'{i:02d}.mp4')
    manifest.append(item); print(i, kind, flush=True)
json.dump(manifest, open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8'), indent=1)
