---
name: promo-creator
description: Make promo videos, ads, explainers, product demos, social clips and motion graphics with Remotion + HyperFrames + FFmpeg together. Read FIRST for any request to make, plan, edit, render, assemble or export a video, ad, explainer, promo, social clip or animation here. Collects the creative brief (taste, key lines, product facts), plans scenes, picks the best framework per scene, enforces a shared render spec, and assembles the final cut with FFmpeg.
---

# Promo Creator (Remotion + HyperFrames + FFmpeg)

You are the **production orchestrator**. You plan the video, split it into scenes, pick the
best rendering technology for each scene, coordinate the renders, and assemble one coherent
final video.

```
Claude Code (orchestrator: plan → choose → coordinate)
   ├── Remotion     React compositions, data viz, frame-based animation
   ├── HyperFrames  HTML/CSS/GSAP, DOM-based motion graphics
   └── FFmpeg       assembly, transitions, audio mix, loudness, final encode
                         ↓
                    Final video  →  exports/final/
```

Framework-specific rules live in their own skills. This skill decides **what** goes where and
**how the pieces meet**; load the framework skill before writing code for it:

| Work | Load |
| --- | --- |
| Any HyperFrames scene | `/hyperframes` (contract, work loop), `/hyperframes-cli`, `/hyperframes-registry` before hand-building effects |
| Any Remotion scene | `/remotion-best-practices` (router), then `/remotion-create`, `/remotion-markup`, `/remotion-render` |
| Music, SFX, VO, footage treatment, images, icons | `/media-use` |
| Captions | `/remotion-captions` or HyperFrames `references/captions.md` |
| Porting a Remotion scene to HyperFrames | `/remotion-to-hyperframes` |
| Remaking an existing video / a proven style | `/reverse-any-video`, `/style-sampling` |
| Figma source | `/figma` |

## First run: set up the studio

The studio is the folder the person installed this skill into. If `.claude/state/.prereq-met`
does not exist there (in Claude Code the SessionStart hook says `FIRST RUN`), load the
`promo-creator-setup` skill and follow it before any video work. The same applies when a
script here says the studio is not set up. Do not install tools or skills any other way.

Script paths below assume the usual install location `.claude/skills/promo-creator/`. If
your harness installed the skill elsewhere (for example `.agents/skills/`), use that folder.

**Packages:** pnpm only. Remotion and HyperFrames are exact devDependencies of each project
(`pnpm exec remotion …`, `pnpm exec hyperframes …`), at the versions pinned for this user in
`~/.config/promo-creator/pins.sh`. Never `npm`, never `npx` (the setup skill's
`npx skills add` is the only exception), never `@latest`.

Detailed references in this skill:

- `references/brief.md` — the creative-brief intake (taste, key lines, product facts)
- `references/folder-structure.md` — where everything lives
- `references/toolchain.md` — pnpm rules and the per-user version pins
- `references/render-spec.md` — the intermediate (mezzanine) spec and per-framework render commands
- `references/ffmpeg.md` — assembly, transitions, audio, loudness, delivery recipes
- `references/review-loop.md` — the 480p preview → feedback → finalize loop
- `references/qa.md` — verification checklist for previews and final
- `templates/` — BRIEF, FEEDBACK, PLAN, production.json, tokens.json (copied by `scaffold.sh`)
- `scripts/production.py` — `validate`, `timeline`, `verify`, `status`, `assemble`, `sync-tokens`
- `scripts/scaffold.sh <slug> [--remotion] [--hyperframes]`, `scripts/common.sh` (shared settings, pins)

## Root folder

The studio folder (where the person installed the skill) is the root: `projects/<slug>/`, `raw-footage/` (read-only),
`references/`, `exports/{drafts,final}/`. Never scaffold outside it. Create and extend projects
only with `scripts/scaffold.sh` (details in `references/folder-structure.md` if needed).

## Multi-Framework Video Production

You have access to three complementary production technologies:

1. Remotion
2. HyperFrames
3. FFmpeg

You are encouraged to use Remotion and HyperFrames together whenever doing so improves the
final video.

### Framework Independence

Do not assume that an entire video must use one framework. Choose the most appropriate
framework for each scene, animation, or composition. Remotion and HyperFrames are
complementary technologies, not mutually exclusive alternatives.

### Remotion

Use Remotion for:

- React-based compositions.
- Data-driven animations.
- Charts and graphs.
- Complex component-based interfaces.
- Frame-accurate animation.
- Dynamic content.
- Reusable React components.

### HyperFrames

Use HyperFrames for:

- HTML/CSS compositions.
- GSAP animations.
- DOM-based motion graphics.
- Website demonstrations.
- CSS-driven effects.
- Animated layouts.
- Browser-native visual effects.

### FFmpeg

Use FFmpeg for:

- Assembling scene renders into one timeline (cuts and transitions).
- Audio: music, voiceover, SFX placement, ducking, fades, loudness normalization.
- Final encoding and delivery variants (aspect ratios, bitrates, thumbnails).
- Inspecting and conforming media (`ffprobe`, normalization of raw footage).

### Example: 60-second software product ad

| Scene | Preferred technology |
| --- | --- |
| Animated logo introduction | HyperFrames |
| Product UI demonstration | HyperFrames |
| Animated statistics | Remotion |
| Complex React interface | Remotion |
| Animated typography | Either |
| Final audio mixing | FFmpeg |

These are preferences, not restrictions.

### Combined Production

When a video benefits from both frameworks:

1. Divide the video into independently manageable scenes.
2. Determine which framework is best suited to each scene.
3. Develop each scene using its respective framework.
4. Maintain consistent resolution, frame rate, color palette, typography and timing.
5. Render each scene using its framework's supported rendering mechanism.
6. Assemble the scenes into a coherent video.
7. Use FFmpeg for final encoding, audio mixing and post-processing.

### Interoperability Requirements

- Never assume that Remotion components can directly execute inside HyperFrames.
- Never assume that HyperFrames compositions can directly execute inside Remotion.
- Treat each framework as an independent rendering environment.
- Use rendered intermediate video files as the integration boundary.
- Standardize intermediate codecs, resolution, frame rate and audio configuration
  (`references/render-spec.md`).
- Avoid unnecessary re-encoding between stages.
- Maintain exact scene durations and transition boundaries.
- Verify that all scenes are synchronized before final assembly
  (`python3 .claude/skills/promo-creator/scripts/production.py verify`).

### Decision Making

You are responsible for choosing the most effective production architecture.

Do not use both frameworks merely for the sake of using both. Use one framework when it is
sufficient. Combine them when their individual strengths provide a meaningful improvement.

The final video should appear as one coherent production, regardless of how many
technologies were used to create it.

Quick tie-breakers when a scene could go either way:

- Data arrays, props-driven variants, charts, or reusing React components → **Remotion**.
- Captured website, GSAP choreography, CSS effects, registry blocks (transitions, kinetic
  type, overlays) that already exist → **HyperFrames**.
- The rest of the video already lives in one framework and the scene has no special need →
  **the same framework** (fewer boundaries, fewer render passes).
- A transition that must morph content *across* two scenes → keep both scenes in one
  framework; FFmpeg can only blend finished pixels (fade, wipe, slide, etc.).

## The production workflow

Work in phases. Each phase has a gate; do not skip a gate unless the person said "no stops".

### Phase 0 — Creative brief  *(gate: person confirms the brief)*

Never start planning a new video without a brief. Follow `references/brief.md` and ask the
person, in one compact round (pre-filling whatever the request or `references/` already says):

1. **Taste**: how it should feel, in words, or as reference videos or photos/mood boards,
   plus brand assets and what to avoid. Ask permission before opening any reference image or
   video (the person's standing media rule).
2. **Key lines**: the hook/headline, supporting lines, the exact call to action, and any
   legal lines. Also whether each is fixed copy or a draft you may tighten. If they have none,
   offer 2–3 drafts to choose from.
3. **Product/service facts**: what it is, audience, problem, proof points, differentiator, and
   the real assets available (UI/URL, photos, footage, logo). Use the type-specific questions
   in `references/brief.md`.
4. **Production facts**: platform and aspect ratio, length, deliverables, music/VO/captions,
   language, deadline. If the video has a voiceover, ask exactly: *"Do you need no-VO files?"*
   (music + SFX only), **once per project**. Record the answer under "No-VO files" in
   `BRIEF.md` and reuse it for every later version, language and aspect ratio of the project.
   Do not ask again unless the person brings it up; the default is no.

Run `scripts/scaffold.sh <slug>` (kebab-case; copies all templates), fill
`projects/<slug>/BRIEF.md`, play it back in 5–8 lines, and
get a yes. If the person says "you decide" or "no questions", choose defaults and record them
under **Assumptions**. Real assets (product screens, logo, footage) beat drawn substitutes.

### Phase 1 — Plan  *(gate: person approves the plan)*

1. Work in `projects/<slug>/` from Phase 0 (`PLAN.md`, `production.json`, `tokens.json` are
   already there from the templates).
2. Write `PLAN.md` from `BRIEF.md`: logline, story beats, a **scene table** (id, duration,
   framework, why, content, transition, audio cues), style decisions, deliverables. Every key
   line from the brief lands in exactly one scene, verbatim if it is marked fixed.
3. Fill `production.json`: format, every scene with its framework, source, render path,
   exact duration (whole frames) and transition, plus audio stems.
4. Run `production.py timeline <project>` to print the scene start/end times and total
   length; check it against the brief.
5. Present the scene table with the framework choice + one-line reason per scene. Wait for
   approval on anything over ~15 s.

### Phase 2 — Style lock

- `tokens.json` is the single source of truth for palette, fonts, type scale, spacing,
  easing curves and motion durations. Every taste adjective from `BRIEF.md` becomes a number here.
- Saving `tokens.json` regenerates `hyperframes/assets/tokens.css` (`:root` custom
  properties such as `--color-accent`, `--type-scale-h1`) and `remotion/src/tokens.ts`
  (`import { tokens } from './tokens'`) through a hook. Without hooks, run
  `production.py sync-tokens <project>`. Never hand-edit the generated files.
- HyperFrames: link `assets/tokens.css` in `index.html` and use `var(--…)`. Remotion: read
  `tokens.*`.
- Same font **files** in both: `remotion/public/fonts/` and `hyperframes/assets/fonts/`.
- Match easing: GSAP `power2.out` ≈ Remotion `Easing.out(Easing.quad)`; `power3.out` ≈
  `Easing.out(Easing.cubic)`; `expo.out` ≈ `Easing.out(Easing.exp)`. Record the chosen pairs
  in `tokens.json` → `motion.easing`.
- Scenes must enter and exit on matching backgrounds/colors at each cut so boundaries read as
  one film.

### Phase 3 — Build scenes

- Scaffold only the frameworks the plan uses:
  `scripts/scaffold.sh <slug> --remotion` and/or `--hyperframes`. It uses pnpm and the user's
  pinned versions; never scaffold by hand, with `npm`/`npx`, or with `@latest`. Running it with
  `--hyperframes` on an older project adds the pinned `hyperframes` devDependency if missing.
- Follow each framework skill's own rules exactly: HyperFrames contract + `check --json` +
  `snapshot`; Remotion markup, Studio preview, interactivity. The framework skills' advice
  to render at full quality is replaced here by the preview tier until the person finalizes.
- Author every scene at the production resolution and fps. Each scene's length must equal
  its `production.json` duration **including transition handles** (see render-spec).
- Keep one composition per scene (Remotion `<Composition id="<scene-id>">`; HyperFrames
  `compositions/<scene-id>.html`) so scenes render independently.
- Keep the framework live previews (HyperFrames `preview`, Remotion Studio) running so the
  person can scrub between preview cuts.

### Phase 4 — The review loop  *(repeats until the person says "finalize")*

Follow `references/review-loop.md`. Every output in this phase is **480p**:

```bash
# render only new/stale scenes, to the preview tier
pnpm exec remotion render <id> ../renders/preview/NN-<id>.mp4 --scale=0.5 --codec=h264 --crf=23 --x264-preset=ultrafast --pixel-format=yuv420p --muted
pnpm exec hyperframes render -c compositions/<id>.html --fps 30 --quality draft -o ../renders/preview/NN-<id>.mp4
# assemble the 480p review cut
python3 .claude/skills/promo-creator/scripts/production.py assemble projects/<slug> --preview
```

1. Render, assemble, and hand over `exports/drafts/<slug>-preview-vN.mp4` with a 2–4 bullet
   "what changed".
2. Collect feedback (timestamps → scenes via `production.py timeline`) and log it verbatim
   in `FEEDBACK.md` with the concrete change list.
3. Apply the changes (`BRIEF.md` / `tokens.json` / `production.json` / scene code) and
   re-render only the affected scenes. Then go back to step 1.
4. End every hand-off with: *"Reply with feedback, or **finalize** to render the
   full-resolution master."* "Looks good" is not approval. Ask.

`verify` fails on any mismatch in aspect ratio, fps, pixel format, codec or duration
(> 1 frame). Fix the scene and re-render; never stretch or pad in FFmpeg to hide it.

### Phase 5 — Finalize and master  *(only after the person's "finalize")*

1. Write `projects/<slug>/APPROVED.md`: their words, the date, the approved preview version.
   A hook refuses this file unless the person's latest message says "finalize".
2. Render every scene at the master tier, `renders/NN-<id>.mp4`, using the commands in
   `references/render-spec.md` (H.264, CRF 16, yuv420p, full size, production fps).
3. `production.py verify projects/<slug>`, then `production.py assemble projects/<slug> --final`:
   two-pass loudness (default −14 LUFS, −1 dBTP), `+faststart`,
   `exports/final/<slug>-final-vN.mp4`. Pure-cut videos stream-copy the video.
4. QA checklist (`references/qa.md`). Extra deliverables (9:16, GIF, thumbnail, captions):
   `references/ffmpeg.md`. Captions ship as a separate sidecar file (`.srt`, plus `.vtt` if the
   platform needs it) next to the master. Do not render burned-in caption videos unless the
   person explicitly asks for one in this project. Render no-VO (`-novo`) versions only when
   `BRIEF.md` records a yes to "Do you need no-VO files?" — never by default, and never re-ask.
5. Report: path, duration, resolution, size, loudness, and which framework made each scene.
   Further changes reopen the loop (remove `APPROVED.md` with the person's agreement).

## Hooks (Claude Code: `.claude/settings.json` → `hooks/promo_hooks.py` in this skill)

`promo-creator-setup` installs these hooks in Claude Code. They enforce the pipeline in code,
so there you do not need to re-check these things by hand.

**Other harnesses have no hooks.** Follow the same rules yourself: run
`production.py validate <project>` after editing `production.json` and
`production.py sync-tokens <project>` after editing `tokens.json`; render only with the
preview flags until the person says "finalize"; never write `APPROVED.md` without that word
in their latest message; never touch `raw-footage/` or overwrite `exports/final/`; send long
render/install output to `.claude/logs/` and read only its tail.

| Event | What it does | What it means for you |
| --- | --- | --- |
| SessionStart | Injects a compact studio status: projects, scene render state (ok/missing/stale), latest exports | Do not explore the tree to find out where things stand |
| PreToolUse Bash | Adds `-hide_banner -loglevel warning -nostats` to plain `ffmpeg` and `-v error` to `ffprobe`. Sends `remotion/hyperframes render`, `create-video` and `pnpm install/add` (or `npm i`) output to `.claude/logs/*.log` and shows only the last 25 lines. Adds `--skip-skills` to `hyperframes init` | Write commands normally. Open the log file only when the tail shows a failure |
| PreToolUse Bash | Denies `npx` (except `npx skills add`) and `npm install`, preview renders without preview flags, master renders (`renders/`) before `APPROVED.md` exists or without spec flags, shell writes of `APPROVED.md`, `rm`/`mv` in `raw-footage/`, and `ffmpeg -y` onto raw-footage or final exports | A denial message gives the corrected command, so use it |
| UserPromptSubmit | Records when the person's latest message says "finalize"; any later message clears it | Only then can `APPROVED.md` be written |
| PreToolUse Write/Edit | Denies writes in `raw-footage/`, overwrites in `exports/final/`, edits to generated token files, and `APPROVED.md` without a recorded "finalize" | Edit `tokens.json` instead; never self-approve |
| PostToolUse Write/Edit | Validates `production.json` on every save (a failure blocks with the errors); regenerates tokens on `tokens.json` save | Fix reported errors right away |
| PostToolUse Bash | After a scene render, reports every scene's state for that tier | Re-render only scenes listed as stale/missing/mismatch |

Rewrites apply only to single, simple commands (no `;`, `&&`, pipes, redirects or `$(…)`), so keep
media commands simple to benefit. Commands containing `-y` are never rewritten.

## Hard rules

1. Rendered video files are the only integration boundary between Remotion and HyperFrames.
2. One production spec per project (`production.json` → `format`); every scene matches it.
3. Durations are whole frames: `duration × fps` must be an integer.
4. Audio is mixed once, in FFmpeg, from stems — not baked into scenes — unless a scene's
   sound is inseparable from its visuals (then set `"scene_audio": true` on that scene).
5. Master tier: one lossy generation per stage, mezzanine renders → one final encode. No
   intermediate re-encodes. Pure-cut assemblies stream-copy video. (Previews may re-encode freely.)
6. `raw-footage/` is read-only. Conformed/derived media goes into the project folder.
7. Until the person says "finalize", render only 480p previews (preview tier). Never decide
   on your own that the video is final, even in "no stops" mode: deliver the preview and wait.
8. Respect each framework's license (Remotion may need a company license —
   `/remotion-license`).
