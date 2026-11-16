# Toolchain: pnpm + per-user pinned versions

**pnpm only.** Never `npm`, never `npx` (the only exception is `npx skills add` in
`promo-creator-setup`), never `@latest`, never `^`/`~` ranges for pinned packages.

## Pins

Versions are pinned **per user**, not per skill, in `~/.config/promo-creator/pins.sh`
(`$XDG_CONFIG_HOME` if set). Every studio and project on the machine uses the same versions, so
pnpm's store holds one copy and new projects install offline without re-downloading.

- `REMOTION_VERSION`, `HYPERFRAMES_VERSION`: set by `promo-creator-setup` on first run (the
  current npm versions that day). An existing pin is kept.
- `REACT_VERSION`, `TYPES_REACT_VERSION`, `TYPESCRIPT_VERSION`, `ESLINT_VERSION`,
  `PRETTIER_VERSION`, `TYPES_WEB_VERSION`: set by `scripts/scaffold.sh` on the first Remotion
  project, from whatever versions that first install resolved.

`scripts/scaffold.sh` applies the pins. Remotion and HyperFrames are exact devDependencies of
each project.

Rules:

- All `@remotion/*` packages share one version with `remotion` itself (Remotion requires it).
- Extra Remotion packages: `pnpm add -E --prefer-offline @remotion/<name>@<REMOTION_VERSION>`.
- Fresh install of an existing project: `pnpm install --prefer-offline`.
- Run CLIs inside the project with `pnpm exec`: `pnpm exec remotion studio|still|render …`,
  `pnpm exec hyperframes check|preview|render|snapshot …` (flags: `references/render-spec.md`),
  `pnpm exec tsc --noEmit`. Outside a project: `hyperframes …` (the pinned per-user CLI that setup puts on PATH).

## Upgrading

Only when the person asks. Use `/remotion-upgrade` (Remotion) or bump the HyperFrames
devDependency, pin the new version exactly, then update the value in the pins file so later
projects use the same version. Existing projects keep their version unless the person asks to
upgrade them.
