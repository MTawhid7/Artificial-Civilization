# 10 — Roadmap

Scoped to the machine in [00-feasibility.md](00-feasibility.md): an 8 GB M1 Air, hobby pace,
roughly 5–10 hours a week.

## Two principles

**1. Every stage ends in something you would show someone.** Scientific rigor and enjoyment are
not in tension here, but they *are* in tension with ordering. A roadmap that puts all the payoff
at the end is a death march for a project nobody is paid to finish.

**2. The gating rule still holds.** A stage ships **a detector and a null model**, not a feature.
"Communication works" is never the criterion; "compositionality above its null across seeds" is.

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

**Ship criteria** — **not met.** See [a1-patchiness](../experiments/a1-patchiness/result.md) and
[a1-hunger-coupling](../experiments/a1-hunger-coupling/result.md).
- [x] population bounded oscillation, no extinction or explosion — holds for patchiness ≥ 0.8;
      below that the config saturates against the array capacity and needs recalibrating
- [ ] trait means drift measurably and **track the resource distribution** — not yet analyzed
- [ ] ~~`directed_foraging` beats its shuffled null~~ — **the detector was withdrawn**
      *(→ [D-056](DECISIONS.md#d-056))*. It beat its null in 39 runs, in the wrong direction, and
      was still measuring the wrong thing. Replacement: `gradient_ascent`.

**Time:** ~1 week. **Payoff:** the first real one. Sweep patchiness, get a dose-response curve,
and you have proven the entire pipeline — sim → log → sweep → detector → null → plot — at the
cheapest possible moment.

What that pipeline actually produced, first time out, was **two negative results and two
methodological corrections** — that z must never be plotted alone when population varies across a
sweep *(→ [D-054](DECISIONS.md#d-054))*, and that a detector must never condition on a variable its
behavior influences *(→ [D-056](DECISIONS.md#d-056))*. Both were caught in under an hour of compute
by the null models and the seed scatter.

That is the stage doing its job. A detector that produces a clean, confident, wrongly-signed
dose-response is exactly the failure this project exists to catch, and catching it in week two
rather than month eight is the whole argument for ordering A1 this early.

> Do not skip ahead from here. Every later stage is a variation on machinery you now trust.

## A2 — First picture

**Build:** the digest builder, the fingerprint strip, and the wall
*(→ [09-visualization.md](09-visualization.md))*. Static, no scrubber yet.

**Time:** ~4 days. **Payoff:** high, for the effort. A hundred histories from identical starting
conditions stacked as colored strips is the entire thesis of the project in one image, and it
needs no explanation to anyone you show it to.

## A3 — First story

**Build:** the Historian — an LLM reading the Chronicle and writing narrative history per era.

**Time:** ~3 days. **Payoff:** disproportionate. Even a world containing only food and movement
produces *"the eastern settlements grew until the drought of year 340, after which most moved
west"* — and it is genuinely delightful to read history from a world you built.

This is scheduled at month one rather than month seven **specifically because it is fun**, it is
cheap, and it costs API money rather than compute. Historian output remains never-evidence.

## A4 — Live viewer *(optional)*

A throwaway pygame or matplotlib window showing dots moving, under
[D-048](DECISIONS.md#d-048). Not in the measurement path. Build it if watching would keep you
going; skip it if not.

---

# Phase B — Minds

*Months 2–3. Goal: agents that learn, and the first genuinely surprising result.*

## B0 — Neural policy

**Build:** S1. One shared network per lineage, per-agent genome embedding, evolved weights. P2
fog at L0 — local view, binary known map.

**Ship:** evolved policies beat the reactive genome on survival; `exploration_rate` above null.
**Time:** ~2 weeks. This is where the ms/tick budget gets tested for real.

## B1 — Plasticity

**Build:** S2 — genome encodes a local update rule rather than weights. Lineage-scored selection
over a multi-generation window *(→ [D-035](DECISIONS.md#d-035))* — cheap now, painful later.

**Ship:** within-life adaptation measurable; plasticity coefficients under selection.
**Time:** ~2 weeks.

## B2 — First word ★

**Build:** a signal channel. Sweep **both** channel capacity and transmission bottleneck
*(→ [D-039](DECISIONS.md#d-039))*.

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
S3 recurrent state and episodic buffer; P3ᴸ¹ identity. Ship: `reputation_effect` beats the
memoryless null. ~2 weeks.

## C1 — Cooperation
Ship: `cooperation_rate` and `reciprocity` beat memoryless. ~2 weeks.
**Payoff:** cooperation appearing without any reward for cooperating — the cleanest demonstration
that D-007 works.

## C2 — Economy
S4 forward model; P5ᴸ¹ claims with two rights. Ship: `specialization` beats random-role,
`trade_network` beats shuffled. ~4 weeks.
**Payoff:** watching a trade network form in the Atlas.

## C3 — Atlas map view
The scrubber, territory rendering, flows. ~1 week. Now you can watch eight thousand years in a
minute.

---

# Phase D — Culture

*Months 7–10. Goal: the project's distinctive bet.*

## D0 — Contagion
P9ᴸ¹⁻ᴸ², S6 social learning with evolved transmission bias
*(→ [D-045](DECISIONS.md#d-045))*. Ship: trait transmission traceable across generations;
genes/culture/ecology decomposable. ~3 weeks.

## D1 — Values
P12ᴸ¹ — the value vector as evolved proxy reward. Ship: `value_conflict` computable;
`bias_composition` under selection. ~3 weeks.
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
