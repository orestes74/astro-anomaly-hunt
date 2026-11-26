"""기존 Kokoro 내레이션(out/tts)을 문장 단위로 ChatterboxVC에 넣어 음색만 바꿉니다.
발음·리듬·문장 위치는 그대로라 장면 길이와 자막 시각이 바뀌지 않습니다.
실행: C:\chatterbox\venv\Scripts\python.exe vc_voice.py <목소리 샘플.wav> [장면:문장 ...(다시 만들 문장만)]
출력: out/tts_myvoice/NN.wav, out/tts_myvoice/sent/NN_K.wav, meta.json (out/tts 는 건드리지 않음)
"""
import os, sys, json, shutil
import numpy as np, soundfile as sf, torch
from chatterbox.vc import ChatterboxVC

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'out', 'tts'); DST = os.path.join(HERE, 'out', 'tts_myvoice')
SENT = os.path.join(DST, 'sent'); os.makedirs(SENT, exist_ok=True)
SR = 24000; PAD = 0.06
ref = sys.argv[1]
only = set(sys.argv[2:])
meta = json.load(open(os.path.join(SRC, 'meta.json'), encoding='utf-8'))
shutil.copy(os.path.join(SRC, 'meta.json'), os.path.join(DST, 'meta.json'))
vc = ChatterboxVC.from_pretrained('cuda'); vc.set_target_voice(ref)
assert vc.sr == SR
tmp = os.path.join(DST, '_in.wav')
for m in meta:
    if not m['subs']: continue
    i = m['i']; src, _ = sf.read(os.path.join(SRC, f'{i:02d}.wav'), dtype='float32')
    for k, (a, b, text) in enumerate(m['subs']):
        sp = os.path.join(SENT, f'{i:02d}_{k}.wav')
        if only and f'{i}:{k}' not in only: continue
        if not only and os.path.exists(sp): continue
        s0 = max(0, int((a - PAD) * SR)); s1 = min(len(src), int((b + PAD) * SR))
        seg = src[s0:s1]; sf.write(tmp, seg, SR)
        if only: torch.manual_seed(1000 + len(only) + k)
        w = vc.generate(tmp).squeeze(0).numpy().astype(np.float32)
        r0 = np.sqrt(np.mean(seg ** 2)) + 1e-9; r1 = np.sqrt(np.mean(w ** 2)) + 1e-9
        w = np.clip(w * (r0 / r1), -0.99, 0.99)
        sf.write(sp, w, SR)
        print(i, k, f'{len(seg)/SR:.2f}s -> {len(w)/SR:.2f}s', flush=True)
    # 장면 음성 다시 조립: 원래 문장 위치에 그대로 놓음
    out = np.zeros(len(src), np.float32)
    for k, (a, b, text) in enumerate(m['subs']):
        w, _ = sf.read(os.path.join(SENT, f'{i:02d}_{k}.wav'), dtype='float32')
        s0 = max(0, int((a - PAD) * SR))
        lim = int((m['subs'][k + 1][0] - PAD) * SR) if k + 1 < len(m['subs']) else len(out)
        if s0 + len(w) > lim: print('  overlap', i, k, f'{(s0 + len(w) - lim)/SR:.2f}s')
        e = min(len(out), s0 + len(w)); out[s0:e] += w[:e - s0]
    sf.write(os.path.join(DST, f'{i:02d}.wav'), out, SR)
os.remove(tmp)
print('done')
