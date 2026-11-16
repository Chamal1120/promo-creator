# Creative brief intake

Run this before planning any new video. The answers go into `projects/<slug>/BRIEF.md`
(template: `templates/BRIEF.md`) and drive `PLAN.md`, `tokens.json` and the scene table.

## How to ask

- Use `AskUserQuestion` for choices (tone, length, format), plain questions for open text
  (key lines, product facts). Ask in **one round** of at most ~4 questions, then a short
  second round only for gaps. Do not interrogate.
- Pre-fill anything already given in the request, `references/scripts/`,
  `references/storyboards/`, `references/inspiration/` or the product's website; ask the
  person to confirm instead of asking from scratch.
- If the person says "you decide" / "no questions", choose sensible defaults, write them in
  `BRIEF.md` under **Assumptions**, and carry on.

## 1. Taste (required)

Ask how the video should *feel*, and accept any of these forms:

| Form | What to do with it |
| --- | --- |
| **Words** ("clean, Apple-like, calm", "energetic, bold, neon") | Turn every adjective into numbers in `tokens.json` and the style section: palette, type weight/size, motion speed (s), easing, cut rhythm (cuts per 10 s), density. |
| **Reference video(s)** (file in `references/inspiration/` or a URL) | Ask permission before opening or analysing it (the person's standing media rule). Then note pacing, transitions, type, color, camera moves. To copy a style closely use `/reverse-any-video`; for a known series style `/style-sampling`. |
| **Photos / screenshots / mood board** | Ask permission before viewing. Extract palette, type mood, texture, composition. |
| **Brand assets** (logo, brand guide, Figma) | Use exact colors/fonts from them; Figma via `/figma`. |

Also ask what to **avoid** (a look, color, cliché, competitor style). Record it.

## 2. Key lines (required)

- The **headline / hook line** — the one sentence the viewer must remember.
- **Supporting lines** — 2–5 short on-screen or voiceover lines, in order.
- **Call to action** — exact wording, URL, handle, offer, date.
- Ask whether lines are fixed copy (use verbatim) or drafts Claude may tighten.
- Legal lines: disclaimers, trademarks, pricing footnotes.

If the person has no copy, draft 2–3 options for the hook and CTA and let them pick.

## 3. Product / service facts (adapt to what it is)

Always: name, what it does in one sentence, audience, the one problem it solves,
2–4 proof points (features, numbers, testimonials), differentiator vs alternatives.

Then by type:

| Type | Ask for |
| --- | --- |
| Software / SaaS / app | Real UI screens or a URL to capture (`hyperframes capture <url>`), the 1–3 flows to show, real numbers for stats scenes, logo files. |
| Physical product | Product photos/renders (angles, transparent PNGs), key specs, packaging, price/where to buy. |
| Service / agency / local business | What the customer gets, process steps, results/case numbers, location, team or workplace footage, booking method. |
| Event / launch | Date, time, place, speakers, registration link, countdown? |
| Educational / explainer | Learning goal, audience level, the concept sequence, any diagrams/data. |
| Personal brand / creator | Face footage?, tone of voice, channel handles, recurring format. |

## 4. Production facts

- Where it will be shown → aspect ratio(s): 16:9, 9:16, 1:1, 4:5.
- Length (or platform limit) and deliverables (master, cut-downs, GIF, thumbnail).
- Audio: music mood / supplied track; voiceover (supplied, TTS via `/media-use`, or none);
  captions (SRT sidecar file / none; burned-in only on explicit request). If there is a
  voiceover, ask "Do you need no-VO files?" once per project and record the answer in BRIEF.md;
  make `-novo` versions only on a yes. Later versions/languages reuse the recorded answer. Default for >15 s story films: music + SFX.
- Language(s); deadline; anything already in `raw-footage/` to use.

## After intake

1. Write `BRIEF.md`; summarise it back in 5–8 lines and get a yes.
2. Map taste → `tokens.json` (the hook regenerates `tokens.css` / `tokens.ts`).
3. Map key lines → scenes in `PLAN.md` (every line belongs to exactly one scene).
4. Map product facts → which scenes need real assets vs drawn graphics.
