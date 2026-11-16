#!/usr/bin/env python3
"""Claude Code hooks for the promo-creator pipeline (installed by promo-creator-setup).

Subcommands (stdin = hook JSON payload):
  session      SessionStart  -> compact studio status as context (saves exploration tokens)
  pre-bash     PreToolUse    -> guard raw-footage / final exports, enforce render spec,
                                quiet ffmpeg/ffprobe, send render logs to a file + tail
  pre-read     PreToolUse    -> keep .env (API keys) out of the transcript
  pre-write    PreToolUse    -> block edits to raw-footage, overwrites in exports/final,
                                and hand edits to generated token files
  post-write   PostToolUse   -> validate production.json, regenerate tokens from tokens.json
  post-bash    PostToolUse   -> after a scene render, report that project's render status
  prompt       UserPromptSubmit -> record an explicit "finalize" from the person (unlocks APPROVED.md)

Every handler fails open: an unexpected error never blocks the tool call.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
SKILL = Path(__file__).resolve().parents[1]
PINS = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "promo-creator" / "pins.sh"
PROD = SKILL / "scripts" / "production.py"
LOGS = ROOT / ".claude" / "logs"
APPROVAL = ROOT / ".claude" / "state" / "approval.json"
FINALIZE_RE = re.compile(r"\b(finali[sz]e|finali[sz]ed|approve(d)?\s+(for|the)\s+final|render\s+the\s+final|"
                         r"go\s+final|ship\s+it)\b", re.I)
sys.path.insert(0, str(PROD.parent))

ENV_PATH = r"(?:\S*/)?\.env(?:\.(?!example\b)[\w-]+)?(?![\w.-])"
# a command that would put .env values on screen or into another file
ENV_READ = re.compile(r"(^|[;&|(]\s*|\n\s*|\b(sudo|xargs)\s+)(cat|less|more|head|tail|bat|nl|tac|strings|xxd|od|hexdump|"
                      r"base64|sed|awk|cut|sort|uniq|diff|cp|mv|rsync|scp|tee|open|code|vim?|nano)\b[^;&|\n]*?"
                      r"(?<![\w.-])" + ENV_PATH + "|"
                      r"\bgrep\b(?![^;&|\n]*\s-\w*[qcl])[^;&|\n]*?(?<![\w.-])" + ENV_PATH + "|"
                      r"(?<![\w./-])(printenv|env)\s*($|[;&|])|(?<![\w./-])set\s*($|[;&|])|"
                      r"\b(echo|printf)\b[^;&|\n]*\$\{?\w*(KEY|TOKEN|SECRET)", re.I)
ENV_MSG = (".env holds the person's API keys: never print, read or copy its values. Load it inside the command "
           "that needs it: `set -a; . ./.env; set +a; <command>` (media-use scripts load it themselves). "
           "To check a key exists: `grep -c '^ELEVENLABS_API_KEY=.' .env`.")
SIMPLE_CMD = re.compile(r"^[^;&|`<>]*$")             # no chaining, pipes, redirects, substitution
SUBST = re.compile(r"\$\(")
QUIET_SKIP = re.compile(r"(-loglevel|\s-v\s|-report|ebur128|print_format|volumedetect|silencedetect|"
                        r"blackdetect|freezedetect|cropdetect|showinfo|\s-(h|help|version|filters|codecs|"
                        r"encoders|decoders|formats|pix_fmts)\b)")


def emit(obj: dict) -> None:
    print(json.dumps(obj))
    sys.exit(0)


def deny(reason: str) -> None:
    emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                 "permissionDecisionReason": reason}})


def context(event: str, text: str) -> None:
    emit({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}})


def rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


def pins() -> dict:
    try:
        return dict(l.split("=", 1) for l in PINS.read_text().split() if "=" in l)
    except OSError:
        return {}


def find_project(start: Path) -> Path | None:
    for d in [start, *start.parents]:
        if (d / "production.json").is_file():
            return d
        if d == ROOT:
            break
    return None


# --------------------------------------------------------------------------- SessionStart

def session(_: dict) -> None:
    lines = ["[promo-studio] For any video work, load the `promo-creator` skill first; it routes to "
             "hyperframes / remotion-* / media-use skills and owns production.json."]
    if not (ROOT / ".claude" / "state" / ".prereq-met").is_file():
        lines.append("FIRST RUN: studio not set up. Before any video work load the `promo-creator-setup` "
                     "skill and follow it.")
    pv = pins()
    if pv:
        lines.append(f"Pins ({PINS}): remotion {pv.get('REMOTION_VERSION', '?')}, "
                     f"hyperframes {pv.get('HYPERFRAMES_VERSION', '?')}. Use pnpm only; npx only for `npx skills add`.")
    projects =sorted((ROOT / "projects").glob("*/production.json"))
    if projects:
        import production as P  # noqa: E402
        lines.append("Projects (scenes ok/missing/stale; total length):")
        for mp in projects:
            try:
                pr = P.Project(str(mp))
                errs, _ = P.validate(pr)
                _, total = P.timeline(pr)
                counts = {"ok": 0, "missing": 0, "stale": 0}
                for s in pr.scenes:
                    r = pr.render_path(s, pr.default_tier())
                    if not r.is_file():
                        counts["missing"] += 1
                        continue
                    src = s.get("source")
                    srcs = [pr.path(x) for x in (src if isinstance(src, list) else [src])] if src else []
                    counts["stale" if srcs and P.newest_mtime(srcs) > r.stat().st_mtime else "ok"] += 1
                fw = sorted({s.get("framework", "?") for s in pr.scenes})
                bad = f", {len(errs)} manifest errors" if errs else ""
                fb = mp.parent / "FEEDBACK.md"
                rounds = len(re.findall(r"^## Round", fb.read_text(), re.M)) if fb.is_file() else 0
                stage = "APPROVED -> master tier" if pr.approved else f"preview loop, {rounds} feedback rounds"
                lines.append(f"  - {rel(mp.parent)}: {stage}; {len(pr.scenes)} scenes [{'+'.join(fw)}] "
                             f"{pr.default_tier()} renders {counts['ok']}/{counts['missing']}/{counts['stale']}; "
                             f"{total:.1f}s{bad}")
            except Exception as e:  # keep the session usable
                lines.append(f"  - {rel(mp.parent)}: unreadable ({e.__class__.__name__})")
    else:
        lines.append("No projects yet (projects/<slug>/production.json).")
    for sub in ("drafts", "final"):
        files = sorted((ROOT / "exports" / sub).glob("*.mp4"), key=lambda f: f.stat().st_mtime)[-3:]
        if files:
            lines.append(f"Latest exports/{sub}: " + ", ".join(f.name for f in files))
    lines.append("Loop rule: only 480p previews until the person replies 'finalize'; master renders and "
                 "assemble --final are blocked before that.")
    lines.append("Hooks active: ffmpeg/ffprobe get quiet flags, render logs go to .claude/logs (tail shown), "
                 "scene renders into renders/ must use the spec flags, production.json is validated on save, "
                 "tokens.json regenerates tokens.css/tokens.ts, raw-footage/ is read-only.")
    context("SessionStart", "\n".join(lines))


# --------------------------------------------------------------------------- PreToolUse Bash

def pre_bash(payload: dict) -> None:
    ti = payload.get("tool_input", {})
    cmd: str = ti.get("command", "")
    c = cmd.strip()

    # 1. raw-footage is read-only
    if re.search(r"(^|[;&|(]\s*|\n\s*|\b(sudo|xargs|then|do)\s+)(rm|mv|truncate|shred|unlink)\s[^;&|\n`]*raw-footage", c) or \
       re.search(r"(>|\btee\b)\s*\S*raw-footage/", c):
        deny("raw-footage/ is read-only source media. Copy or conform into projects/<slug>/media or audio instead.")
    if re.match(r"^ffmpeg\s", c) and re.search(r"\s-y\b", c):
        try:
            out = shlex.split(c)[-1]
        except ValueError:
            out = ""
        if re.search(r"(^|/)(raw-footage|exports/final)/", out):
            deny("Do not run ffmpeg -y onto raw-footage/ or exports/final/. Write a new versioned file "
                 "(production.py assemble picks the next vN) or use -n.")

    # 2. API keys in .env stay out of the transcript
    scan = re.sub(r"'[^']*'", "''", c)  # sed/awk scripts and quoted text are not file reads
    scan = re.sub(r"(^|\s)#[^\n]*", "", scan)  # shell comments
    scan = re.sub(r"\b(cp|mv)\s+\S*\.env\.example\s+\S*\.env\b", "", scan)  # making .env from the example
    if ENV_READ.search(scan):
        deny(ENV_MSG)

    # 2b. pnpm only (npx is allowed just for the official skill installers)
    for seg in re.split(r"&&|\|\||;|\||\n", c):
        s = seg.strip()
        if re.match(r"^npx\s", s) and not re.match(r"^npx\s+(-y\s+|--yes\s+)?skills(@\S+)?\s", s):
            deny("Use pnpm, not npx: inside a project `pnpm exec <cli> ...` (hyperframes and remotion are pinned "
                 "devDependencies; add one with scaffold.sh), elsewhere `pnpm dlx <pkg>@<pinned version> ...`. "
                 "npx is only for `npx skills add`.")
        if re.match(r"^npm\s+(i|install|ci|add|exec|x|create|init)\b", s):
            deny("Use pnpm, not npm: `pnpm add -E --prefer-offline <pkg>@<version>` / `pnpm install --prefer-offline`.")

    # 3. scene renders: preview tier during the loop, master tier only after approval
    is_rem = re.search(r"\bremotion\s+render\b", c) and "--frames" not in c
    is_hf = re.search(r"\bhyperframes\s+render\b", c)
    if (is_rem or is_hf) and "renders/" in c:
        if "renders/preview/" in c:
            if is_rem and ("--scale" not in c or "--crf" not in c or "--x264-preset" not in c):
                deny("Preview renders (feedback loop): pnpm exec remotion render <scene-id> ../renders/preview/NN-<scene-id>.mp4 "
                     "--scale=0.5 --codec=h264 --crf=23 --x264-preset=ultrafast --pixel-format=yuv420p --muted")
            if is_hf and "--quality draft" not in c and "--quality=draft" not in c:
                deny("Preview renders (feedback loop): pnpm exec hyperframes render -c compositions/<scene-id>.html "
                     "--fps <fps> --quality draft -o ../renders/preview/NN-<scene-id>.mp4")
        else:
            m = re.search(r"(\S*renders/[\w.\-]+\.(?:mp4|mov))", c)
            cwd = Path(payload.get("cwd") or ROOT)
            proj = find_project((cwd / m.group(1)).resolve().parent if m else cwd) or find_project(cwd)
            if proj and not (proj / "APPROVED.md").is_file():
                deny("Master renders are locked until the person replies 'finalize'. During the feedback loop render "
                     "previews into renders/preview/ (see references/review-loop.md).")
            if is_rem and "--crf" not in c and "prores" not in c:
                deny("Master scene renders: pnpm exec remotion render <scene-id> ../renders/NN-<scene-id>.mp4 "
                     "--codec=h264 --crf=16 --pixel-format=yuv420p --muted (alpha: --codec=prores --prores-profile=4444).")
            if is_hf and "--crf" not in c and "--format" not in c:
                deny("Master scene renders: pnpm exec hyperframes render -c compositions/<scene-id>.html --fps <fps> "
                     "--crf 16 -o ../renders/NN-<scene-id>.mp4 (alpha: --format mov).")
    if re.search(r">>?\s*\S*APPROVED\.md\b", c) or \
       re.search(r"(^|[;&|(]\s*|\n\s*)(cp|mv|touch|tee|install)\s[^;&|\n`]*APPROVED\.md", c):
        deny("APPROVED.md is written with the Write tool only, after the person replies 'finalize'.")

    # 4. deterministic rewrites — only for single, simple commands
    # (overwriting commands are left to the normal permission flow, since a rewrite auto-approves)
    if not SIMPLE_CMD.match(c) or SUBST.search(c) or "\n" in c or re.search(r"\s-y\b", c):
        return
    new = c
    if re.match(r"^(npx\s+|pnpm\s+(dlx|exec)\s+)?hyperframes(@\S+)?\s+init\b", new) and "--skip-skills" not in new:
        new += " --skip-skills"
    if re.match(r"^ffmpeg\s", new) and not QUIET_SKIP.search(new):
        new = "ffmpeg -hide_banner -loglevel warning -nostats" + new[len("ffmpeg"):]
    if re.match(r"^ffprobe\s", new) and not re.search(r"(\s-v\s|-loglevel)", new):
        new = "ffprobe -v error" + new[len("ffprobe"):]
    is_render = re.match(r"^(npx\s+|pnpm\s+(exec|dlx)\s+|pnpm\s+)?(remotion|hyperframes)(@\S+)?\s+render\b", new)
    is_scaffold = re.match(r"^(npx|pnpm\s+dlx|pnpm\s+create)\s+(create-)?video\b", new)
    is_install = re.match(r"^(npm\s+(i|install|ci)|pnpm\s+(i|install|add))\b", new)
    if is_render or is_scaffold or is_install:
        LOGS.mkdir(parents=True, exist_ok=True)
        kind = "render" if is_render else ("scaffold" if is_scaffold else "install")
        log = LOGS / f"{time.strftime('%Y%m%d-%H%M%S')}-{kind}.log"
        new = (f"{{ {new} ; }} > {shlex.quote(str(log))} 2>&1; rc=$?; tail -n 25 {shlex.quote(str(log))}; "
               f"echo \"[full log: {log}] exit=$rc\"; (exit $rc)")
    if new != c:
        updated = dict(ti)
        updated["command"] = new
        emit({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "promo-studio: normalized media command (quiet flags / log capture)",
            "updatedInput": updated}})


# --------------------------------------------------------------------------- PreToolUse Read

def pre_read(payload: dict) -> None:
    name = Path(payload.get("tool_input", {}).get("file_path", "")).name
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        deny(ENV_MSG)


# --------------------------------------------------------------------------- PreToolUse Write|Edit

def pre_write(payload: dict) -> None:
    fp = payload.get("tool_input", {}).get("file_path", "")
    if not fp:
        return
    p = Path(fp).resolve()
    r = rel(p)
    if r.startswith("raw-footage/"):
        deny("raw-footage/ is read-only. Put derived files in projects/<slug>/media or audio.")
    if r.startswith("exports/final/") and p.exists():
        deny("exports/final/ files are never overwritten. Produce a new version (-vN+1).")
    if p.name == "APPROVED.md" and rel(p).startswith("projects/"):
        ok = False
        try:
            a = json.loads(APPROVAL.read_text())
            ok = a.get("session_id") == payload.get("session_id")
        except (OSError, json.JSONDecodeError):
            pass
        if not ok:
            deny("Only the person can finalize. Ask them to reply 'finalize' (their latest message must say it); "
                 "until then keep iterating on 480p previews.")
    if p.name in ("tokens.css", "tokens.ts") and p.exists() and "GENERATED from tokens.json" in p.read_text(errors="ignore")[:200]:
        deny(f"{p.name} is generated. Edit the project's tokens.json; the hook regenerates this file.")


# --------------------------------------------------------------------------- PostToolUse Write|Edit

def post_write(payload: dict) -> None:
    fp = payload.get("tool_input", {}).get("file_path") or payload.get("tool_response", {}).get("filePath", "")
    if not fp:
        return
    p = Path(fp).resolve()
    if p.name == "production.json":
        r = subprocess.run([sys.executable, str(PROD), "validate", str(p)], capture_output=True, text=True)
        if r.returncode:
            emit({"decision": "block",
                  "reason": f"production.json failed validation — fix before continuing:\n{r.stdout.strip()}"})
        context("PostToolUse", r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "production.json OK")
    if p.name == "tokens.json" and rel(p).startswith("projects/"):
        try:
            json.loads(p.read_text())
        except json.JSONDecodeError as e:
            emit({"decision": "block", "reason": f"tokens.json is not valid JSON: {e}"})
        import production as P  # noqa: E402
        files = P.sync_tokens(p.parent)
        if files:
            context("PostToolUse", "tokens regenerated: " + ", ".join(rel(f) for f in files))


# --------------------------------------------------------------------------- PostToolUse Bash

def post_bash(payload: dict) -> None:
    c = payload.get("tool_input", {}).get("command", "")
    if not re.search(r"\b(remotion|hyperframes)\s+render\b", c) or "renders/" not in c:
        return
    m = re.search(r"(\S*renders/[\w.\-]+\.(?:mp4|mov))", c)
    cwd = Path(payload.get("cwd") or ROOT)
    start = (cwd / m.group(1)).resolve().parent if m else cwd
    proj = find_project(start) or find_project(cwd)
    if not proj:
        return
    tier = "preview" if "renders/preview/" in c else "master"
    r = subprocess.run([sys.executable, str(PROD), "status", str(proj), "--json", "--tier", tier],
                       capture_output=True, text=True)
    try:
        st = json.loads(r.stdout)
    except json.JSONDecodeError:
        return
    if not st.get("valid"):
        context("PostToolUse", f"[{rel(proj)}] production.json invalid: {st.get('errors')}")
    parts = []
    for s in st["scenes"]:
        tag = s["state"] if s["state"] != "ok" else "ok"
        parts.append(f"{s['id']}={tag}" + (f" ({'; '.join(s['problems'])})" if s["problems"] else ""))
    nxt = (f" Next: production.py assemble --{'preview' if tier == 'preview' else 'final'}." if st["ok"] else "")
    context("PostToolUse", f"[{rel(proj)}] {tier} render status: " + ", ".join(parts) + nxt)


# --------------------------------------------------------------------------- UserPromptSubmit

def prompt(payload: dict) -> None:
    text = payload.get("prompt", "") or ""
    if FINALIZE_RE.search(text) and not re.search(r"\b(not|don'?t|do not|never)\b[^.]{0,20}finali", text, re.I):
        APPROVAL.parent.mkdir(parents=True, exist_ok=True)
        APPROVAL.write_text(json.dumps({"session_id": payload.get("session_id"), "time": time.time(),
                                        "prompt": text[:300]}))
        context("UserPromptSubmit", "[promo-studio] The person finalized. Write projects/<slug>/APPROVED.md "
                "(quote their words and the approved preview version), then render master scenes and "
                "assemble --final.")
    elif APPROVAL.exists():
        APPROVAL.unlink()  # approval must come from the latest message


def main() -> None:
    try:
        payload = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    except json.JSONDecodeError:
        payload = {}
    handlers = {"session": session, "pre-bash": pre_bash, "pre-read": pre_read, "pre-write": pre_write,
                "post-write": post_write, "post-bash": post_bash, "prompt": prompt}
    try:
        handlers[sys.argv[1]](payload)
    except SystemExit:
        raise
    except Exception as e:  # fail open
        print(json.dumps({"systemMessage": f"promo hook {sys.argv[1:]} error: {e}"}))
    sys.exit(0)


if __name__ == "__main__":
    main()
