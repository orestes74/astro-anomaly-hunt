**English** | [한국어](REPORT.ko.md)

# Anomaly search results (2026-11-20)

Scope: 5,108 light frames from the raw `Light` folder (one corrupted file, `M 44 ..._0004.fit`, excluded), 581 sequences.
The raw FITS files were only read, never modified. Only sequence center coordinates and times were sent to an external service (IMCCE SkyBoT).

## 1. Moving objects (asteroids & comets): 11 known objects detected, 0 new candidates

| Object | Brightness (V) | Target folder | Notes |
|---|---|---|---|
| Comet C/2025 R3 (PANSTARRS) | comet | C2025 R3 PANSTARRS | about 6.8″/min, coma visible |
| 275 Sapientia | 13.9 | M 44 | detected in 27 of 27 frames |
| 1675 Simonida | 14.6 | NGC 7293 | |
| 1008 La Paz | 15.1 | NGC 7293 | |
| 2525 O'Steen | 15.9 | SH2 248 jellyfish | |
| 6859 Datemasamune | 16.0 | M 3 | |
| 1135 Colchis | 16.1 | M 45 | |
| 1999 Hirayama | 16.2 | sh2 245 | |
| 2436 Hatshepsut | 16.5 | IC 4592 | |
| 51371 2000 XF15 | 16.9 | M 3 | |
| 43354 2000 SZ278 | 17.1 | IC 4604 | |

- There were 317 moving-trail candidates in total. 26 were known objects; the other 291 were all false.
  - 258 removed by the sky-fixed position test
  - 22 stationary stars or blended double stars, checked by eye
  - 11 hot pixels
- **No unidentified moving object passed vetting.**
- Detection limit (fraction of known asteroids in the field that were actually detected): 4 of 6 at V<15, 3 of 6 at V15–16, 4 of 8 at V16–17, 1 of 43 at V17–18, 0 above V18.
  So **only objects brighter than about V≈17 are found reliably.** Detection runs on each frame separately (no stacking), so fainter objects are missed.

## 2. Single-frame flashes (transient events): 1 strong case

- **M 51, `Light_M 51_300.0s_Bin1_20260418-030615_16deg_0019.fit`** (exposure start 2026-04-17 18:01 UTC, 300 s)
  - Two bright point sources at x,y ≈ (1730,1659) and (1328,1242). They are absent from the frames five minutes before and after.
  - They have no tails, look like stars, and are slightly sharper than the long-exposure stars. That is what a flash shorter than a second looks like.
  - Two satellite trails cross the same frame, and (1328,1242) lies on the extension of the fainter one.
  - → **The most likely explanation is a glint from a tumbling satellite.** Matching against TLE orbit data can confirm it.
  - Further review (`shadow.py`, 2026-11-21):
    - The observation was at 03:01 KST, with the Sun 31° below the horizon. Along this line of sight an object had to be **at least about 1,120–1,170 km above the ground** to be in sunlight. Low-orbit satellites like Starlink (~550 km) and the ISS were in Earth's shadow.
    - A round, star-like flash means the object barely moved during the flash. A satellite 1,300 km away moves about 1,000 px per second, so at that distance the flash must have lasted a few milliseconds or less. A glint from a higher, slower object (medium or highly elliptical orbit) would be more natural. B lying on the faint trail could be a coincidence. → Correction (2026-11-21, `results/flashB_track.log`): B is 0.9 px from the faint trail's center line, within the line-fit residual (0.9 px). A random point lands that close only about 0.1% of the time, so **B is taken to be a glint from the object that left the faint trail.** B's total light equals 2,800 px worth of that trail, yet it is not stretched along the trail. So it shone at least about 1,400 times (about 8 magnitudes) brighter than usual, only while the object moved 2 px. The bright trail, by contrast, varies in brightness by up to about 8× along its length, which suggests a tumbling object.
    - Flash A (`flashA_lines.py`, `results/flashA_lines.log`, 2026-11-21):
      - I summed brightness along lines through A in every direction. The 90.5° direction, the same as the other two trails, gave a significance of 7.6. Parallel lines 15–60 px to the side gave 1–4, and the same spot in the neighboring frames (0018, 0020) gave nothing (1–2). The same method gives 32.7 on B, confirming that it works.
      - → **A very faint third parallel trail also passes through A.** It is about 1/4 as bright as the faint trail. A is taken to be a glint from this third object, like B; its peak brightness was more than about 10,000 times its usual level (A is saturated, so this is also a lower limit).
      - Three parallel trails in the same direction (x≈1000, 1330, 1730, spaced 330 and 400 px) can be explained as a group following the same orbit a few seconds apart. During the exposure the observer moves with Earth's rotation, which shifts the trails of leading and trailing objects sideways. At about 1,200 km altitude that means 5–6 seconds apart, about 35–40 km along the orbit (rough estimate).
      - I looked for recent launches: Plesetsk at 4/16 23:17 UTC (Soyuz-2.1b/Volga, several Kosmos military satellites) and Jiuquan at 4/17 04:10 UTC (Long March 4C, Daqi-2). Both went to about 500–700 km and would have been in shadow at the time, so neither made these trails.
    - A third point in the same frame, (2448,2403), lies only 0.23 px off the A–B line. But it is a sharp vertical line 1 px wide and 8 px long, so it is a cosmic ray. The alignment is judged a coincidence.
    - TLE matching (`tle_match.py`, 2026-11-21, `tle/tle_20260417.txt`: epochs 4/16–17, 8,916 objects, no Starlink):
      - During the 300 s exposure, 4 objects came within 3° of the field, and only one crossed the image: CZ-2D DEB (44607, 838 km). That debris was in Earth's shadow, and its direction (−70°) differs from the two trails in the image (nearly vertical, −89°).
      - **No cataloged object passed near A or B while sunlit.** The closest was thousands of pixels away.
      - The two vertical trails (x≈1000 bright, x≈1330 faint, with B on it) also match no object in the list. They may be objects not in this file, for example classified satellites with no public TLE. Two trails flying side by side, needing at least 1,100 km to be sunlit, fits the paired NOSS satellites, but this is an unconfirmed hypothesis.
      - Log: `results/tle_match.log`
    - Classified satellite matching (`tle_plane.py`, 2026-11-21, McCants `classfd.tle`, 451 objects, epoch 2026-11):
      - With epochs seven months later, there is no way to know where each satellite was at the time. So only orbital planes were compared: does an orbit ring cross the field during the exposure, and if so, do its direction and sunlight match? The observer's motion from Earth's rotation during the exposure was included, and the method was validated on CZ-2D DEB from the public TLEs.
      - The only orbits crossing the field were 13 StarShield satellites (about 580 km). All were in Earth's shadow, and their direction (−105°) differs from the trails (−89°).
      - The closest NOSS pair, NOSS 3-5 (A/B), has its orbital plane about 15° away from the field. That is hard to explain with seven months of precession error, so **the NOSS hypothesis is rejected** (assuming no orbital maneuvers in between).
      - Conclusion: neither flash A or B nor the two vertical trails match any object in the public or classified lists. The public file (8,916 objects) was downloaded from Space-Track `gp_history` filtered to apogee above 1,000 km (verified: minimum apogee in the file is 1,000 km). Objects left out never rise above 1,000 km, so along this line of sight, where 1,120 km was needed to be sunlit, they were all in shadow. **Every public object that could have been visible was checked.** What remains is an object not in any list (untracked or unpublished) or an aircraft.
      - Log: `results/tle_plane.log`
    - Brightness and size (`flash_phot.py`, `flash_size.py`, 2026-11-21; zero point from 198 Gaia DR3 stars, ±0.25 mag):
      - Flash A is G 10.7 mag as a 300 s integrated equivalent (the peak is saturated, so it was actually brighter); B is 11.4 mag. If each lasted 1 second, that is 4.5 and 5.2 mag.
      - Both trails are white, like stars, not the red and green of aircraft wingtip navigation lights.
      - Trail object sizes (diffuse reflection, albedo 0.2) at 1,150 km altitude: the bright one about 4 mag and 7 m across, the faint one about 5 mag and 4 m across. Higher altitudes mean larger objects (about 19 m and 12 m at GPS altitude).
      - Flash size (flat mirror reflection, reflectivity 0.9): to look round like a star the flash must last a few ms or less, which requires a mirror at least 20 cm across (at 1,150 km) to 60 cm (at geostationary orbit).
      - It remains unexplained that an object this bright and this large appears in neither the public nor the classified list.
    - Aircraft (fighter jet) hypothesis (2026-11-21, `results/jet_profile.log`): I also checked whether low-flying aircraft could explain it.
      - The telescope is focused at infinity, so an object at distance L is blurred into a disk of about D/L radians for aperture D (a ring, with a central obstruction).
      - Measured profile widths (FWHM, 2×2 binning): bright trail about 3.5″, faint trail ≤1.8″, flashes A and B 1.8–3.5″. All are much narrower than the stars (8.8″) and have a single sharp peak, not a flat or hollow profile.
      - With a conservative aperture of 150–280 mm, a blur of 2–3.5″ or less requires a distance of at least about 10–30 km.
      - Explaining the 288″ gap between the two trails as the wingspan of a fighter jet (about 10 m) requires a distance of about 7 km, which would blur them into rings 6–10″ across. And the color is white, not the red and green of navigation lights. → **The wingtip-light explanation is rejected.**
      - Two aircraft each leaving a trail from above 10 km cannot be fully ruled out without knowing the exact aperture.
- Satellite flares and short trails: M 42 (0011, 0013), Zeta Ophiuchi (0027, dotted), Flame Nebula (0161), Rosette (0224, faint and diffuse, uncertain).
- Excluded:
  - 141+ cosmic rays
  - 51 sources that persist into neighboring frames
  - 37 points on satellite trails
  - 36 extended sources
  - all of sh2-124 frame `_0100` (the mount shook)

## 3. Trails (satellites, aircraft, meteors)

- 113 long trails (800 px or more) in 105 frames.
- Most common targets: M 42 (14), Flame Nebula (12), M 33 (10), Rosette (10).
- Trails have not yet been sorted into satellites, aircraft and meteors.

## 4. Stacking (added 2026-11-23)

- The data were split into 89 sessions (continuous imaging runs), and 76 were stacked. Results are in the stacks folder under `<session>/`.
  - Each holds a linear result and a processed result.
  - Flats taken between 18:00 and 06:00 were used to calibrate lights from the same night.
- Failed sessions:

  | Cause | Sessions |
  |---|---|
  | 0 usable frames | M31 700mm, 63 Gem |
  | 1–2 usable frames | M92, NGC 2264 ×3, test_p2 |
  | Star registration failed | C2025_R3 60s and 30s, LDN 386 |

- The 2026-09-14_GAIA_208068134588948 stack has no WCS, so it was left out of all three analyses below.

## 5. Faint asteroids (shift-and-stack, GPU)

- Method:
  - Sessions were split into chunks of up to 60 minutes.
  - Star-subtracted residual images were shifted along a grid of velocities and summed. Only motions of 6 px or more were considered.
- Recovery of known asteroids:

  | Brightness (V) | Recovered |
  |---|---|
  | 16–17 | 4/4 |
  | 17–18 | 8/13 |
  | 18–19 | 17/65 |

  So the real limit is about V≈18–18.5.
- For each chunk the tail of the noise distribution was fitted, and the significance threshold was set where false alarms come to 0.05 per chunk.
- All 42 candidates above this threshold were inspected visually. Each was one of:
  - edge effects
  - residuals around bright stars
  - nebula structure
  - pieces of satellite trails
- **New moving objects: 0**

## 6. Novae, supernovae and variable stars (comparing session stacks)

- Star-list coordinates were re-fitted to Gaia DR3, including lens distortion (3rd-order SIP), for a median error of 0.2–0.7″.
- **8,133 point sources not in Gaia → 0 new-object candidates**
  - Fixed sources also seen in other sessions: 750
  - Matches with known asteroids: 80
  - Only in this session: 656, of which 189 fell where the coordinates are accurate.
  - Forced photometry at the same positions in other sessions for those 189:
    - 156 were present in other sessions too (they had only been missed in list matching).
    - The rest were one of:
      - satellite trails
      - blended stars
      - stacks with poor star shapes: west veil 10-08 (elongated stars), 09-18 (ring-shaped stars)
- **1,981 stars changed brightness between sessions → 0 new variable stars**
  - Re-checking with forced photometry left 45 (|Δm|>0.4, 6σ or more, no neighboring stars).
  - 33 are variables already listed in VSX.
    - Young stars in Orion: AH Ori, TT Ori, V808 Ori, HY Ori, AS Ori, ...
    - Eclipsing binaries: FN Cep, V1229 Cep, ...
    - YSOs, RR Lyr
  - Of the 12 not listed, 11 are in NGC 6960 (05-08 vs 08-07). Different filters were used, so brightness differences depend on star color.
  - The last one is a giant HII region in M101. It is extended, so its measured brightness depends on the photometry conditions.
  - This also confirms the method catches real variable stars.

## 7. Dust and gas (vs. IRIS 100 µm, Planck 857 GHz and Hα maps)

- 36 flat-calibrated stacks (the deepest for each target) were star-removed, matched to 5′ resolution, and compared with all-sky maps.
- Example correlation coefficients: M101 0.93/0.97, M33 0.90/0.95, NGC 7023 0.75/0.84, NGC 7293 0.86
- Residual blobs above 4σ were one of:
  - the target itself (M82, the disk of M31, ...)
  - vignetting at the image edges
  - halos around bright stars
  - fine structure within known nebulae (M42, IC 443, Horsehead and Flame, Veil, Rosette, M8, Cepheus Flare)
- A few ambiguous 5–6σ blobs remain:
  - small Hα blobs in M5, M106, NGC 6960, M16 and Rosette
  - around a G5.8 star in the Cepheus Flare (probably reflected light)
  - all at the level of the resolution and flattening limits.
- **Conclusion: no anomalous dust or gas structures**

## Summary

None of the three searches found a new anomalous object. Limits and open items:

- Asteroids can be found down to about V≈18.
- Session comparison is only possible for fields imaged two or more times.
- Temporary stacking files were written to a local SSD, not the raw-data disk.

## Files

- `results/tracklets_classified.json`, `results/report.csv`: trail list and classification
- `results/recall.csv`: whether each known asteroid in the field was detected
- `results/flashes.csv`, `results/streaks.csv`, `results/flash_cutouts/`, `results/review/`: flash and trail lists and review images
- Stacking: `stack/run_stack.py`. Asteroids: `analysis/run_ssa.py` → `ssa_sig.py` → `ssa_vet.py`. Session comparison: `analysis/transient.py` (catalog → compare) → `refit_wcs.py` → `vet_transient.py` → `vet_local.py` → `vet_forced.py` → `vet_var.py` → `vet_var_img.py`. Dust and gas: `analysis/dustgas.py` → `dustgas_blobs.py` → `dustgas_ident.py`
- Results: `analysis/results/` (ssa_significant.json, ssa_vet/, transient/var_keep.json, transient/var_keep_montage.png, transient/only_forced.json, dustgas/)
- Frame pipeline order: `extract.py` → `link.py` → `verify.py` → `skyfixed.py` → `verify_events.py` → `recall.py`
