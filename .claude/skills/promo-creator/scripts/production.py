#!/usr/bin/env python3
"""Production manifest tool for the promo-creator skill.

Usage:
  production.py validate <project>            check production.json (no media access)
  production.py timeline <project>            print scene start/end on the final timeline
  production.py verify   <project> [--tier preview|master]   probe scene renders against the spec
  production.py status   <project> [--json]   validate + render state (missing/stale/ok)
  production.py assemble <project> --preview|--final [--dry-run] [--out PATH] [--force-reencode]

Tiers: the feedback loop renders scenes to renders/preview/ and assembles 480p preview cuts
(exports/drafts/<slug>-preview-vN.mp4). Master renders (renders/) and --final are locked until
APPROVED.md exists in the project, written only after the person replies "finalize".
  production.py sync-tokens <project>         tokens.json -> hyperframes/assets/tokens.css + remotion/src/tokens.ts

<project> is a folder containing production.json (or the path to the json file).
Exit codes: 0 ok, 1 problems found, 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

FRAMEWORKS = {"remotion", "hyperframes", "footage"}
XFADE = {
    "fade", "fadeblack", "fadewhite", "fadegrays", "dissolve", "distance",
    "wipeleft", "wiperight", "wipeup", "wipedown",
    "slideleft", "slideright", "slideup", "slidedown",
    "smoothleft", "smoothright", "smoothup", "smoothdown",
    "circleopen", "circleclose", "circlecrop", "rectcrop", "radial",
    "vertopen", "vertclose", "horzopen", "horzclose",
    "diagtl", "diagtr", "diagbl", "diagbr", "hlslice", "hrslice", "vuslice", "vdslice",
    "pixelize", "hblur", "zoomin", "squeezeh", "squeezev",
}
ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SKIP_DIRS = {"node_modules", ".git", ".hyperframes", "renders", "out", "dist", ".cache"}
DEFAULT_FORMAT = {"width": 1920, "height": 1080, "fps": 30, "pix_fmt": "yuv420p"}
DEFAULT_LOUDNESS = {"target_lufs": -14.0, "true_peak": -1.0, "lra": 11.0}
DEFAULT_DELIVERY = {"crf": 18, "preset": "slow", "audio_bitrate": "192k", "reencode_video": False}


# --------------------------------------------------------------------------- loading

class Project:
    def __init__(self, arg: str):
        p = Path(arg).resolve()
        self.manifest_path = p if p.suffix == ".json" else p / "production.json"
        if not self.manifest_path.is_file():
            raise SystemExit(f"error: {self.manifest_path} not found")
        self.dir = self.manifest_path.parent
        try:
            self.data = json.loads(self.manifest_path.read_text())
        except json.JSONDecodeError as e:
            raise SystemExit(f"error: production.json is not valid JSON: {e}")
        d = self.data
        self.fmt = {**DEFAULT_FORMAT, **d.get("format", {})}
        self.fps = float(self.fmt["fps"])
        self.scenes = d.get("scenes", [])
        self.audio = d.get("audio", [])
        self.loudness = {**DEFAULT_LOUDNESS, **d.get("loudness", {})}
        self.delivery = {**DEFAULT_DELIVERY, **d.get("delivery", {})}
        self.slug = d.get("slug") or self.dir.name
        self.studio = self._find_studio()

    def _find_studio(self) -> Path:
        for parent in [self.dir, *self.dir.parents]:
            if (parent / "exports").is_dir() and (parent / "projects").is_dir():
                return parent
        return self.dir

    def path(self, rel: str) -> Path:
        return (self.dir / rel).resolve()

    @property
    def approved(self) -> bool:
        """The person said 'finalize'; master renders and --final are unlocked."""
        return (self.dir / "APPROVED.md").is_file()

    def default_tier(self) -> str:
        return "master" if self.approved else "preview"

    def render_path(self, s: dict, tier: str) -> Path:
        master = self.path(s["render"])
        return master if tier == "master" else master.parent / "preview" / master.name

    def preview_size(self) -> tuple[int, int]:
        """Short side 480, long side scaled and rounded to even (1920x1080 -> 854x480)."""
        w, h = int(self.fmt["width"]), int(self.fmt["height"])
        short = 480
        if w >= h:
            return int(round(short * w / h / 2) * 2), short
        return short, int(round(short * h / w / 2) * 2)


# --------------------------------------------------------------------------- validation

def is_whole_frames(seconds: float, fps: float) -> bool:
    frames = seconds * fps
    return abs(frames - round(frames)) < 1e-6


def validate(pr: Project) -> tuple[list[str], list[str]]:
    errs: list[str] = []
    warns: list[str] = []
    f = pr.fmt
    for k in ("width", "height", "fps"):
        if not isinstance(f.get(k), (int, float)) or f[k] <= 0:
            errs.append(f"format.{k} must be a positive number")
    if f.get("width", 0) % 2 or f.get("height", 0) % 2:
        errs.append("format width/height must be even (yuv420p)")
    if not pr.scenes:
        errs.append("no scenes defined")
    ids: set[str] = set()
    for i, s in enumerate(pr.scenes):
        sid = s.get("id", f"#{i}")
        where = f"scene '{sid}'"
        if not ID_RE.match(str(sid)):
            errs.append(f"{where}: id must be kebab-case")
        if sid in ids:
            errs.append(f"{where}: duplicate id")
        ids.add(sid)
        if s.get("framework") not in FRAMEWORKS:
            errs.append(f"{where}: framework must be one of {sorted(FRAMEWORKS)}")
        if not s.get("render"):
            errs.append(f"{where}: missing 'render' path")
        elif Path(s["render"]).suffix not in (".mp4", ".mov"):
            errs.append(f"{where}: render must be .mp4 or .mov")
        dur = s.get("duration")
        if not isinstance(dur, (int, float)) or dur <= 0:
            errs.append(f"{where}: duration must be a positive number of seconds")
            continue
        if not is_whole_frames(dur, pr.fps):
            errs.append(f"{where}: duration {dur}s is {dur * pr.fps:.3f} frames at {pr.fps:g} fps; use whole frames")
        t = s.get("transition_in")
        if t:
            if i == 0:
                errs.append(f"{where}: first scene cannot have transition_in")
            if t.get("type") not in XFADE:
                errs.append(f"{where}: transition type '{t.get('type')}' is not an xfade transition")
            td = t.get("duration")
            if not isinstance(td, (int, float)) or td <= 0:
                errs.append(f"{where}: transition duration must be > 0")
            else:
                if not is_whole_frames(td, pr.fps):
                    errs.append(f"{where}: transition duration {td}s is not whole frames")
                prev = pr.scenes[i - 1].get("duration", 0) if i else 0
                if td >= dur or (i and td >= prev):
                    errs.append(f"{where}: transition ({td}s) must be shorter than both adjacent scenes")
        if not s.get("source"):
            warns.append(f"{where}: no 'source' set; stale-render detection disabled")
    audio_ids = {a.get("id") for a in pr.audio if a.get("id")}
    for j, a in enumerate(pr.audio):
        where = f"audio '{a.get('id', f'#{j}')}'"
        if not a.get("file"):
            errs.append(f"{where}: missing 'file'")
        if "at_scene" in a and a["at_scene"] not in ids:
            errs.append(f"{where}: at_scene '{a['at_scene']}' is not a scene id")
        if "start" in a and "at_scene" in a:
            errs.append(f"{where}: use either 'start' or 'at_scene' (+ 'offset'), not both")
        if a.get("duck_under") and a["duck_under"] not in audio_ids:
            errs.append(f"{where}: duck_under '{a['duck_under']}' is not an audio id")
        if a.get("duck_under") == a.get("id"):
            errs.append(f"{where}: cannot duck under itself")
    if pr.delivery.get("reencode_video") not in (True, False):
        errs.append("delivery.reencode_video must be true or false")
    return errs, warns


def timeline(pr: Project) -> tuple[list[dict], float]:
    rows, end = [], 0.0
    for i, s in enumerate(pr.scenes):
        d = float(s.get("duration", 0))
        t = s.get("transition_in") or {}
        td = float(t.get("duration", 0)) if i else 0.0
        start = end - td
        end = start + d
        rows.append({"id": s.get("id"), "framework": s.get("framework"), "start": round(start, 6),
                     "end": round(end, 6), "duration": d, "transition_in": t.get("type") if td else None,
                     "transition_duration": td})
    return rows, round(end, 6)


def audio_start(pr: Project, a: dict, rows: list[dict]) -> float:
    if "at_scene" in a:
        base = next(r["start"] for r in rows if r["id"] == a["at_scene"])
        return base + float(a.get("offset", 0))
    return float(a.get("start", 0))


# --------------------------------------------------------------------------- probing

def ffprobe(path: Path) -> dict | None:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt,sample_aspect_ratio,sample_rate,channels",
             "-show_entries", "format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, check=True).stdout
        return json.loads(out)
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        return None


def parse_rate(r: str) -> float:
    n, _, d = r.partition("/")
    return float(n) / float(d or 1) if float(d or 1) else 0.0


def newest_mtime(paths: list[Path]) -> float:
    newest = 0.0
    for p in paths:
        if p.is_file():
            newest = max(newest, p.stat().st_mtime)
        elif p.is_dir():
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for fn in files:
                    try:
                        newest = max(newest, (Path(root) / fn).stat().st_mtime)
                    except OSError:
                        pass
    return newest


def scene_state(pr: Project, s: dict, tier: str = "master") -> dict:
    """Return {'state': ok|missing|stale|mismatch|unreadable, 'problems': [...], 'probe': {...}}"""
    render = pr.render_path(s, tier)
    res = {"id": s["id"], "render": str(render.relative_to(pr.dir)), "problems": [], "state": "ok"}
    if not render.is_file():
        res["state"] = "missing"
        return res
    info = ffprobe(render)
    if not info:
        res["state"] = "unreadable"
        res["problems"].append("ffprobe could not read the file")
        return res
    v = next((st for st in info.get("streams", []) if st.get("codec_type") == "video"), None)
    if not v:
        res["state"] = "mismatch"
        res["problems"].append("no video stream")
        return res
    f = pr.fmt
    fps = parse_rate(v.get("r_frame_rate", "0/1"))
    dur = float(info.get("format", {}).get("duration", 0))
    res["probe"] = {"codec": v.get("codec_name"), "size": f"{v.get('width')}x{v.get('height')}",
                    "fps": round(fps, 3), "pix_fmt": v.get("pix_fmt"), "duration": round(dur, 3)}
    vw, vh = v.get("width") or 0, v.get("height") or 0
    if tier == "master" and (vw, vh) != (f["width"], f["height"]):
        res["problems"].append(f"size {vw}x{vh} != {f['width']}x{f['height']}")
    if tier == "preview" and (not vh or abs(vw / vh - f["width"] / f["height"]) > 0.01 or vh > f["height"]):
        res["problems"].append(f"preview size {vw}x{vh} must keep the {f['width']}x{f['height']} aspect ratio")
    if abs(fps - pr.fps) > 0.01:
        res["problems"].append(f"fps {fps:g} != {pr.fps:g}")
    is_alpha = render.suffix == ".mov"
    if not is_alpha and v.get("pix_fmt") != f.get("pix_fmt", "yuv420p"):
        res["problems"].append(f"pix_fmt {v.get('pix_fmt')} != {f.get('pix_fmt', 'yuv420p')}")
    sar = v.get("sample_aspect_ratio", "1:1")
    if sar not in ("1:1", "0:1", None):
        res["problems"].append(f"SAR {sar} != 1:1")
    if abs(dur - float(s["duration"])) > 1.0 / pr.fps + 1e-3:
        res["problems"].append(f"duration {dur:.3f}s != planned {s['duration']}s (>1 frame)")
    if s.get("scene_audio") and not any(st.get("codec_type") == "audio" for st in info["streams"]):
        res["problems"].append("scene_audio is true but the render has no audio stream")
    if res["problems"]:
        res["state"] = "mismatch"
        return res
    src = s.get("source")
    if src:
        srcs = [pr.path(x) for x in (src if isinstance(src, list) else [src])]
        if newest_mtime(srcs) > render.stat().st_mtime:
            res["state"] = "stale"
            res["problems"].append("source changed after this render; re-render")
    return res


def verify(pr: Project, tier: str = "master") -> tuple[list[dict], bool]:
    states = [scene_state(pr, s, tier) for s in pr.scenes]
    codecs = {st["probe"]["codec"] for st in states if "probe" in st and not st["render"].endswith(".mov")}
    if len(codecs) > 1:
        for st in states:
            st["problems"].append(f"mixed codecs across scenes: {sorted(codecs)}")
            if st["state"] == "ok":
                st["state"] = "mismatch"
    ok = all(st["state"] == "ok" for st in states)
    return states, ok


# --------------------------------------------------------------------------- assembly

def next_version(directory: Path, stem: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    n = 1
    pat = re.compile(rf"^{re.escape(stem)}-v(\d+)\.mp4$")
    for f in directory.iterdir():
        m = pat.match(f.name)
        if m:
            n = max(n, int(m.group(1)) + 1)
    return directory / f"{stem}-v{n}.mp4"


def media_duration(path: Path) -> float | None:
    info = ffprobe(path) if path.is_file() else None
    try:
        return float(info["format"]["duration"]) if info else None
    except (KeyError, TypeError, ValueError):
        return None


def build_command(pr: Project, mode: str, out: Path, force_reencode: bool,
                  loudnorm_filter: str | None, measure_only: bool = False) -> tuple[list[str], dict]:
    rows, total = timeline(pr)
    fps, fmt = pr.fps, pr.fmt
    has_transitions = any(r["transition_duration"] for r in rows)
    tier = "preview" if mode == "preview" else "master"
    pw, ph = pr.preview_size()
    copy_video = (tier == "master" and not has_transitions and not force_reencode and not pr.delivery["reencode_video"]
                  and all(s["render"].endswith(".mp4") for s in pr.scenes))
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostats"]
    filters: list[str] = []
    meta = {"total": total, "copy_video": copy_video, "transitions": has_transitions}

    # ---- video inputs
    if copy_video:
        concat = pr.dir / "renders" / ".concat.txt"
        meta["concat_file"] = concat
        meta["concat_body"] = "".join(f"file '{pr.render_path(s, tier)}'\n" for s in pr.scenes)
        args += ["-f", "concat", "-safe", "0", "-i", str(concat)]
        n_inputs = 1
        vlabel = None
    else:
        for s in pr.scenes:
            args += ["-i", str(pr.render_path(s, tier))]
        n_inputs = len(pr.scenes)
    if not copy_video and not measure_only:  # measurement pass maps audio only
        for i, s in enumerate(pr.scenes):
            filters.append(f"[{i}:v]trim=duration={s['duration']},setpts=PTS-STARTPTS,"
                           f"settb=AVTB,fps={fps:g},"
                           + (f"scale={pw}:{ph}:flags=bicubic," if tier == "preview" else "")
                           + f"format={fmt.get('pix_fmt', 'yuv420p')},setsar=1[v{i}]")
        cur, cur_len = "v0", float(pr.scenes[0]["duration"])
        for i in range(1, len(pr.scenes)):
            s, r = pr.scenes[i], rows[i]
            lab = f"x{i}"
            if r["transition_duration"]:
                td = r["transition_duration"]
                filters.append(f"[{cur}][v{i}]xfade=transition={r['transition_in']}:duration={td:g}:"
                               f"offset={cur_len - td:.6f}[{lab}]")
                cur_len += float(s["duration"]) - td
            else:
                filters.append(f"[{cur}][v{i}]concat=n=2:v=1:a=0[{lab}]")
                cur_len += float(s["duration"])
            cur = lab
        vlabel = cur

    # ---- audio inputs
    stems: list[dict] = []
    for i, s in enumerate(pr.scenes):
        if s.get("scene_audio"):
            stems.append({"id": f"scene:{s['id']}", "file": str(pr.render_path(s, tier)), "start": rows[i]["start"],
                          "length": float(s["duration"]), "volume": s.get("scene_audio_volume", 1.0)})
    for a in pr.audio:
        stems.append({**a, "start": audio_start(pr, a, rows)})

    alabels: dict[str, str] = {}
    for k, a in enumerate(stems):
        idx = n_inputs + k
        path = pr.path(a["file"])
        args += ["-i", str(path)]
        start = max(0.0, float(a["start"]))
        trim_start = float(a.get("trim_start", 0))
        src_len = media_duration(path)
        avail = (src_len - trim_start) if src_len else None
        length = a.get("length") or avail or (total - start)
        length = max(0.0, min(float(length), total - start))
        chain = [f"atrim=start={trim_start:g}:duration={length:.6f}", "asetpts=PTS-STARTPTS",
                 "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"]
        if "gain_db" in a:
            chain.append(f"volume={float(a['gain_db']):g}dB")
        elif "volume" in a:
            chain.append(f"volume={float(a['volume']):g}")
        if a.get("fade_in"):
            chain.append(f"afade=t=in:st=0:d={float(a['fade_in']):g}")
        if a.get("fade_out"):
            fo = min(float(a["fade_out"]), length)
            chain.append(f"afade=t=out:st={length - fo:.6f}:d={fo:g}")
        ms = int(round(start * 1000))
        if ms:
            chain.append(f"adelay={ms}:all=1")
        lab = f"a{k}"
        filters.append(f"[{idx}:a]{','.join(chain)}[{lab}]")
        alabels[a.get("id") or lab] = lab

    # ducking: key streams are split so they can be both mixed and used as sidechain
    keys = {a["duck_under"] for a in stems if a.get("duck_under")}
    for key in keys:
        lab = alabels[key]
        filters.append(f"[{lab}]asplit=2[{lab}m][{lab}k]")
    mix_inputs = []
    for a in stems:
        lab = alabels[a.get("id") or f"a{stems.index(a)}"]
        if (a.get("id") in keys):
            lab = f"{lab}m"
        if a.get("duck_under"):
            key = alabels[a["duck_under"]]
            ducked = f"{lab}d"
            amt = a.get("duck", {})
            filters.append(f"[{lab}][{key}k]sidechaincompress=threshold={amt.get('threshold', 0.05)}:"
                           f"ratio={amt.get('ratio', 8)}:attack={amt.get('attack', 20)}:"
                           f"release={amt.get('release', 300)}[{ducked}]")
            lab = ducked
        mix_inputs.append(f"[{lab}]")

    alabel = None
    if mix_inputs:
        tail = f"apad,atrim=0:{total:.6f}"
        if loudnorm_filter:
            tail += "," + loudnorm_filter
        if len(mix_inputs) == 1:
            filters.append(f"{mix_inputs[0]}{tail}[aout]")
        else:
            filters.append(f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=longest:"
                           f"normalize=0,{tail}[aout]")
        alabel = "aout"

    if filters:
        args += ["-filter_complex", ";".join(filters)]

    if measure_only:
        args[3] = "info"  # loudnorm prints its JSON at info level
        args += ["-map", f"[{alabel}]", "-f", "null", "-"]
        return args, meta

    if copy_video:
        args += ["-map", "0:v:0", "-c:v", "copy"]
    else:
        crf = 23 if tier == "preview" else pr.delivery["crf"]
        preset = "ultrafast" if tier == "preview" else pr.delivery["preset"]
        args += ["-map", f"[{vlabel}]", "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
                 "-profile:v", "high", "-pix_fmt", fmt.get("pix_fmt", "yuv420p"), "-r", f"{fps:g}"]
    if alabel:
        args += ["-map", f"[{alabel}]", "-c:a", "aac",
                 "-b:a", "128k" if tier == "preview" else pr.delivery["audio_bitrate"],
                 "-ar", "48000", "-ac", "2"]
    else:
        args += ["-an"]
    args += ["-t", f"{total:.6f}", "-movflags", "+faststart", "-n", str(out)]
    return args, meta


def assemble(pr: Project, mode: str, dry_run: bool, out_arg: str | None, force_reencode: bool) -> int:
    errs, warns = validate(pr)
    if errs:
        print_issues(errs, warns)
        return 1
    if mode == "final" and not pr.approved:
        msg = ("final is locked: the person has not finalized. Keep iterating with --preview; "
               "write APPROVED.md only after they reply 'finalize'.")
        if not dry_run:
            print("error: " + msg)
            return 1
        print("# note: " + msg)
    tier = "preview" if mode == "preview" else "master"
    if not dry_run:
        states, ok = verify(pr, tier)
        if not ok:
            print_states(states)
            print(f"\nassemble aborted: fix/re-render the {tier} scenes above.")
            return 1
    sub = "drafts" if mode == "preview" else "final"
    out = Path(out_arg).resolve() if out_arg else next_version(pr.studio / "exports" / sub, f"{pr.slug}-{mode}")
    if out.exists():
        print(f"error: {out} exists; never overwrite exports")
        return 1
    L = pr.loudness
    base_ln = f"loudnorm=I={L['target_lufs']}:TP={L['true_peak']}:LRA={L['lra']}"
    has_audio = bool(pr.audio or any(s.get("scene_audio") for s in pr.scenes))

    ln = base_ln if has_audio else None
    if mode == "final" and has_audio:
        mcmd, meta = build_command(pr, mode, out, force_reencode, base_ln + ":print_format=json", measure_only=True)
        if dry_run:
            print("# pass 1 (loudness measurement)")
            print(shlex.join(mcmd))
            ln = base_ln + ":measured_I=<I>:measured_TP=<TP>:measured_LRA=<LRA>:measured_thresh=<T>:offset=<O>:linear=true"
        else:
            write_concat(meta)
            r = subprocess.run(mcmd, capture_output=True, text=True)
            m = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr)
            if r.returncode or not m:
                print("loudness measurement failed:\n" + r.stderr[-2000:])
                return 1
            j = json.loads(m[-1])
            ln = (f"{base_ln}:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
                  f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:"
                  f"offset={j['target_offset']}:linear=true")
    if ln:
        ln += ",aresample=48000"
    cmd, meta = build_command(pr, mode, out, force_reencode, ln)
    if dry_run:
        if meta.get("concat_body"):
            print(f"# concat list {meta['concat_file']}:\n" + meta["concat_body"])
        print(f"# {mode}: total {meta['total']:.3f}s, video {'stream-copy' if meta['copy_video'] else 're-encode'}")
        print(shlex.join(cmd))
        print(f"# output -> {out}")
        return 0
    write_concat(meta)
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print("ffmpeg failed:\n" + r.stderr[-3000:])
        return 1
    dur = media_duration(out) or 0.0
    size = out.stat().st_size / 1e6
    ok = abs(dur - meta["total"]) <= 1.0 / pr.fps + 1e-3
    print(f"{'OK' if ok else 'WARNING'}: {out}")
    print(f"  duration {dur:.3f}s (timeline {meta['total']:.3f}s), {size:.1f} MB, "
          f"video {'stream-copied' if meta['copy_video'] else 're-encoded'}, "
          f"audio {'none' if not has_audio else str(L['target_lufs']) + ' LUFS target'}")
    if not ok:
        print("  output duration differs from the timeline by more than one frame")
    return 0 if ok else 1


def write_concat(meta: dict) -> None:
    if meta.get("concat_body"):
        meta["concat_file"].parent.mkdir(parents=True, exist_ok=True)
        meta["concat_file"].write_text(meta["concat_body"])


# --------------------------------------------------------------------------- tokens

GENERATED = "GENERATED from tokens.json by production.py sync-tokens. Do not edit; edit tokens.json."


def flatten(d: dict, prefix: str = "") -> list[tuple[str, str]]:
    out = []
    for k, v in d.items():
        key = f"{prefix}-{k}" if prefix else str(k)
        key = re.sub(r"[^a-zA-Z0-9-]", "-", key).lower()
        if isinstance(v, dict):
            out += flatten(v, key)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            unit = "px" if re.search(r"-px(?=-|$)", key) else ("s" if re.search(r"-s(?=-|$)", key) else "")
            out.append((re.sub(r"-(px|s)(?=-|$)", "", key), f"{v:g}{unit}"))
        elif isinstance(v, str):
            out.append((key, f"'{v}'" if " " in v and not v.startswith("#") else v))
    return out


def sync_tokens(project_dir: Path) -> list[Path]:
    """Write tokens.css (HyperFrames) and tokens.ts (Remotion) from tokens.json. Returns written files."""
    tj = project_dir / "tokens.json"
    tokens = json.loads(tj.read_text())
    written = []
    hf = project_dir / "hyperframes" if (project_dir / "hyperframes").is_dir() else (
        project_dir if (project_dir / "index.html").is_file() else None)
    if hf:
        css = [f"/* {GENERATED} */", ":root {"] + [f"  --{k}: {v};" for k, v in flatten(tokens)] + ["}", ""]
        dest = hf / "assets" / "tokens.css"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("\n".join(css))
        written.append(dest)
    rm = project_dir / "remotion" if (project_dir / "remotion").is_dir() else (
        project_dir if (project_dir / "remotion.config.ts").is_file() else None)
    if rm and (rm / "src").is_dir():
        dest = rm / "src" / "tokens.ts"
        dest.write_text(f"// {GENERATED}\nexport const tokens = {json.dumps(tokens, indent=2)} as const;\n"
                        "export type Tokens = typeof tokens;\n")
        written.append(dest)
    return written


# --------------------------------------------------------------------------- output

def print_issues(errs: list[str], warns: list[str]) -> None:
    for e in errs:
        print(f"ERROR   {e}")
    for w in warns:
        print(f"warning {w}")


def print_states(states: list[dict]) -> None:
    for st in states:
        mark = {"ok": "ok     ", "missing": "MISSING", "stale": "STALE  "}.get(st["state"], "BAD    ")
        line = f"{mark} {st['id']:<20} {st['render']}"
        if st.get("probe"):
            p = st["probe"]
            line += f"  [{p['codec']} {p['size']} {p['fps']}fps {p['pix_fmt']} {p['duration']}s]"
        print(line)
        for pb in st["problems"]:
            print(f"        - {pb}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["validate", "timeline", "verify", "status", "assemble", "sync-tokens"])
    ap.add_argument("project")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--preview", "--draft", dest="preview", action="store_true",
                   help="480p review cut from renders/preview/ (the feedback loop)")
    g.add_argument("--final", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--force-reencode", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--tier", choices=["preview", "master"],
                    help="verify/status: which renders to check (default: master if APPROVED.md exists, else preview)")
    a = ap.parse_args()
    if a.command == "sync-tokens":
        d = Path(a.project).resolve()
        d = d.parent if d.suffix == ".json" else d
        if not (d / "tokens.json").is_file():
            print(f"error: {d / 'tokens.json'} not found")
            return 1
        files = sync_tokens(d)
        print("wrote " + ", ".join(str(f.relative_to(d)) for f in files) if files
              else "no hyperframes/ or remotion/ app found yet; nothing written")
        return 0
    pr = Project(a.project)

    if a.command == "validate":
        errs, warns = validate(pr)
        print_issues(errs, warns)
        if not errs:
            _, total = timeline(pr)
            print(f"production.json OK: {len(pr.scenes)} scenes, {total:.3f}s at "
                  f"{pr.fmt['width']}x{pr.fmt['height']} {pr.fps:g}fps")
        return 1 if errs else 0

    if a.command == "timeline":
        errs, _ = validate(pr)
        rows, total = timeline(pr)
        print(f"{'scene':<20} {'framework':<12} {'start':>9} {'end':>9} {'dur':>7}  in")
        for r in rows:
            tr = f"{r['transition_in']} {r['transition_duration']:g}s" if r["transition_in"] else "cut"
            print(f"{r['id']:<20} {r['framework'] or '?':<12} {r['start']:>9.3f} {r['end']:>9.3f} {r['duration']:>7.3f}  {tr}")
        print(f"total {total:.3f}s ({round(total * pr.fps)} frames)")
        for j, au in enumerate(pr.audio):
            try:
                print(f"audio {au.get('id', j)}: starts {audio_start(pr, au, rows):.3f}s ({au.get('file')})")
            except StopIteration:
                pass
        if errs:
            print(f"({len(errs)} validation errors; run validate)")
        return 1 if errs else 0

    if a.command in ("verify", "status"):
        errs, warns = validate(pr)
        if errs:
            if a.json:
                print(json.dumps({"slug": pr.slug, "valid": False, "errors": errs}))
            else:
                print_issues(errs, warns)
            return 1
        tier = a.tier or pr.default_tier()
        states, ok = verify(pr, tier)
        if a.json:
            _, total = timeline(pr)
            print(json.dumps({"slug": pr.slug, "valid": True, "total": total, "ok": ok, "tier": tier,
                              "approved": pr.approved,
                              "scenes": [{k: st.get(k) for k in ("id", "state", "problems")} for st in states]}))
        else:
            print_states(states)
            print(f"[{tier} tier] " + ("all scenes match the spec" if ok else "scenes need attention (see above)"))
        return 0 if ok else 1

    if a.command == "assemble":
        if not (a.preview or a.final):
            print("assemble needs --preview or --final")
            return 2
        return assemble(pr, "preview" if a.preview else "final", a.dry_run, a.out, a.force_reencode)
    return 2


if __name__ == "__main__":
    sys.exit(main())
