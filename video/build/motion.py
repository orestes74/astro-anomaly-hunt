"""모션 그래픽 장면을 만듭니다 (matplotlib로 그린 프레임 → ffmpeg).
장면 길이는 내레이션 길이(out/tts/meta.json)에 맞춥니다.
실행: python motion.py [장면 번호 ...]
"""
import os, sys, json, subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle, Wedge
from scipy.ndimage import gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scenes import SCENES

OUT = os.path.join(HERE, 'out', 'motion'); os.makedirs(OUT, exist_ok=True)
FPS = 30
BG = np.array((9, 13, 26)) / 255; TOP = np.array((16, 22, 44)) / 255
GOLD = np.array((232, 194, 122)) / 255; FG = np.array((236, 238, 245)) / 255; DIM = np.array((150, 160, 185)) / 255
RED = '#ff5a5a'; GREEN = '#7ee787'; BLUE = '#5b9dff'
SERIF = 'Georgia'
GRAD = (TOP[None, None] * (1 - np.linspace(0, 1, 108)[:, None, None]) + BG[None, None] * np.linspace(0, 1, 108)[:, None, None]) * np.ones((1, 2, 1))

def ease(x): x = np.clip(x, 0, 1); return x * x * (3 - 2 * x)
def win(t, a, b): return ease((t - a) / max(b - a, 1e-6))

def stars(n, seed, x0=0, x1=192, y0=0, y1=108):
    r = np.random.default_rng(seed)
    x = r.uniform(x0, x1, n); y = r.uniform(y0, y1, n)
    m = r.exponential(1, n)
    return x, y, np.clip(4 + 40 * m ** 2, 3, 400), np.clip(.25 + .35 * m, .2, 1)

def draw_stars(ax, st, alpha=1.0, color='white', z=2):
    x, y, s, a = st
    ax.scatter(x, y, s=s * .6, c=[(*matplotlib.colors.to_rgb(color), min(1, v * alpha)) for v in a], linewidths=0, zorder=z)

def text(ax, x, y, s, size, color=FG, alpha=1, serif=False, ha='center', va='center', **k):
    if alpha <= 0.01: return
    k.setdefault('family', SERIF if serif else None)
    ax.text(x, y, s, fontsize=size, color=color, alpha=alpha, ha=ha, va=va, **k)

def render(i, dur, draw):
    n = int(round(dur * FPS))
    path = os.path.join(OUT, f'{i:02d}.mp4')
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', '1920x1080', '-r', str(FPS),
                          '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', path], stdin=subprocess.PIPE)
    for f in range(n):
        fig.clf(); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 192); ax.set_ylim(0, 108); ax.axis('off')
        ax.imshow(GRAD, extent=(0, 192, 0, 108), aspect='auto', zorder=0)
        draw(ax, f / FPS, dur)
        fig.canvas.draw(); p.stdin.write(fig.canvas.buffer_rgba().tobytes())
    p.stdin.close(); p.wait(); plt.close(fig)
    print('motion', i, f'{dur:.1f}s', flush=True)

# ---------------------------------------------------------------- 장면들
ST = stars(260, 1)

def m_three(ax, t, T):
    text(ax, 96, 92, 'Three ways to find something new', 44, alpha=win(t, 0, 1), serif=True)
    for k, (lab, sub) in enumerate((('MOVE', 'asteroids · comets'), ('CHANGE', 'novae · variable stars'), ('SPREAD', 'dust · gas'))):
        a = win(t, .8 + k * .8, 1.6 + k * .8); cx = 40 + k * 56
        if a <= 0: continue
        ax.add_patch(Circle((cx, 52), 20, fc=(1, 1, 1, .04 * a), ec=(*GOLD, a), lw=2, zorder=1))
        if k == 0:
            for j in range(6):
                ph = (t * .5 + j * .06) % 1
                ax.plot(cx - 14 + 28 * ph, 44 + 16 * ph, 'o', color=GOLD, alpha=a * (.15 + .85 * (j == 0)), ms=6 if j == 0 else 3)
        elif k == 1:
            b = .5 + .5 * np.sin(t * 3)
            ax.plot(cx, 52, '*', color='white', ms=12 + 22 * b, alpha=a)
        else:
            ax.add_patch(Circle((cx - 4, 50), 12, fc=(.9, .3, .4, .25 * a), lw=0)); ax.add_patch(Circle((cx + 6, 56), 9, fc=(.35, .5, 1, .25 * a), lw=0))
        text(ax, cx, 24, lab, 30, GOLD, a); text(ax, cx, 18, sub, 18, DIM, a)

def m_move(ax, t, T):
    draw_stars(ax, ST)
    p = ease(t / T)
    for j in range(14):
        q = p - j * .012
        if q < 0: break
        ax.plot(30 + 130 * q, 25 + 55 * q, 'o', color=GOLD, ms=7 if j == 0 else 4, alpha=1 if j == 0 else .5 * (1 - j / 14), zorder=3)
    ax.add_patch(Circle((30 + 130 * p, 25 + 55 * p), 4, fill=False, ec=GOLD, lw=1.5, zorder=3))
    text(ax, 12, 98, '1.  Things that MOVE', 40, alpha=win(t, 0, 1), serif=True, ha='left')
    text(ax, 12, 90, 'asteroids · comets — the stars stay put, one dot moves', 22, DIM, win(t, .8, 1.8), ha='left')
    text(ax, 180, 6, f'frame {int(t * 2) + 1}', 18, DIM, ha='right')

def m_change(ax, t, T):
    draw_stars(ax, stars(200, 2, 0, 120))
    b = .5 + .5 * np.sin(2 * np.pi * t / 4)
    ax.plot(60, 50, '*', color='white', ms=8 + 34 * b, zorder=3)
    ax.plot([60 - 10, 60 - 5], [50, 50], color=GOLD, lw=2); ax.plot([60, 60], [50 + 5, 50 + 10], color=GOLD, lw=2)
    x0, y0, w, h = 128, 30, 56, 36
    ax.add_patch(Rectangle((x0, y0), w, h, fill=False, ec=DIM, lw=1))
    tt = np.linspace(0, t, max(2, int(t * 10)))
    ax.plot(x0 + w * (tt / T), y0 + 4 + (h - 8) * (.5 + .5 * np.sin(2 * np.pi * tt / 4)), color=GOLD, lw=2.5)
    text(ax, x0 + w / 2, y0 - 4, 'brightness over time', 18, DIM)
    text(ax, 12, 98, '2.  Things that CHANGE', 40, alpha=win(t, 0, 1), serif=True, ha='left')
    text(ax, 12, 90, 'novae · supernovae · variable stars', 22, DIM, win(t, .8, 1.8), ha='left')

NEB = None
def m_spread(ax, t, T):
    global NEB
    if NEB is None:
        r = np.random.default_rng(3); a = gaussian_filter(r.normal(size=(108, 192)), 9); b = gaussian_filter(r.normal(size=(108, 192)), 14)
        a = np.clip((a - a.mean()) / a.std(), 0, 3) / 3; b = np.clip((b - b.mean()) / b.std(), 0, 3) / 3
        NEB = np.dstack([.95 * a + .2 * b, .25 * a + .35 * b, .35 * a + .9 * b, np.clip(a + b, 0, 1) * .85])
    ax.imshow(NEB * np.array([1, 1, 1, win(t, .5, T * .6)]), extent=(0, 192, 0, 108), aspect='auto', zorder=1)
    draw_stars(ax, ST, z=2)
    text(ax, 12, 98, '3.  Things that SPREAD', 40, alpha=win(t, 0, 1), serif=True, ha='left')
    text(ax, 12, 90, 'faint cosmic dust and gas along the Milky Way', 22, DIM, win(t, .8, 1.8), ha='left')

MAPST = stars(70, 5, 20, 172, 18, 80)
def m_map(ax, t, T):
    x, y, s, a = MAPST
    text(ax, 96, 98, 'Compare with the map.  Find what is not on it.', 38, alpha=win(t, 0, 1.2), serif=True)
    # 1) 사진의 별, 2) Gaia 지도 원이 내려와 겹침, 3) 지도에 없는 별 강조
    draw_stars(ax, (x, y, s, a), alpha=win(t, .5, 3))
    odd = (120, 40)
    ax.plot(*odd, '*', color='white', ms=14, alpha=win(t, 2, 4), zorder=3)
    k = int(len(x) * win(t, 5, 16))
    drop = 1 - win(t, 4, 7)
    for j in range(len(x)):
        if j < k:
            ax.add_patch(Circle((x[j], y[j] + 10 * drop), 1.8, fill=False, ec=BLUE, lw=1.2, alpha=.9, zorder=4))
    text(ax, 30, 88, f'matched with Gaia: {k}', 22, BLUE, win(t, 5, 6), ha='left')
    if t > 17:
        r = 3 + 1.5 * np.sin((t - 17) * 4)
        ax.add_patch(Circle(odd, r, fill=False, ec=RED, lw=2.5, zorder=5))
        text(ax, odd[0] + 7, odd[1] + 5, 'not on the map  →  candidate', 24, RED, win(t, 17, 18.5), ha='left')
    text(ax, 96, 10, 'Gaia DR3: 1.8 billion stars   ·   ~1.4 million known asteroids', 24, GOLD, win(t, 25, 27))

SESS = [('Night 1', '700 mm', '0°', 9, '#5b8def'), ('Night 1', '700 mm', '90°', 6, '#46b3a0'), ('Night 2', '700 mm', '0°', 8, '#e8c27a'), ('Night 3', '620 mm', '0°', 10, '#d96c8a')]
def m_sessions(ax, t, T):
    text(ax, 96, 96, 'One target folder  →  separate sessions', 40, alpha=win(t, 0, 1))
    tot = sum(g[3] for g in SESS); k = 0; gap = 7 * win(t, 8, 11); color_a = win(t, 6, 8); x = 14
    for gi, (night, scope, rot, n, c) in enumerate(SESS):
        x0 = x
        for _ in range(n):
            d = win(t, .5 + 5 * k / tot, .9 + 5 * k / tot)
            col = np.array(matplotlib.colors.to_rgb(c)) * color_a + np.array((.5, .52, .58)) * (1 - color_a)
            if d > 0: ax.add_patch(Rectangle((x, 62 + 30 * (1 - d)), 3.2, 12, color=col, alpha=d))
            x += 4.2; k += 1
        la = win(t, 11 + gi * .6, 12 + gi * .6)
        ax.plot([x0, x - 1], [80, 80], color=c, lw=3, alpha=la)
        text(ax, (x0 + x - 1) / 2, 84, f'Session {"ABCD"[gi]}', 24, matplotlib.colors.to_rgb(c), la)
        text(ax, (x0 + x - 1) / 2, 50, f'{night}\n{scope}\nrotation {rot}', 18, DIM, la, linespacing=1.4)
        x += gap
    text(ax, 96, 22, 'New session when the night, telescope, camera rotation (>5°), exposure or gain changes, or after a 2+ hour gap.', 19, FG, win(t, 14, 15.5))
    n89 = int(89 * win(t, 18, 21)); n76 = int(76 * win(t, 19.5, 22.5))
    text(ax, 96, 9, f'Nearly a year of imaging  →  {n89} sessions  →  {n76} stacks', 30, GOLD, win(t, 18, 19))

WST = stars(150, 7, 12, 180, 8, 92)
def m_wall(ax, t, T):
    x, y, s, a = WST
    draw_stars(ax, WST, z=2)
    fix = win(t, 12, 19)                                    # 왜곡 보정 진행
    cx, cy = 96, 50; dx, dy = x - cx, y - cy; r2 = (dx ** 2 + dy ** 2) / 90 ** 2
    k = .09 * (1 - fix)                                     # 지도 원이 가장자리에서 어긋남
    gx, gy = cx + dx * (1 + k * r2 * 3), cy + dy * (1 + k * r2 * 3)
    ca = win(t, 1, 3)
    for j in range(len(x)):
        ax.add_patch(Circle((gx[j], gy[j]), 1.6, fill=False, ec=BLUE, lw=1, alpha=.8 * ca, zorder=3))
    off = np.hypot(gx - x, gy - y) > 1.2
    ra = win(t, 3, 6) * (1 - fix)
    if ra > .02:
        ax.scatter(x[off], y[off], s=30, c=RED, alpha=ra, zorder=4)
    for gxl in np.linspace(12, 180, 9):                     # 휘어진 격자
        yy = np.linspace(8, 92, 40); xx = cx + (gxl - cx) * (1 + k * ((gxl - cx) ** 2 + (yy - cy) ** 2) / 90 ** 2 * 3)
        ax.plot(xx, yy, color=DIM, lw=.6, alpha=.35 * ca)
    if t < 12: n = int(69000 * win(t, 3, 9))
    else: n = int(69000 - 61000 * fix)
    text(ax, 96, 100, f'stars "not on the map":  {n:,}', 34, RED if t < 19 else GOLD, win(t, 2.5, 3.5))
    text(ax, 96, 6, 'lens distortion at the edges  →  modeled and corrected', 22, DIM, win(t, 10, 11.5))
    la = win(t, 22, 24.5)
    if la > 0:
        ax.add_patch(Rectangle((0, 30), 192, 34, color=BG, alpha=.85 * la, zorder=6))
        text(ax, 96, 47, '90% of finding something new\nis throwing out the fakes.', 44, GOLD, la, serif=True, zorder=7, linespacing=1.4)

SSA = None
def m_ssa(ax, t, T):
    global SSA
    if SSA is None:
        r = np.random.default_rng(9); N = 48; sz = 61
        fr = r.normal(0, 1, (N, sz, sz)).astype(np.float32)
        for k in range(N):                                   # 잡음 0.6σ짜리 희미한 점이 오른쪽 위로 이동
            px, py = 14 + k * .7, 14 + k * .7
            yy, xx = np.mgrid[0:sz, 0:sz]; fr[k] += .6 * np.exp(-((xx - px) ** 2 + (yy - py) ** 2) / 4)
        SSA = fr
    N = len(SSA)
    k = min(N, 1 + int(N * win(t, 3, T * .75)))
    single = SSA[min(int(t * 2) % N, N - 1)]
    acc = np.zeros_like(SSA[0])
    for j in range(k):
        acc += np.roll(np.roll(SSA[j], -int(round(j * .7)), 0), -int(round(j * .7)), 1)
    acc /= np.sqrt(k)
    ax.imshow(np.clip(single, -2.5, 4), cmap='gray', extent=(14, 84, 18, 88), vmin=-2.5, vmax=4, interpolation='nearest', zorder=2)
    ax.imshow(np.clip(acc, -2.5, 6), cmap='gray', extent=(108, 178, 18, 88), vmin=-2.5, vmax=6, interpolation='nearest', zorder=2, alpha=win(t, 1.5, 3))
    text(ax, 49, 94, 'one frame: nothing visible', 24, FG, win(t, 0, 1))
    text(ax, 143, 94, f'shift by the guessed motion & stack: {k} frames', 24, GOLD, win(t, 1.5, 3))
    ax.annotate('', xy=(104, 53), xytext=(88, 53), arrowprops=dict(arrowstyle='->', color=GOLD, lw=3), alpha=win(t, 1.5, 3))
    if k > 20:
        ax.add_patch(Circle((108 + 70 * 14 / 61, 88 - 70 * 14 / 61), 4, fill=False, ec=RED, lw=2.5, zorder=4, alpha=win(t, T * .55, T * .6)))
    text(ax, 96, 8, 'thousands of directions and speeds tried on a GPU  ·  reaches about magnitude 18', 22, DIM, win(t, T * .6, T * .65))

ITEMS = ['Look again at the photos you already have', 'Shoot the same field again and again', 'Take your flats the same night',
         'Shoot with a goal', 'Be skeptical']
SUB4 = ['new asteroids: near the ecliptic, 2–3 h on one field', 'supernovae: Virgo, Perseus — every few weeks', 'novae: the Andromeda Galaxy, often']
def m_check(k):
    def draw(ax, t, T):
        text(ax, 22, 96, 'What you can try', 40, alpha=1 if k else win(t, 0, 1), serif=True, ha='left')
        y = 80
        for j, it in enumerate(ITEMS):
            if k == 0: a = win(t, .8 + j * .9, 1.6 + j * .9); col = FG
            elif j < k - 1: a = .55; col = DIM
            elif j == k - 1: a = 1; col = GOLD
            else: a = .3; col = DIM
            hl = (j == k - 1)
            if hl: ax.add_patch(Rectangle((18, y - 4.5), 156, 9, color=GOLD, alpha=.08 * win(t, 0, .6)))
            mark = '✓' if (k and j < k - 1) else f'{j + 1}.'
            text(ax, 24, y, mark, 30 if hl else 24, GREEN if mark == '✓' else col, a, ha='left')
            text(ax, 34, y, it, 32 if hl else 24, col, a, ha='left')
            y -= 11
            if j == 3 and k == 4:
                for q, sline in enumerate(SUB4):
                    text(ax, 44, y + 2, '·  ' + sline, 20, FG, win(t, 3 + q * 4, 4 + q * 4), ha='left'); y -= 7
    return draw

BOXES = [((6, 50, 22, 12), 'Raw photos\n(read only)', FG), ((36, 50, 26, 12), 'Sort into sessions\n+ same-night flats', FG), ((70, 50, 22, 12), 'Stack\n(Siril)', FG),
         ((104, 64, 32, 10), 'Faint asteroids\n(GPU shift-and-stack)', GOLD), ((104, 48, 32, 10), 'New & variable stars\n(Gaia · VSX)', GOLD),
         ((104, 32, 32, 10), 'Dust & gas\n(IRAS · Planck · Hα)', GOLD), ((36, 22, 26, 12), 'Frame by frame:\nmoving objects, flashes', FG),
         ((150, 38, 34, 14), 'Report\n+ list to check by eye', GOLD)]
ARROWS = [((28.8, 56), (35.2, 56)), ((62.8, 56), (69.2, 56)), ((92.8, 56), (103.2, 69)), ((92.8, 56), (103.2, 53)), ((92.8, 56), (103.2, 37)),
          ((17, 49.2), (35.2, 28)), ((136.8, 69), (149.2, 45)), ((136.8, 53), (149.2, 45)), ((136.8, 37), (149.2, 45)), ((62.8, 28), (149.2, 42))]
def m_pipeline(ax, t, T):
    text(ax, 96, 97, 'astrohunt: one command, the whole pipeline', 38, alpha=win(t, 0, 1), serif=True)
    ca = win(t, 1, 2)
    ax.add_patch(FancyBboxPatch((40, 79), 112, 8, boxstyle='round,pad=0.6', fc=(0, 0, 0, .5 * ca), ec=(*DIM, ca), lw=1.5))
    cmd = '$ python astrohunt.py'; nch = int(len(cmd) * win(t, 1.5, 4))
    text(ax, 43, 83, cmd[:nch] + ('▌' if int(t * 2) % 2 else ''), 26, GREEN, ca, ha='left', family='Consolas')
    order = [0, 1, 2, 6, 3, 4, 5, 7]
    for oi, bi in enumerate(order):
        (x, y, w, h), lab, c = BOXES[bi]; a = win(t, 4 + oi * 1.6, 5 + oi * 1.6)
        if a <= 0: continue
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.8', fc=(1, 1, 1, .05 * a), ec=(*matplotlib.colors.to_rgb(c), a), lw=2))
        text(ax, x + w / 2, y + h / 2, lab, 18, c, a, linespacing=1.35)
    aa = win(t, 6, 16)
    for j, ((x0, y0), (x1, y1)) in enumerate(ARROWS):
        if aa <= j / len(ARROWS): continue
        curved = (j == len(ARROWS) - 1)
        ax.annotate('', xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle='->', color=DIM, lw=1.8, connectionstyle='arc3,rad=0.18' if curved else 'arc3'))
        if curved: continue
        ph = (t * .6 + j * .17) % 1                          # 화살표를 따라 흐르는 빛
        ax.plot(x0 + (x1 - x0) * ph, y0 + (y1 - y0) * ph, 'o', color=GOLD, ms=5, alpha=.9 * win(t, 16, 17))
    text(ax, 96, 8, 'only new photos are processed  ·  temp files cleaned up  ·  code is open on GitHub', 22, DIM, win(t, 18, 20))

def m_shadow(ax, t, T):
    R = 6371.0; S = 108 / 13800.0                            # km → 화면
    def P(x, y): return 96 + (x - 1200) * S, 6 + (y + 1500) * S
    ox, oy = P(0, 0)
    a0 = win(t, 0, 1.5)
    sx0, sy0 = P(0, -R); sx1, sy1 = P(14000, R)
    ax.add_patch(Rectangle((ox, sy0), 200, sy1 - sy0, color='black', alpha=.55 * a0, zorder=1))
    ax.add_patch(Circle((ox, oy), R * S, color='#1f4f8f', alpha=a0, zorder=2))
    ax.add_patch(Wedge((ox, oy), R * S, 90, 270, color=GOLD, alpha=.18 * a0, zorder=3))
    sa = win(t, 1, 2.5)
    for yy in (7000, 4000, 1000):
        xs, ys = P(-10500, yy); xe, _ = P(-7200, yy); sh = (t * 8) % 6
        ax.annotate('', xy=(xe + sh, ys), xytext=(xs + sh, ys), arrowprops=dict(arrowstyle='->', color=GOLD, lw=3, alpha=sa))
    text(ax, *P(-10500, 8000), 'Sunlight', 26, GOLD, sa, ha='left')
    text(ax, *P(8300, 2600), "Earth's shadow", 26, DIM, win(t, 2, 3), ha='left')
    n = np.array([.515, .857]); O = R * n; Pt = np.array([np.sqrt((R + 1120) ** 2 - R ** 2), R])
    oa = win(t, 4, 5)
    ax.plot(*P(*O), 'o', color='white', ms=12, alpha=oa, zorder=6)
    text(ax, P(*O)[0] - 2, P(*O)[1] - 9, 'Observer\nSun 31° below horizon', 20, FG, oa, ha='right', zorder=6)
    for rr, c, a in ((R + 420, DIM, win(t, 7, 8)), (R + 550, DIM, win(t, 7.5, 8.5))):
        ax.add_patch(Circle((ox, oy), rr * S, fill=False, ls='--', lw=1.4, ec=(*c, a), zorder=4))
    text(ax, *P(8300, 800), 'ISS ~420 km, Starlink ~550 km:\nalready in the shadow', 17, DIM, win(t, 8, 9), ha='left')
    la = win(t, 10, 15)
    d = (Pt - O) / np.linalg.norm(Pt - O); Q = O + d * 9000 * la
    ax.plot([P(*O)[0], P(*Q)[0]], [P(*O)[1], P(*Q)[1]], color=GREEN, lw=3, zorder=5, alpha=oa)
    if la > .95: text(ax, P(*Q)[0] - 2, P(*Q)[1] + 3, 'toward M51', 20, GREEN, 1)
    ga = win(t, 14, 16)
    ax.add_patch(Circle((ox, oy), (R + 1120) * S, fill=False, ls='--', lw=2.5, ec=(*GOLD, ga), zorder=4))
    if ga > 0:
        pul = 1 + .3 * np.sin(t * 5)
        ax.plot(*P(*Pt), '*', color=GOLD, ms=26 * pul, alpha=ga, zorder=7)
        text(ax, P(*Pt)[0] + 4, P(*Pt)[1] + 4, 'sunlit only above 1,120 km', 26, GOLD, ga, ha='left', zorder=7)
    text(ax, 6, 101, 'Who could reflect sunlight at 3 a.m.?', 34, FG, win(t, 0, 1), serif=True, ha='left')

def m_count(target, sub):
    r = np.random.default_rng(target)
    lines = [(r.uniform(-40, 200), r.uniform(0, 108), r.uniform(-.5, .5), r.uniform(.3, 1.2)) for _ in range(40)]
    def draw(ax, t, T):
        for x, y, sl, sp in lines:                           # 지나가는 위성 궤적
            ph = (t * sp * .15 + x / 240) % 1; xs = -40 + 280 * ph
            ax.plot([xs, xs + 18], [y, y + 18 * sl], color=DIM, lw=1, alpha=.25)
        n = int(target * win(t, .3, 4))
        text(ax, 96, 62, f'{n:,}', 150, GOLD, 1, serif=True)
        text(ax, 96, 34, sub, 28, FG, win(t, 1, 2))
        sa = win(t, T * .55, T * .55 + .4)
        if sa > 0:
            ax.text(96, 14, 'NO MATCH', fontsize=60, color=RED, alpha=sa, ha='center', va='center', fontweight='bold', rotation=-6,
                    bbox=dict(boxstyle='round,pad=0.3', fc='none', ec=RED, lw=4, alpha=sa))
    return draw

MOTIONS = {'three': m_three, 'move': m_move, 'change': m_change, 'spread': m_spread, 'map': m_map, 'sessions': m_sessions,
           'wall': m_wall, 'ssa': m_ssa, 'pipeline': m_pipeline, 'shadow': m_shadow,
           'check0': m_check(0), 'check1': m_check(1), 'check2': m_check(2), 'check3': m_check(3), 'check4': m_check(4), 'check5': m_check(5),
           'count8916': m_count(8916, 'public satellites that could have been in that part of the sky'),
           'count451': m_count(451, 'classified satellites tracked by amateur observers')}

if __name__ == '__main__':
    meta = json.load(open(os.path.join(HERE, 'out', 'tts', 'meta.json'), encoding='utf-8'))
    only = {int(a) for a in sys.argv[1:]}
    for i, ((sec, vis, lines), m) in enumerate(zip(SCENES, meta)):
        if vis[0] != 'motion' or (only and i not in only): continue
        if os.path.exists(os.path.join(OUT, f'{i:02d}.mp4')) and not only: continue
        render(i, m['dur'], MOTIONS[vis[1]])
