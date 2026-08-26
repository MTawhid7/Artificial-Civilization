# 14 — Handoff: where this is and what to build next

**Read this first in a new session.** It is the only document that goes stale on purpose; everything
else here is design, and this is state. Update it when a stage ships.

*Last updated: after A2 shipped and the Phase B prerequisites landed.*

---

## Status

| Stage | State | Evidence |
|---|---|---|
| **A0 — skeleton** | shipped | [a0-baseline](../experiments/a0-baseline/result.md) — 11 ms/tick, forking exact |
| **A1 — first evolution** | shipped | [a1-gradient-ascent](../experiments/a1-gradient-ascent/result.md) + [heredity control](../experiments/a1-heredity-control/result.md) |
| **A2 — first picture** | shipped | [a2-wall](../experiments/a2-wall/result.md) — 102 worlds, 9.4× between/within divergence |
| **A3 — the Historian** | **next** | criteria written, nothing built |
| **B0 — neural policy** | budget measured, nothing built | [00-feasibility § S1](00-feasibility.md#s1-measured-before-b0) |

**Gate:** 59 tests, green on macOS and Ubuntu. `uv run pytest` before anything else.

### What exists

```
src/core/       the simulation — 11-phase tick loop, S0 reactive policy, P1 + P10 at L0
src/chronicle/  event log (Parquet, 3 tiers), checkpoints
src/lens/       pop_stability, gradient_ascent, collapse  (+ directed_foraging, WITHDRAWN)
src/digest/     Chronicle -> versioned viz digest
src/forge/      run, sweep, viability precheck
atlas/          wall.template.html — the viewer, no build step
tools/          render_wall, build_atlas, check_links
bench/          bench_tick (S0), bench_policy (S1)
```

### Numbers worth not re-deriving

| | |
|---|---|
| S0 cost | **0.425 µs per agent-tick**, scales as `worlds × capacity × ticks` |
| S0 tick at 32×1000 | 11.0 ms — observe 3.6, decide 0.8 |
| S1 at hidden 48 | decide **2.60 ms** (3.2× S0), tick 12.8 ms (**1.16×**) |
| Sustained-load throttle | **1.88×** — every long projection carries it |
| Chronicle at `aggregated` | ~26 MB per 34-world × 30k run |
| Digest | 0.91 MB per run; budget is 5 MB |

**The binding constraint is compute, not disk** *(→ [00-feasibility](00-feasibility.md#the-constraint-moved))*.
Tiering worked well enough to invalidate D-047's premise. `population.capacity` is a linear tax on
the dominant phase, so headroom is paid for in wall-clock.

---

## What to build next

### 1. A3 — the Historian *(~3 days, next)*

An LLM reading the Chronicle and writing narrative history per era. Criteria are in
[10-roadmap.md § A3](10-roadmap.md#a3--first-story).

It is deliberately next because it is the **one stage where none of this project's inference
discipline applies** — its output is never evidence, by construction. That makes it low-risk, and it
costs API credit rather than compute. Needs an `ANTHROPIC_API_KEY` in `.env` (git-ignored).

The containment rules are the whole design: output lands under `narrative/`, never `metrics/`; it is
labelled generated wherever it is displayed; and a run with the Historian attached must produce a
byte-identical Chronicle to one without.

### 2. B0 — neural policy *(~2 weeks)*

**The budget question is already answered** — see the table above. Sizes are set, not to be
discovered: `hidden: 48`, `view_radius: 2`, one to a few lineages, which stays inside a ~13 ms tick.

- the gather still dominates at hidden 48; the bottleneck flips between hidden 64 and 128
- `view_radius` is the expensive lever and gets *worse* at S1: r=4 costs 11.66 ms of gather
  against 2.88 ms of policy
- lineages cost ~1.6× on `decide` at two and ~2.2× at sixteen — almost all of it in the 1→2 step,
  where the single fused matmul is lost

Expect the determinism gate to go red on a new platform once `tanh` runs every tick. That is
[D-057](DECISIONS.md#d-057), already settled: record the platform's golden, do not chase it.

### 3. B2 — first word ★ *(the biggest payoff)*

**The schema is already decided** *(→ [schemas/events.md](../schemas/events.md), [D-066](DECISIONS.md#d-066))*.
`SIGNAL` (40) and `SIGNAL_HEARD` (43) have their payloads specified and their enum slots claimed;
implement to that spec rather than re-deriving it. The reasoning matters more than the layout: each
column closes a specific way this stage could produce a confident wrong number.

The criterion that separates a result from a correlation is the **remap test** — rebuild the world
so the referent moves, and ask whether the signal follows the concept or the location.

---

## Open threads

**The most interesting one, from A1.** Agents evolved to calibrate reliance on local information to
that information's reliability — exploration temperature tracks patchiness at r = +0.937 while
gradient sensitivity holds steady. That is the S0 shadow of *belief calibrated to evidence quality*,
which is the machinery the Chronicle Gap (D2) runs on. Worth a dedicated experiment before Phase D
assumes it.

**Run length as a variable.** A2 showed between-world divergence still climbing at year 2,500 while
every A1 result was scored at 15,000 ticks, which makes "was that negative result simply
length-limited?" a live question about conclusions already committed.
`gradient_ascent` takes `max_tick`, so one long run can be scored at several windows — paired on the
same worlds, which beats comparing two runs of different lengths. See
`experiments/a1-run-length/`.

**Formal open questions** are tracked at the bottom of [DECISIONS.md](DECISIONS.md).

---

## Things that will waste a day if you don't know them

- **`uv sync` before `src/` exists** installs a broken package. Fix:
  `uv sync --reinstall-package artificial-civilization`.
- **The headroom precheck runs before every sweep** and takes a couple of minutes. When it fails it
  is right — raise `population.capacity` to what it suggests. `--skip-precheck` exists for studying
  a pinned ceiling deliberately, not for making a red gate go away.
- **A detector that reports `skipped` is not `silent`.** Skipped means the run does not carry the
  data — usually a log tier below `sampled`. `gradient_ascent` cannot read an `aggregated` run.
- **Commit before a run that matters**, or `meta.json` records a `-dirty` code version and the run
  cannot be tied to a commit.
- **`corpus/` is ~2.8 GB, git-ignored, and fully regenerable.** Delete it freely.
- **A stale CI run from 2026-08-19 is wedged in `queued`** on GitHub's side — cancel, force-cancel
  and delete all return 5xx. It blocks nothing (no `concurrency:` key, no branch protection) and
  consumed no minutes. Ignore it unless a CI badge is ever added to the README.
