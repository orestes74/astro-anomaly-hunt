import glob, os
from PIL import Image, ImageDraw
fs = sorted(glob.glob('results/ssa_vet/*.png'))
ims = [Image.open(f) for f in fs]
for k in range(0, len(ims), 8):
    grp = ims[k:k + 8]; w = max(i.width for i in grp); h = sum(i.height + 14 for i in grp)
    M = Image.new('L', (w, h), 0); y = 0; d = ImageDraw.Draw(M)
    for f, i in zip(fs[k:k + 8], grp):
        d.text((2, y), os.path.basename(f)[:60], fill=255); M.paste(i, (0, y + 14)); y += i.height + 14
    M.save(f'results/ssa_vet_montage_{k // 8}.png')
print(len(fs))
