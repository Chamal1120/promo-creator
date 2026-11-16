# The review loop

Production is a loop, not a straight line. Until the person says **finalize**, every
rendered output is a **480p preview**. Full-resolution renders happen exactly once, at the end.

```
brief ─► plan ─► build ─► preview render (480p) ─► show ─► feedback ─┐
                   ▲                                                 │
                   └──────────── apply changes ◄─────────────────────┘
                                         │  person replies "finalize"
                                         ▼
                        APPROVED.md ─► master renders ─► assemble --final
```

## Tiers

| | Preview tier (loop) | Master tier (after finalize) |
| --- | --- | --- |
| Scene renders | `renders/preview/NN-<id>.mp4` | `renders/NN-<id>.mp4` |
| Remotion | `--scale=0.5 --codec=h264 --crf=23 --x264-preset=ultrafast --pixel-format=yuv420p --muted` | `--codec=h264 --crf=16 --pixel-format=yuv420p --muted` |
| HyperFrames | `--fps <fps> --quality draft` | `--fps <fps> --crf 16` |
| Assembly | `production.py assemble <p> --preview` → 854×480 (vertical 480×854), CRF 23 + `ultrafast` preset, single-pass loudness | `assemble <p> --final` → full size, two-pass loudness |
| Output | `exports/drafts/<slug>-preview-vN.mp4` | `exports/final/<slug>-final-vN.mp4` |

HyperFrames cannot render below composition size, so its previews render at full size with
the fast `draft` encoder; the assembler scales every scene down to 480p. Remotion renders at
half size. The 480p cut is the only file shown for review.

Hooks enforce this: preview renders without the preview flags are denied, master renders and
`assemble --final` are refused until `APPROVED.md` exists, and `APPROVED.md` can only be
written after the person's latest message contains "finalize".

## One iteration

1. **Render** only scenes that are new or stale (`production.py status <p>` lists them; the
   post-render hook reports them as well).
2. **Assemble** `--preview` and give the person the file path and what changed since the
   last version (2–4 bullets). Mention that live previews exist (HyperFrames preview and
   Remotion Studio) for scrubbing.
3. **Collect feedback.** Ask open questions about the result, not about the code. When
   useful, offer specific choices with `AskUserQuestion` (e.g. "pace: tighter / as is /
   slower"). Accept timestamps ("at 0:12 the text is too small"). Map timestamps to scenes
   with `production.py timeline`.
4. **Log** the round in `projects/<slug>/FEEDBACK.md` (template `templates/FEEDBACK.md`):
   the preview version, the person's words verbatim, your interpretation as concrete changes
   (scene → change), and anything you need to confirm.
5. **Apply** the changes. Edit `BRIEF.md`, `tokens.json` or `production.json` when the
   feedback changes taste, copy or structure, then the scene sources. Re-render only the
   scenes affected; a token change touches every scene that uses it.
6. Repeat. End each preview hand-off with:
   *"Reply with feedback, or **finalize** to render the full-resolution master."*

Never decide that the video is done yourself. Never treat "looks good", "nice" or "ok" as
approval; ask whether they want to finalize or keep refining.

## Finalize

When the person's message says "finalize" (the hook records it):

1. Write `projects/<slug>/APPROVED.md` with their words, the date, and the approved preview
   version (`<slug>-preview-vN`).
2. Render every scene at the master tier (`renders/`), then `production.py verify <p>`.
3. `production.py assemble <p> --final`, then run the QA checklist (`qa.md`) and report.
4. If they want changes after the final, delete `APPROVED.md` (with their agreement) and go
   back to the preview loop. Final versions are never overwritten; the next final is `-vN+1`.
