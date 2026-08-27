# 00 — Feasibility and Scale

**Read this before anything else.** It is numbered 00 because it constrains every other document.

## The machine

```
Apple M1 · 4 performance cores + 4 efficiency cores · 8 GB unified memory · fanless
```

Fanless matters more than it sounds: sustained all-core load throttles after roughly 10–15
minutes. Budget **1.3–1.5× wall-clock** for anything running longer than that, and prefer
overnight runs on a machine you are not also using.

8 GB matters more still. macOS takes 3–4 GB, so the working budget is **~4 GB**, and the
Chronicle will hit it long before the simulation does.

---

## What this rules out

The docs were written describing a machine we do not have. These are now explicitly out of scope:

| Was planned | Reality | Decision |
|---|---|---|
| 1,000 worlds × 10,000 years overnight on GPU | not on this hardware | corpus target drops to **32–64 worlds per batch** |
| 10,000 agents per world | policy cost scales linearly | **500–2,000 agents** |
| JAX/Metal GPU backend | `jax-metal` is immature; PyTorch MPS helps little for this shape | **NumPy on CPU only** *(→ [D-046](DECISIONS.md#d-046))* |
| Level-of-detail promotion/demotion | only needed above ~10k agents | **cut entirely** — and with it the worst determinism hazard *(D-010)* |
| S7 model criticism, P8ᴸ³ substances, P2ᴸ³ records | years of hobby time away | **someday tier** — kept in the docs as design, not as plan |

Cutting GPU and LOD removes the two hardest engineering risks in the project, and both existed
only to reach a scale that is unreachable anyway. This is a simplification, not a loss.

---

## What the corpus thesis saves us

The constraint pushes toward the design already chosen, which is a fortunate accident.

> **Seeds are the unit of replication, not agents.** A thousand agents in one world is N=1.

Effect sizes come from seed count, not from population size. We need **many small worlds**, which
is exactly what a CPU with a batch axis is good at. Fewer agents per world costs statistical power
only where population size is itself the variable — mainly the cultural-evolution sweeps, where a
100 → 2,000 range still spans a factor of twenty.

---

## Measured budget

**Measured in A0, not estimated.** Machine: Apple M1, 8 GB, numpy 2.5.2 through Accelerate,
Python 3.13. Reproduce with `uv run python -m bench.bench_tick --scales all`; raw output is in
`bench/results/`.

The original estimates were **wrong by roughly an order of magnitude** at S0 — 1–2 ms/tick
predicted against 8.9 measured. The prediction assumed the gather was bandwidth-bound at
sequential rates; it is a scattered gather, which is several times worse, and it dominates
everything else.

### Per-tick cost, batched over worlds

State is `[W, N, …]`; a tick is array ops over the whole batch.

| Configuration | Dominant cost | ms/tick |
|---|---|---|
| **S0** — W=8, N=500, 96² grid | observation gather | **1.2** |
| **S0** — W=32, N=1000, 96² grid *(the default)* | observation gather | **8.9** |
| **S0** — W=64, N=2000, 96² grid | observation gather | **36.0** |
| **S0, full tick loop** — W=32, N=1000, at steady state | gather + policy + births | **11.0** |

The last row is the real simulation rather than the synthetic harness: it includes births, deaths,
mutation, contention resolution, and event emission. Treat **11 ms/tick** as the planning number.

### Where a tick goes, at the default scale

| Phase | ms | Note |
|---|---|---|
| observe | 3.6 | the scattered gather — irreducible memory traffic |
| resolve (gather) | 1.9 | contention sort |
| vitals | 1.6 | per-world birth loop |
| decide | 0.8 | S0 is cheap; S1 will not be |
| move | 0.9 | |
| world | 0.3 | regrowth over the whole grid |
| metabolism, emit | <0.1 | |

**The observation gather is the single largest performance lever**, and it scales linearly in patch
cells: 9 cells → 1.4 ms, 25 → 3.5 ms, 49 → 6.9 ms. `view_radius` is therefore a budget decision,
not only a modelling one. Wrapping the grid in a halo to remove per-agent modulo arithmetic cut
this phase by 2.2×.

### Thermal throttling is worse than assumed

| | ms/tick |
|---|---|
| first 30 s of sustained load | 8.9 |
| after 15 min of sustained load | 16.8 |

**Throttle factor: 1.88×** — not the 1.3–1.5× assumed above. Every long-run projection must carry
it. A run that benchmarks at 9 minutes takes 17.

### What that buys

| Run | S0 measured | S0 with throttling |
|---|---|---|
| 50k ticks × 32 worlds | ~9 min | **~17 min** |
| 100k ticks × 32 worlds | ~18 min | **~35 min** |
| overnight (8 h) | — | ~14 runs at 100k ticks |

**A 32-seed sweep in under half an hour is the target**, and at 50k ticks it is met. At 100k ticks
it is not, so 100k-tick sweeps are overnight work. That is the number that decides whether this
stays fun: if a sweep fits in a coffee break, you iterate. If it takes a day, you stop.

### The constraint moved

<a id="the-constraint-moved"></a>

[D-047](DECISIONS.md#d-047) declared the Chronicle the binding resource: a naive log is ~2 GB per
world against a 50 MB target. **Tiering worked, and worked well enough to invalidate its own
premise.** Measured at A2, on a 3-seed × 34-world × 30,000-tick experiment:

| | Measured | What it means |
|---|---|---|
| Chronicle per run | **25.8 MB** | a rounding error against the disk available |
| Wall-clock per run | **14.5 min** | the real cost of an experiment |
| Cost per agent-tick | **0.425 µs** | scales as `worlds × capacity × ticks` |
| Capacity vs mean population | **2,000 / 525** | **3.8× of the compute went to headroom** |

Two consequences worth planning around.

**Capacity is a compute tax, not a memory one.** The observation gather runs over every slot
whether an agent occupies it or not, so cost is set by `population.capacity` and not by how many
agents are alive. Headroom cannot simply be trimmed either: it is demanded by the single largest
world in the batch while the average world needs a quarter of it. Setting it too low is worse —
a population regulated by the array is not regulated by the world
*(→ [D-065](DECISIONS.md#d-065))*.

**Plan in agent-ticks.** `worlds × capacity × ticks × 0.425 µs` predicted A2 within a few percent
and is the right back-of-envelope for any S0 experiment. It will not survive S1: `decide` is 9% of
an S0 tick and a neural forward pass is the first thing that can make it dominant, which is why
the budget is re-measured *before* B0 rather than during it
*(→ [10-roadmap.md § B0](10-roadmap.md#b0--neural-policy))*.

### S1 measured before B0, not during it

<a id="s1-measured-before-b0"></a>

Synthetic forward pass at the real shapes — 32 worlds × 1,000 agents, D-004's one shared network
per lineage, patch + genome embedding + scalars in, four actions out. Reproduce with
`uv run python -m bench.bench_policy`; raw output in `bench/results/bench_policy_s1.json`.

**B0 is affordable, and by a wider margin than the roadmap's warning implied.**

| hidden | decide ms | tick ms | decide share | vs S0 tick |
|---|---|---|---|---|
| 16 | 1.14 | 11.3 | 10% | 1.03× |
| 32 | 1.79 | 12.0 | 15% | 1.09× |
| **48** *(the documented width)* | **2.60** | **12.8** | **20%** | **1.16×** |
| 64 | 3.25 | 13.4 | 24% | 1.22× |
| 128 | 6.31 | 16.5 | 38% | 1.50× |
| 256 | 13.06 | 23.3 | 56% | 2.12× |

At `hidden: 48` the policy costs **3.2× the S0 `decide` phase and 16% more per tick overall**.
Three consequences, all of which set B0's shape rather than being discovered inside it:

**The bottleneck does not flip.** `observe` is 3.6 ms and `decide` is 2.60 ms at the documented
width, so the gather stays dominant. It flips somewhere between hidden 64 and 128 — which makes
**hidden width the first thing to sweep** if B0 needs more capacity, and the first thing to cut if
it needs more speed.

**View radius is still the expensive knob, and it is expensive on the other side.** Going to
`view_radius: 4` costs 11.66 ms of gather against 2.88 ms of policy: a wider view is roughly *four
times* the price of a wider hidden layer, for the same tick budget. This was already true at S0 and
S1 does not change it.

**Lineages cost about what a second network costs, then flatten.**

| lineages | 1 | 2 | 4 | 8 | 16 | 32 |
|---|---|---|---|---|---|---|
| decide ms | 2.54 | 3.97 | 4.47 | 5.33 | 5.51 | 6.06 |

Most of the penalty is the 1 → 2 step: one lineage is a single fused matmul, and any number above
one pays grouping plus smaller matmuls. Beyond that it grows slowly. So lineage count is a
**swept variable and not a free one** — budget ~2× on `decide` the moment it exceeds one, and note
that going from 8 lineages to 32 costs less than going from 1 to 2.

> A caveat on all of the above: this is a forward pass, not a stage. It excludes the evolution
> outer loop, the per-lineage weight updates at generation boundaries, and whatever B0's selection
> bookkeeping turns out to cost. It bounds the part that runs every tick for every agent, which is
> the part that was in doubt.

<a id="s1-measured-again-after-b0"></a>

### What the real tick actually cost, and where the projection missed

The caveat above was right to exist and understated the size of the gap. Measured on the **real**
loop once B0 built it — `uv run python -m bench.bench_tick --real S0,S1`, 32 worlds × 1,000, hidden
48, against a 12.33 ms S0 baseline on the same machine and the same day:

| lineages | groups per tick | ms/tick | vs S0 | min per 30k, throttled |
|---|---|---|---|---|
| 1 | 32 | 15.91 | 1.29× | 15.0 |
| 2 | 64 | 16.87 | 1.37× | 15.9 |
| 4 | 128 | 17.85 | 1.45× | 16.8 |
| **8** *(the default)* | 256 | **19.35** | **1.57×** | **18.2** |
| 16 | 512 | 21.37 | 1.73× | 20.1 |

**The projection said 1.16× and the answer is 1.57×, and the reason is a modelling error worth
naming.** `bench_policy` grouped agents by *lineage*: L groups of `W·N/L` rows each. The real
policy groups by **(world, lineage)**, because weights differ on both axes — worlds are independent
replicates and sharing a network across them would couple the very thing the corpus varies. So
there are `W × L = 256` groups of ~125 rows, not 8 groups of 4,000, and a matmul on 125 rows is
overhead-dominated. The synthetic benchmark under-modelled the group count by a factor of `W`.

Two consequences:

- **The lineage curve is much flatter than projected.** 1 → 8 lineages costs 22% of a tick, not the
  ~2× `bench_policy` implied, because per-world grouping already fragments the batch at L=1. Eight
  independent policies per world are cheap, and they are what gives selection something to act on
  from tick zero *(→ [D-071](DECISIONS.md#d-071))*.
- **The floor moved, not the ceiling.** Even L=1 costs 1.29×, so the *unavoidable* part of S1 is
  larger than projected while the *optional* part is smaller. A profile puts `build_inputs` at
  0.50 ms and the stable argsort at 0.83 ms — neither is the problem, and the counting-sort
  optimization B0 was planning is not worth writing. The matmuls are the cost, and their shape is
  set by the replicate axis.

The general lesson is the one this document keeps relearning: a synthetic benchmark measures the
model you built of the thing, and the model omits whatever you had not yet decided. Group count was
not a knob when `bench_policy` was written, because per-world weights were not yet a decision.

### Time scale

Pick tick duration so a lifetime is 200–400 ticks — long enough for a life to have structure,
short enough that 100k ticks covers deep history.

```
1 tick ≈ 1 month  ·  lifespan ≈ 400 ticks (33 yrs)  ·  100k ticks ≈ 8,000 years
```

### Memory

| Item | At W=32, N=1000, 96² | Note |
|---|---|---|
| agent state (~200 floats) | ~26 MB | fine |
| resource/climate grids | ~10 MB | fine |
| `known_mask` bool[W,N,H,W] | **295 MB** | **pack to bits (37 MB) or coarsen to a 24² region map** |
| Chronicle in flight | **the binding constraint** | see below |

---

## The Chronicle is the real bottleneck

At 1,000 agents emitting a few events each per tick over 100k ticks, a naive log is
**10⁸ events ≈ 2 GB per world**. Multiply by 32 and it is hopeless.

**Tiered logging** is not an optimization, it is a requirement *(→ [D-047](DECISIONS.md#d-047))*:

| Tier | What | Rate |
|---|---|---|
| **Always** | births, deaths, discoveries, pledges, detector-relevant rare events | every occurrence |
| **Sampled** | movement, gathering, routine transfers | 1-in-K, K in config |
| **Aggregated** | per-region totals per M ticks — stocks, flows, population | binned, never per-agent |
| **Snapshot** | full state | every C ticks (checkpoints) |

Target: **≤ 50 MB per world-run.** Detectors must be writable against sampled and aggregated data;
if one needs every movement event, it needs redesigning.

---

## The recommended default

```yaml
worlds_per_batch: 32        # the batch axis; 64 if memory allows
agents_per_world: 1000      # 500 while iterating, 2000 for population sweeps
grid: [96, 96]
ticks: 100_000              # ≈ 8,000 years at 1 tick/month
checkpoint_every: 2000
log_tier: sampled
```

Everything above is a starting point to be measured and revised, not a commitment.

---

## What is still reachable

The good news, and the reason to keep going. All of these fit on this machine:

- evolved foraging, migration, population dynamics
- **emergent signalling that passes the concept-vs-location test** — the first real "whoa"
- reputation, reciprocity, stable cooperation
- specialization and trade networks
- cultural transmission, and knowledge that spreads and is re-lost
- **the Chronicle Gap** — the project's distinctive bet
- 30–60-seed sweeps with real effect sizes on all of the above

That is a genuine research programme and most of a year of enjoyable work.

## What is not

Deep technology ladders, paradigm shifts, substance chemistry, 1,000-world corpora, and anything
needing 10⁴ agents. Keep the designs — they cost nothing to leave in the docs and they shape the
data model correctly — but treat them as a destination rather than a plan.

---

## One concession to fun

[D-013](DECISIONS.md#d-013) says the Atlas reads a digest, never live state. For a hobby project
that rule removes something genuinely enjoyable — watching it run.

**Permitted:** a throwaway live viewer as a development tool, reading sampled state at low
frequency, on a run flagged as non-scientific. It must never be in the measurement path and its
output is never evidence. *(→ [D-048](DECISIONS.md#d-048))*

The science still runs on digests. The joy runs on watching dots move.
