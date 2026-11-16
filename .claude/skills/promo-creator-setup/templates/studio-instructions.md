<!-- promo-creator:start (written by promo-creator-setup; edit freely outside this block) -->
# Promo studio

This folder is a promo-video studio (Remotion + HyperFrames + FFmpeg).

- For ANY video request (make, plan, edit, render, assemble, export), load the `promo-creator`
  skill first. It runs the creative brief, picks a framework per scene and routes to the
  `hyperframes*`, `remotion-*` and `media-use` skills.
- If `.claude/state/.prereq-met` is missing, load `promo-creator-setup` first.
- Each video lives in `projects/<slug>/` with `BRIEF.md`, `PLAN.md`, `production.json` and `tokens.json`.
- `raw-footage/` is read-only. Exports are versioned (`-vN`) and never overwritten.
- Use pnpm for every package and CLI (`pnpm exec`, `pnpm dlx`); `npx` only for `npx skills add`.
<!-- promo-creator:end -->
