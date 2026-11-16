---
name: promo-creator-setup
description: Set up a folder as a promo-creator video studio - studio folders, the Remotion and HyperFrames skills, version pins, Claude Code hooks and the tools (pnpm, Python, FFmpeg, Chrome) - with no root or sudo. Use right after promo-creator is installed, when the studio says FIRST RUN or `.claude/state/.prereq-met` is missing, when a promo-creator script says the studio is not set up, or when the person asks to set up, install, repair or check the video studio.
---

# Promo Creator setup

Turns the folder the person installed `promo-creator` into a working studio. Everything runs
as the normal user: tools go under `~/.local`, studio files into the folder. Never use `sudo`.
Works in any harness that can run bash (Linux, macOS, WSL on Windows).

The script is `scripts/setup.sh` in this skill's folder (usually
`.claude/skills/promo-creator-setup/scripts/setup.sh`). Run it from the studio folder.

## Steps

1. **Check** (changes nothing):
   ```bash
   bash .claude/skills/promo-creator-setup/scripts/setup.sh --check
   ```
   - "promo-creator is not installed next to promo-creator-setup": ask the person to install
     both skills into this folder, then start again.
   - **Node.js missing or older than 22: stop.** Tell the person to install Node.js 22+ (LTS
     from https://nodejs.org or their version manager), open a new terminal, restart the
     harness and ask again. Do not install Node yourself.
   - pnpm missing is fine: setup installs it with `curl -fsSL https://get.pnpm.io | sh -`.

2. **Ask before downloading tools.** If the check lists missing tools (Python, FFmpeg), tell
   the person what will be downloaded and where, in one message:
   > Setup needs: Python 3.12 (~30 MB, via uv), FFmpeg + FFprobe (~40 MB, static build) and
   > HyperFrames' Chrome (~150 MB). All go into ~/.local or your user cache; no admin rights.
   > It will also add ~/.local/bin to PATH in your shell profile. OK to go ahead?

   Only list what is actually missing. Wait for a yes.

3. **Set up**:
   ```bash
   bash .claude/skills/promo-creator-setup/scripts/setup.sh                    # tools already there
   bash .claude/skills/promo-creator-setup/scripts/setup.sh --install-tools    # after the person's yes
   ```
   Outside Claude Code, add `--agent <id>` with the `npx skills` agent id of your harness
   (`codex`, `cursor`, `opencode`, `gemini-cli`, …), the same one used to install promo-creator.

   It then:
   - creates the studio folders (`projects/`, `raw-footage/`, `references/`, `exports/`)
   - installs the Remotion and HyperFrames skills with their official installers
     (`npx skills add remotion-dev/skills`, `npx skills add heygen-com/hyperframes`). This is
     the only place `npx` is used; everything else uses pnpm.
   - pins the Remotion and HyperFrames versions for this user in
     `~/.config/promo-creator/pins.sh`. Versions already pinned there are reused, so pnpm's
     cache serves every later project without downloading again. Never change a pin unless
     the person asks to upgrade.
   - Claude Code: merges the hooks into `.claude/settings.json` and adds the studio block to
     `CLAUDE.md`. Other harnesses: adds the studio block to `AGENTS.md` (no hooks).
   - writes `.claude/state/.prereq-met`.

4. **Read the exit code**:
   - `0`: ready. Continue with the person's video request (load `promo-creator`).
   - `2`: ready, but new skills or PATH changes need a fresh session. Ask the person to
     restart the harness (and open a new terminal if tools were installed), then ask for
     their video.
   - `1`: relay the listed problems. "Chrome needs system libraries" is the one case that
     needs admin rights. Give the person the package names and let them decide; do not run
     `sudo` yourself. Full output is in `.claude/logs/setup.log`.

Re-running is safe. Once `.prereq-met` exists, setup exits at once. Pass `--force` to repair
or re-check.

## What it never does

- Install or upgrade Node.js, or install anything system-wide.
- Use `sudo`, `npm install` or `npx` (except `npx skills add`).
- Change existing version pins, other hooks, or your text outside its marked block in
  `CLAUDE.md` / `AGENTS.md`.
