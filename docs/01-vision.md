# 01 — Vision

## Thesis

**Artificial Civilization is a comparative history laboratory.**

It is not a world you watch. It is a machine that produces thousands of divergent histories
from controlled initial conditions, plus the tooling to ask causal questions of them.

> The simulation is the instrument. The histories are the data. The science is comparative.

---

## Why the framing decides everything

Almost every artificial-society project fails identically: it produces one beautiful world,
someone watches it, says "wow, emergent," and nothing is learned — because a single trajectory
has no counterfactual. You cannot tell whether what you saw was caused by anything.

Reframing the output from *a world* to *a corpus of worlds* changes every downstream
engineering decision:

| If the product is a world | If the product is a corpus |
|---|---|
| optimize for fidelity | optimize for worlds-per-dollar |
| rich per-agent detail | vectorized state, batched worlds |
| live inspection UI | append-only log, offline analysis |
| "look what happened!" | "here is the effect size, N=64 seeds" |
| LLM agents (they seem smart) | numeric agents (they can't cheat) |
| objects and pointers | columns and batch dimensions |

Every invariant in [05-architecture.md](05-architecture.md) exists to keep the right-hand
column true.

---

## The three inversions

### 1. Simulate to compare, not to watch

One world is an anecdote. The unit of scientific work is a **sweep**: N worlds, one variable
changed, an effect size at the end. This makes cost-per-world-year a first-class engineering
metric — a regression in it is a bug, not an inconvenience. *(→ [11-engineering.md](11-engineering.md#performance-budget))*

### 2. The log is the artifact

Every run emits an append-only event stream. Analysis happens offline against that log, never
by reading live state. This is a discipline rather than a convenience: it forces us to decide
what we are measuring *before* building the mechanism that produces it. *(→ [06-data-model.md](06-data-model.md))*

### 3. No English inside the core

The simulation speaks numbers. LLMs live strictly at the boundary — the **Historian** (writes
narrative from logs) and the **Analyst** (forms hypotheses across the corpus).

> If agents are LLMs and they invent democracy, **that is not emergence — it is recall.** The
> model read about democracy. You have measured your prompt, not your world.

An LLM policy is permitted later only as an *experimental condition A/B'd against a numeric
baseline*, never as the default substrate. See [D-003](DECISIONS.md#d-003).

---

## What this project is not

Naming these explicitly, because each is a plausible-sounding drift that would destroy the
thesis:

- **Not a game.** No player, no win condition, no balance work. The Atlas
  *(→ [09-visualization.md](09-visualization.md))* makes runs watchable; it does not make them playable-first.
- **Not a historical reconstruction.** We are not modelling Rome. We are building conditions
  under which Rome-shaped things may or may not appear, and measuring which. The goal is not to
  reproduce humanity — human history is one reference point, not the boundary of the search
  space. Forms of cognition, cooperation, and knowledge organization that humans never developed
  are the more interesting outcome.
- **Not an LLM agent society.** See inversion 3. That project is well-explored and its results
  are uninterpretable for our questions.
- **Not a fidelity exercise.** More realistic ≠ more informative. Every mechanism must pay for
  itself in questions it lets us answer.
- **Not a single simulation.** If a feature only makes sense when watching one run, it is
  probably the wrong feature.

---

## Scope

**In scope:** the 12 primitives at depth levels L0–L2 — eleven describing the world, one the
agent's interior
*(→ [02-primitives.md](02-primitives.md))*, intelligence stages S0–S6
*(→ [04-intelligence.md](04-intelligence.md))*, the detector suite, the fork-based experiment
protocol, the Atlas viewer.

**A note on ambition.** The primitives are deliberately rich — resources with extraction curves
and substitutes, information with provenance and partial knowledge, technology that rewrites the
parameters of every other primitive. That richness is the point: the real world is not binary,
and primitives that are will only ever produce toy phenomena. But it enters under three
constraints — through **generators** rather than config surface, as **modulators** rather than
special cases, and **gated** by what agents can actually use. Complexity in the primitives is
the goal; complexity in the phenomena is the failure.

**Explicitly out of scope, for now:** 3D rendering, real-time multiplayer, natural-language
agent dialogue, biologically detailed physiology, continuous-space physics, anything requiring
a cluster to run a single world.

---

## What success looks like

Ordered by ambition. Each tier is a real outcome; the project is worth doing even if it stops
at tier 2.

**Tier 1 — the instrument works.** Deterministic, forkable, batched simulation with a
queryable corpus and detectors that reproduce known artificial-life results (population
cycles, migration, evolved foraging, specialization) against null baselines. This validates
the machine. It is not a new finding.

**Tier 2 — measured emergence.** Signals that pass the concept-vs-location test.
Cooperation stable under reputation. Trade networks with structure beyond random exchange.
Knowledge that diffuses and is re-lost. Known to be achievable; our contribution is the
measurement discipline.

**Tier 3 — the actual bets.** Two of them, structurally identical. The **Chronicle Gap**:
institutions outliving their causes, belief diverging from truth on a plotted curve, and whether
high-fidelity record-keeping makes a society adaptive or rigid. And the **Value Gap**: what
agents pursue coming apart from what actually produces offspring — conviction as measurable
proxy drift, which is the inner/outer alignment problem in an evolved population. Both are
available to us for the same reason: we hold ground truth on one side of a divergence the agents
cannot see.

**Tier 4 — the closed loop.** The Analyst proposes a hypothesis, Forge runs it as matched
counterfactual forks, and the hypothesis survives. An AI scientist with a laboratory that can
say no. *(→ [08-experiments.md](08-experiments.md#the-analyst-loop))*

**Tier 5 — the stagnation programme.** Where does intelligence plateau, and what moves it? This
tier is unusual in that **every outcome is a result.** Open-ended evolution is unsolved — four
decades of artificial life, and every system plateaus — so we expect to plateau too. Measuring
*where* and *why*, on a substrate where a negative result can actually be trusted, is a
contribution the field does not currently have.
*(→ [03-mechanisms.md](03-mechanisms.md#i-the-stagnation-problem--and-why-we-study-it-rather-than-solve-it))*

Running alongside tiers 2–3 is the depth bet: whether **cascades**
*(→ [03-mechanisms.md](03-mechanisms.md#f-the-cascade--how-revolutions-happen-without-a-revolution))*
occur at all, and what conditions produce one rather than a fizzle or a runaway. If the corpus
can answer *"what makes an industrial revolution happen?"* with an effect size, that is a tier-3
result by a different route — and unlike the Chronicle Gap, we would not be the first to ask,
only the first able to intervene.

---

## The one rule

> **No new mechanism without a detector.**

If you cannot write down the number that would prove trade is happening, and the null it must
beat, you are not ready to build trade. You are ready to think about it for another day.

This is the rule that keeps an ambitious project from becoming a beautiful thing that proves
nothing.
