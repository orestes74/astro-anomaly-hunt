"""GPU shift-and-stack (C:\\chatterbox\\venv 의 torch로 실행; numpy·torch만 사용).
입력: C:\\stackwork\\ssa\\<세션>.npz (정렬된 프레임, 3x3 비닝 휘도 float16, DATE-OBS, EXPTIME)
출력: <out>\\<세션>.json  — 구간(≤60분)별 후보: 비닝 좌표(구간 기준 시각), 속도(px/h), S/N, 반반 검증 S/N
사용법: python ssa_gpu.py <npz> <out_dir> <binned_scale_arcsec> [vmax_arcsec_per_h=100]"""
import sys, os, json, time, math, numpy as np, torch
import torch.nn.functional as Fn
from datetime import datetime, timezone

npz, out_dir, scale = sys.argv[1], sys.argv[2], float(sys.argv[3])
VMAX = float(sys.argv[4]) if len(sys.argv) > 4 else 100.0
CHUNK_H = 1.0
dev = 'cuda'
z = np.load(npz)
cube = np.nan_to_num(z['cube'], nan=0, posinf=65504, neginf=0); dobs = z['dateobs']; exp = z['exptime']
t = np.array([datetime.fromisoformat(s[:26]).replace(tzinfo=timezone.utc).timestamp() / 3600 for s in dobs]) + exp / 7200   # 노출 중간(시)
o = np.argsort(t); cube = cube[o]; t = t[o]
N, H, W = cube.shape
sid = os.path.basename(npz)[:-4]
t0 = time.time()

def robust(x):
    s = x.flatten()[::97].float()
    m = s.median(); mad = (s - m).abs().median() * 1.4826
    return m, mad

# 구간 나누기(≤60분)
chunks, cur = [], [0]
for i in range(1, N):
    if t[i] - t[cur[0]] > CHUNK_H:
        chunks.append(cur); cur = [i]
    else:
        cur.append(i)
chunks.append(cur)
chunks = [c for c in chunks if len(c) >= 5]

result = dict(sid=sid, N=int(N), H=int(H), W=int(W), scale_binned=scale, vmax_arcsec_h=VMAX, chunks=[])
for ci, idx in enumerate(chunks):
    F = torch.from_numpy(cube[idx].astype(np.float32)).to(dev)
    tc = torch.tensor(t[idx] - t[idx].mean(), dtype=torch.float32)
    n = len(idx); T = float(t[idx][-1] - t[idx][0])
    bg = torch.zeros(n, device=dev); sg = torch.zeros(n, device=dev)
    for i in range(n):
        bg[i], sg[i] = robust(F[i])
    F -= bg[:, None, None]
    static = F.median(0).values
    shp = static - Fn.avg_pool2d(static[None, None], 31, 1, 15, count_include_pad=False)[0, 0]   # 고역 통과한 정적 하늘
    sm, ss = robust(shp)
    bright = (shp > sm + 20 * ss) & (static > 10 * ss) & (static < 30000)   # 포화·0 화소 제외(0/0 → NaN 방지)
    a = torch.ones(n, device=dev)
    if bright.sum() > 100:
        for i in range(n):
            a[i] = (F[i][bright] / static[bright]).nanmedian()
    a = torch.nan_to_num(a, nan=1.0, posinf=1.0, neginf=1.0)
    R = F - a[:, None, None] * static[None]
    del F
    mask = (shp > sm + 5 * ss).float()[None, None]
    mask = (Fn.max_pool2d(mask, 7, 1, 3)[0, 0] > 0)                # 별·밝은 성운 주변 마스크(3px 팽창)
    R[:, mask] = 0
    # 큰 규모 밝기 변화(구름·기울기 변화) 제거: 31px 평균을 빼는 고역 통과
    for i in range(n):
        R[i] -= Fn.avg_pool2d(R[i][None, None], 31, 1, 15, count_include_pad=False)[0, 0]
        m_, s_ = robust(R[i][~mask])
        sg[i] = s_; R[i] = (R[i] - m_) / s_
    R[:, mask] = 0
    inj = []
    if os.environ.get('INJECT'):   # 주입 시험: 프레임당 피크 S/N A인 가우스(σ=1px) 이동 천체
        g = torch.Generator().manual_seed(ci)
        yy_, xx_ = torch.meshgrid(torch.arange(-4, 5), torch.arange(-4, 5), indexing='ij')
        psf = torch.exp(-(xx_ ** 2 + yy_ ** 2) / 2.0).to(dev)
        for A in [float(a) for a in os.environ['INJECT'].split(',')]:
            for _ in range(15):
                x0 = float(torch.randint(60, W - 60, (1,), generator=g)); y0 = float(torch.randint(60, H - 60, (1,), generator=g))
                ang = float(torch.rand(1, generator=g)) * 6.283; sp = (0.3 + 0.7 * float(torch.rand(1, generator=g))) * VMAX / scale
                vx0, vy0 = sp * math.cos(ang), sp * math.sin(ang)
                for i in range(n):
                    xi, yi = int(round(x0 + vx0 * float(tc[i]))), int(round(y0 + vy0 * float(tc[i])))
                    R[i, yi - 4:yi + 5, xi - 4:xi + 5] += A * psf
                inj.append(dict(A=A, x=x0, y=y0, vx=vx0, vy=vy0))
    R.clamp_(-4, 4)                                                  # 우주선·위성 궤적·핫픽셀 억제
    wts = (a / sg.mean() * sg.mean() / sg)                            # 투명도/잡음 가중
    wts = (wts / wts.pow(2).sum().sqrt()).to(dev)
    vmax = VMAX / scale                                             # px/h
    step = 0.8 / max(T, 0.05)
    nv = int(2 * vmax / step) + 1
    if nv * nv > 25000:                                             # 속도 격자 상한
        step = 2 * vmax / (math.sqrt(25000) - 1); nv = int(2 * vmax / step) + 1
    vs = torch.linspace(-vmax, vmax, nv)
    M = int(math.ceil(vmax * float(tc.abs().max()))) + 2
    Rp = Fn.pad(R, (M, M, M, M))
    del R
    best = torch.full((H, W), -1e9, device=dev); barg = torch.zeros((H, W), dtype=torch.int32, device=dev)
    k = 0; vlist = []
    for vy in vs:
        for vx in vs:
            if float(torch.hypot(vx, vy)) * max(T, 0.05) < 6:       # 거의 정지(6px 미만 이동) → 정적 하늘·별 잔상과 구분 불가
                continue
            dx = torch.round(vx * tc).int().tolist(); dy = torch.round(vy * tc).int().tolist()
            acc = torch.zeros((H, W), device=dev)
            for i in range(n):
                acc.add_(Rp[i, M + dy[i]:M + dy[i] + H, M + dx[i]:M + dx[i] + W], alpha=float(wts[i]))
            upd = acc > best
            best = torch.where(upd, acc, best); barg = torch.where(upd, torch.full_like(barg, k), barg)
            vlist.append((float(vx), float(vy))); k += 1
    # 후보: 국소 최대 & S/N > 5.5
    pk = (best == Fn.max_pool2d(best[None, None], 9, 1, 4)[0, 0]) & (best > 5.5)
    pk[:12, :] = False; pk[-12:, :] = False; pk[:, :12] = False; pk[:, -12:] = False
    ys, xs = torch.nonzero(pk, as_tuple=True)
    sn = best[ys, xs]
    order = torch.argsort(sn, descending=True)[:400]
    cands = []
    half = n // 2
    for j in order.tolist():
        y, x = int(ys[j]), int(xs[j]); vx, vy = vlist[int(barg[y, x])]
        dx = torch.round(vx * tc).int().tolist(); dy = torch.round(vy * tc).int().tolist()
        def part(sel):
            s = 0.0; w2 = 0.0
            for i in sel:
                yy, xx = M + dy[i] + y, M + dx[i] + x
                s += float(Rp[i, yy, xx]) * float(wts[i]); w2 += float(wts[i]) ** 2
            return s / math.sqrt(w2) if w2 > 0 else 0.0
        # 경로(구간 처음·중간·끝 위치)에 정적 광원이 있는지: 고역 정적 하늘의 S/N 최대값
        st_sn = 0.0
        for tt_ in (float(tc[0]), 0.0, float(tc[-1])):
            yy, xx = int(round(y + vy * tt_)), int(round(x + vx * tt_))
            if 2 <= yy < H - 2 and 2 <= xx < W - 2:
                st_sn = max(st_sn, float(((shp[yy - 2:yy + 3, xx - 2:xx + 3] - sm) / ss).max()))
        cands.append(dict(x=x, y=y, vx=vx, vy=vy, snr=float(sn[j]), static_sn=st_sn, snr_first=part(range(half)), snr_second=part(range(half, n)),
                          snr_even=part(range(0, n, 2)), snr_odd=part(range(1, n, 2))))
    if inj:
        bm = best.cpu().numpy()
        for d_ in inj:
            xi, yi = int(round(d_['x'])), int(round(d_['y']))
            d_['rec_snr'] = float(bm[yi - 2:yi + 3, xi - 2:xi + 3].max())
    result['chunks'].append(dict(injected=inj, i=ci, n=n, T_h=T, t_ref_unix_h=float(t[idx].mean()), frames=[int(o[i]) for i in idx],
                                 nv=k, step_px_h=step, masked_frac=float(mask.float().mean()), cands=cands))
    os.makedirs(out_dir, exist_ok=True)
    np.savez_compressed(os.path.join(out_dir, f'{sid}_c{ci}_max.npz'), best=best.clamp(-50, 500).cpu().numpy().astype(np.float16))
    del Rp, best, barg
    torch.cuda.empty_cache()
    print(f'{sid} 구간 {ci}: {n}장 {T*60:.0f}분, 속도 {k}개, 후보 {len(cands)}개, 누적 {time.time()-t0:.0f}s', flush=True)
os.makedirs(out_dir, exist_ok=True)
json.dump(result, open(os.path.join(out_dir, sid + '.json'), 'w'))
