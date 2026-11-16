#!/usr/bin/env bash
# Set up a promo-creator studio in the current folder. No root/sudo needed, for any harness.
#   bash <promo-creator-setup>/scripts/setup.sh --check            # report only, changes nothing
#   bash <promo-creator-setup>/scripts/setup.sh [--agent <id>]     # set up the studio folder
#   bash <promo-creator-setup>/scripts/setup.sh --install-tools    # also install missing tools (user-level)
#   add --force to re-run after the studio is already set up
#
# Studio (inside the folder): studio folders, Remotion + HyperFrames skills (`npx skills add`, the only
#   npx use), Claude Code hooks, the CLAUDE.md / AGENTS.md pointer, version pins, .claude/state/.prereq-met.
# Node.js must already be installed: setup stops and asks the person to install it.
# pnpm is installed automatically when missing (curl -fsSL https://get.pnpm.io | sh -).
# Tools (only with --install-tools, all under ~/.local, never system-wide):
#   Chrome for HyperFrames via pnpm dlx, Python via uv, FFmpeg + FFprobe static builds.
# Exit codes: 0 ready; 1 something missing (listed); 2 ready, but restart the harness first
#   (new skills or a new PATH entry are only seen by a fresh session).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTER="$HERE/../../promo-creator"
if [[ ! -f "$MASTER/scripts/common.sh" ]]; then
  echo "promo-creator is not installed next to promo-creator-setup. Install both skills into this folder first."
  exit 1
fi
# shellcheck source=../../promo-creator/scripts/common.sh
source "$MASTER/scripts/common.sh"

check=0; install_tools=0; force=0; agent="claude-code"
while (( $# )); do
  case "$1" in
    --check) check=1 ;;
    --install-tools) install_tools=1 ;;
    --force) force=1 ;;
    --agent) agent="${2:?--agent needs a value}"; shift ;;
    *) echo "unknown option: $1"; exit 1 ;;
  esac
  shift
done

ROOT="$(studio_root "$HERE")"
cd "$ROOT" || exit 1
MARKER=".claude/state/.prereq-met"
LOCAL="$HOME/.local"; BIN="$LOCAL/bin"; SHARE="$LOCAL/share/promo-creator"
ORIG_PATH="$PATH"
export PNPM_HOME="${PNPM_HOME:-$LOCAL/share/pnpm}"
export PATH="$BIN:$PNPM_HOME:$PATH"
mkdir -p .claude/logs 2>/dev/null; LOG="$ROOT/.claude/logs/setup.log"
(( check )) || : > "$LOG"

if [[ -f "$MARKER" && $force -eq 0 && $check -eq 0 ]]; then
  echo "setup: studio already set up ($(head -1 "$MARKER")). Pass --force to re-run."
  exit 0
fi

problems=(); restart=0
ok()   { echo "  ok   $*"; }
bad()  { echo "  FAIL $*"; problems+=("$*"); }
note() { echo "  ...  $*"; }
has()  { command -v "$1" >/dev/null 2>&1; }
fetch() { if has curl; then curl -fsSL "$1"; else wget -qO- "$1"; fi; }

echo "promo-creator setup in $ROOT"
case "$(uname -s)" in
  Linux) OS=linux ;; Darwin) OS=darwin ;;
  *) echo "Unsupported system $(uname -s). On Windows, run this inside WSL."; exit 1 ;;
esac
case "$(uname -m)" in x86_64|amd64) ARCH=x64 ;; aarch64|arm64) ARCH=arm64 ;; *) ARCH="$(uname -m)" ;; esac

# ------------------------------------------------------------------ tools (user-level installs)
python_ok() { has python3 && python3 -c "import sys; sys.exit(sys.version_info < tuple(map(int, '$MIN_PYTHON'.split('.'))))" 2>/dev/null; }
node_ok()   { has node && (( $(node -p 'process.versions.node.split(".")[0]') >= MIN_NODE_MAJOR )); }

install_python() {
  note "installing Python 3.12 with uv (into $BIN)"
  has uv || fetch https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$BIN" UV_NO_MODIFY_PATH=1 sh >>"$LOG" 2>&1
  uv python install 3.12 >>"$LOG" 2>&1 && ln -sf "$(uv python find 3.12)" "$BIN/python3"
  restart=1
}
install_ffmpeg() {
  mkdir -p "$SHARE" "$BIN"
  if [[ $OS == darwin ]] && has brew; then
    note "installing ffmpeg with Homebrew"; brew install ffmpeg >>"$LOG" 2>&1; return
  fi
  local tmp; tmp="$(mktemp -d)"
  if [[ $OS == linux ]]; then
    local a; a=$([[ $ARCH == arm64 ]] && echo arm64 || echo amd64)
    note "downloading FFmpeg static build (johnvansickle.com, $a)"
    fetch "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-$a-static.tar.xz" > "$tmp/ff.tar.xz" &&
      tar -xJf "$tmp/ff.tar.xz" -C "$tmp" && rm -rf "$SHARE/ffmpeg" &&
      mv "$tmp"/ffmpeg-*-static "$SHARE/ffmpeg" &&
      ln -sf "$SHARE/ffmpeg/ffmpeg" "$BIN/ffmpeg" && ln -sf "$SHARE/ffmpeg/ffprobe" "$BIN/ffprobe"
  else
    note "downloading FFmpeg + FFprobe (evermeet.cx; Intel build, needs Rosetta on Apple silicon)"
    mkdir -p "$SHARE/ffmpeg"
    for t in ffmpeg ffprobe; do
      local u="https://evermeet.cx/ffmpeg/getrelease/zip"; [[ $t == ffprobe ]] && u="https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip"
      fetch "$u" > "$tmp/$t.zip" && unzip -o -q "$tmp/$t.zip" -d "$SHARE/ffmpeg" && ln -sf "$SHARE/ffmpeg/$t" "$BIN/$t"
    done
  fi
  rm -rf "$tmp"
  restart=1
}

# Node.js: required, never installed by this script.
if ! node_ok; then
  echo "  FAIL node $MIN_NODE_MAJOR+ not found"
  has node && echo "       found $(node -v), which is too old."
  echo
  echo "setup: STOPPED. Ask the person to install Node.js $MIN_NODE_MAJOR or newer (LTS from https://nodejs.org"
  echo "  or their usual version manager), open a new terminal, restart the harness, and run setup again."
  exit 1
fi
ok "node $(node -v)"

# pnpm: installed automatically with the official script (user-level, no sudo).
if ! has pnpm; then
  has curl || { echo "  FAIL pnpm not found and curl is missing; ask the person to install curl or pnpm."; exit 1; }
  note "installing pnpm: curl -fsSL https://get.pnpm.io | sh -"
  curl -fsSL https://get.pnpm.io | sh - >>"$LOG" 2>&1
  hash -r; restart=1
fi
has pnpm && ok "pnpm $(pnpm -v)" || { echo "  FAIL pnpm install failed (see ${LOG#$ROOT/})"; exit 1; }

need_tools=()
python_ok  || need_tools+=(python)
{ has ffmpeg && has ffprobe; } || need_tools+=(ffmpeg)

if (( install_tools && ${#need_tools[@]} )); then
  has curl || has wget || { echo "need curl or wget to download tools"; exit 1; }
  for t in "${need_tools[@]}"; do "install_$t"; hash -r; done
fi

python_ok && ok "python $(python3 -c 'import platform; print(platform.python_version())')" || bad "python3 >= $MIN_PYTHON not found"
for t in ffmpeg ffprobe; do has "$t" && ok "$t" || bad "$t not found"; done
if (( ${#problems[@]} )) && (( ! install_tools )); then
  echo
  echo "setup: missing tools: ${need_tools[*]}. Ask the person, then re-run with --install-tools"
  echo "  (user-level, no sudo: Python ~30 MB, FFmpeg ~40 MB, Chrome ~150 MB)."
  exit 1
fi
(( ${#problems[@]} )) && { echo; echo "setup: tools still missing (see ${LOG#$ROOT/})."; exit 1; }

if (( check )); then
  [[ -f "$PINS_FILE" ]] && ok "pins: $(tr '\n' ' ' < "$PINS_FILE")" || echo "  --   no version pins yet (setup pins them)"
  [[ -f "$MARKER" ]] && ok "studio set up" || echo "  --   studio not set up yet (run without --check)"
  exit 0
fi

# ------------------------------------------------------------------ version pins (per user)
if [[ -z "${REMOTION_VERSION:-}" ]]; then
  v="$(pnpm view create-video version 2>>"$LOG")" && [[ -n "$v" ]] && pin_set REMOTION_VERSION "$v" || bad "could not look up the Remotion version"
fi
if [[ -z "${HYPERFRAMES_VERSION:-}" ]]; then
  v="$(pnpm view hyperframes version 2>>"$LOG")" && [[ -n "$v" ]] && pin_set HYPERFRAMES_VERSION "$v" || bad "could not look up the HyperFrames version"
fi
[[ -n "${REMOTION_VERSION:-}" && -n "${HYPERFRAMES_VERSION:-}" ]] &&
  ok "pins: remotion $REMOTION_VERSION, hyperframes $HYPERFRAMES_VERSION ($PINS_FILE)"

# ------------------------------------------------------------------ Chrome for HyperFrames
if [[ -n "${HYPERFRAMES_VERSION:-}" ]]; then
  if chrome="$(pnpm dlx "hyperframes@$HYPERFRAMES_VERSION" browser path 2>>"$LOG" | tail -1)" && [[ -x "$chrome" ]]; then
    ok "chrome (hyperframes)"
  elif (( install_tools )); then
    note "downloading HyperFrames' pinned Chrome (~150 MB, user cache)"
    pnpm dlx "hyperframes@$HYPERFRAMES_VERSION" browser ensure >>"$LOG" 2>&1
    chrome="$(pnpm dlx "hyperframes@$HYPERFRAMES_VERSION" browser path 2>>"$LOG" | tail -1)"
    [[ -x "$chrome" ]] && ok "chrome (hyperframes)" || bad "chrome download failed (see ${LOG#$ROOT/})"
  else
    bad "chrome for HyperFrames missing (re-run with --install-tools)"
  fi
  if [[ $OS == linux && -x "${chrome:-}" ]] && has ldd; then
    libs="$(ldd "$chrome" 2>/dev/null | awk '/not found/{print $1}' | tr '\n' ' ')"
    [[ -n "$libs" ]] && bad "Chrome needs system libraries (needs root, the person's call): $libs"
  fi
fi

# ------------------------------------------------------------------ studio folder
for d in "${STUDIO_DIRS[@]}"; do mkdir -p "$d"; done
ok "studio folders"

# Framework skills: each framework's official installer (the only npx use).
for entry in "${SKILL_SOURCES[@]}"; do
  src="${entry%%=*}"; sentinel="${entry#*=}"
  if compgen -G ".*/skills/$sentinel/SKILL.md" >/dev/null; then
    ok "skills from $src"
  else
    note "npx skills add $src"
    npx -y skills add "$src" --skill '*' -a "$agent" -y >>"$LOG" 2>&1
    if compgen -G ".*/skills/$sentinel/SKILL.md" >/dev/null; then ok "skills from $src installed"; restart=1
    else bad "skills from $src did not install (see ${LOG#$ROOT/})"; fi
  fi
done

# Claude Code hooks (other harnesses have none; the promo-creator skill covers that case).
if [[ $agent == claude-code ]]; then
  py=python3; [[ "$(PATH="$ORIG_PATH" command -v python3)" == "$(command -v python3)" ]] || py="$(command -v python3)"
  python3 "$HERE/install_hooks.py" "$ROOT" "$py" || bad "could not write hooks"
fi

# Pointer block so the harness loads promo-creator first.
doc=AGENTS.md; [[ $agent == claude-code ]] && doc=CLAUDE.md
if ! grep -q "promo-creator:start" "$doc" 2>/dev/null; then
  [[ -s "$doc" ]] && echo >> "$doc"
  cat "$HERE/../templates/studio-instructions.md" >> "$doc"
  ok "studio instructions in $doc"
else
  ok "studio instructions already in $doc"
fi

# API keys: .env.example to copy, and .env kept out of git.
[[ -f .env.example ]] || { cp "$HERE/../templates/env.example" .env.example; ok ".env.example"; }
if ! grep -qxF ".env" .gitignore 2>/dev/null; then
  [[ -s .gitignore ]] && echo >> .gitignore
  printf '# promo-creator: API keys stay local\n.env\n.env.*\n!.env.example\n' >> .gitignore
  ok ".env added to .gitignore"
fi

# Put ~/.local/bin and PNPM_HOME on PATH for new shells when tools were installed there.
if (( install_tools )); then
  for rc in "$HOME/.profile" "$HOME/.bashrc" "$HOME/.zshrc"; do
    [[ -f "$rc" || "$rc" == "$HOME/.profile" ]] || continue
    grep -q "promo-creator PATH" "$rc" 2>/dev/null && continue
    printf '\n# promo-creator PATH\nexport PNPM_HOME="%s"\nexport PATH="$HOME/.local/bin:$PNPM_HOME:$PATH"\n' "$PNPM_HOME" >> "$rc"
    restart=1
  done
fi

echo
if (( ${#problems[@]} )); then
  echo "setup: NOT ready (${#problems[@]} problem(s)). Tell the person:"
  printf '  - %s\n' "${problems[@]}"
  exit 1
fi
mkdir -p .claude/state
{ date -Iseconds; echo "node=$(node -v) pnpm=$(pnpm -v) remotion=$REMOTION_VERSION hyperframes=$HYPERFRAMES_VERSION"; } > "$MARKER"
echo "setup: ready. Wrote $MARKER."
missing_keys=()
for k in ELEVENLABS_API_KEY GEMINI_API_KEY; do
  grep -qE "^$k=.+" .env 2>/dev/null || missing_keys+=("$k")
done
if (( ${#missing_keys[@]} )); then
  echo
  echo "API keys: tell the person to add them (optional; free local tools are used without them):"
  [[ -f .env ]] || echo "  1. In this folder run: cp .env.example .env"
  echo "  $([[ -f .env ]] && echo 1 || echo 2). Open .env in an editor and fill in: ${missing_keys[*]}"
  echo "     (ElevenLabs: voiceover, SFX, music. Gemini: TTS voiceover, Lyria music.)"
  echo "  Keys go in the file only, never in the chat. .env is gitignored."
fi
if (( restart )); then
  echo "Restart the harness (new skills or PATH changes are only seen by a new session), then ask for a video."
  exit 2
fi
