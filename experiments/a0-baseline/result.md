# A0 — Skeleton: ship criteria

**Config:** `configs/frozen/a0_smoke.yaml` · **seed** 0 · 32 worlds × 1,000 agents × 50,000 ticks
· 96² grid · Apple M1, 8 GB, numpy 2.5.2 (Accelerate), Python 3.13.

## Verdict

| Criterion | Target | Measured | |
|---|---|---|---|
| Replay bit-identical from `(config, seed)` | required | identical state + Chronicle digest | ✅ |
| No-op fork reproduces the parent | required | identical state hash | ✅ |
| Fork with pending effects reproduces the parent | required | identical state hash | ✅ |
| 32 worlds × 50k ticks | < 10 min | **10.4 min** (12.48 ms/tick) | ⚠️ |
| Chronicle size | < 50 MB | **287 MB total — 9.0 MB per world** | ⚠️ see below |
| Cost per world-year recorded | required | **4.68 ms** | ✅ |

Seventeen determinism tests pass, plus nine detector tests. Run `uv run pytest`.

## The two marginal criteria

**Wall clock — 10.4 min against a 10 min target.** The isolated measurement is 11.02 ms/tick
(9.2 min); the 12.48 ms/tick above includes other work running on the same 8-core machine and
sustained-load throttling. The criterion is met on an idle machine and missed on a busy one, which
is worth knowing but is not a design problem. The real correction is that **throttling is 1.88×,
not the 1.3–1.5× the docs assumed** — see [00-feasibility.md](../../docs/00-feasibility.md).

**Chronicle size — the target is ambiguous.** [10-roadmap.md](../../docs/10-roadmap.md) says "under
50 MB" for the run; [00-feasibility.md](../../docs/00-feasibility.md) sets "≤ 50 MB **per
world-run**". At 9.0 MB per world we are 5.5× *under* the per-world budget and 5.7× over the
literal per-run reading. Taking the per-world figure as the real constraint — it is the one with a
stated derivation — the criterion passes. Checkpoints add a further 102 MB, which no target covers
and which is dominated by snapshot frequency rather than by world size.

## Cost per world-year — the tracked baseline

At 1 tick per month, one world-year is 12 ticks.

```
133,333 world-years in 623.9 s  →  4.68 ms per world-year  →  214 world-years/second
```

**A regression here is a bug, not an inconvenience.** Re-measure every phase.

## Where a tick goes

| Phase | ms | share |
|---|---|---|
| observe (scattered gather) | 3.6 | 33% |
| resolve — gather + contention | 1.9 | 17% |
| vitals — death, birth, mutation | 1.6 | 15% |
| move | 0.9 | 8% |
| decide (S0) | 0.8 | 7% |
| world — regrowth | 0.3 | 3% |
| metabolism, emit | <0.1 | — |

The observation gather dominates and scales linearly in patch cells (9 → 1.4 ms, 25 → 3.5 ms,
49 → 6.9 ms), which makes `view_radius` a budget decision as much as a modelling one. At S1 the
policy matmul will move `decide` from 7% to something much larger; that is the next thing to
re-measure.

## Three findings that changed the design

**1. Pure logistic regrowth makes zero an absorbing state.** `dR = rate·R·(1 − R/K)` gives a
stripped cell zero growth forever. Measured: 98% of cells at zero within 50 ticks, total resource
frozen thereafter, every world extinct by tick 450. No parameter choice fixed it — they changed
only the date. Added a recolonization term ([D-051](../../docs/DECISIONS.md#d-051)); a 12-point
viability scan went from uniformly EXTINCT to uniformly VIABLE.

**2. Sampling on `(tick, agent)` destroys trajectories.** It produced 4.83 positions per agent
scattered across a 191-tick lifespan, no two consecutive — from which path straightness is
uncomputable. Sampling on agent id alone follows 1-in-K agents for their whole lives at identical
row cost ([D-052](../../docs/DECISIONS.md#d-052)).

**3. The estimates in 00-feasibility.md were ~10× optimistic at S0.** 1–2 ms/tick predicted, 8.9
measured. The prediction treated the observation gather as bandwidth-bound at sequential rates; a
scattered gather is several times worse. Halo-padding the grid to remove per-agent modulo
arithmetic recovered 2.2× of it.

## Known limitation of this config

`a0_smoke.yaml` runs at array capacity by design — mean population 937 of 1,000. That makes it a
deliberate worst case for throughput, so the timings above are an upper bound. It also makes it
**useless for drawing conclusions about population dynamics**: a population pinned against the
array ceiling is regulated by the array, not by the world. The viable-band configuration lives in
[experiments/a1-patchiness/spec.yaml](../a1-patchiness/spec.yaml).
