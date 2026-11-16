# QA checklist

## Before assembly (every scene)

- [ ] Framework gate passed: HyperFrames `check --json` zero errors and snapshots reviewed;
      Remotion Studio preview reviewed, no console errors.
- [ ] Rendered at the project spec (`production.py verify` passes).
- [ ] Duration = planned duration (±0 frames ideally, ±1 tolerated).
- [ ] First and last frames match the neighbours' backgrounds/colors at each boundary.
- [ ] Text inside title-safe (80%), content inside action-safe (90%).
- [ ] Fonts actually loaded (no fallback serif/sans in snapshots).

## Each preview round

- [ ] `production.py timeline` total matches the brief.
- [ ] Look at frames around every boundary (½ s before/after each cut) for jumps, flashes,
      blank frames, color shifts between frameworks.
- [ ] Audio cues land on their visuals (VO lines, SFX hits, music downbeats on cuts).
- [ ] Music ends cleanly (fade or musical ending), not cut mid-note.
- [ ] The person has watched the 480p preview (`exports/drafts/<slug>-preview-vN.mp4`) and the round is logged in `FEEDBACK.md`.

Looking at frames or audio means opening media files: follow the person's standing rules
(e.g. ask before viewing images/video).

## Final

- [ ] Output duration = timeline total (±1 frame) — `assemble` checks this automatically.
- [ ] Integrated loudness at target (±1 LU), true peak ≤ −1 dBTP.
- [ ] `+faststart` set, H.264 High, yuv420p, AAC 48 kHz stereo.
- [ ] Versioned file name; previous versions untouched.
- [ ] Report: path, duration, resolution, size, loudness, scene → framework map.
