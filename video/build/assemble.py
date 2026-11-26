"""장면 클립 + 영어 내레이션 + 배경음악 + 자막을 묶어 MP4 초안을 만듭니다.
실행: C:\\kokoro-tts\\venv\\Scripts\\python.exe assemble.py   (numpy, soundfile, ffmpeg 필요)
"""
import os, sys, json, subprocess
import numpy as np, soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
from scenes import SCENES, MUSIC, SECTION_MUSIC

OUT = os.path.join(HERE, 'out'); SEG = os.path.join(OUT, 'seg'); os.makedirs(SEG, exist_ok=True)
FPS, FADE = 30, 0.4
# TTS_DIR: 내레이션 폴더(out 아래, 기본 tts), OUT_NAME: 결과 파일 이름(기본 draft_en)
TTS = os.environ.get('TTS_DIR', 'tts'); NAME = os.environ.get('OUT_NAME', 'draft_en')
meta = json.load(open(os.path.join(OUT, TTS, 'meta.json'), encoding='utf-8'))
man = json.load(open(os.path.join(OUT, 'frames', 'manifest.json'), encoding='utf-8'))
ENC = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', str(FPS)]
QSTEP, QHOLD, LAST = 3.4, 6.0, 7.0

def ff(args):
    r = subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error'] + args, capture_output=True, text=True)
    if r.returncode: raise RuntimeError(r.stderr[-2000:])

def fades(d): return f'fade=t=in:st=0:d={FADE},fade=t=out:st={d - FADE:.3f}:d={FADE}'

durs, segs = [], []
for m, item in zip(meta, man):
    i, kind = item['i'], item['kind']
    if kind == 'quote':
        d = QSTEP * (len(item['frames']) - 1) + QHOLD
    else:
        d = m['dur'] if m['dur'] else LAST
    if kind == 'skip':
        durs.append(0.0); continue
    durs.append(d)
    out = os.path.join(SEG, f'{i:02d}.mp4'); segs.append(out)
    if os.path.exists(out) and os.environ.get('REBUILD') != '1':
        continue
    n = int(round(d * FPS))
    if kind == 'img':
        vf = (f"zoompan=z='1+0.07*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s=1920x1080:fps={FPS},"
              f"{fades(d)}")
        ff(['-loop', '1', '-framerate', str(FPS), '-t', f'{d:.3f}', '-i', item['frame'], '-vf', vf, '-frames:v', str(n)] + ENC + [out])
    elif kind == 'pan':          # pan.py가 미리 렌더링 (페이드 포함)
        ff(['-i', os.path.join(OUT, 'pan', f'{i:02d}.mp4'), '-frames:v', str(n)] + ENC + [out])
    elif kind == 'motion':
        ff(['-i', item['motion'], '-vf', fades(d), '-frames:v', str(n)] + ENC + [out])
    elif kind == 'scroll':
        vf = f"crop=1920:1080:0:'(ih-1080)*min(max((t-1)/({d:.3f}-2),0),1)',{fades(d)}"
        ff(['-loop', '1', '-framerate', str(FPS), '-t', f'{d:.3f}', '-i', item['frame'], '-vf', vf, '-frames:v', str(n)] + ENC + [out])
    elif kind in ('card', 'ph', 'gen', 'cardimg'):
        ff(['-loop', '1', '-framerate', str(FPS), '-t', f'{d:.3f}', '-i', item['frame'],
            '-vf', f'scale=1920:1080,{fades(d)}', '-frames:v', str(n)] + ENC + [out])
    elif kind == 'vid':
        fc = (f"[1:v]fps={FPS},scale=-2:760:flags=neighbor[a];[0:v][a]overlay=(W-w)/2:150,{fades(d)}[v]")
        ff(['-loop', '1', '-framerate', str(FPS), '-t', f'{d:.3f}', '-i', item['frame'],
            '-stream_loop', '-1', '-i', item['video'], '-filter_complex', fc, '-map', '[v]', '-frames:v', str(n)] + ENC + [out])
    elif kind == 'quote':
        lst = os.path.join(SEG, f'{i:02d}_q.txt')
        with open(lst, 'w') as f:
            for k, p in enumerate(item['frames']):
                f.write(f"file '{p}'\nduration {QHOLD if k == len(item['frames']) - 1 else QSTEP}\n")
            f.write(f"file '{item['frames'][-1]}'\n")
        ff(['-f', 'concat', '-safe', '0', '-i', lst, '-vf', f'fps={FPS},scale=1920:1080,{fades(d)}', '-frames:v', str(int(round(d * FPS)))] + ENC + [out])
    print(i, kind, f'{d:.1f}s', flush=True)

starts = np.concatenate([[0], np.cumsum(durs)[:-1]]); total = float(sum(durs))
print('total', round(total / 60, 2), 'min')

# 영상 이어 붙이기
lst = os.path.join(OUT, 'segments.txt')
open(lst, 'w').write(''.join(f"file '{s}'\n" for s in segs))
video = os.path.join(OUT, 'video_noaudio.mp4')
ff(['-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', video])

# 내레이션 트랙 (24 kHz)
SRN = 24000
narr = np.zeros(int(total * SRN) + SRN, np.float32)
for m, s in zip(meta, starts):
    p = os.path.join(OUT, TTS, f"{m['i']:02d}.wav")
    if m['dur'] and os.path.exists(p):
        a, _ = sf.read(p, dtype='float32'); k = int(s * SRN); narr[k:k + len(a)] += a
sf.write(os.path.join(OUT, 'narration.wav'), narr, SRN)

# 배경음악 트랙: 섹션별 곡을 이어 붙이고, 내레이션 중에는 작게
def load(name):
    a, sr = sf.read(os.path.join(REPO, 'video', 'music', name), dtype='float32', always_2d=True)
    return a, sr
tracks = {k: load(v) for k, v in MUSIC.items()}
SRM = next(iter(tracks.values()))[1]
N = int(total * SRM) + SRM
bed = np.zeros((N, 2), np.float32)
XF = int(2.5 * SRM)
def looped(a, n):
    """곡을 n샘플 길이로 반복 (이음새 2.5초 크로스페이드)"""
    out = np.zeros((n + XF, 2), np.float32); pos = 0
    ramp = np.linspace(0, 1, XF)[:, None]
    while pos < n:
        seg = a.copy(); seg[:XF] *= ramp if pos else 1; seg[-XF:] *= ramp[::-1]
        end = min(pos + len(seg), len(out)); out[pos:end] += seg[:end - pos]; pos += len(seg) - XF
    return out[:n]
blocks = []
for i, (sec, _, _) in enumerate(SCENES):
    key = SECTION_MUSIC[sec]
    if blocks and blocks[-1][0] == key: blocks[-1][2] = starts[i] + durs[i]
    else: blocks.append([key, starts[i], starts[i] + durs[i]])
for bi, (key, t0, t1) in enumerate(blocks):
    a0 = int(t0 * SRM); a1 = min(N, int(t1 * SRM) + (XF if bi < len(blocks) - 1 else 0))
    seg = looped(tracks[key][0], a1 - a0)
    ramp = np.linspace(0, 1, min(XF, len(seg)))[:, None]
    if bi: seg[:len(ramp)] *= ramp
    if bi < len(blocks) - 1: seg[-len(ramp):] *= ramp[::-1]
    bed[a0:a1] += seg
gain = np.zeros(N, np.float32)
for i, (sec, vis, lines) in enumerate(SCENES):
    g = 0.16 if lines else 0.75
    gain[int(starts[i] * SRM):int((starts[i] + durs[i]) * SRM)] = g
gain[int(total * SRM):] = gain[int(total * SRM) - 1]
k = int(1.5 * SRM)                                     # 1.5초 이동 평균 (누적합으로 빠르게)
cs = np.concatenate([[0], np.cumsum(np.pad(gain, (k // 2, k - k // 2 - 1), mode='edge'), dtype=np.float64)])
gain = ((cs[k:] - cs[:-k]) / k).astype(np.float32)
fo = int(5 * SRM); e = int(total * SRM); gain[e - fo:e] *= np.linspace(1, 0, fo); gain[e:] = 0
bed *= gain[:, None]
sf.write(os.path.join(OUT, 'music_bed.wav'), bed, SRM)

# 자막 (ASS)
def ts(t):
    h = int(t // 3600); m_ = int(t % 3600 // 60); s = t % 60
    return f'{h}:{m_:02d}:{s:05.2f}'
ass = ['[Script Info]', 'ScriptType: v4.00+', 'PlayResX: 1920', 'PlayResY: 1080', 'WrapStyle: 0', '',
       '[V4+ Styles]',
       'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
       'Style: Default,Segoe UI,44,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,3,1,2,160,160,48,1',
       '', '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
srt = []
for m, s in zip(meta, starts):
    for a, b, text in m['subs']:
        ass.append(f'Dialogue: 0,{ts(s + a)},{ts(s + b + 0.15)},Default,,0,0,0,,{text}')
        srt.append((s + a, s + b + 0.15, text))
open(os.path.join(OUT, 'subs.ass'), 'w', encoding='utf-8').write('\n'.join(ass) + '\n')
def srt_ts(t): return f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d},{int(t * 1000 % 1000):03d}'
open(os.path.join(REPO, 'video', NAME + '.srt'), 'w', encoding='utf-8').write(
    ''.join(f'{k + 1}\n{srt_ts(a)} --> {srt_ts(b)}\n{t}\n\n' for k, (a, b, t) in enumerate(srt)))

# 최종 합치기
final = os.path.join(REPO, 'video', NAME + '.mp4')
r = subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', 'video_noaudio.mp4', '-i', 'narration.wav', '-i', 'music_bed.wav',
                    '-filter_complex', '[1:a]aresample=48000,pan=stereo|c0=c0|c1=c0[n];[2:a]aresample=48000[m];[n][m]amix=inputs=2:normalize=0:duration=first[a];[0:v]ass=subs.ass[v]',
                    '-map', '[v]', '-map', '[a]', '-t', f'{total:.2f}'] + ENC + ['-c:a', 'aac', '-b:a', '192k', final],
                   cwd=OUT, capture_output=True, text=True)
if r.returncode: raise RuntimeError(r.stderr[-2000:])
print('done', final)
