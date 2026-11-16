# Promo-Creator

An agent skill for creating promo videos using motion-graphics with the help of **Remotion**, **Hyperframes** and **ffmpeg**.
Your harness (agent) acts as the production orchestrator. It collects a creative brief, splits the video into scenes,
picks the best framework for each scene, renders the scenes to a shared spec, and assembles and masters the final cut with ffmpeg.

## Installation

01. Create a folder for the video edits and `cd` into it.

```bash
mkdir my-promos && cd my-promos
```

02. Install the skill and open the harness.

```bash
npx skills add Chamal1120/promo-creator --skill promo-creator --skill promo-creator-setup -a claude-code -y
claude    # or your harness of choice
```

03. Then say *"set up the studio"* (or just ask for a video). Then the `promo-creator-setup` skill fires and:

- installs pnpm if missing (`curl -fsSL https://get.pnpm.io | sh -`)
- with your consent, downloads missing Python, ffmpeg and Hyperframes' Chrome into `~/.local`
- installs the Remotion and Hyperframes skills using `npx skills add`.
- pins the Remotion and Hyperframes versions for your user in `~/.config/promo-creator/pins.sh`,
  so every later project reuses pnpm's cache instead of downloading again.
- adds the Claude Code hooks and a `CLAUDE.md` block. (`AGENTS.md` in other harnesses)

Other harnesses: install with their `-a <agent>` id and the setup skill passes it on.

> !NOTE
> Windows users -> use WSL.

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
3. **Style lock**: `tokens.json` generates `tokens.css` for Hyperframes and `tokens.ts` for Remotion.
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
