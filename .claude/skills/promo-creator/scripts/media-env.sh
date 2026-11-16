# Source before running media-use's audio engine directly (music, SFX):
#   . .claude/skills/promo-creator/scripts/media-env.sh; node .claude/skills/media-use/audio/scripts/audio.mjs ...
# Points media-use at this user's Python venv and pinned HyperFrames CLI. Sets no API keys:
# media-use reads those from the studio .env itself. scripts/voiceover.py does this on its own.
_promo_home="${XDG_DATA_HOME:-$HOME/.local/share}/promo-creator"
[ -x "$_promo_home/venv/bin/python" ] && export HYPERFRAMES_PYTHON="$_promo_home/venv/bin/python"
_hf_pkg="$_promo_home/hyperframes/node_modules/hyperframes"
if [ -f "$_hf_pkg/package.json" ]; then
  HYPERFRAMES_CLI_ENTRY="$(cd "$_hf_pkg" && node -p "const b=require('./package.json').bin; require('path').resolve(typeof b=='string'?b:b.hyperframes)")"
  export HYPERFRAMES_CLI_ENTRY
fi
unset _promo_home _hf_pkg
