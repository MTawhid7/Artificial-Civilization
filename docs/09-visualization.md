# 09 — The Atlas (Visualization)

## Design premise

The instinct is "live map with dots." Resist it. For a 10,000-year run that is either
unwatchably slow or an unreadable blur, and 10,000 dots is noise rather than spectacle.

**The right data source is not the live state — it is the Chronicle.** A complete, replayable
log means the visualization is a *history you scrub through*, not a feed you stare at. That
unlocks fast-forward, jump-to-the-interesting-part, and side-by-side timeline comparison.

> The Atlas is how a non-technical person understands the project in sixty seconds. It is not
> the project. It reads a digest and can never affect a run.

---

## Layout

Four views, one shared time scrubber.

```text
┌─────────────────────────────────────────────────────────────┐
│  ATLAS ▸ World K-4471 ▸ Year 3,847          [1x] [50x] [▶▶] │
├────────────────────────────────┬────────────────────────────┤
│                                │  THE CHRONICLE             │
│        [ living map ]          │  ──────────────            │
│    territories · borders       │  Years 3,801–3,900         │
│    trade flows · migration     │  The western league held   │
│                                │  the river for a century.  │
│                                │  Then the grain failed…    │
├────────────────────────────────┴────────────────────────────┤
│  ▓▓▒▒░░ ▓▓▓▓ ██ ▒▒▒▒▒ ░░░ ████ ▒▒▒ ░ ██████ ▒▒             │
│  ├───┴────┴──▲──┴────┴─────┴────┴──────┴───→ year 10,000    │
│      ⚔ war   ☠ plague   ✦ discovery   ⚑ revolution          │
└─────────────────────────────────────────────────────────────┘
```

### View 1 — The map: aggregates, never agents

Territories as colored influence regions with borders that visibly breathe and shift. Trade as
flowing lines whose thickness is volume. Migration as particle streams. Contagion as a dark
stain spreading along the contact network.

**Never render individual dots. Render what individuals add up to.**

### View 2 — The Chronicle panel

The Historian's text, scrolling in sync with the scrubber. This is what makes the project
legible to non-technical people — they don't read charts, they read stories.

Extension: generate **an encyclopedia for a world that never existed** — cross-linked entries
for cities, wars, inventors, technologies, all derived from the log. Browsable and highly
shareable.

⚠️ Historian output is *never* evidence. It is an interface, and must be visibly labelled as
generated narrative *(→ [12-risks.md](12-risks.md))*.

#### Built at A3, without the scrubber

Click a band on the wall and that world's written history opens below it, era by era. There is no
scrubber yet, so the panel highlights the era containing the frame that was clicked rather than
following a playhead — the same reading experience with none of the machinery C3 will need.

Three things about it are load-bearing rather than decorative:

- **The generated label is permanent**, in the panel header and in the markdown file itself. A file
  gets pasted into a chat or an issue where the viewer's label does not follow it, so the label has
  to travel with the bytes.
- **Every sentence keeps its citation.** Hovering one shows the fact ids it rests on and the
  aggregate rows behind them. The containment cannot stop at the file if the file is not what most
  people read *(→ [D-068](DECISIONS.md#d-068))*.
- **Removed sentences are counted in view.** The panel shows how many failed the grounding checks.
  A panel showing only what survived would report perfect grounding by construction.

Only a handful of a hundred worlds are narrated, and those bands are marked in the gutter — a
chronicle nobody can find is a chronicle that was not written. Narrative is optional throughout: a
digest built before A3 renders a wall with no panel rather than a broken page.

### View 3 — The fingerprint strip

An entire 10,000-year history compressed into one horizontal band: height for population,
color for technology level, red slashes for wars, dark bands for plagues, breaks for
collapses. One world, one strip.

#### Strip encoding v0.1 — built

| Channel | S0 meaning |
|---|---|
| bar height | population, on one scale shared by every world in the image |
| bar color | a chosen series, default `energy_gini`; also on a shared scale |
| red column | a drawdown marker from the detector suite |
| dark tail | extinction — population reached zero and stayed there |

The encoding above is what the design asks for with the channels that exist at S0. There is no
technology level to color by, no war to slash, no plague to band; those channels arrive with the
primitives that produce them, and the renderer takes `--color` so the substitution is a documented
choice rather than a hidden one.

**A mark is not a finding.** The strip draws every drawdown it is given; whether there are more of
them than a population of that volatility produces by chance is what the `collapse` detector's
effect size answers, and it travels in the digest beside the markers precisely so a renderer
cannot show one without the other.

### View 4 — The wall (the money shot)

```text
K-4471  ▓▓▒▒░░ ▓▓▓▓ ██ ▒▒▒▒▒ ░░░ ████ ▒▒▒ ░ ██████ ▒▒
K-4472  ▓▓▓▒▒▒ ░░ ▓▓▓▓▓▓ ▒▒ ███ ░░░░░░░░ ✕
K-4473  ▓▒░ ✕
K-4474  ▓▓▒▒░░ ▓▓▓ ██ ▒▒▒▒ ░░ ████ ▒▒ ░░ ███ ▒▒▒▒▒
                          ↑
          same starting conditions. every one of them.
```

A hundred fingerprints stacked. No explanation needed: identical worlds went wildly different
ways, and then the viewer spots that three share the same dark band at year 3,000 and *asks
why*. The entire thesis of the project, legible in two seconds — and the one visualization
nobody else can produce, because nobody else runs a corpus.

---

## The four moments that land

**The truth/belief split screen.** Two maps side by side: what happened, and what the
civilization believes happened. The north river glows warning-red on the belief map and clean
blue on the truth map — for nine hundred years after it ran clear. Watch a myth form as the
two maps drift apart. Unique to this design, because nothing else tracks belief separately
from truth *(→ [03-mechanisms.md](03-mechanisms.md#a-the-chronicle-gap--belief-vs-truth-measured))*.

**Follow one person.** Pick a random agent; watch their whole life narrated. *Born year 4,412
in the eastern settlements, moved west during the grain failure, four children, died at 39 in
the northern raid.* Aggregate statistics inform; one life lands.

**The scarcity ghost.** A second split, and the clearest way to show P1ᴸ²: physical stock on one
side, *effective* scarcity on the other. The mountain holds as much iron as it ever did while
the map beside it shifts from red to green, because someone discovered smelting. Nothing in the
ground changed. Everything about what it means changed.

**The cascade.** When `modulator_cascade` fires, animate it: a discovery lights up, its
modulators fan out to the primitives they touch, the newly-reachable region of the search space
glows, and the next discoveries fire from inside it. Thirty seconds, and a non-technical viewer
has watched an industrial revolution happen without anyone having written one
*(→ [03-mechanisms.md](03-mechanisms.md#f-the-cascade--how-revolutions-happen-without-a-revolution))*.

Then run the same seed with modulators disabled and show the fizzle beside it. That side-by-side
**is the null model, rendered** — a visualization that teaches the methodology rather than only
the outcome, which is a rare thing to get for free.

---

## Gamified modes

| Mode | What it does | Why it works |
|---|---|---|
| **God mode** | viewer applies a typed intervention, watches it propagate; forking lets them rewind and try differently | agency is the whole game |
| **Prediction** | "which of these three survives?" → scrub forward → reveal | turns watching into playing, nearly free to build |
| **Civilization cards** | shareable card per world: *survived 8,200 years · discovered gravity year 3,100 · fell to plague* | people collect and compare without being asked |
| **Speed** | 10,000 years in 60 seconds | time-lapse is the medium, not a feature of it |

God mode reuses the typed intervention system from
[06-data-model.md](06-data-model.md#interventions-typed) exactly — no separate code path.

---

## The architectural rule

**Never couple the Atlas to a live run.** Sim writes the Chronicle; Atlas reads a digest.
Nothing rendered can ever slow a run, and the Atlas can be built entirely against recorded
runs — including before the simulator exists, using synthetic digests.

```text
   Core ──→ Chronicle (GBs, columnar)  ──→ Lens ──→ metrics
                    │                            │
                    └──── digest builder ←───────┘
                                 ↓
                        digest.json (0.91 MB measured)
                                 ↓
                              ATLAS
```

Ten gigabytes of events cannot be shipped to a browser. ~2,000 downsampled frames can. The
digest schema *(→ [06-data-model.md](06-data-model.md#viz-digest))* is a **versioned contract**
— pin it before the Chronicle schema hardens.

## The best reuse in the design

**Lens detectors become the chapter markers.** We already need detectors that fire on war,
revolution, collapse, and discovery — for science
*(→ [07-detectors.md](07-detectors.md))*. Those exact firings annotate the timeline so a viewer
can jump straight to the interesting parts.

The scientific instrumentation *is* the narrative UI. Build detectors once, get both.

---

## Implementation notes

- **Web, single page.** It must be a URL you can send someone.
- **Canvas/WebGL** for the map and particle flows; Canvas for strips (SVG will not survive 100
  strips × 2,000 frames).
- **Digest loaded once, fully client-side.** No server round-trips while scrubbing.
- **Deterministic playback.** Frame N always renders identically — a screenshot must be
  reproducible.
- **Build order:** strip ✓ → wall ✓ → chronicle panel ✓ → map. The strip and wall carry the thesis
  and are by far the cheapest; the panel came free with A3 because the prose was already written.

**A2 built the first two with no toolchain** *(→ [D-062](DECISIONS.md#d-062))*: one HTML file,
vanilla JS, a 2D canvas, and the digest inlined at build time by `tools/build_atlas.py`. Inlining
is not a stylistic preference — the page has to render from `file://` and from a sandboxed host,
and neither will fetch a sibling `digest.json`. TypeScript and a bundler wait for C3, where the
scrubber over thousands of frames is the thing that actually needs them.

There are two consumers of the digest for a reason. The Python renderer produces the committed PNG;
the HTML page is what proved the contract, because a schema with only its own producer to answer to
is untested. Their decoders were checked against each other on real data before either was trusted.
