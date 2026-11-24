"""astrohunt 공통 설정. 모든 단계 스크립트가 이 모듈에서 경로를 가져갑니다.

설정 파일 위치(우선순위):
  1) 환경변수 ASTROHUNT_CONFIG
  2) 저장소 최상위의 astrohunt.json
"""
import os, sys, json
from zoneinfo import ZoneInfo

PKG = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(PKG)
CONFIG_PATH = os.environ.get('ASTROHUNT_CONFIG') or os.path.join(REPO, 'astrohunt.json')
if not os.path.exists(CONFIG_PATH):
    sys.exit(f'설정 파일이 없습니다: {CONFIG_PATH}\n  astrohunt.example.json 을 astrohunt.json 으로 복사해 경로를 고쳐 주세요.')
_C = json.load(open(CONFIG_PATH, encoding='utf-8'))

def _p(key, default=None):
    v = _C.get(key, default)
    return os.path.normpath(os.path.expandvars(os.path.expanduser(v))) if isinstance(v, str) else v

# 입력 (읽기만 함)
RAW = _p('raw_root')                       # 그 아래 Light/<대상>/, Flat/, Dark/
LIGHT = os.path.join(RAW, 'Light')
# 출력
STACKS = _p('stacks_dir')                  # 세션별 linear.fit, processed.tif/jpg, info.json
WORK = _p('work_dir')                      # 분석 결과·캐시 (오래 남는 것)
TEMP = _p('temp_dir')                      # 스태킹 임시 파일 (빠른 SSD 권장, 끝나면 지움)
# 프로그램
SIRIL = _p('siril', r'C:\Program Files\Siril\bin\siril-cli.exe')
GPU_PY = _p('gpu_python') or sys.executable   # CUDA PyTorch가 설치된 파이썬
TIMEZONE = _C.get('timezone', 'Asia/Seoul')
TZ = ZoneInfo(TIMEZONE)
NIGHT_START, NIGHT_END = _C.get('night_hours', [18, 6])   # 이 시간 사이 촬영만 스태킹 (현지 시각)
MIN_EXPTIME = float(_C.get('min_exptime', 10))
MIN_FRAMES = int(_C.get('min_frames', 5))
SCOPE_BINS = _C.get('scope_bins', {'620': [0, 660], '700': [660, 780], '857': [780, 100000]})   # 초점거리 → 망원경 이름(mm)
DEFAULT_BIAS = _C.get('default_bias')     # 다크가 없을 때 쓸 바이어스(ADU). 비우면 다크에서 계산

# 작업 폴더 구조 (기존 분석 폴더와 같은 배치)
INVENTORY = os.path.join(WORK, 'stack', 'inventory')
STACK_LOG = os.path.join(WORK, 'stack', 'logs')
FRAME_RESULTS = os.path.join(WORK, 'results')
FRAME_CACHE = os.path.join(WORK, 'cache')
SKYBOT_CACHE = os.path.join(WORK, 'skybot_cache')
ANALYSIS = os.path.join(WORK, 'analysis')
ANALYSIS_RESULTS = os.path.join(ANALYSIS, 'results')
ANALYSIS_CACHE = os.path.join(ANALYSIS, 'cache')
REPORT_DIR = os.path.join(WORK, 'report')
RUN_LOG = os.path.join(WORK, 'logs')
# 임시 폴더 구조
MASTERS = os.path.join(TEMP, 'masters')
SSA_IN = os.path.join(TEMP, 'ssa')
SSA_OUT = os.path.join(TEMP, 'ssa_out')

for d in (STACKS, WORK, TEMP, INVENTORY, STACK_LOG, FRAME_RESULTS, FRAME_CACHE, SKYBOT_CACHE, ANALYSIS_RESULTS, ANALYSIS_CACHE, REPORT_DIR, RUN_LOG):
    os.makedirs(d, exist_ok=True)


def scope_of(focallen):
    for name, (lo, hi) in SCOPE_BINS.items():
        if lo <= focallen < hi:
            return int(name)
    return int(round(focallen))


def local_dt(astropy_time):
    """UTC astropy Time → 현지 datetime (naive)"""
    from datetime import timezone
    return astropy_time.to_datetime().replace(tzinfo=timezone.utc).astimezone(TZ).replace(tzinfo=None)
