"""모든 세션 shift-and-stack: GPU(chatterbox venv) → 해석(ssa_post). 이미 처리한 세션은 건너뜀.
--wait: 스태킹이 끝날 때까지 새로 생기는 npz를 계속 처리."""
import os, sys, json, glob, time, subprocess
import ssa_post as P
GPU_PY = r'C:\chatterbox\venv\Scripts\python.exe'
HERE = os.path.dirname(os.path.abspath(__file__))
SCALE = {620: 1.253, 700: 1.108, 857: 0.905}

def done(sid):
    return os.path.exists(os.path.join(P.RES, sid + '.json'))

def one(npz):
    sid = os.path.basename(npz)[:-4]
    info = json.load(open(os.path.join(r'H:\asiair\Stacks', sid, 'info.json'), encoding='utf-8'))
    sc = info.get('scale')
    if not sc or sc != sc:
        sc = SCALE[info['scope_mm']]
    env = dict(os.environ, PYTHONIOENCODING='utf-8'); env.pop('INJECT', None)
    r = subprocess.run([GPU_PY, os.path.join(HERE, 'ssa_gpu.py'), npz, P.SSA_OUT, f'{3 * sc:.4f}'], capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
    if r.returncode != 0:
        print(f'{sid}: GPU 실패 {r.stderr[-500:]}', flush=True); return
    if not os.path.exists(os.path.join(P.SSA_OUT, sid + '.json')):
        print(f'{sid}: 구간 없음(5장 미만)', flush=True)
        json.dump(dict(sid=sid, chunks=[], cands=[], note='no chunk'), open(os.path.join(P.RES, sid + '.json'), 'w')); return
    res = json.load(open(os.path.join(P.SSA_OUT, sid + '.json')))
    if not res['chunks']:
        json.dump(dict(sid=sid, chunks=[], cands=[], note='no chunk'), open(os.path.join(P.RES, sid + '.json'), 'w')); return
    P.process(sid)

if __name__ == '__main__':
    while True:
        todo = [f for f in sorted(glob.glob(os.path.join(P.SSA_IN, '*.npz'))) if not done(os.path.basename(f)[:-4])]
        for f in todo:
            try:
                one(f)
            except Exception as e:
                print(f'{os.path.basename(f)}: 실패 {e}', flush=True)
        stacking = os.path.exists(r'C:\stackwork\masters')
        if '--wait' not in sys.argv or (not todo and not stacking):
            break
        if not todo:
            time.sleep(60)
