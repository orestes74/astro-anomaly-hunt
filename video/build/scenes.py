"""영상 초안의 장면 목록 (영어 내레이션).

각 장면: (섹션, 화면, 내레이션 문장 목록)
화면 종류
  ('img', 경로)              저장소 기준 이미지, 천천히 확대
  ('vid', 경로)              저장소 기준 애니메이션, 반복 재생
  ('card', 제목, 본문)       글자 카드
  ('ph', 설명, 배경 이미지)  직접 찍어 넣을 자리 (주황색 표시)
  ('gen', 이름)              build_visuals.py가 그리는 도식
  ('quote', 줄 목록, 배경)   내레이션 없는 자막 장면
  ('cardimg', 제목, 본문, 배경)  어둡게 처리한 사진 위 글자 카드
  ('scroll', 경로)           긴 화면 캡처를 위에서 아래로 천천히 스크롤
"""

S = 'images/stacks/'
import os
U = os.environ.get('ASTRO_PHOTOS', 'video/build/photos').replace('\\', '/').rstrip('/') + '/'   # 직접 보정한 사진 폴더 (절대경로 권장)
FLAME, JELLY, M45, ROSE, SH124, SHARK = (U + 'Flame_Nebula_30s_color.jpg', U + 'SH2_248_jellyfish_30s60s_final.jpg',
    U + 'r_pp_M45_stacked.jpg', U + 'Rosette_natural.jpg', U + 'SH2_124_bright3_natural.jpg', U + 'LDN1235_Shark_final.jpg')
VEIL, MWDUST = U + 'west_veil_1009_reference_final.jpg', U + 'SH2_245_reference_style.jpg'
SCENES = [
    # 1. The dream
    (1, ('img', FLAME), [
        "Anyone who photographs the night sky eventually has this dream."]),
    (1, ('img', JELLY), [
        "What if one of my photos holds a star that no one has ever seen?"]),
    (1, ('img', M45), [
        "What if a nameless asteroid is drifting through the frame?"]),
    (1, ('img', ROSE), [
        "Or... what if it captured something no one can explain?"]),
    (1, ('img', SHARK), [
        "When I was in elementary school, E.T. was playing in theaters.",
        "I was the kid who carried a little E.T. doll on the tip of a pencil."]),
    (1, ('img', SH124), [
        "Korea was only just racing into industrialization back then, and the night sky was still dark.",
        "Whenever I looked up, the Milky Way flowed across it in a violet haze.",
        "And under it, I always wondered the same thing.",
        "Does that star have a name? And if not... could I give it one?"]),
    (1, ('cardimg', 'Pan-STARRS  ·  ZTF  ·  ATLAS  ·  Catalina', 'giant survey telescopes sweep the whole sky every few nights', JELLY), [
        "Years later, I finally got a telescope of my own.",
        "But when I aimed it at the sky, there was almost nothing left to name.",
        "Giant survey telescopes sweep the entire sky every night, and they find almost everything new first."]),
    (1, ('scroll', 'video/build/assets/folders.webp'), [
        "So, like most of us, I picked a few pretty pictures to process, and buried the rest on a hard drive.",
        "Nearly a year of imaging. Over five thousand frames, just sleeping there."]),
    (1, ('img', VEIL), [
        "But is that really the end of the story?",
        "Somewhere in those five thousand frames, could there still be something no one has seen?",
        "Today, I want to share what it actually takes to turn that childhood dream into reality. Because I tried."]),

    # 2. What can we find
    (2, ('card', 'Three ways to find something new', ''), [
        "With an amateur telescope, there are three ways to find something new."]),
    (2, ('card', '1.  Things that MOVE', 'asteroids  ·  comets'), [
        "First, things that move. Asteroids and comets, creeping slowly between the stars."]),
    (2, ('card', '2.  Things that CHANGE', 'novae  ·  supernovae  ·  variable stars'), [
        "Second, things that change.",
        "A nova that suddenly brightens, a supernova exploding in a distant galaxy, a variable star that rises and fades."]),
    (2, ('card', '3.  Things that SPREAD', 'faint cosmic dust and gas'), [
        "Third, things that spread out. The faint cosmic dust and gas scattered all along the Milky Way."]),
    (2, ('card', 'Compare with the map.\nFind what is not on it.', 'Gaia DR3: 1.8 billion stars  ·  1.4 million known asteroids'), [
        "And the principle behind all three is the same.",
        "Compare your image with a map of the sky, and look for what isn't on the map.",
        "Fortunately, that map already exists, and it's incredibly precise.",
        "The European Space Agency's Gaia satellite has measured the positions of nearly two billion stars.",
        "And the position of every known asteroid, more than a million of them, can be calculated for any date and time.",
        "So all I had to do was line up my photos precisely with that map. Easier said than done."]),

    # 3. Method
    (3, ('gen', 'sessions'), [
        "The first step, surprisingly, is just getting organized.",
        "Even in the same target folder, photos taken on a different night, with a different telescope, or with the camera rotated, are really different data.",
        "So I grouped everything into sessions. Same night, same telescope, same angle.",
        "Nearly a year of imaging became eighty-nine sessions."]),
    (3, ('vid', 'animations/single_vs_stack_M51.mp4'), [
        "A single frame is full of noise.",
        "But stack many frames of the same sky, perfectly aligned, and the noise fades while faint details emerge.",
        "Using flat frames from the same night to remove dust shadows and vignetting, I built seventy-six stacks."]),
    (3, ('img', 'images/transient/only_montage_0.png'), [
        "Next, every star in each image gets sky coordinates, and is matched against the Gaia map.",
        "That's where I hit my first wall.",
        "Tiny distortions near the edges of the lens produced sixty-nine thousand stars that weren't on the map.",
        "After modeling the distortion and matching again, that number dropped to about eight thousand.",
        "And here's the one big lesson.",
        "Ninety percent of finding something new is throwing out the fakes."]),
    (3, ('vid', 'animations/asteroid_1675.mp4'), [
        "Flip through the frames, and while the stars stay put, one dot moves on its own.",
        "That's how I re-found ten named asteroids and one comet in my own data.",
        "1675 Simonida."]),
    (3, ('vid', 'animations/asteroid_1008.mp4'), ["1008 La Paz."]),
    (3, ('vid', 'animations/asteroid_275.mp4'), ["275 Sapientia."]),
    (3, ('vid', 'animations/asteroid_C_2025.mp4'), [
        "And comet C/2025 R3, wrapped in its glowing coma."]),
    (3, ('img', 'images/ssa/ssa_vet/00_2026-04-20_M_101_857mm_300s_c0.png'), [
        "Asteroids too faint to see in a single frame need another trick.",
        "Guess the direction they're moving, shift each frame by that amount, and stack.",
        "Using a graphics card, I tried thousands of directions and speeds.",
        "Tested on known asteroids, it reached down to about magnitude eighteen."]),
    (3, ('vid', 'animations/variable_TT_Ori.mp4'), [
        "Then I compared star brightness between stacks of the same field, taken on different nights.",
        "This is TT Orionis, inside the Orion Nebula.",
        "Within a few weeks, its brightness changed dramatically. It's a very young star."]),
    (3, ('vid', 'animations/variable_V808_Ori.mp4'), [
        "In total, thirty-three stars changed brightness.",
        "And every single one was an already known variable star."]),
    (3, ('vid', 'animations/variable_FN_Cep.mp4'), [
        "That might sound disappointing, but it's actually good news.",
        "It means this method can catch a new variable star or a nova, as long as it's bright enough for my images."]),
    (3, ('img', 'images/dustgas/2026-05-15_NGC_7000_857mm_180s.png'), [
        "Finally, I overlaid the faint glow in my images with dust maps made by infrared satellites.",
        "In the best fields, the correlation was above zero point nine. Almost a perfect match.",
        "Nothing new turned up, at least down to what my images can resolve."]),

    # 4. What you can try
    (4, ('card', 'What you can try', ''), [
        "So what can you actually do to chase this dream? Here's what I learned."]),
    (4, ('card', '1.  Look again at the photos you already have', ''), [
        "One. Look again at the photos you already have.",
        "There are almost certainly asteroids in them. In my case, twenty-six asteroid trails were hiding in plain sight."]),
    (4, ('card', '2.  Shoot the same field again and again', ''), [
        "Two. Shoot the same field again and again.",
        "A field you've imaged only once can't be compared. Change only shows up across two or more images."]),
    (4, ('card', '3.  Take your flats the same night', ''), [
        "Three. Take your flats the same night.",
        "The fainter your target, the more your calibration decides the result."]),
    (4, ('card', '4.  Shoot with a goal',
         'New asteroids: near the ecliptic, 2 to 3 hours on one field\n'
         'Supernovae: galaxy-rich regions (Virgo, Perseus) every few weeks\n'
         'Novae: the Andromeda Galaxy (M31), often'), [
        "Four. Shoot with a goal.",
        "For new asteroids, stay on one field near the ecliptic for two to three hours.",
        "For supernovae, revisit galaxy-rich regions like Virgo or the Perseus cluster every few weeks.",
        "For novae, check the Andromeda Galaxy often. Dozens erupt there every year."]),
    (4, ('card', '5.  Be skeptical', 'satellite trails  ·  hot pixels  ·  overlapping stars'), [
        "And five. Be skeptical.",
        "Most things that look new are satellite trails, hot pixels, or overlapping stars.",
        "The first test is always the same. Does it show up on another night?"]),

    # 5. Automation
    (5, ('gen', 'pipeline'), [
        "Doing all of this by hand takes weeks. So I bundled it into a single program, as a first draft.",
        "Point it at your raw photo folder, run one command, and it splits the sessions, stacks them, hunts for asteroids, compares brightness, checks the dust, and writes a report.",
        "It only processes new photos, so you can simply run it after every imaging night."]),
    (5, ('gen', 'review'), [
        "At the bottom of the report is a list of candidates that a human needs to look at, with pictures.",
        "In the end, the final call is always made by human eyes.",
        "It's still a draft, tuned to my own setup and its folder layout. But all of the code is open."]),

    # 6. What I found
    (6, ('img', 'images/flash/m51_flash_full.png'), [
        "Through all of this, I found no new asteroid, and no new variable star.",
        "But one thing remained that I couldn't explain."]),
    (6, ('vid', 'animations/m51_flash_A.mp4'), [
        "April eighteenth, 2026. Three in the morning.",
        "A single five minute exposure of the galaxy M51.",
        "Two round, star-like dots."]),
    (6, ('vid', 'animations/m51_flash_B.mp4'), [
        "They're not in the frame five minutes earlier.",
        "And they're not in the frame five minutes later."]),
    (6, ('img', 'images/flash/M51_섬광_일직선.png'), [
        "Looking closer, there were three extremely faint streaks, running side by side in the same direction.",
        "And both flashes sat exactly on that line.",
        "Something seems to have been flying along that path, catching the sunlight for an instant."]),
    (6, ('gen', 'shadow'), [
        "But here's the strange part.",
        "At that moment, the Sun was thirty-one degrees below the horizon.",
        "To catch sunlight in that direction, an object had to be higher than one thousand one hundred twenty kilometers.",
        "Starlink satellites and the space station were already deep inside Earth's shadow."]),
    (6, ('card', '8,916', 'public satellites in that part of the sky  →  no match'), [
        "So I checked every one of the eight thousand nine hundred sixteen public satellites that could have been in that part of the sky.",
        "None of them matched."]),
    (6, ('card', '451', 'classified satellites tracked by amateurs  →  no match'), [
        "I also checked four hundred fifty-one classified satellites tracked by amateur observers.",
        "Their orbits were from seven months later, so I could only compare orbital planes. None of them lined up.",
        "I considered a low flying aircraft, but the shape and color of the light didn't fit."]),
    (6, ('img', 'images/flash/m51_flash_zoom.png'), [
        "As of today, it matches nothing in the catalogs I checked.",
        "I'm not saying it was an alien spacecraft. My best guess is sunlight glinting off something no one is tracking.",
        "But that's only a hypothesis.",
        "But the truth is, we don't know what it was."]),

    # 7. Your turn
    (7, ('img', U + 'r_pp_IC1318_Butterfly_stacked.jpg'), [
        "The dream of finding a new star sounds grand. But it starts on your own hard drive.",
        "Just by looking again at nearly a year of photos, I met ten asteroids, a comet, thirty-three variable stars, and one mysterious flash."]),
    (7, ('img', SH124), [
        "This time, I didn't get to name a new star.",
        "But that kid with the E.T. doll on a pencil, looking up at the Milky Way, asking, does that star have a name?",
        "Now, I finally have a way to search for the answer myself."]),
    (7, ('card', 'github.com/orestes74/astro-anomaly-hunt', 'code  ·  data  ·  images'), [
        "I hope you'll go looking for the star you've been carrying in your heart all these years.",
        "All of the code and data are linked in the description.",
        "And if you know what this flash might have been, please tell me in the comments."]),
    (7, ('quote', [
        "The solar system, a dot in the universe.",
        "The Earth, a dot within it.",
        "And on it, the small dot that is a human being.",
        "",
        "Through space, the universe engulfs me like a point.",
        "Through thought, I comprehend the universe.",
        "",
        "Blaise Pascal, Pensées"], MWDUST), []),
    (7, ('img', FLAME), []),
]

# 모션 그래픽으로 바꾼 장면 (motion.py가 내레이션 길이에 맞춰 렌더링)
MOTION = {9: 'three', 10: 'move', 11: 'change', 12: 'spread', 13: 'map', 14: 'sessions', 16: 'wall', 21: 'ssa',
          26: 'check0', 27: 'check1', 28: 'check2', 29: 'check3', 30: 'check4', 31: 'check5',
          32: 'pipeline', 38: 'shadow', 39: 'count8916', 40: 'count451'}
for _i, _name in MOTION.items():
    SCENES[_i] = (SCENES[_i][0], ('motion', _name), SCENES[_i][2])
# 팡세 엔딩은 뺌 (장면 번호는 유지해야 하므로 'skip'으로 표시)
SCENES = [(a, ('skip',), l) if v[0] == 'quote' else (a, v, l) for a, v, l in SCENES]
# 도입 15초: M51 섬광 미리보기 (장면 번호가 밀리므로 MOTION 적용 뒤에 앞에 붙임)
COLD_OPEN = [
    (0, ('img', 'video/build/assets/m51_open.jpg'), [
        "This is the galaxy M51, through my own telescope."]),
    (0, ('vid', 'animations/m51_flash_A.mp4'), [
        "In one five minute frame, two points of light appeared. Five minutes later, they were gone."]),
    (0, ('motion', 'count8916'), [
        "I checked thousands of satellites. None of them matched.",
        "So what was it? Let me start from the beginning."]),
]
SCENES = COLD_OPEN + SCENES
# 애니메이션은 영어 라벨판 사용
SCENES = [(a, ('vid', v[1].replace('animations/', 'video/build/assets/anim_en/')) if v[0] == 'vid' else v, l) for a, v, l in SCENES]

MUSIC = {   # 섹션별 배경음악 (video/music 기준)
    'main': 'sicilienne_c_flute_piano_strings_s42.wav',
    'mystery': 'sicilienne_b_cello_piano_s11.wav',
}
SECTION_MUSIC = {0: 'mystery', 1: 'main', 2: 'main', 3: 'main', 4: 'main', 5: 'main', 6: 'mystery', 7: 'main'}
VOICE, SPEED = 'am_michael', 0.95
