# 10 — Roadmap

Scoped to the machine in [00-feasibility.md](00-feasibility.md): an 8 GB M1 Air, hobby pace,
roughly 5–10 hours a week.

## Two principles

**1. Every stage ends in something you would show someone.** Scientific rigor and enjoyment are
not in tension here, but they *are* in tension with ordering. A roadmap that puts all the payoff
at the end is a death march for a project nobody is paid to finish.

**2. The gating rule still holds, and Phase A made it stricter.** A stage ships **a detector, a
null model, a declared replication unit, and — for any causal claim — a control**, not a feature.
"Communication works" is never the criterion; "compositionality above its null across seeds" is.

The addition is not bureaucracy. `directed_foraging` shipped a null, beat it in 39 runs, and was
measuring a consequence of the behavior it claimed to measure. A null answers *is this chance?*; it
does not answer *am I measuring the right thing?* *(→ [D-064](DECISIONS.md#d-064),
[07-detectors.md](07-detectors.md#detector-contract))*

**Every stage below now carries criteria.** Eight did not until A2 was built and the omission became
visible — including all four C stages, where "it looks like cooperation" is exactly the substitution
this rule exists to prevent.

---

## The shape of it, honestly

| Phase | Calendar | What you get |
|---|---|---|
| **A — Foundations** | weeks 1–5 | evolution visibly working; pictures; an AI-written history of your world |
| **B — Minds** | months 2–3 | learning agents, and **the first emergent word** |
| **C — Society** | months 4–6 | reputation, cooperation, trade, specialization |
| **D — Culture** | months 7–10 | ideas spreading; values; **the Chronicle Gap** |
| **E — Technology** | months 11–16 | recipes, ladders, the cascade |
| **F — Someday** | year 2+ | institutions, substances, records, model criticism |

Phases A–D are the project. E is a stretch. F is a destination that shapes the data model and may
never be built — and that is a fine outcome.

---

# Phase A — Foundations

*Weeks 1–5. Goal: a trustworthy pipeline and three things worth showing.*

## A0 — Skeleton

**Build:** grid world, agents as structure-of-arrays, energy/age/position, death, birth with
mutation, food with regrowth. Chronicle as Parquet with tiered logging. Seeded RNG split by
purpose.

**Also build, first:** the benchmark from [00-feasibility.md](00-feasibility.md). Measure real
ms/tick at three scales and write the numbers into that doc, replacing the estimates. Every later
scale decision depends on them.

**Ship criteria** — **done**, see [experiments/a0-baseline/result.md](../experiments/a0-baseline/result.md)
- [x] replay from `(config, seed)` is bit-identical, verified in CI
- [x] no-op fork at tick T reproduces the parent exactly *(and with pending effects queued)*
- [x] a 32-world × 50k-tick run completes in under 10 minutes — 9.2 min idle, 10.4 min loaded
- [x] Chronicle for that run is under 50 MB — **9.0 MB per world**; 287 MB for all 32
- [x] cost-per-world-year recorded as a tracked baseline — **4.68 ms**

**Time:** ~1 week. **Payoff:** none. This is the tax.

> The no-op fork test is the one people skip. A fork that doesn't reproduce its parent means
> determinism is already broken, and finding that in week one instead of month eight is worth
> more than anything else in this stage.

Three things A0 changed rather than confirmed, all measured: pure logistic regrowth makes zero an
absorbing state and kills every world *([D-051](DECISIONS.md#d-051))*; Chronicle sampling must key
on the agent, not the agent-tick, or trajectories are unreconstructable
*([D-052](DECISIONS.md#d-052))*; and the ms/tick estimates in
[00-feasibility.md](00-feasibility.md) were about 10× optimistic at S0.

## A1 — First evolution

**Build:** genome of ~8 floats driving a reactive foraging rule. Patchy resource distribution.
`pop_stability` and `directed_foraging` detectors with nulls and unit tests.

**Ship criteria** — **met.** See [a1-gradient-ascent](../experiments/a1-gradient-ascent/result.md),
with its control [a1-heredity-control](../experiments/a1-heredity-control/result.md).
- [x] population bounded oscillation, no extinction or explosion — at patchiness ≥ 0.4, across 80
      world-instances; marginal below, where 2–3 worlds in 16 leave the viable band
- [x] trait means drift measurably and **track the resource distribution** — 7 of 8 genes move off
      their 0.500 founding value; exploration temperature tracks patchiness at r = +0.937 and
      heading persistence at r = −0.848
- [x] a foraging detector beats its null — `gradient_ascent`, 30 runs of 30, 5 seeds of 5, at all
      six patchiness levels *(the originally-specified `directed_foraging` was withdrawn first —
      → [D-056](DECISIONS.md#d-056))*

**Time:** ~1 week. **Payoff:** the first real one. Sweep patchiness, get a dose-response curve,
and you have proven the entire pipeline — sim → log → sweep → detector → null → plot — at the
cheapest possible moment.

**What it actually produced.** The dose-response came out *negative* — gradient-following gets
weaker as resources clump — and the gene means explain why: patchier worlds select for **more
exploration randomness and less commitment to a heading**, while gradient sensitivity holds steady.
Agents did not stop caring about the local gradient; they stopped acting on it deterministically,
because in a mostly-barren world the local gradient is mostly noise.

> Agents evolved to calibrate how much to trust local information to how much that information was
> worth. Nobody wrote that, and it is the S0 shadow of something Phase D depends on.

Getting there cost three withdrawn or corrected claims, all caught by the machinery rather than by
luck: z must not be plotted alone when population varies *(→ [D-054](DECISIONS.md#d-054))*, a
detector must not condition on a variable its behavior influences
*(→ [D-056](DECISIONS.md#d-056))*, and an evolutionary claim needs a no-heredity control
*(→ [D-059](DECISIONS.md#d-059))*. That is the stage doing its job, in week two rather than
month eight.

> Do not skip ahead from here. Every later stage is a variation on machinery you now trust.

## A2 — First picture

**Build:** the digest builder, the fingerprint strip, and the wall
*(→ [09-visualization.md](09-visualization.md))*. Static, no scrubber yet.

**Ship criteria** — this stage originally listed none, which contradicts the gating rule at the top
of this document. A visualization stage ships a detector too, or the rule has an exception in it.
**Met** — see [experiments/a2-wall/result.md](../experiments/a2-wall/result.md).
- [x] the digest builds from a run directory, stays under 5 MB, and building it twice gives the
      same hash — **0.91 MB** for 34 worlds × 2,000 frames *(→ [schemas/digest.md](../schemas/digest.md))*
- [x] `collapse` ships with a null model and two unit tests, and its verdict is recorded **either
      way** — it is **silent**, at z = −1.16, and the negative sign is the result
- [x] the wall renders 102 worlds from identical config, reproducibly, from the digest alone
- [x] the page opens from `file://` with no network access and renders the same wall
- [x] unimplemented digest fields are **declared as reserved, never invented**

**Time:** ~4 days. **Payoff:** high, for the effort. A hundred histories from identical starting
conditions stacked as colored strips is the entire thesis of the project in one image, and it
needs no explanation to anyone you show it to.

**What it actually produced.** The premise held, and this is the first time it was measured rather
than assumed: between-world spread reaches **9.4×** within-world variation by year 2,500, and final
populations span **tenfold** from one configuration. Every effect size A1 reported clusters on
worlds; this is the evidence that worlds are worth clustering on.

`collapse` came out **silent with a negative z** — drawdowns are *rarer* than a volatility-matched
random walk produces, which is the signature of regulation and corroborates `pop_stability` firing
at +17.5 on the same runs. The direction was predicted in the detector before the run, which is the
only reason it counts.

> The wall had to be built twice. At capacity 1,200 four worlds pinned against the array, and a
> pinned world renders as a flat full-height bar — several of them side by side read as
> *convergence* that the array alone produced. A ceiling that is merely a nuisance in a table is a
> false claim in a picture.

## A3 — First story

**Build:** the Historian — an LLM reading the Chronicle and writing narrative history per era.

**Ship criteria** — **done**, see [experiments/a3-historian/result.md](../experiments/a3-historian/result.md).
The one stage with no detector, because its output is *never evidence*
*(→ [12-risks.md](12-risks.md))*. The criteria are therefore about containment, not measurement.
- [x] every claim in generated prose is traceable to an event range or an aggregate row — **enforced,
      not intended**: the model is given a numbered fact table and nothing else, emits sentences with
      fact ids, and [`verify.py`](../src/historian/verify.py) deletes any sentence that fails one of
      five checks *(→ [D-068](DECISIONS.md#d-068))*
- [x] output is stored under `narrative/`, never under `metrics/`, and is visibly labelled generated
      — the banner is in the file, not only in the viewer
- [x] the Historian reads the digest and aggregate tier only — never live state, never a checkpoint;
      CI greps for it and a test runs the builder with `checkpoints/` moved away
- [x] a run with the Historian attached produces a byte-identical Chronicle to one without — it is
      never attached. A test hashes every file in the run directory before and after

Three things the criteria did not ask for and the stage produced anyway: the **acceptance rate**,
which is the only number this stage measures about itself; the **rejection log**, shipped beside the
prose because a narrative that hid its failures would report perfect grounding by construction; and
the **Chronicle panel** in the Atlas *(→ [09-visualization.md](09-visualization.md))*, which came
almost free once the prose existed.

**Time:** ~3 days. **Payoff:** disproportionate. Even a world containing only food and movement
produces *"the eastern settlements grew until the drought of year 340, after which most moved
west"* — and it is genuinely delightful to read history from a world you built.

This is scheduled at month one rather than month seven **specifically because it is fun**, it is
cheap, and it costs API money rather than compute. Historian output remains never-evidence.

## A4 — The viewer *(optional, tiered)*

**Build:** a viewer that is never attached. [D-048](DECISIONS.md#d-048) permits reading sampled live
state on runs flagged non-scientific; this stage declines the permission and `meta.json` keeps
`live_viewer: false` *(→ [D-070](DECISIONS.md#d-070))*. Determinism makes streaming unnecessary — a
checkpoint is a keyframe, [`nearest_before`](../src/chronicle/checkpoint.py) is a seek, and an
intervention is a fork rather than a mutation.

**It is not only a treat.** *"The agents are circling in a corner"* is invisible in
`aggregate.parquet` and obvious in four seconds of motion. B0 is the first stage where a policy can
be **wrong** rather than merely unlucky, and the aggregate tier cannot separate those — population
falls either way. That is the argument for building tier 1 *before* B0 rather than after it.

**What it must never become** is [D-001](DECISIONS.md#d-001)'s rejected alternative: *one
high-fidelity world with rich per-agent detail and a live inspection UI — the default shape of this
genre, and the reason the genre produces demos instead of findings.* Hence tiers that each ship on
their own, and a hard rule that no tier draws a claim the Lens has not earned.

| Tier | What | Cost | Build when |
|---|---|---|---|
| **1 — the scope** | matplotlib over the 21 checkpoints of one world: dots, the harvest field, a population trace | ~2 h | now, as a B0 instrument |
| **2 — the Era Theatre** | one self-contained HTML page — an era in motion beside the Historian's paragraph for it, every sentence clickable back into the frames it cites | ~3 d | after B0, or when the wall stops being enough |
| **3 — the Divergence Chamber** | two forks of one checkpoint played side by side; interventions declared in config, never painted into a running world | ~1 wk | not before Phase C needs the manipulation arm |

### Tier 1 — the scope

Everything it draws is already on disk. A checkpoint carries `x`, `y`, `energy`, `heading`,
`genome[8]`, `parent`, and **both** the `resource` and `capacity` fields — so `resource / capacity`
is a harvest-pressure map that no picture in this project has yet shown. At `checkpoint_every: 1500`
that is 21 frames, one per 125 simulated years: a slideshow rather than a film, and enough to see a
population pinned in a corner or a founding cohort failing to spread.

**Ship — done.** [`tools/scope.py`](../tools/scope.py): a window with a slider over the keyframes
(`space` plays, `←/→` steps), or `-o sheet.png` for the whole history on one page. 21 checkpoints
read in 1.7 s; the run directory hashes identical before and after. No test — this tier is allowed
to be throwaway, and saying so is what stops it growing.

Two things it showed on its first run, which is the argument for having built it. Movement is
four-directional, so **depletion is axis-aligned** — the harvest field is streaked with horizontal
and vertical bands that no scalar series can carry. And world 0 holds near **0.16 of capacity** for
thousands of years with a flat population, while world 3 keeps visible resource blobs and grows to
652. Neither is a finding — one world is N=1 *(→ [D-058](DECISIONS.md#d-058))* — but both are
questions a detector could be aimed at, which is the whole job of a scope.

### Tier 2 — the Era Theatre

The unit is the **era**, because [D-069](DECISIONS.md#d-069) already fixed one: 3,000 ticks, 250
years, the same window the Historian narrated and the wall rendered. Play those frames with that
era's prose beside them and every citation live — click *"Population fell from 812 to 389"* and the
scrubber bounds the exact ticks the fact was computed from.

This is the loop nothing else closes. The wall argues **that** worlds diverge; the Historian says
**what happened**; the theatre lets you **watch it**, with the citation chain intact through all
three. It also does something for A3 that A3 could not do for itself — grounding checkable only in a
JSON file is grounding nobody checks, and a citation you can click and watch is falsifiable by eye.

Frames come from a short **cinema run**: one world, `checkpoint_every` in the tens rather than the
thousands. A corpus run's 1500-tick cadence is far too coarse for motion, and re-running one world
for 250 years costs seconds at `0.425 µs` per agent-tick. Nothing about it is compromised —
`live_viewer` stays false and it is a pure function of `(config, seed)` like any other — but it is
**one world, which is N=1** *(→ [D-058](DECISIONS.md#d-058))*, so it stays out of the corpus index
for the same reason no single world is ever an argument. One era at a few hundred agents inlines in
a few hundred KB: the wall's budget and the wall's method
*(→ [D-062](DECISIONS.md#d-062), [09-visualization.md](09-visualization.md))*.

**Ship:**
- [ ] renders from `file://` with the network off — one HTML file, no build step, theme-aware
- [ ] the run directory is byte-identical before and after; the theatre reads, like the Historian
- [ ] every sentence shown carries its citation, and the generated-content label is permanent
- [ ] the cinema run stays out of the corpus index — one world is not a replication unit

### Tier 3 — the Divergence Chamber

Load one checkpoint, run two copies, perturb one agent by one cell, play them side by side. You
watch two identical maps stay identical, and then you watch the frame where they stop. That is the
wall's thesis in motion, and [`checkpoint.py`](../src/chronicle/checkpoint.py) already carries it:
*rewind to tick T, change one thing, re-run* is invariant I3, and `test_noop_fork` already guards it.

The interactive version — paint food, trigger a drought — is the one idea in this stage that can
cost an invariant, and it is worth being exact about why. Mutating live state from a UI ends
determinism, ends *(config, seed)*, and produces a history that can never be reproduced or explained
afterwards. The version that costs nothing is that **a click writes an intervention into a config and
forks from the nearest checkpoint**. The drought becomes reproducible by construction — and it stops
being a toy, because a config-declared intervention over a fork is exactly the manipulation arm
[D-064](DECISIONS.md#d-064) demands of a causal claim.

That is also why it is scheduled last. Designing a control arm before knowing what claim it controls
for is how you end up with an API that fits no experiment.

### What no tier may draw

A picture asserts as loudly as a sentence, and A3's verifier already deleted prose for one of the
words below. The viewer inherits the discipline rather than being trusted with it.

- **No phenomenon names** *(→ [D-002](DECISIONS.md#d-002))*. Colour by founder lineage if you like —
  `parent` is in every checkpoint — but it is a *lineage*, not a tribe, and where one clusters is not
  a territory. `territory` is the exact word the Historian's gate rejected.
- **No label the world does not contain.** There are no predators, so the population trace is
  carrying-capacity overshoot and not a predator–prey wave. Naming it the second thing is
  [12-risks.md](12-risks.md)'s beautiful nonsense drawn as a chart instead of written as a sentence.
- **No borrowed rungs.** There is no brain to inspect at S0 and no known-map to fog; those are B0 and
  P2ᴸ⁰. The genome is eight named reactive traits, and the viewer should name them the way
  [`facts.py`](../src/historian/facts.py) does — *"moves less"*, not *"gene 6"*.
- **A mark is not a finding**, in motion as on the strip *(→ [D-063](DECISIONS.md#d-063))*.
  `collapse` came out silent on this corpus: a drawdown may be drawn and may not be captioned
  significant.

---

# Phase B — Minds

*Months 2–3. Goal: agents that learn, and the first genuinely surprising result.*

## B0 — Neural policy

**Build:** S1. One shared network per lineage, per-agent genome embedding, evolved weights. P2
fog at L0 — local view, binary known map.

**The budget is already measured** *(→ [00-feasibility.md](00-feasibility.md#s1-measured-before-b0),
`uv run python -m bench.bench_policy`)*. This stage was flagged as "where the ms/tick budget gets
tested for real"; it was tested first instead, and the answer is reassuring:

- at the documented `hidden: 48`, S1 costs **3.2× the S0 `decide` phase and 1.16× the tick**
- **the gather still dominates** — 3.6 ms observe against 2.60 ms policy. The bottleneck flips
  somewhere between hidden 64 and 128, so hidden width is the first knob to sweep for capacity and
  the first to cut for speed
- `view_radius` remains the expensive lever and gets worse, not better: r=4 costs 11.66 ms of
  gather against 2.88 ms of policy
- lineages cost ~1.6× on `decide` at two and ~2.2× at sixteen — a swept variable, not a free one

Sizes are therefore chosen up front rather than discovered: **hidden 48, view_radius 2, one to a
few lineages** stays inside a 13 ms tick, which is ~12 min per 30k-tick run with throttling.

**Ship:** evolved policies beat the reactive genome on survival; `exploration_rate` above null.
**Time:** ~2 weeks. This is where the ms/tick budget gets tested for real.

> S1 puts `tanh`/`exp` on every agent every tick, and those are exactly the functions whose last
> ulp differs across instruction sets. [D-057](DECISIONS.md#d-057) already settled this — the
> guarantee is per-platform and the goldens are per-platform. Do not re-litigate it when the
> cross-machine test goes red; add the platform's golden and move on.

## B1 — Plasticity

**Build:** S2 — genome encodes a local update rule rather than weights. Lineage-scored selection
over a multi-generation window *(→ [D-035](DECISIONS.md#d-035))* — cheap now, painful later.

**Ship:** within-life adaptation measurable; plasticity coefficients under selection.
**Time:** ~2 weeks.

## B2 — First word ★

**Build:** a signal channel. Sweep **both** channel capacity and transmission bottleneck
*(→ [D-039](DECISIONS.md#d-039))*.

**Decide the `SIGNAL` payload before B0, not at B2.** The event must carry the **choice set** —
which signals were available and which referents were present — not only which signal was emitted
*(→ [D-066](DECISIONS.md#d-066))*. Compositionality metrics are unusually easy to compute on
something downstream of the intended target, which is precisely the defect that withdrew
`directed_foraging`, and a permutation null does not catch it. Logging the choice set is what lets
this stage's null be *derived* rather than shuffled. Enum values are permanent: one decision now,
or a re-run of the whole corpus later.

**Ship criteria**
- [ ] `compositionality` above chance against the mute null
- [ ] **`referential_validity` passes the remap test** — rebuild the world so the referent moves;
      does the signal follow the concept or the location?

**Time:** ~3 weeks. **Payoff: the biggest in the project.** One agent emits `7`, others move
north, and you never defined what `7` means. The remap test is what separates that from a cute
correlation, and passing it is the moment this stops being a toy.

If you only get this far, the project was worth doing.

---

# Phase C — Society

*Months 4–6. Goal: agents that remember each other.*

## C0 — Memory and reputation
S3 recurrent state and episodic buffer; P3ᴸ¹ identity. ~2 weeks.

**Ship criteria**
- [ ] `reputation_effect` beats the memoryless null across ≥3 seeds, clustered on world
- [ ] the memory-ablated **control** shows the effect collapse — a null alone cannot separate
      "agents remember" from "agents met more often" *(→ [D-064](DECISIONS.md#d-064))*
- [ ] the detector conditions on identity, never on accumulated wealth or energy
      *(→ [D-056](DECISIONS.md#d-056))*

## C1 — Cooperation
~2 weeks.

**Ship criteria**
- [ ] `cooperation_rate` and `reciprocity` beat the memoryless null across ≥3 seeds
- [ ] a **no-memory control arm**, compared on raw effect and never on z
      *(→ [D-060](DECISIONS.md#d-060))*
- [ ] cooperation is not an artifact of co-location: the null preserves encounter rates and
      destroys only who-with-whom
**Payoff:** cooperation appearing without any reward for cooperating — the cleanest demonstration
that D-007 works.

## C2 — Economy
S4 forward model; P5ᴸ¹ claims with two rights. ~4 weeks.

**Ship criteria**
- [ ] `specialization` beats a random-role null across ≥3 seeds
- [ ] `trade_network` beats a shuffled-partner null that preserves each agent's trade *volume*
- [ ] both cluster on world, not on agent or transaction *(→ [D-058](DECISIONS.md#d-058))*
- [ ] transfers are logged with the choice set — what else the agent could have traded, and to
      whom *(→ [D-066](DECISIONS.md#d-066))*
**Payoff:** watching a trade network form in the Atlas.

## C3 — Atlas map view
The scrubber, territory rendering, flows. ~1 week. Now you can watch eight thousand years in a
minute.

**Ship criteria** — a visualization stage still ships criteria; A2 shipped a detector too.
- [ ] `territory` and `flows` move out of the digest's `reserved` list with a `digest_version` bump
- [ ] scales are shared across panels and across worlds; no per-panel normalization
      *(→ [D-063](DECISIONS.md#d-063))*
- [ ] every rendered marker carries its detector's verdict, so the map cannot imply significance
      nobody measured
- [ ] this is where TypeScript and a bundler earn their cost *(→ [D-062](DECISIONS.md#d-062))*

---

# Phase D — Culture

*Months 7–10. Goal: the project's distinctive bet.*

## D0 — Contagion
P9ᴸ¹⁻ᴸ², S6 social learning with evolved transmission bias
*(→ [D-045](DECISIONS.md#d-045))*. ~3 weeks.

**Ship criteria**
- [ ] trait transmission traceable across generations
- [ ] genes / culture / ecology decomposable, each with its own ablation arm
- [ ] the decomposition is reported as raw variance explained, never as three z-scores — the
      ablation that works best will *look* least significant *(→ [D-060](DECISIONS.md#d-060))*

## D1 — Values
P12ᴸ¹ — the value vector as evolved proxy reward. ~3 weeks.

**Ship criteria**
- [ ] `value_conflict` computable from the log alone, with a null
- [ ] `bias_composition` under selection, against a **no-heredity control**
      *(→ [D-059](DECISIONS.md#d-059))*
- [ ] value dimensions are generated, never named — the detector reports cluster structure, not
      labels *(→ [D-029](DECISIONS.md#d-029))*
**Payoff:** the drama scalar. You can now automatically find the most conflicted moments in a
history and have the Historian narrate them.

## D2 — The Chronicle Gap ★
Belief store separate from truth, with decay, provenance, and the first-hand flag. Then **E2**:
poison the river, kill the witnesses, silently un-poison it.

**Ship:** `zombie_institution` fires; `chronicle_gap` plotted over time.
**Time:** ~4 weeks. **Payoff:** the result nobody else has. Also the truth/belief split screen,
which is the best thing the Atlas will ever show.

---

# Phase E — Technology

*Months 11–16. A stretch at hobby pace.*

**E0 — Recipes and ladder density.** P8ᴸ¹, then **E22 before anything else**
*(→ [D-043](DECISIONS.md#d-043))*. If ladder density is wrong, every later technology experiment
measures nothing while appearing to work.

**E1 — Modulators and the cascade.** P8ᴸ², P1ᴸ². Ship: `modulator_cascade` above the no-modulator
null. **Payoff:** an industrial revolution nobody implemented.

**E2 — Latent physics.** Randomized constants, `law_recovery` across ≥60 worlds. Note the corpus
size is down from 200 — see [00-feasibility.md](00-feasibility.md).

---

# Phase F — Someday

Kept as design, not as plan: P4/P6/P7 institutions, P1ᴸ³ substances, P8ᴸ³ artifacts, P2ᴸ³ records,
S7 model criticism, the Analyst loop, the stagnation programme.

These shape the data model correctly and cost nothing to leave documented. If the project is still
alive in year two, they are what it grows into.

---

## If you only have three months

A0 → A1 → A2 → A3 → B0 → B2.

Skeleton, first evolution, the wall, the Historian, neural policies, the first emergent word. That
is a complete, self-contained, genuinely interesting project with a real result and two things
worth showing people. Everything after it is optional.

---

## Standing rules

- **A month with no committed `result.md` means stop adding mechanisms.** The most likely failure
  is not running out of compute, it is building forever and measuring never
  *(→ [12-risks.md](12-risks.md))*.
- **Re-measure the budget every phase.** Cost-per-world-year is a tracked metric; a regression is
  a bug.
- **Cut scope before cutting rigor.** Fewer agents, fewer ticks, fewer seeds — never fewer nulls.
- **Stages are not deadlines.** The calendar above assumes 5–10 hours a week and will be wrong.
  The ordering is what matters.
