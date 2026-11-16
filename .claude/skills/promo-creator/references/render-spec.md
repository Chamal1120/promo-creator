# Render spec — the integration boundary

Every scene, from either framework, is rendered to an intermediate ("mezzanine") file that
matches this spec. FFmpeg only ever sees these files.

> **Two tiers.** This page is the **master** tier (`renders/`), used only after the person
> says "finalize". During the feedback loop, scenes go to `renders/preview/` with the preview
> flags and are assembled at 480p. See `review-loop.md`. Size, fps and duration rules apply
> to both tiers, but a preview only has to match the aspect ratio, not the exact size.

## Default mezzanine

| Property | Value | Notes |
| --- | --- | --- |
| Container | `.mp4` | `.mov` only for alpha overlays (below) |
| Video codec | H.264 (High) | Both frameworks emit it natively |
| Quality | CRF 16 | Visually lossless for motion graphics; final encode is the only other generation |
| Pixel format | `yuv420p` | `yuv444p` only if the whole project agrees (thin colored text/UI) — then every scene uses it |
| Resolution | `production.json → format.width × height` (default 1920×1080) | Author at this size; no scaling in assembly |
| Frame rate | `format.fps` (default 30), constant | Same value in Remotion `<Composition fps>` and HyperFrames `data-fps` / `--fps` |
| SAR | 1:1 | |
| Audio | none (default) | Stems are mixed in FFmpeg. If `scene_audio: true`: AAC, 48 kHz, stereo |
| Duration | exactly `duration × fps` frames | Includes transition handles |

Change the spec only per project, in `production.json → format`, and re-render everything.

## Durations, transitions and handles

- Durations are whole frames. At 30 fps: 4.0 s = 120 frames ✓, 4.05 s ✗.
- A **cut** between A and B: A ends, B starts. Timeline length adds up exactly.
- An **FFmpeg transition** of `d` seconds (`transition_in` on the incoming scene) overlaps the
  last `d` s of A with the first `d` s of B. The timeline gets shorter by `d`:
  `total = Σ durations − Σ transition durations`.
  - A's last `d` s must keep something worth seeing (hold or continue motion; do not fade
    to black inside A unless that is the intent).
  - B's first `d` s must already contain its opening frame/background, not a blank frame.
- Transitions that morph content between scenes (shared-element moves, a logo flying from
  one layout to the next) cannot be done in FFmpeg. Put both scenes in the same framework and
  author the transition there; FFmpeg then sees a single scene or a hard cut.
- `production.py timeline <project>` prints each scene's start/end on the final timeline.
  Use those numbers for voiceover and SFX cues.

## Rendering from Remotion

One `<Composition>` per scene, id = scene id, `width`/`height`/`fps` from `format`,
`durationInFrames = duration × fps`.

```bash
cd projects/<slug>/remotion          # or the project root for Remotion-only
pnpm exec remotion render <scene-id> ../renders/02-<scene-id>.mp4 \
  --codec=h264 --crf=16 --pixel-format=yuv420p --muted
```

- Drop `--muted` only for `scene_audio: true` scenes (Remotion writes AAC).
- Add `--is-production=false` on test renders and `--license-key=...` if the person has a
  license (`/remotion-render`, `/remotion-license`).
- Remotion-only project: replace `..` with `.` (renders/ sits next to `src/`).

## Rendering from HyperFrames

One sub-composition per scene: `compositions/<scene-id>.html`, sized to the format, with its
own `data-duration` equal to the scene duration.

```bash
cd projects/<slug>/hyperframes
pnpm exec hyperframes check --json                # gate: zero errors
pnpm exec hyperframes render -c compositions/<scene-id>.html \
  --fps 30 --crf 16 -o ../renders/01-<scene-id>.mp4
```

- If a scene needs the root `index.html` (variables, shared audio, several sub-comps), give it
  its own root or render `index.html` with the root's `data-duration` set to that scene.
- HyperFrames may put audio in the file; the assembler ignores scene audio unless
  `scene_audio: true`, so no extra pass is needed.
- Follow `/hyperframes-cli` for render failures and long renders.

## Alpha overlays (lower thirds, logo bugs, captions over footage)

When one framework draws an overlay that sits on top of another framework's scene:

- Remotion: `--codec=prores --prores-profile=4444 --pixel-format=yuva444p10le` → `.mov`
  (see `/remotion-render` → transparent-videos).
- HyperFrames: `--format mov` (transparent) → `.mov`.
- Composite with FFmpeg `overlay` at an exact time (`references/ffmpeg.md`). Overlays are
  not handled by `production.py`; add them as a final step.

Prefer building the overlay inside the same framework as the scene beneath it when possible;
alpha mezzanines are large and add a compositing pass.

## Footage from raw-footage/

Footage that goes straight into the FFmpeg timeline (not inside a framework scene) must be
conformed to the spec first, into `projects/<slug>/media/`:

```bash
ffmpeg -i raw-footage/videos/clip.mov -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p,setsar=1" \
  -c:v libx264 -crf 16 -preset slow -an projects/<slug>/media/clip.mp4
```

Then list it in `production.json` as a scene with `"framework": "footage"`.
