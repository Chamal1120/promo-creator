# AI Video Editor

A Claude Code studio for motion-graphics videos built with **Remotion**, **HyperFrames** and **FFmpeg**.
Claude acts as the production orchestrator. It collects a creative brief, splits the video into scenes,
picks the best framework for each scene, renders the scenes to a shared spec, and assembles and
masters the final cut with FFmpeg.

## Install (new users)

You need **Node.js 22+**. Everything else is installed for you as your normal user (no sudo).

```bash
mkdir my-promos && cd my-promos
npx skills add Chamal1120/promo-creator --skill promo-creator --skill promo-creator-setup -a claude-code -y
claude    # or your harness of choice
```

Then say *"set up the studio"* (or just ask for a video). The `promo-creator-setup` skill:

- installs pnpm if missing (`curl -fsSL https://get.pnpm.io | sh -`)
- with your OK, downloads missing Python, FFmpeg and HyperFrames' Chrome into `~/.local`
- installs the Remotion and HyperFrames skills (`npx skills add`, the only npx use)
- pins the Remotion and HyperFrames versions for your user in `~/.config/promo-creator/pins.sh`,
  so every later project reuses pnpm's cache instead of downloading again
- adds the Claude Code hooks and a `CLAUDE.md` block (`AGENTS.md` in other harnesses)

Other harnesses: install with their `-a <agent>` id and the setup skill passes it on.
Windows: use WSL.

## Layout

```
projects/<slug>/      one video: BRIEF.md, PLAN.md, production.json, tokens.json,
                      remotion/ and/or hyperframes/, audio/, media/, renders/
raw-footage/          source videos, audio, images (read-only)
references/           inspiration, scripts, storyboards
exports/drafts|final  480p previews (<slug>-preview-vN.mp4), masters (<slug>-final-vN.mp4)
.claude/skills/       promo-creator + promo-creator-setup (committed); Remotion / HyperFrames skills (installed, ignored)
                      hooks live in promo-creator/hooks/promo_hooks.py
```

## Workflow

1. **Brief**: taste (words, reference videos, photos), key lines, product facts, format.
2. **Plan**: a scene table that names the framework for each scene, and `production.json`.
3. **Style lock**: `tokens.json` generates `tokens.css` for HyperFrames and `tokens.ts` for Remotion.
4. **Build and preview** each scene in its framework.
5. **Review loop**: render changed scenes to `renders/preview/`, then `assemble --preview` (480p),
   collect feedback in `FEEDBACK.md`, and repeat. Nothing renders at full resolution yet.
6. **Finalize**: when you reply "finalize", Claude writes `APPROVED.md`, renders master scenes
   to `renders/` (H.264 CRF 16, full size), and runs `assemble --final` (two-pass loudness, versioned).

```bash
P=.claude/skills/promo-creator/scripts/production.py
python3 $P timeline projects/<slug>
python3 $P verify   projects/<slug>
python3 $P assemble projects/<slug> --preview   # 480p review cut; add --dry-run to print the ffmpeg commands
python3 $P assemble projects/<slug> --final     # only after "finalize" (APPROVED.md)
```

Requirements: Node 22+ (installed by you). pnpm, Python 3.10+, FFmpeg/ffprobe and Chrome are set up by `promo-creator-setup`.
