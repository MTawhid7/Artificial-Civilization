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
