"""astrohunt: 망원경 원본 사진 폴더 → 스태킹 → 이상 천체 탐색 → 보고서, 한 번에.

사용법
  python astrohunt.py                     # 전체 실행 (새로 생긴 파일·세션만 처리)
  python astrohunt.py --dry-run           # 무엇을 할지만 보여줌
  python astrohunt.py --steps stack,ssa   # 일부 단계만
  python astrohunt.py --skip dustgas      # 일부 단계 빼기
  python astrohunt.py --retry-failed      # 예전에 실패한 세션도 다시 스태킹
  python astrohunt.py --config 다른설정.json

단계
  inventory  원본 FITS 헤더 목록 (새 파일만 읽음)
  sessions   세션 나누기(대상·밤·망원경·카메라 각도·노출) + 같은 밤 플랫 짝짓기
  stack      Siril로 보정·정렬·스태킹 → 스택 폴더에 linear.fit / processed.tif / processed.jpg
  frames     프레임 한 장씩: 이동 천체 궤적, 단일 프레임 섬광, 알려진 소행성 대조, 검출 한계
  ssa        GPU shift-and-stack으로 어두운 소행성 (이번에 스태킹한 세션)
  transient  세션 스택 비교: Gaia에 없는 새 천체, 밝기가 변한 별 → VSX 대조, 강제측광 재확인
  dustgas    전천 먼지(IRAS/Planck)·Hα 지도와 비교
  report     보고서와 '눈으로 확인할 목록' 만들기
  cleanup    임시 폴더 비우기 (stack과 ssa가 이번 실행에서 끝났을 때 자동)
"""
import os, sys, json, glob, time, shutil, argparse, subprocess, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(HERE, 'astrohunt')

STEPS = {
    'inventory': [('stack/inventory.py', [])],
    'sessions': [('stack/sessions.py', [])],
    'stack': [('stack/run_stack.py', ['--all'])],
    'frames': [('frames/extract.py', []), ('frames/link.py', []), ('frames/verify.py', []), ('frames/skyfixed.py', []),
               ('frames/verify_events.py', []), ('frames/recall.py', [])],
    'ssa': [('analysis/run_ssa.py', []), ('analysis/ssa_sig.py', []), ('analysis/ssa_vet.py', []), ('analysis/ssa_montage.py', [])],
    'transient': [('analysis/prefetch_gaia.py', []), ('analysis/transient.py', ['catalog', '--all']), ('analysis/refit_wcs.py', []),
                  ('analysis/transient.py', ['compare']), ('analysis/vet_transient.py', []), ('analysis/vet_local.py', []),
                  ('analysis/vet_montage.py', []), ('analysis/vet_forced.py', []), ('analysis/vet_var.py', []), ('analysis/vet_var_img.py', [])],
    'dustgas': [('analysis/dustgas.py', ['--best']), ('analysis/dustgas_blobs.py', []), ('analysis/dustgas_ident.py', [])],
    'report': [('report.py', [])],
    'cleanup': [],
}
ORDER = list(STEPS)
# 다시 계산하며 덮어쓰는 결과는 실행 전에 백업
BACKUP = {'frames': ['results/tracklets_classified.json', 'results/report.csv', 'results/flashes.csv', 'results/events.json'],
          'transient': ['analysis/results/transient/transient_candidates.json', 'analysis/results/transient/var_keep.json',
                        'analysis/results/transient/only_forced.json'],
          'ssa': ['analysis/results/ssa_significant.json']}


class Tee:
    def __init__(self, path):
        self.f = open(path, 'a', encoding='utf-8')
    def __call__(self, s=''):
        print(s, flush=True); self.f.write(s + '\n'); self.f.flush()


def run_script(log, rel, args, env):
    script = os.path.join(PKG, rel)
    cmd = [sys.executable, '-W', 'ignore', script] + args
    log(f'  $ {rel} {" ".join(args)}')
    t = time.time()
    p = subprocess.Popen(cmd, cwd=os.path.dirname(script), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding='utf-8', errors='replace')
    tail = []
    for line in p.stdout:
        line = line.rstrip()
        log('    ' + line); tail = (tail + [line])[-15:]
    p.wait()
    log(f'    → 종료 코드 {p.returncode}, {time.time() - t:.0f}초')
    return p.returncode == 0, tail


def main():
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding='utf-8')   # 파이프·파일로 보낼 때 한글 깨짐 방지
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--config', default=os.path.join(HERE, 'astrohunt.json'))
    ap.add_argument('--steps', help='쉼표로 구분한 단계 (기본: 전체)')
    ap.add_argument('--skip', default='', help='뺄 단계')
    ap.add_argument('--retry-failed', action='store_true')
    ap.add_argument('--keep-temp', action='store_true', help='끝나도 임시 폴더를 지우지 않음')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    os.environ['ASTROHUNT_CONFIG'] = os.path.abspath(a.config)
    sys.path.insert(0, PKG)
    import cfg
    steps = [s.strip() for s in a.steps.split(',')] if a.steps else ORDER[:]
    bad = [s for s in steps if s not in STEPS]
    if bad:
        sys.exit(f'모르는 단계: {bad}. 가능한 단계: {ORDER}')
    steps = [s for s in ORDER if s in steps and s not in a.skip.split(',')]

    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    log = Tee(os.path.join(cfg.RUN_LOG, f'run_{ts}.log'))
    log(f'astrohunt 시작 {ts}\n  설정 {cfg.CONFIG_PATH}\n  원본 {cfg.RAW} (읽기만)\n  스택 {cfg.STACKS}\n  작업 {cfg.WORK}\n  임시 {cfg.TEMP}\n  단계 {steps}')
    if not os.path.isdir(cfg.LIGHT):
        sys.exit(f'원본 폴더에 Light 폴더가 없습니다: {cfg.LIGHT}')
    if 'stack' in steps and not os.path.exists(cfg.SIRIL):
        sys.exit(f'Siril을 찾을 수 없습니다: {cfg.SIRIL}')
    if 'ssa' in steps:
        r = subprocess.run([cfg.GPU_PY, '-c', 'import torch;print(torch.cuda.is_available())'], capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f'gpu_python 에 PyTorch가 없습니다: {cfg.GPU_PY}  (ssa 단계를 빼려면 --skip ssa)')
        log(f'  GPU 사용 가능: {r.stdout.strip()}')
    if a.dry_run:
        for s in steps:
            log(f'[{s}] ' + ', '.join(f'{r} {" ".join(x)}'.strip() for r, x in STEPS[s]))
        return

    env = dict(os.environ, PYTHONIOENCODING='utf-8', ASTROHUNT_CONFIG=os.path.abspath(a.config))
    ok_steps, failed = [], []
    for s in steps:
        log(f'\n=== [{s}] {datetime.datetime.now():%H:%M:%S}')
        if s == 'cleanup':
            continue
        if s in BACKUP:
            bdir = os.path.join(cfg.WORK, 'backup', ts, s)
            for relp in BACKUP[s]:
                src = os.path.join(cfg.WORK, relp)
                if os.path.exists(src):
                    os.makedirs(bdir, exist_ok=True); shutil.copy2(src, bdir)
        if s == 'sessions':
            before = set(os.listdir(cfg.STACKS))
        good = True
        for rel, args in STEPS[s]:
            args = args + (['--retry-failed'] if s == 'stack' and a.retry_failed else [])
            ok, tail = run_script(log, rel, args, env)
            if not ok:
                good = False; failed.append((s, rel, tail)); break
        if s == 'sessions' and good:
            import pandas as pd
            S = pd.read_pickle(os.path.join(cfg.INVENTORY, 'sessions.pkl'))
            new = [x for x in S[S.do_stack].sid if x not in before]
            log(f'  스태킹할 새 세션 {len(new)}개' + (': ' + ', '.join(new[:20]) + (' ...' if len(new) > 20 else '') if new else ''))
        (ok_steps if good else []).append(s)

    # 임시 폴더 정리: 스태킹 임시 파일과 SSA 입력은 ssa가 끝난 뒤에만 필요
    do_clean = ('cleanup' in steps and a.steps) or ('stack' in ok_steps and 'ssa' in ok_steps and not a.keep_temp)
    if do_clean:
        for d in os.listdir(cfg.TEMP):
            p = os.path.join(cfg.TEMP, d)
            shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)
        log(f'\n임시 폴더를 비웠습니다: {cfg.TEMP}')
    elif os.listdir(cfg.TEMP):
        log(f'\n임시 폴더를 남겨 두었습니다: {cfg.TEMP} (ssa 단계 뒤 `--steps cleanup` 으로 비우기)')

    log('\n=== 결과')
    log(f'  성공 단계: {ok_steps}')
    for s, rel, tail in failed:
        log(f'  실패: [{s}] {rel}\n      ' + '\n      '.join(tail[-6:]))
    rep = os.path.join(cfg.REPORT_DIR, 'REPORT_auto.md')
    if os.path.exists(rep):
        log(f'  보고서: {rep}')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
