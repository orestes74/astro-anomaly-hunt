"""세션별 Siril 스태킹.
- 임시 파일: C:\\stackwork (SSD). 세션이 끝나면 지움. 마스터(다크·플랫·BPM)는 전체 완료 후 지움(--cleanup-masters).
- 결과: H:\\asiair\\Stacks\\<세션>\\  linear.fit(32bit), processed.tif(16bit), processed.jpg, info.json
- shift-and-stack용: 정렬된 프레임을 3x3 비닝 휘도(float16)로 C:\\stackwork\\ssa\\<세션>.npz 에 저장(분석 후 지움).
- 원본(H:\\asiair\\Autorun)은 읽기만 함. 사용자 Siril 설정을 건드리지 않도록 별도 설정 파일(-i) 사용.
사용법: python run_stack.py [세션ID ...] | --all"""
import sys as _s, os as _o; _s.path.insert(0, _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))); import cfg
import os, sys, json, time, shutil, subprocess, glob, numpy as np, pandas as pd, warnings
from astropy.io import fits
warnings.filterwarnings('ignore')
HERE = cfg.WORK + '/stack'
SIRIL = cfg.SIRIL
WORK = cfg.TEMP
MAST = cfg.MASTERS
SSA = cfg.SSA_IN
OUT = cfg.STACKS
CFG = os.path.join(WORK, 'siril_isolated.config')
LOG = cfg.STACK_LOG; os.makedirs(LOG, exist_ok=True)
S = pd.read_pickle(f'{HERE}/inventory/sessions.pkl')
FG = pd.read_pickle(f'{HERE}/inventory/flatgroups.pkl')
D = pd.read_csv(f'{HERE}/inventory/dark.csv')
D = D[[fits.getheader(x)['BITPIX'] == 16 for x in D.path]] if len(D) else D   # 원본 16bit 다크만 (32bit는 예전 처리 결과물)

def p(x):   # Siril 경로 표기
    return x.replace('\\', '/')

def siril(script, name, cwd):
    if not os.path.exists(CFG):   # 사용자 Siril 설정과 분리된 빈 설정 파일 (없으면 Siril이 종료함)
        os.makedirs(os.path.dirname(CFG), exist_ok=True); open(CFG, 'w', encoding='utf-8').write('[core]\n')
    path = os.path.join(cwd, f'{name}.ssf')
    open(path, 'w', encoding='utf-8').write('requires 1.4.0\n' + script)
    t = time.time()
    r = subprocess.run([SIRIL, '-i', CFG, '-d', cwd, '-s', path], capture_output=True, text=True, encoding='utf-8', errors='replace')
    log = r.stdout + r.stderr
    open(os.path.join(LOG, f'{name}.log'), 'w', encoding='utf-8').write(log)
    ok = 'Script execution finished successfully' in log
    if not ok:
        raise RuntimeError(f'Siril 실패: {name} (로그 {LOG}\\{name}.log)\n' + '\n'.join(l for l in log.splitlines() if 'rror' in l or 'fail' in l.lower())[-1500:])
    return time.time() - t

def copy_files(files, dst):
    os.makedirs(dst, exist_ok=True)
    for i, f in enumerate(files):
        shutil.copyfile(f, os.path.join(dst, f'f_{i:05d}.fit'))

def master_dark(exptime, gain):
    """노출·게인이 같은 다크로 마스터 다크 + 핫픽셀 목록(bpm) 만들기. 없으면 None."""
    os.makedirs(MAST, exist_ok=True)
    g = D[(D.EXPTIME == exptime) & (D.GAIN == gain)] if len(D) else D
    if len(g) < 10:
        return None
    tag = f'{exptime:g}s_g{gain:g}'
    md = os.path.join(MAST, f'master_dark_{tag}.fit')
    if not os.path.exists(md):
        raw = os.path.join(MAST, f'dark_raw_{tag}'); copy_files(sorted(g.path), raw)
        siril(f'set16bits\ncd {p(raw)}\nconvert dark -out=../dk_{tag}\ncd ../dk_{tag}\nstack dark rej w 3 3 -nonorm -32b -out=../master_dark_{tag}\n'
              f'cd ..\nload master_dark_{tag}\nfind_hot bpm_{tag} 5 5\n', f'master_dark_{tag}', MAST)
        shutil.rmtree(raw, ignore_errors=True); shutil.rmtree(os.path.join(MAST, f'dk_{tag}'), ignore_errors=True)
    return md, os.path.join(MAST, f'bpm_{tag}.lst'), len(g)

def dark_level(md):
    lvl = float(np.median(fits.getdata(md)))
    return lvl * 65535 if lvl < 1.5 else lvl   # Siril가 [0,1]로 저장한 경우

def masters():
    """합성 바이어스·핫픽셀 목록용 기준 다크(가장 장수가 많은 노출·게인). 다크가 전혀 없으면 설정의 default_bias 사용."""
    if not len(D):
        if cfg.DEFAULT_BIAS is None:
            raise SystemExit('다크가 하나도 없습니다. astrohunt.json 의 default_bias 를 정해 주세요.')
        return None, None, float(cfg.DEFAULT_BIAS)
    eg = D.groupby(['EXPTIME', 'GAIN']).size().idxmax()
    m = master_dark(*eg)
    if m is None:
        if cfg.DEFAULT_BIAS is None:
            raise SystemExit('다크가 10장 이상인 노출·게인 조합이 없습니다. astrohunt.json 의 default_bias 를 정해 주세요.')
        return None, None, float(cfg.DEFAULT_BIAS)
    md, bpm, _ = m
    return md, bpm, (float(cfg.DEFAULT_BIAS) if cfg.DEFAULT_BIAS is not None else dark_level(md))

def master_flat(fid, bias):
    mf = os.path.join(MAST, f'mflat_{fid}.fit')
    if not os.path.exists(mf):
        raw = os.path.join(MAST, f'flat_raw_{fid}'); copy_files(FG.loc[fid, 'files'], raw)
        siril(f'set16bits\ncd {p(raw)}\nconvert flat -out=../fl_{fid}\ncd ../fl_{fid}\ncalibrate flat -bias="={bias:.0f}"\n'
              f'stack pp_flat rej w 3 3 -norm=mul -32b -out=../mflat_{fid}\n', f'master_flat_{fid}', MAST)
        shutil.rmtree(raw, ignore_errors=True); shutil.rmtree(os.path.join(MAST, f'fl_{fid}'), ignore_errors=True)
    return mf

def read_seq(path):
    """Siril .seq → 프레임별 fwhm, roundness, nstars (1부터 번호)"""
    rows = [l.split() for l in open(path) if l.startswith('R')]
    inc = [l.split() for l in open(path) if l.startswith('I ')]
    q = pd.DataFrame([dict(fwhm=float(a[1]), round=float(a[3]), nstars=int(float(a[6]))) for a in rows])
    q.index = range(1, len(q) + 1)
    q['included'] = [int(a[2]) == 1 for a in inc][:len(q)]
    return q

def select_frames(q):
    """세션 안 상대 기준으로 불량 프레임 제외: 정렬 실패, 덜 둥근 별(이중 별·흔들림), 큰 별(초점·구름), 적은 별(구름)"""
    ok = q[q.included & (q.fwhm > 0)]
    if not len(ok):
        return [], None, {}
    r75, f25, n75 = ok['round'].quantile(.75), ok.fwhm.quantile(.25), ok.nstars.quantile(.75)
    why = {}
    for i, r in q.iterrows():
        if not r.included or r.fwhm <= 0: why[i] = '정렬 실패'
        elif r['round'] < r75 - 0.05: why[i] = f"둥근 정도 {r['round']:.2f} < {r75 - 0.05:.2f}"
        elif r.fwhm > 1.35 * f25: why[i] = f'FWHM {r.fwhm:.1f} > {1.35 * f25:.1f}'
        elif r.nstars < 0.4 * n75: why[i] = f'별 {r.nstars}개 < {0.4 * n75:.0f}'
    good = [i for i in q.index if i not in why]
    if not good:
        return [], None, why
    g = q.loc[good]
    ref = int((g.nstars * g['round'] / g.fwhm).idxmax())
    return good, ref, why

def export_ssa(wdir, sid):
    """정렬된 프레임(r_pp_light_*) → 3x3 비닝 휘도 float16 + 시각"""
    fs = sorted(glob.glob(os.path.join(wdir, 'r_pp_light_*.fit')))
    cube, mjd, exp = [], [], []
    for f in fs:
        with fits.open(f, memmap=False) as hd:
            d = hd[0].data.astype(np.float32); h = hd[0].header
        lum = d.sum(0) if d.ndim == 3 else d
        ny, nx = lum.shape[0] // 3 * 3, lum.shape[1] // 3 * 3
        cube.append(lum[:ny, :nx].reshape(ny // 3, 3, nx // 3, 3).mean((1, 3)).astype(np.float16))
        mjd.append(h.get('MJD-OBS') or 0); exp.append(h.get('EXPTIME') or 0)
        dobs = h.get('DATE-OBS'); mjd[-1] = dobs
    os.makedirs(SSA, exist_ok=True)
    np.savez(os.path.join(SSA, f'{sid}.npz'), cube=np.array(cube), dateobs=np.array(mjd, dtype=str), exptime=np.array(exp, dtype=float))
    return len(fs)

def run(sid, md, bpm, bias):
    r = S[S.sid == sid].iloc[0]
    out = os.path.join(OUT, sid)
    if os.path.exists(os.path.join(out, 'info.json')):
        print(f'{sid}: 이미 완료, 건너뜀'); return
    wdir = os.path.join(WORK, sid); shutil.rmtree(wdir, ignore_errors=True)
    t0 = time.time()
    copy_files(r.files, os.path.join(wdir, 'raw'))
    t_copy = time.time() - t0
    cal = []
    dk = master_dark(r.EXPTIME, r.GAIN) if r.dark else None
    if dk:
        cal.append(f'-dark={p(dk[0])} -cc=dark 5 5')
    elif bpm:
        cal.append(f'-bias="={bias:.0f}" -cc=bpm {p(bpm)}')
    else:
        cal.append(f'-bias="={bias:.0f}"')
    mf = None
    if pd.notna(r.flat):
        mf = master_flat(int(r.flat), bias); cal.append(f'-flat={p(mf)}')
    # 1단계: 보정 + 정렬 계산만(-2pass) → 프레임 품질
    t_siril = siril(f'set16bits\ncd {p(wdir)}/raw\nconvert light -out=../w\ncd ../w\n'
                    f'calibrate light {" ".join(cal)} -cfa -equalize_cfa -debayer\nregister pp_light -2pass\n', sid + '_1', wdir)
    shutil.rmtree(os.path.join(wdir, 'raw'), ignore_errors=True)
    q = read_seq(os.path.join(wdir, 'w', 'pp_light_.seq'))
    good, ref, why = select_frames(q)
    if len(good) < 3:
        raise RuntimeError(f'쓸 만한 프레임 {len(good)}장뿐')
    rej = 'w 3 3' if len(good) >= 10 else 's 3 3'
    sel = ''.join(f'unselect pp_light {i} {i}\n' for i in q.index if i not in good)
    # 2단계: 가장 좋은 프레임을 기준으로, 좋은 프레임만 정렬·스택 + 후보정
    t_siril += siril(f'cd {p(wdir)}/w\nsetref pp_light {ref}\n{sel}register pp_light -selected -interp=lanczos4\n'
                     f'stack r_pp_light rej {rej} -norm=addscale -rgb_equal -32b -out=../linear\n'
                     f'cd ..\nload linear\nsubsky 1 -samples=25 -tolerance=1.0\nrmgreen\nautostretch\n'
                     f'savetif processed -astro\nsavejpg processed 92\n', sid + '_2', wdir)
    # 정렬 결과 요약(.seq의 채택 프레임 수)
    t1 = time.time()
    n_ssa = export_ssa(os.path.join(wdir, 'w'), sid)
    t_ssa = time.time() - t1
    os.makedirs(out, exist_ok=True)
    for f in ('linear.fit', 'processed.tif', 'processed.jpg'):
        shutil.copyfile(os.path.join(wdir, f), os.path.join(out, f))
    info = dict(sid=sid, target=r.folder, night=r.night, scope_mm=int(r.scope), exptime=float(r.EXPTIME), gain=float(r.GAIN),
                n_input=int(r.n), n_registered=n_ssa, t_first=r.t0, t_last=r.t1, rot180=r.rot180, scale=r.scale,
                dark=(f'master_dark {r.EXPTIME:g}s gain {r.GAIN:g} x{dk[2]}' if dk else f'none (synthetic bias {bias:.0f} ADU' + (' + BPM)' if bpm else ')')),
                flat=(f"night {FG.loc[int(r.flat), 'night']} exp {FG.loc[int(r.flat), 'fexp']}s x{FG.loc[int(r.flat), 'nflat']}" if mf else 'none'),
                rejection=rej, reference_frame=ref, excluded={str(k): v for k, v in why.items()}, files=list(r.files),
                timing_s=dict(copy=round(t_copy), siril=round(t_siril), ssa_export=round(t_ssa)))
    json.dump(info, open(os.path.join(out, 'info.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    shutil.rmtree(wdir, ignore_errors=True)
    print(f'{sid}: {r.n}장 → 사용 {n_ssa}장 (제외 {len(why)}), 복사 {t_copy:.0f}s, Siril {t_siril:.0f}s, SSA추출 {t_ssa:.0f}s', flush=True)

if __name__ == '__main__':
    os.makedirs(WORK, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    md, bpm, bias = masters()
    print(f'마스터 다크 바닥값(합성 바이어스) {bias:.0f} ADU', flush=True)
    ids = list(S[S.do_stack].sort_values('n').sid) if '--all' in sys.argv else [a for a in sys.argv[1:] if not a.startswith('--')]
    FAILED = os.path.join(HERE, 'failed.json')
    failed = json.load(open(FAILED, encoding='utf-8')) if os.path.exists(FAILED) else {}
    if '--retry-failed' in sys.argv:
        failed = {}
    for sid in ids:
        if sid in failed:
            print(f'{sid}: 이전 실패({failed[sid][:60]}), 건너뜀 (--retry-failed로 재시도)', flush=True); continue
        try:
            run(sid, md, bpm, bias)
        except Exception as e:
            print(f'{sid}: 실패 — {e}', flush=True)
            failed[sid] = str(e)[:300]
            shutil.rmtree(os.path.join(WORK, sid), ignore_errors=True)
        json.dump(failed, open(FAILED, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if '--cleanup-masters' in sys.argv:
        shutil.rmtree(MAST, ignore_errors=True)
