"""모든 단계 결과를 모아 보고서(REPORT_auto.md)와 '눈으로 확인할 목록'을 만듭니다."""
import os, sys, json, glob, csv, collections, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfg

def jload(p, default=None, enc='utf-8'):
    if not os.path.exists(p):
        return default
    for e in (enc, 'utf-8', 'cp949'):
        try:
            return json.load(open(p, encoding=e))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return default

def rel(p):
    return os.path.relpath(p, cfg.REPORT_DIR).replace('\\', '/')

L = []
w = L.append
now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
w(f'# 이상 천체 탐색 자동 보고서 ({now})\n')
w(f'- 원본: `{cfg.RAW}`\n- 스택: `{cfg.STACKS}`\n- 작업 폴더: `{cfg.WORK}`\n')
review = []

# 1. 스태킹
w('\n## 1. 스태킹\n')
infos = [jload(p) for p in glob.glob(os.path.join(cfg.STACKS, '*', 'info.json'))]
infos = [i for i in infos if i]
failed = jload(os.path.join(cfg.WORK, 'stack', 'failed.json'), {})
sess_csv = os.path.join(cfg.INVENTORY, 'sessions.csv')
n_sess = sum(1 for _ in open(sess_csv, encoding='utf-8-sig')) - 1 if os.path.exists(sess_csv) else 0
w(f'- 세션 {n_sess}개 중 스택 {len(infos)}개 완료, 실패 {len(failed)}개')
w(f"- 플랫 보정 {sum(i['flat'] != 'none' for i in infos)}개, 다크 보정 {sum(str(i['dark']).startswith('master') for i in infos)}개")
if failed:
    w('\n| 실패 세션 | 이유 |\n|---|---|')
    for k, v in sorted(failed.items()):
        w(f"| {k} | {v.splitlines()[0][:80]} |")

# 2. 한 장씩 탐색 (이동 천체·섬광)
w('\n## 2. 이동 천체·섬광 (프레임 한 장씩)\n')
tr = jload(os.path.join(cfg.FRAME_RESULTS, 'tracklets_classified.json'), [])
cls = collections.Counter(t['class'] for t in tr)
w(f'- 이동 궤적 {len(tr)}개: ' + ', '.join(f'{k} {v}' for k, v in cls.most_common()))
known = sorted({(t['known_name'], t.get('known_V') or 99, t['target']) for t in tr if t['class'] == 'known'}, key=lambda a: a[1])
if known:
    w('\n| 알려진 천체 | V | 대상 |\n|---|---|---|')
    for n, v, tg in known:
        w(f'| {n} | {v:.1f} | {tg} |' if v != 99 else f'| {n} | - | {tg} |')
for t in tr:
    if t['class'] == 'unidentified':
        review.append(('미확인 이동 천체', t['target'], f"{t['ra_mid']:.4f} {t['dec_mid']:+.4f}", f"{t['rate_arcsec_min']:.2f}\"/분, {t['n']}장",
                       rel(os.path.join(cfg.FRAME_RESULTS, 'cutouts'))))
fl = os.path.join(cfg.FRAME_RESULTS, 'flashes.csv')
if os.path.exists(fl):
    rows = list(csv.DictReader(open(fl, encoding='utf-8-sig')))
    c = collections.Counter(r.get('class', '') for r in rows)
    w(f'\n- 단일 프레임 섬광 후보 {len(rows)}개' + (': ' if rows else '') + ', '.join(f'{k or "?"} {v}' for k, v in c.most_common()))
    for r in rows:
        if r.get('class', '') in ('flash-candidate', 'short-trail'):
            review.append(('섬광', r.get('target', ''), f"{r.get('x', '')},{r.get('y', '')}", os.path.basename(r.get('file', '')), rel(os.path.join(cfg.FRAME_RESULTS, 'flash_cutouts'))))
rc = os.path.join(cfg.FRAME_RESULTS, 'recall.csv')
if os.path.exists(rc):
    rows = [r for r in csv.DictReader(open(rc, encoding='utf-8-sig')) if r['type'] != 'Comet']
    w('\n검출 한계(시야 안 알려진 소행성 중 찾은 비율):\n\n| V | 찾음 |\n|---|---|')
    for lo, hi in ((0, 15), (15, 16), (16, 17), (17, 18), (18, 19)):
        g = [r for r in rows if lo <= float(r['V']) < hi]
        if g:
            w(f"| {lo}–{hi} | {sum(r['detected'] == 'True' for r in g)}/{len(g)} |")

# 3. 어두운 소행성 (shift-and-stack)
w('\n## 3. 어두운 소행성 (shift-and-stack)\n')
ssa = [jload(p, {}) for p in glob.glob(os.path.join(cfg.ANALYSIS_RESULTS, 'ssa', '*.json'))]
det = collections.Counter(); tot = collections.Counter()
for r in ssa:
    seen = {}
    for ch in r.get('chunks', []):
        for k in ch.get('known', []):
            if (k.get('vx') or 0) ** 2 + (k.get('vy') or 0) ** 2 < (6 / max(ch.get('T_h', 1), 1e-3)) ** 2:   # 구간 동안 6px 미만 이동은 제외
                continue
            b = '<16' if k['V'] < 16 else ('16–17' if k['V'] < 17 else ('17–18' if k['V'] < 18 else ('18–19' if k['V'] < 19 else None)))
            if b:
                seen[k['name']] = (b, seen.get(k['name'], (b, False))[1] or bool(k.get('detected')))
    for n, (b, d) in seen.items():
        tot[b] += 1; det[b] += d
w(f'- 처리한 세션 {len(ssa)}개')
if tot:
    w('\n| V | 찾음 |\n|---|---|')
    for b in ('<16', '16–17', '17–18', '18–19'):
        if tot[b]:
            w(f'| {b} | {det[b]}/{tot[b]} |')
sig = jload(os.path.join(cfg.ANALYSIS_RESULTS, 'ssa_significant.json'), [])
w(f'\n- 유의 수준을 넘은 미확인 후보 {len(sig)}개 → 그림 `{rel(os.path.join(cfg.ANALYSIS_RESULTS, "ssa_vet"))}`')
for c in sig:
    review.append(('shift-and-stack 후보', c['sid'], f"{c['ra']:.4f} {c['dec']:+.4f}", f"S/N {c['snr']:.1f} (문턱 {c['thr']:.1f}), {c['rate']:.2f}\"/분",
                   rel(os.path.join(cfg.ANALYSIS_RESULTS, 'ssa_vet', f"{c['sid'][:30]}_c{c['chunk']}_{int(c['x'])}_{int(c['y'])}.png"))))

# 4. 신성·초신성·변광성
w('\n## 4. 신성·초신성·변광성 (세션 스택 비교)\n')
TD = os.path.join(cfg.ANALYSIS_RESULTS, 'transient')
tc = jload(os.path.join(TD, 'transient_candidates.json'), {})
cands = tc.get('cands', []); var = tc.get('variables', [])
kc = collections.Counter(c['kind'] for c in cands)
w(f"- Gaia에 없는 점광원 {len(cands)}개: 다른 세션에도 있음 {kc.get('persistent_no_gaia', 0)}, 이번 세션에만 {kc.get('only_this_session', 0)}, "
  f"비교 불가 {kc.get('no_gaia', 0)}, 알려진 소행성 {sum(bool(c.get('asteroid')) for c in cands)}")
of = jload(os.path.join(TD, 'only_forced.json'), [])
ab = [o for o in of if o.get('absent')]
w(f'- 좌표가 정확한 곳의 단독 후보 {len(of)}개 → 다른 세션 강제측광에서 확실히 없음 {len(ab)}개')
for o in ab:
    review.append(('새로 나타난 천체?', o['sid'], f"{o['ra']:.4f} {o['dec']:+.4f}", f"{o['mag']:.1f}등, S/N {o['snr']:.0f}", rel(os.path.join(TD, 'only_montage_0.png'))))
vk = jload(os.path.join(TD, 'var_keep.json'), [])
w(f'- 밝기가 변한 별 {len(var)}개 → 정밀 재측정 통과 {len(vk)}개 (VSX 등록 {sum(bool(v.get("vsx")) for v in vk)}개)')
if vk:
    w('\n| 별 | Δ등급 | 세션 | VSX |\n|---|---|---|---|')
    for v in sorted(vk, key=lambda v: -abs(v['fdm'])):
        name = f"{v['vsx'][0][0]} ({v['vsx'][0][1]})" if v.get('vsx') else '**미등록**'
        w(f"| {v['ra']:.4f} {v['dec']:+.4f} | {v['fdm']:+.2f} | {v['sid_a'][:10]} → {v['sid_b'][:10]} | {name} |")
        if not v.get('vsx'):
            review.append(('미등록 변광 후보', v['target'], f"{v['ra']:.4f} {v['dec']:+.4f}", f"Δm {v['fdm']:+.2f} ({v['fsig']:.0f}σ)", rel(os.path.join(TD, 'var_keep_montage.png'))))

# 5. 먼지·가스
w('\n## 5. 먼지·가스 (IRIS/Planck/Hα 지도 비교)\n')
dg = [jload(p, {}) for p in glob.glob(os.path.join(cfg.ANALYSIS_RESULTS, 'dustgas', '*.json'))]
if dg:
    w('| 스택 | IRIS r | Planck r | Hα r |\n|---|---|---|---|')
    for r in sorted(dg, key=lambda r: r.get('sid', '')):
        f = lambda k: f"{r[k]['r']:+.2f}" if isinstance(r.get(k), dict) else '-'
        w(f"| {r.get('sid', '')} | {f('dust_iris')} | {f('dust_planck')} | {f('halpha')} |")
ident = jload(os.path.join(cfg.ANALYSIS_RESULTS, 'dustgas_ident.json'), [], enc='cp949') or []
un = [b for b in ident if b.get('verdict', '').upper() == 'UNEXPLAINED']
w(f'\n- 시야 안쪽 5σ 이상 잔차 덩어리 {len(ident)}개, 알려진 천체·밝은 별로 설명 안 되는 것 {len(un)}개')
for b in un:
    review.append(('설명 안 되는 먼지/가스 덩어리', b.get('sid', ''), f"{b['ra']:.3f} {b['dec']:+.3f}", f"{b.get('map', '')} {b.get('peak_sigma', 0):.1f}σ",
                   rel(os.path.join(cfg.ANALYSIS_RESULTS, 'dustgas', b.get('sid', '') + '.png'))))

# 확인 목록
w('\n## 눈으로 확인할 것\n')
if review:
    w('| 종류 | 세션/대상 | 위치 | 내용 | 그림 |\n|---|---|---|---|---|')
    for k in review:
        w('| ' + ' | '.join(str(x) for x in k[:4]) + f' | [보기]({k[4]}) |')
else:
    w('없음: 모든 후보가 알려진 천체이거나 자동 검사에서 가짜로 걸러졌습니다.')
w('\n자동 판정은 1차 거르기입니다. 표의 그림을 열어 이동·정지·가장자리·위성 궤적 여부를 직접 확인하세요.')

out = os.path.join(cfg.REPORT_DIR, 'REPORT_auto.md')
open(out, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
json.dump([dict(zip(('kind', 'where', 'pos', 'note', 'image'), r)) for r in review], open(os.path.join(cfg.REPORT_DIR, 'review.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'보고서: {out}  (확인할 항목 {len(review)}개)')
