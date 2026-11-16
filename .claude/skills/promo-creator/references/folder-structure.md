# Folder structure

The `promo-creator-setup` skill creates the studio folders; `scripts/scaffold.sh` creates each project.
Every project uses the same layout, whichever frameworks it needs:

```
projects/<slug>/
├── BRIEF.md  PLAN.md  FEEDBACK.md  production.json  tokens.json   (from templates/)
├── remotion/        Remotion app, only with --remotion (src/, public/fonts/, package.json)
├── hyperframes/     HyperFrames project, only with --hyperframes (index.html, compositions/, assets/fonts/)
├── audio/           conformed stems: music, vo, sfx
├── media/           conformed footage/images derived from raw-footage/
└── renders/         master scene renders NN-<id>.mp4; renders/preview/ = loop renders
```

Studio root: `raw-footage/{videos,audio,images}/` (read-only), `references/{inspiration,scripts,storyboards}/`,
`exports/drafts/` (480p previews), `exports/final/` (masters).

`scaffold.sh` passes `--skip-skills` to `hyperframes init`: skills live once at the studio root
(`.claude/skills/`, installed by `promo-creator-setup` via `npx skills add`), never per project.

## Naming

- Project slug: kebab-case (`q3-feature-launch`).
- Scene ids: short kebab-case, identical everywhere — `production.json`, Remotion
  `<Composition id>`, HyperFrames `compositions/<id>.html` and `data-composition-id`.
- Renders: `renders/<NN>-<scene-id>.mp4` with a two-digit order prefix.
- Exports: `exports/drafts/<slug>-preview-v<N>.mp4` (480p), `exports/final/<slug>-final-v<N>.mp4`,
  variants `<slug>-final-v<N>-9x16.mp4`, `<slug>-thumb.png`.

## Assets

- Never edit or overwrite files in `raw-footage/`. Copy or conform into the project
  (`media/`, `audio/`, `hyperframes/assets/`, `remotion/public/`).
- Remotion loads assets from `public/` through `staticFile()`. HyperFrames loads from
  `assets/...` (relative, no leading `/`). A file needed by both is copied into both.
- Fonts: the same font files in `remotion/public/fonts/` and `hyperframes/assets/fonts/`.
