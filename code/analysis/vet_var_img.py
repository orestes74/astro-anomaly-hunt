import os, json, glob, numpy as np
from PIL import Image, ImageDraw
import common as C
import vet_montage_lib as M
R = os.path.join(C.HERE, 'results', 'transient')
K = json.load(open(os.path.join(R, 'var_keep.json'), encoding='utf-8'))
vo = []
for f in glob.glob(os.path.join(C.HERE, 'cache_vsx', '*.json')):
    vo += json.load(open(f))
vr = np.array([float(x['RA2000']) for x in vo]); vd = np.array([float(x['Declination2000']) for x in vo])
for v in K:
    s = np.hypot((vr - v['ra']) * np.cos(np.radians(v['dec'])), vd - v['dec']) * 3600
    j = np.where(s < 6)[0]
    v['vsx'] = [(vo[i]['Name'], vo[i].get('VariabilityType', ''), vo[i].get('MaxMag', ''), vo[i].get('MinMag', ''), round(float(s[i]), 1)) for i in j]
json.dump(K, open(os.path.join(R, 'var_keep.json'), 'w'), ensure_ascii=False, indent=0)
K.sort(key=lambda v: (v['target'], -abs(v['fdm'])))
rows = []
for i, v in enumerate(K):
    row = Image.new('RGB', (130 + 200, 112), (40, 40, 40)); dr = ImageDraw.Draw(row)
    dr.text((2, 2), f"#{i} {v['target'][:12]}", fill=(255, 255, 0))
    dr.text((2, 16), f"dm={v['fdm']:+.2f} s={v['fsig']:.0f}", fill=(255, 255, 255))
    dr.text((2, 30), f"m={v['mag_a']:.1f}", fill=(255, 255, 255))
    dr.text((2, 44), f"{v['ra']:.4f} {v['dec']:+.4f}", fill=(200, 200, 200))
    dr.text((2, 58), ('VSX ' + v['vsx'][0][0][:16] + ' ' + v['vsx'][0][1]) if v['vsx'] else 'no VSX', fill=(0, 255, 0) if v['vsx'] else (255, 120, 120))
    for k, s in enumerate((v['sid_a'], v['sid_b'])):
        row.paste(M.cut(s, v['ra'], v['dec']).convert('RGB'), (130 + 100 * k, 2))
        ImageDraw.Draw(row).text((132 + 100 * k, 100), s[:10], fill=(180, 180, 255))
    rows.append(row)
W = Image.new('RGB', (3 * rows[0].width, 112 * ((len(rows) + 2) // 3)))
for j, r in enumerate(rows):
    W.paste(r, ((j % 3) * r.width, 112 * (j // 3)))
W.save(os.path.join(R, 'var_keep_montage.png'))
print('VSX 일치', sum(bool(v['vsx']) for v in K), '/', len(K))
for i, v in enumerate(K):
    print(i, v['target'], f"{v['ra']:.4f} {v['dec']:+.4f}", v['vsx'][:1])
