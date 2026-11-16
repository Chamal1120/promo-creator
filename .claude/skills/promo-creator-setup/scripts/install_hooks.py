#!/usr/bin/env python3
"""Merge the promo-creator hooks into <studio>/.claude/settings.json (Claude Code only).

    python3 install_hooks.py <studio-root> <python-command>

Keeps every other setting and hook. Replaces earlier promo-creator / video-production hook
entries, so it is safe to run again.
"""
from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

HOOK = '"$CLAUDE_PROJECT_DIR/.claude/skills/promo-creator/hooks/promo_hooks.py"'
OURS = ("promo_hooks.py", "video_hooks.py")

# event -> list of (matcher or None, subcommand, timeout seconds)
SPEC = {
    "SessionStart": [(None, "session", 20)],
    "UserPromptSubmit": [(None, "prompt", 10)],
    "PreToolUse": [("Bash", "pre-bash", 10), ("Read", "pre-read", 10), ("Write|Edit", "pre-write", 10)],
    "PostToolUse": [("Write|Edit", "post-write", 30), ("Bash", "post-bash", 60)],
}


def is_ours(group: dict) -> bool:
    return any(any(o in h.get("command", "") for o in OURS) for h in group.get("hooks", []))


def main() -> int:
    root, python = Path(sys.argv[1]), sys.argv[2]
    py = python if python == "python3" else shlex.quote(python)
    path = root / ".claude" / "settings.json"
    text = path.read_text() if path.is_file() else ""
    settings = json.loads(text) if text.strip() else {}
    hooks = settings.setdefault("hooks", {})
    for event, entries in SPEC.items():
        groups = [g for g in hooks.get(event, []) if not is_ours(g)]
        for matcher, sub, timeout in entries:
            group = {"hooks": [{"type": "command", "command": f"{py} {HOOK} {sub}", "timeout": timeout}]}
            if matcher:
                group = {"matcher": matcher, **group}
            groups.append(group)
        hooks[event] = groups
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n")
    print("  ok   hooks in .claude/settings.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
