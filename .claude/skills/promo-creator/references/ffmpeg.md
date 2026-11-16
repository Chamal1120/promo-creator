# FFmpeg recipes

`scripts/production.py` covers the standard path (verify → cuts/transitions → audio mix →
loudness → encode). Use these recipes for anything it does not cover, and to understand what
it runs (`assemble --dry-run` prints the exact commands).

## Inspect

```bash
# Stream facts that must match the spec
ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,width,height,r_frame_rate,pix_fmt,sample_aspect_ratio,nb_frames \
  -show_entries format=duration -of json renders/01-intro.mp4

# Exact frame count (slow but exact)
ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 renders/01-intro.mp4

# Loudness of a file
ffmpeg -hide_banner -i exports/final/x.mp4 -af ebur128=peak=true -f null - 2>&1 | tail -12
```

## Cuts only — no re-encode

All scenes share codec, size, fps and pixel format, so the concat demuxer can copy:

```bash
printf "file '%s'\n" renders/*.mp4 > renders/concat.txt
ffmpeg -f concat -safe 0 -i renders/concat.txt -map 0:v -c:v copy video-only.mp4
```

## Transitions (one re-encode)

`xfade` offset = when the transition starts on the *output* timeline:
`offset = (length of everything so far) − d`.

```bash
# A = 4 s, B = 5 s, 0.5 s fade → offset 3.5, total 8.5 s
ffmpeg -i A.mp4 -i B.mp4 -filter_complex \
 "[0:v]settb=AVTB,fps=30,format=yuv420p[a];[1:v]settb=AVTB,fps=30,format=yuv420p[b];\
  [a][b]xfade=transition=fade:duration=0.5:offset=3.5[v]" \
 -map "[v]" -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p out.mp4
```

Useful `xfade` transitions: `fade`, `fadeblack`, `fadewhite`, `dissolve`, `wipeleft`,
`wiperight`, `slideleft`, `slideright`, `smoothleft`, `circleopen`, `circleclose`, `radial`,
`zoomin`, `pixelize`, `hblur`. Keep transitions consistent within a video (one or two
types). Heavily designed transitions belong inside a framework, not here.

## Audio

```bash
# Place a stem at 2.25 s, -6 dB, 0.5 s fade in
[1:a]volume=0.5,afade=t=in:st=0:d=0.5,adelay=2250|2250[vo]

# Music bed with fade out ending at 30 s (fade starts at 28 s on the output timeline)
[2:a]volume=0.7,afade=t=out:st=28:d=2[music]

# Mix without amix's automatic level drop, then loudness-normalize
[vo][music]amix=inputs=2:duration=longest:normalize=0,atrim=0:30,loudnorm=I=-14:TP=-1:LRA=11[aout]

# Duck music under voiceover (sidechain)
[music][vo]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=300[ducked]
```

Sidechain: the first input is compressed, the second is the key; mix the key back in after.
`production.py` supports `"duck_under": "<audio id>"` on a stem for this.

Loudness targets: web/social −14 LUFS, −1 dBTP. Broadcast −23 LUFS (EBU R128) / −24 LKFS
(ATSC). The final pass uses two-pass `loudnorm` (measure, then apply with `linear=true`).

## Overlay an alpha render

```bash
ffmpeg -i base.mp4 -i lower-third.mov -filter_complex \
 "[1:v]setpts=PTS-STARTPTS+12/TB[ov];[0:v][ov]overlay=0:0:enable='between(t,12,17)':eof_action=pass[v]" \
 -map "[v]" -map 0:a? -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p -c:a copy out.mp4
```

## Delivery encodes

```bash
# Web master (what production.py --final does after mixing)
-c:v libx264 -crf 18 -preset slow -profile:v high -pix_fmt yuv420p -movflags +faststart \
-c:a aac -b:a 192k -ar 48000 -ac 2

# Higher fidelity / archive
-c:v libx264 -crf 14 -preset slower ...            # or ProRes: -c:v prores_ks -profile:v 3

# Size-capped (e.g. platform limit): two-pass bitrate
ffmpeg -y -i in.mp4 -c:v libx264 -b:v 6M -pass 1 -an -f null /dev/null && \
ffmpeg -i in.mp4 -c:v libx264 -b:v 6M -pass 2 -c:a aac -b:a 192k -movflags +faststart out.mp4
```

## Variants

```bash
# 9:16 from a 16:9 master — center crop (check that key content survives; prefer
# authoring a real vertical version in the frameworks when text is near the edges)
-vf "crop=ih*9/16:ih,scale=1080:1920"

# 1:1
-vf "crop=ih:ih,scale=1080:1080"

# Thumbnail at 3.2 s
ffmpeg -ss 3.2 -i final.mp4 -frames:v 1 -q:v 2 thumb.png

# GIF preview (palette)
ffmpeg -i final.mp4 -vf "fps=15,scale=720:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse" preview.gif

# Captions: deliver a sidecar .srt (default). WebVTT copy when a platform needs it:
ffmpeg -i captions.srt captions.vtt
# Burn-in ONLY when the person explicitly asks for a captioned video:
# -vf "subtitles=captions.srt:force_style='FontName=Inter,FontSize=22,Outline=2'"
```

## Rules of thumb

- Inputs to a filter graph: normalize every video branch with `settb=AVTB,fps=<fps>,format=yuv420p,setsar=1`.
- Never `-c copy` across mismatched files; verify first.
- `-ss` before `-i` is fast seek (keyframe), after `-i` is frame-accurate; for exact trims
  in a graph use `trim=start=..:end=..,setpts=PTS-STARTPTS`.
- Always end with `-movflags +faststart` for web delivery.
- Write to a new file; never overwrite an input in place.
