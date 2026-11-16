#!/usr/bin/env bash
# Create or extend a project folder. Idempotent: existing files and apps are left alone.
#   bash <promo-creator>/scripts/scaffold.sh <slug>                 # folder + templates (Phase 0/1)
#   bash <promo-creator>/scripts/scaffold.sh <slug> --remotion      # + Remotion app (pinned, pnpm)
#   bash <promo-creator>/scripts/scaffold.sh <slug> --hyperframes   # + HyperFrames project (pinned)
# Layout: projects/<slug>/{BRIEF.md,PLAN.md,FEEDBACK.md,production.json,tokens.json,
#         remotion/,hyperframes/,audio/,media/,renders/preview/}
# Versions come from the user's pin file (see common.sh). A package without a pin is installed
# at the version npm gives today, then pinned, so every later project reuses the cached copy.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES="$HERE/../templates"
# shellcheck source=common.sh
source "$HERE/common.sh"
ROOT="$(studio_root "$HERE")"

slug="${1:-}"
[[ "$slug" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || { echo "usage: scaffold.sh <kebab-slug> [--remotion] [--hyperframes]"; exit 1; }
shift
want_remotion=0; want_hf=0
for a in "$@"; do
  case "$a" in
    --remotion) want_remotion=1 ;;
    --hyperframes) want_hf=1 ;;
    --both) want_remotion=1; want_hf=1 ;;
    *) echo "unknown option: $a"; exit 1 ;;
  esac
done

[[ -f "$ROOT/.claude/state/.prereq-met" ]] || { echo "Studio not set up in $ROOT. Load the promo-creator-setup skill first."; exit 1; }
[[ -n "${REMOTION_VERSION:-}" && -n "${HYPERFRAMES_VERSION:-}" ]] || { echo "No version pins in $PINS_FILE. Run promo-creator-setup."; exit 1; }

P="$ROOT/projects/$slug"
LOG="$ROOT/.claude/logs/scaffold-$slug.log"
mkdir -p "$P"/{audio,media,renders/preview} "$ROOT/.claude/logs"
: >> "$LOG"
for f in BRIEF.md PLAN.md FEEDBACK.md production.json tokens.json; do
  [[ -e "$P/$f" ]] || { cp "$TEMPLATES/$f" "$P/$f"; echo "  + $f"; }
done

run() {  # quiet runner: full output to the log, tail on failure
  if ! "$@" >>"$LOG" 2>&1; then
    echo "FAILED: $*"; tail -n 25 "$LOG"; exit 1
  fi
}

# spec PKG VAR -> "pkg@pin", or "pkg" when VAR is not pinned yet
spec() { local v="${!2:-}"; [[ -n "$v" ]] && echo "$1@$v" || echo "$1"; }
# pin_installed PKG VAR -> pin the version pnpm resolved, if VAR was not pinned
pin_installed() {
  [[ -n "${!2:-}" ]] && return
  local v; v="$(node -p "require('./node_modules/$1/package.json').version")"
  pin_set "$2" "$v"; echo "  pinned $1@$v for this user ($PINS_FILE)"
}

if (( want_remotion )) && [[ ! -f "$P/remotion/package.json" ]]; then
  echo "  + remotion/ (create-video@$REMOTION_VERSION, pnpm, exact pins)"
  (cd "$P" && run pnpm dlx "create-video@$REMOTION_VERSION" --yes --blank --no-tailwind remotion)
  rm -f "$P/remotion/package-lock.json"
  (cd "$P/remotion" &&
    run pnpm add -E --prefer-offline "remotion@$REMOTION_VERSION" "@remotion/cli@$REMOTION_VERSION" \
        "$(spec react REACT_VERSION)" "$(spec react-dom REACT_VERSION)" &&
    run pnpm add -E -D --prefer-offline "@remotion/eslint-config-flat@$REMOTION_VERSION" \
        "$(spec @types/react TYPES_REACT_VERSION)" "$(spec typescript TYPESCRIPT_VERSION)" \
        "$(spec eslint ESLINT_VERSION)" "$(spec prettier PRETTIER_VERSION)" "$(spec @types/web TYPES_WEB_VERSION)" &&
    pin_installed react REACT_VERSION && pin_installed @types/react TYPES_REACT_VERSION &&
    pin_installed typescript TYPESCRIPT_VERSION && pin_installed eslint ESLINT_VERSION &&
    pin_installed prettier PRETTIER_VERSION && pin_installed @types/web TYPES_WEB_VERSION)
  if grep -qE '"(remotion|@remotion/[^"]+|react|react-dom)": "[\^~]' "$P/remotion/package.json"; then
    echo "WARNING: package.json still has ^/~ ranges on pinned packages"; exit 1
  fi
  mkdir -p "$P/remotion/public/fonts"
fi

if (( want_hf )); then
  if [[ ! -f "$P/hyperframes/index.html" ]]; then
    echo "  + hyperframes/ (hyperframes@$HYPERFRAMES_VERSION)"
    run pnpm dlx "hyperframes@$HYPERFRAMES_VERSION" init "$P/hyperframes" --example=blank \
        --non-interactive --skip-skills --skill=hyperframes
    mkdir -p "$P/hyperframes/assets/fonts"
  fi
  # The CLI is an exact devDependency so `pnpm exec hyperframes ...` runs the pinned copy from
  # the pnpm store (also upgrades older projects whose scripts used npx).
  if ! grep -q '"hyperframes": "' "$P/hyperframes/package.json" 2>/dev/null; then
    echo "  + hyperframes@$HYPERFRAMES_VERSION as devDependency"
    (cd "$P/hyperframes" && run pnpm add -E -D --prefer-offline "hyperframes@$HYPERFRAMES_VERSION")
  fi
  node -e '
    const f = process.argv[1], p = require(f);
    for (const k of Object.keys(p.scripts || {}))
      p.scripts[k] = p.scripts[k].replace(/^npx (--yes |-y )?hyperframes(@\S+)? /, "hyperframes ");
    require("fs").writeFileSync(f, JSON.stringify(p, null, 2) + "\n");' "$P/hyperframes/package.json"
fi

if [[ -f "$P/tokens.json" ]] && (( want_remotion || want_hf )); then
  python3 "$HERE/production.py" sync-tokens "$P" >>"$LOG" 2>&1 || true
fi
echo "scaffold: projects/$slug ready (log: ${LOG#$ROOT/})"
