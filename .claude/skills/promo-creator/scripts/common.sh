# Shared settings for promo-creator scripts (sourced by scaffold.sh and promo-creator-setup).
#
# Package versions are NOT shipped with the skill. They are pinned per user in
#   ${XDG_CONFIG_HOME:-~/.config}/promo-creator/pins.sh
# so every studio and project on this machine uses the same versions and pnpm reuses one
# cached copy (no repeat downloads). promo-creator-setup pins REMOTION_VERSION and
# HYPERFRAMES_VERSION on first run (the versions current on npm that day); scaffold.sh pins
# React/TypeScript/ESLint/Prettier on the first Remotion project. Change a pin only when the
# person asks to upgrade (references/toolchain.md).

MIN_NODE_MAJOR=22

MIN_PYTHON="3.10"

# Framework skills: official source = a skill that proves the source is installed.
SKILL_SOURCES=(heygen-com/hyperframes=hyperframes remotion-dev/skills=remotion-best-practices)

# Studio folders created by setup.
STUDIO_DIRS=(projects raw-footage/videos raw-footage/audio raw-footage/images
             references/inspiration references/scripts references/storyboards
             exports/drafts exports/final .claude/logs .claude/state)

PINS_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/promo-creator/pins.sh"
# Per-user installs shared by every studio: the pinned HyperFrames CLI and a Python venv for
# the audio providers (ElevenLabs TTS, Gemini Lyria).
PROMO_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/promo-creator"
PROMO_HF_CLI="$PROMO_HOME/hyperframes"
PROMO_VENV="$PROMO_HOME/venv"
PY_AUDIO_PKGS=(elevenlabs google-genai python-dotenv)
# shellcheck disable=SC1090
[[ -f "$PINS_FILE" ]] && source "$PINS_FILE"

# pin_set NAME VALUE — record a version in the user's pin file (replaces an earlier value).
pin_set() {
  mkdir -p "$(dirname "$PINS_FILE")"
  touch "$PINS_FILE"
  local tmp; tmp="$(mktemp)"
  grep -v "^$1=" "$PINS_FILE" > "$tmp" || true
  echo "$1=$2" >> "$tmp"
  mv "$tmp" "$PINS_FILE"
  printf -v "$1" '%s' "$2"
}

# studio_root SCRIPT_DIR — the studio folder (where projects/ lives).
# Order: $PROMO_STUDIO, $CLAUDE_PROJECT_DIR, the folder the skill is installed in
# (<root>/.<agent>/skills/<skill>/scripts), else the current directory.
studio_root() {
  if [[ -n "${PROMO_STUDIO:-}" ]]; then echo "$PROMO_STUDIO"; return; fi
  if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then echo "$CLAUDE_PROJECT_DIR"; return; fi
  local d; d="$(cd "$1/../../../.." && pwd)"
  if [[ "$1" == */.*/skills/promo-creator*/scripts && "$d" != "$HOME" ]]; then echo "$d"; return; fi
  pwd
}
