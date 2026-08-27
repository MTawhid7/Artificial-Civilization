# 14 — Handoff: where this is and what to build next

**Read this first in a new session.** It is the only document that goes stale on purpose; everything
else here is design, and this is state. Update it when a stage ships.

*Last updated: after B0 shipped whole. Both its criteria were measured and neither was met; the
next stage is B1 or B2.*

---

## Status

| Stage | State | Evidence |
|---|---|---|
| **A0 — skeleton** | shipped | [a0-baseline](../experiments/a0-baseline/result.md) — 11 ms/tick, forking exact |
| **A1 — first evolution** | shipped | [a1-gradient-ascent](../experiments/a1-gradient-ascent/result.md) + [heredity control](../experiments/a1-heredity-control/result.md) |
| **A2 — first picture** | shipped | [a2-wall](../experiments/a2-wall/result.md) — 102 worlds, 9.4× between/within divergence |
| **Phase B prerequisites** | done | headroom precheck (D-065), S1 budget, `SIGNAL` payload (D-066), [a1-run-length](../experiments/a1-run-length/result.md) |
| **A3 — the Historian** | shipped | [a3-historian](../experiments/a3-historian/result.md) — 230 cited sentences; the gate rejects 19% of unguarded prose |
| **A4 — the viewer** | tier 1 shipped | [`tools/scope.py`](../tools/scope.py) — one world, keyframe by keyframe. Tiers 2–3 scoped, not built |
| **B0.1 — S1 policy** | shipped | [b0-neural](../experiments/b0-neural/result.md) — survival criterion **not met**; gradient-following rediscovered from blind in 105/105 scored worlds |
| **B0.2 — fog + `exploration_rate`** | shipped | [b0-fog](../experiments/b0-fog/result.md) — detector **silent**, 0/3 seeds; fires 14–26× larger on S0, so the silence is about the policy |

**Gate:** 112 tests, green on macOS and Ubuntu. `uv run pytest` before anything else.

### What exists

```
src/core/       the simulation — 11-phase tick loop, S0 reactive + S1 neural, P1 + P2 + P10 at L0
src/chronicle/  event log (Parquet, 3 tiers), checkpoints
src/lens/       pop_stability, gradient_ascent, collapse, exploration_rate  (+ directed_foraging, WITHDRAWN)
src/digest/     Chronicle -> versioned viz digest
src/historian/  facts -> LLM -> verified prose. Never evidence
src/forge/      run, sweep, viability precheck
atlas/          wall.template.html — the wall + the Chronicle panel, no build step
tools/          render_wall, build_atlas, check_links, scope (A4 tier 1)
bench/          bench_tick (S0), bench_policy (S1)
```

### Numbers worth not re-deriving

| | |
|---|---|
| S0 cost | **0.425 µs per agent-tick**, scales as `worlds × capacity × ticks` |
| S0 tick at 32×1000 | 11.0 ms — observe 3.6, decide 0.8 |
| S1 at hidden 48, **measured on the real loop** | 19.35 ms at 32×1000, grid 96 — **1.57× the S0 tick** at 8 lineages, 1.29× at one |
| ~~S1 projected by `bench_policy`~~ | ~~1.16×~~ — the synthetic bench grouped by lineage; the real one groups by **(world, lineage)** *(→ [00-feasibility](00-feasibility.md#s1-measured-again-after-b0))* |
| Sustained-load throttle | **1.88×** — every long projection carries it |
| Chronicle at `aggregated` | ~26 MB per 34-world × 30k run |
| Digest | 0.91 MB per run; budget is 5 MB |

**The binding constraint is compute, not disk** *(→ [00-feasibility](00-feasibility.md#the-constraint-moved))*.
Tiering worked well enough to invalidate D-047's premise. `population.capacity` is a linear tax on
the dominant phase, so headroom is paid for in wall-clock.

---

## What to build next

### 1. B2 — first word ★ *(next, and the biggest payoff)*

B0 is finished and B1 (plasticity, S2) is the roadmap's next rung, but **B2 is the better next
move** and B0's results are the argument. B0.2 found a channel with no payoff attached going
unused; B1 would add a second one — a plasticity rule refines a policy toward a reward, and this
world's only reward is food that the local patch already reports. A signal channel is different:
what one agent knows and another does not is *created* by the world rather than added to the agent,
so there is something for the channel to carry.

**The schema is already decided** *(→ [schemas/events.md](../schemas/events.md), [D-066](DECISIONS.md#d-066))*.
`SIGNAL` (40) and `SIGNAL_HEARD` (43) have their payloads specified and their enum slots claimed.
Implement to that spec rather than re-deriving it — each column closes a specific way this stage
could produce a confident wrong number.

The criterion that separates a result from a correlation is the **remap test**: rebuild the world so
the referent moves, and ask whether the signal follows the concept or the location.

### The B0 results, and what they license

**Both criteria were measured and neither was met.** What sits underneath them is worth more.

- **Selection rediscovered gradient-following from a blind start.** S1's founding cohort scores
  0.033–0.066 on `gradient_ascent` — a random network is nearly blind — and reaches 0.19–0.22 by the
  last tenth of the run, in **every world that survived to be scored**. It did not reach a rule
  written for this exact world in ~79 generations. Two results; only the first was in doubt.
- **Extinction is the survival mechanism**, not a lower steady state: S1 loses 28 of 48 worlds at
  `gather_efficiency` 1.5 and 2 of 48 at 2.5, and survivors are not far behind S0. The deficit is a
  founding-phase failure — the network must become competent before the founders' energy runs out.
- **`advantage_delta` is survivorship-biased.** The gather-2.5 arm (46 of 48 worlds scored) is the
  only one where that bias is small enough to ignore.
- **Fog earned nothing, and the measurement is trustworthy.** `exploration_rate` is silent on S1
  at 0/3 seeds, and reads **14–26× larger** on S0, whose `heading_persistence` gene is exactly the
  path-ordering it looks for. Fog moved observed coverage by +1.8% and shuffled coverage by +1.8%,
  so it changed how far agents walk and not how they order it.

**The one-line diagnosis, and the cheapest thing that would test it: the capacity was added without
the incentive.** `primitives.p10.rate` has been **0.0 in every run this project has ever made**. A
capacity field that drifts makes yesterday's knowledge stale, which is the first world in which
remembering where you have been could pay. Turning it on costs nothing — the primitive is built and
has been since A0.

**Use the scope on any S1 run.** It earned its keep at B0.1: S0's harvest field is a rectilinear
cross-hatch — its N/E/S/W sector rule made visible — while S1's population organizes into a band
along the resource ridges by year ~1,750. Neither is in any series either experiment records.
`uv run python tools/scope.py corpus/runs/<id> --world 4`.

### 2. B1 — plasticity *(deferred, deliberately)*

S2: the genome encodes a local update rule rather than weights
*(→ [10-roadmap.md § B1](10-roadmap.md#b1--plasticity))*. Still the interesting rung, and still
worth building — but it refines a policy toward a reward, and B0.2's finding is that this world's
rewards are already fully described by the local patch. Build it after B2, or after P10 drift makes
within-life adaptation worth something. [D-035](DECISIONS.md#d-035)'s multi-generation scoring
window is a B1 question and is untouched by B0's outer loop *(→ [D-071](DECISIONS.md#d-071))*.

---

## Open threads

**The most interesting one, from A1.** Agents evolved to calibrate reliance on local information to
that information's reliability — exploration temperature tracks patchiness at r = +0.937 while
gradient sensitivity holds steady. That is the S0 shadow of *belief calibrated to evidence quality*,
which is the machinery the Chronicle Gap (D2) runs on. Worth a dedicated experiment before Phase D
assumes it.

**Run length — closed.** A1's negative dose-response is *not* an artifact of stopping at 15,000
ticks: the correlation holds between −0.87 and −0.93 across a fourfold window range, negative in
20 of 20 seed–window combinations. The *magnitude* is length-dependent, so A1's +0.268 is a lower
bound. See [a1-run-length](../experiments/a1-run-length/result.md) — answered by re-scoring
committed runs at four windows, at zero simulation cost.

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

### The Historian's environment, which cost an afternoon

- **The Gemini free tier is 20 requests per DAY per model.** Not per minute. Measured by exhausting
  three of them: `gemini-3.7-flash`, `gemini-3.6-flash` and `gemini-3.5-flash` all report
  `limit: 20`. A 41-brief narration needs several keys, several models, or several days.
- **Quota is enforced per Google Cloud *project*, not per key.** Several keys from one project
  rotate through several names against one 20-request budget. `GEMINI_API_KEY_2` … `_8` in `.env`
  are read automatically and only help if each comes from a different project.
- **`uv sync --group historian` silently drops the analysis extras**, and the next `duckdb` import
  fails. It is `uv sync --all-extras --group historian`.
- **`google-genai` must be >= 2.0.** A 1.x install passes every test — the gate replays fixtures and
  never calls the API — and then fails on the first live call with *"the legacy Interactions API
  schema is no longer supported"*.
- **The narrative cache is keyed on the brief, not the model.** That is deliberate: it is what lets
  a run continue tomorrow, or on another model, without re-billing the eras already written.
  `--refresh` re-asks anyway.
