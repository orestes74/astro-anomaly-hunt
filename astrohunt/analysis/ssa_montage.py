import sys as _s, os as _o; _s.path.insert(0, _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))); import cfg
import glob, os
from PIL import Image, ImageDraw
fs = sorted(glob.glob(os.path.join(cfg.ANALYSIS_RESULTS, 'ssa_vet', '*.png')))
ims = [Image.open(f) for f in fs]
for k in range(0, len(ims), 8):
    grp = ims[k:k + 8]; w = max(i.width for i in grp); h = sum(i.height + 14 for i in grp)
    M = Image.new('L', (w, h), 0); y = 0; d = ImageDraw.Draw(M)
    for f, i in zip(fs[k:k + 8], grp):
        d.text((2, y), os.path.basename(f)[:60], fill=255); M.paste(i, (0, y + 14)); y += i.height + 14
    M.save(os.path.join(cfg.ANALYSIS_RESULTS, f'ssa_vet_montage_{k // 8}.png'))
print(len(fs))
