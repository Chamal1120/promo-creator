#!/usr/bin/env python3
"""Generate voiceover lines for a project with media-use's audio engine.

    python3 voiceover.py <project> --line intro="Every word has a moment." --line cta="Try it free."
    python3 voiceover.py <project> --lines vo.json        # [{"id": "intro", "text": "...", "style": "..."}]
    python3 voiceover.py <project> --script vo.txt        # one line per paragraph -> vo-01, vo-02, ...
    options: --provider auto|elevenlabs|gemini|kokoro|heygen  --voice ID  --model ID  --style TEXT
             --lang en  --dry-run

<project> is a slug (projects/<slug>) or a path. Output: projects/<slug>/audio/vo/<id>.wav (stems
for the FFmpeg mix) and audio/vo/voiceover.json (provider, voice, durations, word timings).

Provider "auto" (default): ElevenLabs if ELEVENLABS_API_KEY is set, else Gemini if GEMINI_API_KEY
(or GOOGLE_API_KEY) is set, else local Kokoro. HeyGen only when asked for (--provider heygen).

API keys come from the studio's .env. Only the known provider keys are read, they are passed to
the engine's environment only, and they are never printed or written anywhere.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

KEYS = ("ELEVENLABS_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "HEYGEN_API_KEY")
PROMO_HOME = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "promo-creator"
VENV_PY = PROMO_HOME / "venv" / "bin" / "python"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def die(msg: str) -> None:
    print(f"voiceover: {msg}", file=sys.stderr)
    sys.exit(1)


def studio_root(start: Path) -> Path:
    for d in [start, *start.parents]:
        if (d / ".claude" / "state" / ".prereq-met").is_file():
            return d
    env = os.environ.get("PROMO_STUDIO") or os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env) if env else Path.cwd()


def load_keys(root: Path) -> dict[str, str]:
    """Provider keys from <root>/.env (values never leave this function except into the child env)."""
    out: dict[str, str] = {}
    env_file = root / ".env"
    if not env_file.is_file():
        return out
    for raw in env_file.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.removeprefix("export ").split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k in KEYS and v:
            out[k] = v
    return out


def find_audio_engine(root: Path) -> Path:
    for base in sorted(root.glob(".*/skills/media-use/audio/scripts/audio.mjs")):
        return base
    die("media-use skill not found. Run the promo-creator-setup skill (it installs the HyperFrames skills).")
    raise SystemExit  # unreachable


def find_cli_entry(project: Path) -> str | None:
    if os.environ.get("HYPERFRAMES_CLI_ENTRY"):
        return os.environ["HYPERFRAMES_CLI_ENTRY"]
    for pkg in (PROMO_HOME / "hyperframes" / "node_modules" / "hyperframes",
                project / "hyperframes" / "node_modules" / "hyperframes"):
        pj = pkg / "package.json"
        if pj.is_file():
            b = json.loads(pj.read_text()).get("bin")
            rel = b if isinstance(b, str) else (b or {}).get("hyperframes")
            if rel:
                return str((pkg / rel).resolve())
    return None


def read_lines(a: argparse.Namespace) -> list[dict]:
    lines: list[dict] = []
    for item in a.line or []:
        if "=" not in item:
            die(f"--line needs ID=TEXT, got {item!r}")
        i, text = item.split("=", 1)
        lines.append({"id": i.strip(), "text": text.strip()})
    if a.lines:
        data = json.loads(Path(a.lines).read_text())
        lines += data["lines"] if isinstance(data, dict) else data
    if a.script:
        paras = [p.strip() for p in re.split(r"\n\s*\n", Path(a.script).read_text()) if p.strip()]
        lines += [{"id": f"vo-{n:02d}", "text": " ".join(p.split())} for n, p in enumerate(paras, 1)]
    if not lines:
        die("no lines: use --line ID=TEXT, --lines file.json or --script file.txt")
    seen = set()
    for ln in lines:
        if not ID_RE.match(str(ln.get("id", ""))) or not str(ln.get("text", "")).strip():
            die(f"bad line {ln!r}: ids are lowercase kebab/snake case and text must not be empty")
        if ln["id"] in seen:
            die(f"duplicate line id {ln['id']!r}")
        seen.add(ln["id"])
    return lines


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("project")
    p.add_argument("--line", action="append", metavar="ID=TEXT")
    p.add_argument("--lines", metavar="FILE.json")
    p.add_argument("--script", metavar="FILE.txt")
    p.add_argument("--provider", default="auto", choices=["auto", "elevenlabs", "gemini", "kokoro", "heygen"])
    p.add_argument("--voice", help="ElevenLabs voice_id, Gemini voice (e.g. Kore), Kokoro voice (e.g. af_heart)")
    p.add_argument("--model", help="TTS model, e.g. gemini-3.8-flash-tts (Gemini only)")
    p.add_argument("--style", help="delivery direction (Gemini), e.g. 'Warm, confident, unhurried.'")
    p.add_argument("--lang", default="en")
    p.add_argument("--dry-run", action="store_true", help="print the plan and request, generate nothing")
    a = p.parse_args()

    proj = Path(a.project)
    if not proj.is_dir():
        proj = studio_root(Path.cwd()) / "projects" / a.project
    if not (proj / "production.json").is_file():
        die(f"{proj} is not a project (no production.json). Scaffold it first.")
    proj = proj.resolve()
    root = studio_root(proj)
    lines = read_lines(a)
    keys = load_keys(root)
    env = {**os.environ, **{k: v for k, v in keys.items() if k not in os.environ}}

    provider = a.provider
    if provider == "auto":
        provider = ("elevenlabs" if env.get("ELEVENLABS_API_KEY")
                    else "gemini" if env.get("GEMINI_API_KEY") or env.get("GOOGLE_API_KEY") else "kokoro")
    if provider == "elevenlabs" and not env.get("ELEVENLABS_API_KEY"):
        die("ELEVENLABS_API_KEY is not set. Add it to .env (see .env.example), or use --provider gemini|kokoro.")
    if provider == "gemini" and not (env.get("GEMINI_API_KEY") or env.get("GOOGLE_API_KEY")):
        die("GEMINI_API_KEY is not set. Add it to .env (see .env.example), or use --provider elevenlabs|kokoro.")

    if VENV_PY.is_file():
        env["HYPERFRAMES_PYTHON"] = str(VENV_PY)
    elif provider == "elevenlabs":
        die(f"{VENV_PY} missing (ElevenLabs needs the Python 'elevenlabs' package). Re-run promo-creator-setup with --force.")
    cli = find_cli_entry(proj)
    if cli:
        env["HYPERFRAMES_CLI_ENTRY"] = cli
    elif provider == "kokoro":
        die("no HyperFrames CLI found for local Kokoro voices. Re-run promo-creator-setup with --force.")
    else:
        print("voiceover: note: no HyperFrames CLI found, so word timings may be missing.", file=sys.stderr)

    engine = find_audio_engine(root)
    req = {"provider": provider, "lang": a.lang, "lines": lines, "bgm": {"mode": "none"}}
    if a.voice:
        req["voice"] = a.voice
    if a.model:
        req["tts_model"] = a.model
    if a.style:
        req["style"] = a.style

    vo_dir = proj / "audio" / "vo"
    work = proj / "audio" / ".vo-work"
    print(f"voiceover: {len(lines)} line(s) with {provider}"
          f"{' voice ' + a.voice if a.voice else ''} -> {vo_dir.relative_to(root)}/")
    if a.dry_run:
        print(json.dumps(req, indent=2))
        return

    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    (work / "audio_request.json").write_text(json.dumps(req, indent=2))
    logs = root / ".claude" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    log = logs / f"{time.strftime('%Y%m%d-%H%M%S')}-voiceover.log"
    with log.open("w") as fh:
        rc = subprocess.run(["node", str(engine), "--request", str(work / "audio_request.json"),
                             "--hyperframes", str(work), "--out", str(work / "audio_meta.json"), "--only", "tts"],
                            env=env, stdout=fh, stderr=subprocess.STDOUT, cwd=work).returncode
    out = log.read_text()
    meta_path = work / "audio_meta.json"
    if rc != 0 or not meta_path.is_file():
        print("\n".join(out.splitlines()[-25:]))
        die(f"engine failed (exit {rc}); full log: {log}")

    meta = json.loads(meta_path.read_text())
    vo_dir.mkdir(parents=True, exist_ok=True)
    result = {"provider": meta.get("tts_provider", provider), "voice": meta.get("voice_id") or a.voice,
              "voice_credit": meta.get("voice_credit"), "lines": []}
    by_id = {v.get("id"): v for v in meta.get("voices", [])}
    problems = []
    for ln in lines:
        v = by_id.get(ln["id"])
        src = work / v["path"] if v and v.get("path") else None
        if not src or not src.is_file():
            problems.append(f"{ln['id']}: no audio")
            continue
        dst = vo_dir / f"{ln['id']}.wav"
        shutil.move(str(src), dst)
        words = v.get("words") or []
        if not words:
            problems.append(f"{ln['id']}: no word timings")
        result["lines"].append({"id": ln["id"], "text": ln["text"], "file": str(dst.relative_to(proj)),
                                "duration_s": v.get("duration_s"), "words": words})
        print(f"  {ln['id']:<16} {v.get('duration_s', 0):6.2f}s  {dst.relative_to(root)}  ({len(words)} words)")
    (vo_dir / "voiceover.json").write_text(json.dumps(result, indent=2) + "\n")
    shutil.rmtree(work, ignore_errors=True)
    anomalies = out.split("anomalies (non-fatal):", 1)[1].strip() if "anomalies (non-fatal):" in out else ""
    if anomalies:
        print("engine notes:\n" + "\n".join("  " + l.strip() for l in anomalies.splitlines()[:10]))
    print(f"voiceover: wrote {(vo_dir / 'voiceover.json').relative_to(root)} (log: {log.relative_to(root)})")
    if problems:
        die("; ".join(problems))


if __name__ == "__main__":
    main()
