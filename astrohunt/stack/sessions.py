"""Light를 스태킹 세션으로 나누고, 같은 밤의 플랫과 짝짓기.
세션 = 같은 타깃 폴더 + 같은 밤(KST 18:00~다음날 06:00) + 같은 망원경(초점거리) + 같은 카메라 회전(파일명 각도 mod 180)
       + 같은 노출·게인·이미지 크기. 같은 밤 안에서 2시간 넘게 끊기면 다른 세션으로 나눔(그 사이 장비 변경 가능성).
플랫 = 같은 밤(18:00~다음날 06:00, 새벽 플랫은 07:00까지 같은 밤으로 봄) + 같은 망원경 + 같은 카메라 회전(±5°)."""
import sys as _s, os as _o; _s.path.insert(0, _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))); import cfg
import numpy as np, pandas as pd, os, warnings
from astropy.io import fits
warnings.filterwarnings('ignore')
HERE = cfg.WORK + '/stack'
L = pd.read_csv(f'{HERE}/inventory/light.csv'); F = pd.read_csv(f'{HERE}/inventory/flat.csv'); D = pd.read_csv(f'{HERE}/inventory/dark.csv')
# 플랫·다크 폴더가 비면(예전 inventory 결과는 열 이름도 없음) 플랫·다크 없이 진행
_FCOLS = ['path', 'DATE-OBS', 'EXPTIME', 'FOCALLEN', 'NAXIS1', 'NAXIS2', 'angle_fn', 'mjd', 'local']
if not all(c in F for c in _FCOLS):
    F = pd.DataFrame(columns=_FCOLS) if not len(F) else F.reindex(columns=list(F.columns) + [c for c in _FCOLS if c not in F])
if not all(c in D for c in ('DATE-OBS', 'EXPTIME', 'GAIN')):
    D = D.iloc[0:0]
import re as _re
def _orig(p):   # 원본만: Light/<대상>/Light_*.fit (하위 폴더의 처리 결과물 제외)
    p = os.path.normpath(p); parts = p.split(os.sep)
    return len(parts) >= 3 and parts[-3] == 'Light' and parts[-1].startswith('Light_') and 'postprocess' not in parts[-2].lower()
L = L[L.path.apply(_orig)]
L = L[L['DATE-OBS'].notna()].copy(); F = F[F['DATE-OBS'].notna()].copy()

def scope(fl):
    return cfg.scope_of(fl)
for df in (L, F):
    df['scope'] = df.FOCALLEN.apply(scope)
    df['rot180'] = df.angle_fn % 180
    df['lt'] = pd.to_datetime(df.local)
    h = df['lt'].dt.hour + df['lt'].dt.minute / 60
    df['night'] = np.where(h >= 12, df['lt'].dt.strftime('%Y-%m-%d'), (df['lt'] - pd.Timedelta(days=1)).dt.strftime('%Y-%m-%d'))
L['in_window'] = (L['lt'].dt.hour >= cfg.NIGHT_START) | (L['lt'].dt.hour < cfg.NIGHT_END)
F['in_window'] = (F['lt'].dt.hour >= cfg.NIGHT_START) | (F['lt'].dt.hour < cfg.NIGHT_END + 1)

# 스태킹 대상: 노출 10초 이상, 18~06시
DERIVED = {'work', 'postprocess', 'postprocess_1009', 'project_assets'}   # 예전 처리 결과물(원본 아님)
use = L[(L.EXPTIME >= cfg.MIN_EXPTIME) & L.in_window & ~L.folder.isin(DERIVED)].copy()
skipped = L[~L.index.isin(use.index)]
use = use.sort_values('mjd')
key = ['folder', 'night', 'scope', 'EXPTIME', 'GAIN', 'NAXIS1', 'NAXIS2']
sess = []
for k, g in use.groupby(key):
    g = g.sort_values('mjd')
    # 카메라 회전: mod 180 값이 5° 넘게 바뀌면 분리, 2시간 넘는 공백도 분리
    part = 0; prev = None
    for i, r in g.iterrows():
        if prev is not None:
            drot = abs(((r.rot180 - prev.rot180) + 90) % 180 - 90)
            if drot > 5 or (r.mjd - prev.mjd) * 24 > 2:
                part += 1
        use.loc[i, 'part'] = part; prev = r
for k, g in use.groupby(key + ['part']):
    sess.append(dict(zip(key + ['part'], k)) | dict(n=len(g), t0=g.local.min(), t1=g.local.max(), rot180=float(np.median(g.rot180)),
                     scale=float(np.nanmedian(g.scale)) if g.scale.notna().any() else np.nan, temp=float(np.median(g['CCD-TEMP'])),
                     files=list(g.path)))
S = pd.DataFrame(sess)
S['sid'] = [f"{r.night}_{r.folder.replace(' ', '_')}_{int(r.scope)}mm_{int(r.EXPTIME)}s" + (f'_p{int(r.part)}' if r.part else '') for r in S.itertuples()]

# 플랫 그룹(같은 밤·망원경·회전·노출) + 평균 밝기
fg = []
for k, g in F[F.error.isna() if 'error' in F else slice(None)].groupby(['night', 'scope', 'rot180', 'EXPTIME', 'NAXIS1', 'NAXIS2']):
    lv = [float(np.median(fits.getdata(p)[1000:3000:4, 1500:4500:4])) for p in g.path.iloc[[0, len(g) // 2, -1]]]
    fg.append(dict(night=k[0], scope=k[1], rot180=k[2], fexp=k[3], NAXIS1=k[4], NAXIS2=k[5], nflat=len(g), level=np.median(lv),
                   in_window=bool(g.in_window.all()), ft0=g.local.min(), files=list(g.path)))
FG = pd.DataFrame(fg, columns=['night', 'scope', 'rot180', 'fexp', 'NAXIS1', 'NAXIS2', 'nflat', 'level', 'in_window', 'ft0', 'files'])
FG.to_pickle(f'{HERE}/inventory/flatgroups.pkl')
print('플랫 그룹:'); print(FG.drop(columns='files').to_string())

def pick_flat(r):
    c = FG[(FG.night == r.night) & (FG.scope == r.scope) & (FG.NAXIS1 == r.NAXIS1) & (FG.NAXIS2 == r.NAXIS2) & FG.in_window]
    if not len(c):
        return None
    c = c[[abs(((a - r.rot180) + 90) % 180 - 90) <= 5 for a in c.rot180]]
    c = c[(c['level'] > 8000) & (c.level < 50000) & (c.nflat >= 8)]   # 너무 어둡거나 포화된 세트 제외
    if not len(c):
        return None
    return c.iloc[(c['level'] - 25000).abs().argsort().iloc[0]].name   # 밝기가 중간(25k ADU)에 가장 가까운 세트
S['flat'] = S.apply(pick_flat, axis=1)
D = D[D['DATE-OBS'].notna()] if 'DATE-OBS' in D else D
_dk = D.groupby(['EXPTIME', 'GAIN']).size() if len(D) else pd.Series(dtype=int)
S['dark'] = [bool(len(D)) and _dk.get((r.EXPTIME, r.GAIN), 0) >= 10 for r in S.itertuples()]
S['do_stack'] = S.n >= cfg.MIN_FRAMES
S.to_pickle(f'{HERE}/inventory/sessions.pkl')
S.drop(columns='files').to_csv(f'{HERE}/inventory/sessions.csv', index=False, encoding='utf-8-sig')
print(f'\n세션 {len(S)}개, 프레임 {S.n.sum()}장 (제외: 노출<10s 또는 06~18시 {len(skipped)}장)')
print(f'플랫 있음 {S.flat.notna().sum()}세션/{S[S.flat.notna()].n.sum()}장, 다크 있음 {S.dark.sum()}세션/{S[S.dark].n.sum()}장')
print('세션 크기 분포', S.n.describe()[['min', '50%', 'max']].to_dict(), ' 3장 미만', (S.n < 3).sum())
print('스택 대상', S.do_stack.sum(), '세션', S[S.do_stack].n.sum(), '장; 플랫', S[S.do_stack].flat.notna().sum(), '다크', S[S.do_stack].dark.sum())
print(S[S.n >= 3].drop(columns=['files', 'part']).sort_values('n', ascending=False).head(60).to_string())
