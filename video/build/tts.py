"""장면별 영어 내레이션을 Kokoro로 만들고 문장별 시각(자막용)을 기록합니다.
실행: C:\\kokoro-tts\\venv\\Scripts\\python.exe tts.py
"""
import os, sys, json
import numpy as np, soundfile as sf, torch
from kokoro import KPipeline
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scenes import SCENES, VOICE, SPEED

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'tts')
os.makedirs(OUT, exist_ok=True)
SR = 24000
GAP, LEAD, TAIL = 0.45, 0.5, 0.9
pipe = KPipeline(lang_code='a', device='cuda' if torch.cuda.is_available() else 'cpu')

def say(text):
    parts = []
    for r in pipe(text, voice=VOICE, speed=SPEED, split_pattern=None):
        a = r.audio
        if a is not None:
            parts.append(np.asarray(a.detach().cpu().numpy() if hasattr(a, 'detach') else a, dtype=np.float32))
    return np.concatenate(parts) if parts else np.zeros(0, np.float32)

meta = []
for i, (sec, vis, lines) in enumerate(SCENES):
    if not lines:
        meta.append({'i': i, 'dur': None, 'subs': []}); continue
    buf = [np.zeros(int(LEAD * SR), np.float32)]; t = LEAD; subs = []
    for k, line in enumerate(lines):
        a = say(line)
        subs.append([t, t + len(a) / SR, line])
        buf.append(a); t += len(a) / SR
        if k < len(lines) - 1:
            buf.append(np.zeros(int(GAP * SR), np.float32)); t += GAP
    buf.append(np.zeros(int(TAIL * SR), np.float32)); t += TAIL
    sf.write(os.path.join(OUT, f'{i:02d}.wav'), np.concatenate(buf), SR)
    meta.append({'i': i, 'dur': t, 'subs': subs})
    print(i, f'{t:.1f}s', flush=True)
json.dump(meta, open(os.path.join(OUT, 'meta.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('total narration', round(sum(m['dur'] or 0 for m in meta) / 60, 1), 'min')
