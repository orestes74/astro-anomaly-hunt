# 작업 인수인계 (2026-11-25)

새 Claude 세션에서 이어서 할 때 이 파일부터 읽게 하세요.

## 현재 상태
- 영어판 초안 `video/draft_en.mp4` (11:52) 완성. 저장소에는 없음(용량). 영어 내레이션(Kokoro `am_michael`, 속도 0.95), 하단 영어 자막(번인), 영어 라벨 애니메이션, 직접 보정한 사진, 모션 그래픽 18종. 팡세 엔딩은 뺌.
- 자막 `video/draft_en.srt`, 유튜브 소개란 `video/description_en.txt`(챕터 포함), 한국어 대본 `video/script_v2.md`.
- 사용자는 초안이 마음에 든다고 함.

## 남은 작업 (순서대로)
1. **도입부 끝에 M51 섬광 미리보기 2~3초** (시청 유지용). `scenes.py`에서 도입부 마지막 장면 뒤에 `animations/m51_flash_A` 짧게 삽입.
2. **잘 안 읽히는 분석 그림 2장을 모션 그래픽으로 교체**: 장면 25(먼지·가스 비교 패널), 장면 33(검토 표). `motion.py`에 새 함수 추가 후 `scenes.py`의 `MOTION` 사전에 등록.
3. **배경음악 교체**: 포레 「시실리엔」 분위기. 지금은 ACE-Step 생성곡 `sicilienne_c_flute_piano_strings_s42.wav`(임시, 피아노가 지저분함). 사용자가 곡을 고르면 `scenes.py`의 `MUSIC` 수정, 소개란 크레딧도 수정.
4. **최종본**: 하단 자막 없이 렌더(`assemble.py`에서 ass 필터 끄기) + 영어 SRT 별도.
5. **다국어**: 한국어·일본어·독일어·프랑스어·스페인어·중국어·포르투갈어 자막(SRT) + 더빙. 더빙은 Chatterbox Multilingual(`chatterbox.mtl_tts.ChatterboxMultilingualTTS`)로 영어 내레이션 목소리 복제. 언어별로 장면 길이를 다시 맞춘 영상. 화면 속 글자 카드는 영어 유지.

## 빌드 방법
```
# 직접 보정한 사진 폴더
set ASTRO_PHOTOS=<사진 폴더>
<kokoro venv python> video/build/tts.py
python video/build/build_visuals.py
python video/build/motion.py
python video/build/assemble.py
```
- 출력: `video/build/out/` (중간 파일), `video/draft_en.mp4`
- 영어 라벨 애니메이션: `ANIM_LANG=en ANIM_OUT=video/build/assets/anim_en python tools/make_animations.py`
- ffmpeg 필요. 인코딩은 libx264 veryfast crf20, 30fps, 최종 loudnorm -14 LUFS.

## 저장소에 없는 파일 (원래 PC에만 있음)
| 무엇 | 위치 |
|---|---|
| 직접 보정한 사진 (Flame, Jellyfish, M45, Rosette, SH2-124, Shark, Veil, SH2-245, IC1318) | `ASTRO_PHOTOS` 폴더 |
| 폴더 화면 캡처, 영어 애니메이션, M45 보정본 | `video/build/assets/` |
| 생성 음악 WAV | `video/music/` |
| 음성·장면·모션 중간 파일 | `video/build/out/` |
| 음악 생성 (ACE-Step, GPU 필요) | 별도 설치 폴더 |

## 지켜야 할 것
- 답변은 한국어로.
- 원본 FITS 폴더는 읽기만. 임시 파일은 끝나면 지움.
- 공개 저장소에 개인 경로·이메일·관측지 위치를 넣지 않음.
- 외부 서비스에는 하늘 좌표와 시각만 보냄.
