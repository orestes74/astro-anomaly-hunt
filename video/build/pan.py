"""'pan' 장면: 직접 보정한 사진을 확대·이동하며 보여 주는 클립을 원본 사진에서 직접 렌더링합니다.
같은 사진이 이어지는 장면('cont')은 한 그룹으로 묶어 움직임이 끊기지 않게 하고,
그룹의 처음에만 페이드 인, 끝에만 페이드 아웃을 넣습니다.
실행: python pan.py [장면 번호 ...]   (opencv, scipy 필요. build_visuals.py와 tts.py 다음, assemble.py 전)
환경변수: TTS_DIR (assemble.py와 같게, 기본 tts), PAN_W·PAN_H (기본 1920x1080, 최종본은 3840x2160)
"""
import os, sys, json, subprocess
import numpy as np, cv2
from scipy.interpolate import PchipInterpolator

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out'); DST = os.path.join(OUT, 'pan'); os.makedirs(DST, exist_ok=True)
FPS, FADE, LAST = 30, 0.4, 7.0                       # assemble.py와 같은 값
PAN_W, PAN_H = int(os.environ.get('PAN_W', 1920)), int(os.environ.get('PAN_H', 1080))
ENC = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', str(FPS)]
TTS = os.environ.get('TTS_DIR', 'tts')

def pan_path(keys, D):
    """키프레임 → 시각 t의 (확대, 중심 x, 중심 y). 전체를 부드럽게 가감속하고 키 사이는 PCHIP으로 매끄럽게."""
    k = np.array(keys, float)
    if len(k) == 1: k = np.vstack([k, k]); k[1, 0] = 1
    fz = PchipInterpolator(k[:, 0], np.log(k[:, 1])); fx = PchipInterpolator(k[:, 0], k[:, 2]); fy = PchipInterpolator(k[:, 0], k[:, 3])
    def at(t):
        u = np.clip(t / D, 0, 1); u = 0.5 - 0.5 * np.cos(np.pi * u)      # 가감속
        return float(np.exp(fz(u))), float(fx(u)), float(fy(u))
    return at

def render(src, keys, D, t0, t1, out, fade_in, fade_out):
    """그룹 전체 길이 D 중 [t0, t1) 구간을 out에 씀. 2배 크기로 그린 뒤 줄여 별이 반짝이지 않게 함."""
    ih, iw = src.shape[:2]
    cw0 = min(iw, ih * 16 / 9)                                # 확대 1.0 = 사진에 들어가는 가장 큰 16:9
    at = pan_path(keys, D); SW, SH = PAN_W * 2, PAN_H * 2
    d = t1 - t0; n = int(round(d * FPS))
    vf = []
    if fade_in: vf.append(f'fade=t=in:st=0:d={FADE}')
    if fade_out: vf.append(f'fade=t=out:st={d - FADE:.3f}:d={FADE}')
    p = subprocess.Popen(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24',
                          '-s', f'{PAN_W}x{PAN_H}', '-r', str(FPS), '-i', '-'] + (['-vf', ','.join(vf)] if vf else [])
                         + ['-frames:v', str(n)] + ENC + [out], stdin=subprocess.PIPE)
    for f in range(n):
        z, cx, cy = at(t0 + f / FPS)
        cw = cw0 / z; ch = cw * 9 / 16
        x = min(max(cx * iw, cw / 2), iw - cw / 2); y = min(max(cy * ih, ch / 2), ih - ch / 2)
        s = SW / cw
        M = np.float32([[s, 0, SW / 2 - s * x], [0, s, SH / 2 - s * y]])
        big = cv2.warpAffine(src, M, (SW, SH), flags=cv2.INTER_CUBIC if s > 1 else cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        p.stdin.write(cv2.resize(big, (PAN_W, PAN_H), interpolation=cv2.INTER_AREA).tobytes())
    p.stdin.close()
    if p.wait(): raise RuntimeError('ffmpeg failed: ' + out)

if __name__ == '__main__':
    meta = json.load(open(os.path.join(OUT, TTS, 'meta.json'), encoding='utf-8'))
    man = json.load(open(os.path.join(OUT, 'frames', 'manifest.json'), encoding='utf-8'))
    only = {int(a) for a in sys.argv[1:]}
    groups, g = [], None
    for m, item in zip(meta, man):
        if item['kind'] != 'pan': g = None; continue
        if item['keys'] == 'cont':
            if g is None: raise ValueError(f"scene {item['i']}: 'cont' without a preceding pan")
        else:
            g = {'photo': item['photo'], 'keys': item['keys'], 'D': 0.0, 'members': []}; groups.append(g)
        d = m['dur'] if m['dur'] else LAST
        g['members'].append((item['i'], g['D'], d)); g['D'] += d
    for g in groups:
        todo = [x for x in g['members'] if not only or x[0] in only]
        if not todo: continue
        src = cv2.imread(g['photo'], cv2.IMREAD_COLOR)
        if src is None: raise FileNotFoundError(g['photo'])
        first, last = g['members'][0][0], g['members'][-1][0]
        for i, t, d in todo:
            render(src, g['keys'], g['D'], t, t + d, os.path.join(DST, f'{i:02d}.mp4'), i == first, i == last)
            print(i, os.path.basename(g['photo']), f'{t:.1f}-{t + d:.1f}s of {g["D"]:.1f}s', flush=True)
