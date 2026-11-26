"""섬광·궤적 대조에 쓰는 위성 궤도(TLE)를 받습니다. tle_match.py, tle_plane.py가 이 파일들을 읽습니다.

1) 공개 위성, 관측한 날의 궤도 (Space-Track gp_history)
   CelesTrak 등은 '현재' 궤도만 주므로, 지난 날짜의 궤도는 Space-Track(미국 우주군 운영, 무료 가입)에서만 받을 수 있습니다.
   계정 정보는 환경변수로만 읽습니다 (코드·저장소에 넣지 마세요):
       set SPACETRACK_USER=<가입 이메일>
       set SPACETRACK_PASS=<비밀번호>
   python get_tle.py public 2026-04-16 2026-04-18 [최소 원지점 km, 기본 1000]
   → tle/tle_20260416_20260418.txt (3줄 형식, 같은 위성의 여러 epoch 포함. tle_match.py가 관측 시각에 가장 가까운 것을 고름)
   원지점 조건: 밤 깊은 시각에는 높은 위성만 햇빛을 받으므로, 그림자 안에 있었을 낮은 위성은 빼서 용량을 줄입니다.
   사진의 시선 방향에서 햇빛을 받는 최소 높이보다 낮게 잡아야 빠짐없이 대조됩니다 (M51 섬광은 1,120 km 이상 → 1,000 km).
   Space-Track 이용 규칙: gp_history는 무거운 조회라 같은 범위를 반복해서 받지 말고 파일로 저장해 다시 쓰세요.

2) 기밀 위성 (Mike McCants classfd, 아마추어 관측자들이 추적한 비공식 궤도)
   python get_tle.py classified
   → tle/classfd/classfd.tle
   한계: 최신본 하나만 공개되므로 지난 날짜의 위치는 알 수 없습니다. 궤도면(위성이 지나는 고리)은 몇 달 사이 크게 바뀌지 않아,
   tle_plane.py는 '궤도 고리가 시야를 지나갔는지, 방향·햇빛 조건이 맞는지'만 봅니다. 맞지 않으면 배제할 수 있지만,
   맞는다고 해서 그 위성이라고 확정할 수는 없습니다.
"""
import os, sys, io, zipfile
import requests

OUT = 'tle'
ST = 'https://www.space-track.org'
CLASSFD = 'https://www.mmccants.org/tles/classfd.zip'

def public(start, end, min_apogee=1000):
    user, pw = os.environ.get('SPACETRACK_USER'), os.environ.get('SPACETRACK_PASS')
    if not (user and pw):
        sys.exit('SPACETRACK_USER, SPACETRACK_PASS 환경변수를 설정하세요 (https://www.space-track.org 무료 가입)')
    q = (f'{ST}/basicspacedata/query/class/gp_history/EPOCH/{start}--{end}/APOAPSIS/>{min_apogee}'
         f'/orderby/NORAD_CAT_ID,EPOCH/format/3le')
    with requests.Session() as s:
        r = s.post(f'{ST}/ajaxauth/login', data={'identity': user, 'password': pw}, timeout=60)
        if r.status_code != 200 or 'Failed' in r.text:
            sys.exit('Space-Track 로그인 실패')
        r = s.get(q, timeout=600); r.raise_for_status()
    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, f"tle_{start.replace('-', '')}_{end.replace('-', '')}.txt")
    open(dst, 'w', encoding='utf-8').write(r.text)
    n = sum(1 for l in r.text.splitlines() if l.startswith('1 '))
    print(dst, n, 'TLE sets')

def classified():
    r = requests.get(CLASSFD, timeout=60); r.raise_for_status()
    d = os.path.join(OUT, 'classfd'); os.makedirs(d, exist_ok=True)
    zipfile.ZipFile(io.BytesIO(r.content)).extract('classfd.tle', d)
    print(os.path.join(d, 'classfd.tle'))

if __name__ == '__main__':
    if len(sys.argv) >= 4 and sys.argv[1] == 'public':
        public(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 1000)
    elif len(sys.argv) == 2 and sys.argv[1] == 'classified':
        classified()
    else:
        sys.exit(__doc__)
