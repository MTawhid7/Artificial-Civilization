# 11 — Engineering

## Stack

| Layer | Choice | Rationale |
|---|---|---|
| Core | **Python + NumPy** through Accelerate, structure-of-arrays | the only backend. No GPU — see [D-046](DECISIONS.md#d-046) |
| Chronicle | **Parquet** shards | columnar, compressed, no server |
| Analysis | **DuckDB** over Parquet | full-corpus SQL for free, zero infrastructure |
| Config | **YAML**, resolved + hashed | reproducibility depends on a canonical resolved form |
| Atlas | **TypeScript + Canvas/WebGL**, single page | must be a URL you can send someone |
| LLM layer | **Gemini 3.7 Flash** via `google-genai` | Historian and Analyst only, strictly at the boundary *(→ [D-067](DECISIONS.md#d-067))* |

**Structure-of-arrays is still non-negotiable** *(→ [D-005](DECISIONS.md#d-005))* — not for a
future GPU backend, but because batching worlds along a leading axis is what makes a 32-seed sweep
one run instead of thirty-two. On CPU that is the difference between minutes and an afternoon.

Rust and a GPU backend are both deferred indefinitely. Neither is the bottleneck at this scale;
memory and the Chronicle are.

---

## Repo layout

```
artificial-civilization/
├── docs/                     ← this folder; canonical design
├── src/
│   ├── core/                 the world. no strings, no LLM, no I/O beyond event emission
│   │   ├── state.py          SoA definitions
│   │   ├── tick.py           the phase loop
│   │   ├── generators/       world structure sampled from (config, seed)  [D-020]
│   │   ├── modulators.py     the cross-primitive influence table          [D-021]
│   │   ├── pending.py        scheduled effects + threshold accumulators   [D-025]
│   │   ├── primitives/       p01_scarcity.py … p11_coupling.py
│   │   └── policy/           s0_reactive.py … s6_social.py
│   ├── chronicle/            event emission, sharding, checkpointing
│   ├── lens/                 detectors + null models (one file per detector)
│   ├── forge/                sweeps, forks, viability scans, corpus index
│   ├── digest/               Chronicle → viz digest
│   ├── historian/            LLM narrative
│   └── analyst/              LLM hypothesis → experiment spec
├── atlas/                    the viewer (separate build)
├── configs/
│   ├── frozen/               locked defaults per freeze protocol
│   └── experiments/
├── experiments/<name>/       spec.yaml + result.md (incl. negative results)
├── schemas/                  events.md, digest.md — versioned
└── tests/
```

**One file per primitive, one file per detector.** Both are things we add incrementally and
need to reason about in isolation.

---

## Determinism rules

Invariant I1 *(→ [05-architecture.md](05-architecture.md#i1--determinism))* is the easiest to
break and the most expensive to repair. Non-negotiable rules:

1. **One explicit RNG**, split by purpose (`rng.world`, `rng.mutation`, `rng.policy`). Never
   the global default. Never reseed mid-run. Streams are keyed by a **hash of the name**, not by
   spawn index, so adding a stream later does not renumber — and therefore does not invalidate —
   every run already in the corpus.
1b. **Draw at a shape fixed by config, then mask** *(→ [D-053](DECISIONS.md#d-053))*. Never draw
   per living agent: stream position must not depend on how many agents are alive, or a fork
   diverges from its parent the moment the populations differ by one. Where full capacity is
   wasteful, bound the shape with a config constant (`birth_cap`) rather than with population.
2. **No wall-clock**, no `time()`, no `uuid4()`, no unseeded shuffles.
3. **No iteration-order dependence.** Sort by agent id before any operation whose result
   depends on order.
4. **Fixed-order float reductions.** Parallel sums must use a deterministic tree, not
   whatever the scheduler picks.
5. **Pinned versions** for NumPy in a lockfile. Determinism is version-sensitive.
6. **Deterministic tiebreaks.** Two agents grabbing one cell resolves by id, always.
7. **Checkpoints capture RNG state.** An incomplete checkpoint breaks forking in a way that is
   very hard to detect later.
8. **LOD decisions are a function of world state, never of available compute.**
   *(→ [D-010](DECISIONS.md#d-010))*
9. **Generators run once at init, from `(config, seed)`.** Never sample generated structure
   lazily mid-run — a resource kind that materializes on first access makes world identity
   depend on access order *(→ [D-020](DECISIONS.md#d-020))*.
10. **Modulator application order is fixed**, sorted by `mod_id`. An active set must compose
    identically regardless of the order modulators were bound.
11. **The pending queue is ordered by `(fire_tick, insertion_id)`**, never by heap
    tie-break order, and is captured in full by every checkpoint
    *(→ [D-025](DECISIONS.md#d-025))*.

### CI gate

```
test_determinism:      run 1,000 ticks twice → hash state + Chronicle → assert equal
test_noop_fork:        fork at T with no intervention → assert branch == parent
test_cross_machine:    assert state hash matches a committed golden hash
test_generator_repro:  same (config, seed) → identical generated structure
test_pending_fork:     fork at T with effects pending → assert branch == parent
test_gate_enforcement: config violating a depth gate → assert load fails loudly
test_log_tier_invariance: same seed at two log tiers → assert identical state
```

The cross-machine test will fail first and teach you the most. **It did**, on the first push, and
what it taught was that cross-ISA bit-identity is not available at an acceptable price
*(→ [D-057](DECISIONS.md#d-057))*. Per-stage hashes located the divergence at `world_init`, before
any tick ran: `np.exp` in the resource generator differs in the last ulp between NEON and AVX.
Goldens are therefore recorded **per platform**, and the test asserts each platform against its
own — which is what actually catches a code change silently altering results on the machine you
use.

`test_pending_fork` is the one that catches the most dangerous bug class: a checkpoint missing
scheduled effects produces forks that silently diverge from their parents with no visible symptom.

`test_log_tier_invariance` was added during A0 and is not in the original list. It catches the
inverse hazard: if the sampled tier ever drew from an RNG stream, *how much history you wrote down
would change what happened*. Observation would alter the observed. Sampling is therefore a hash of
the agent id, never a draw *(→ [D-052](DECISIONS.md#d-052))*.

---

## Performance budget

Cost per world-year is a **tracked metric**; a regression is a bug, not an inconvenience.

| Milestone | Target |
|---|---|
| A0 | 32 worlds × 1,000 agents × 50k ticks, < 10 min |
| B0 | same with S1 neural policy, < 30 min including throttling |
| D2 | same with beliefs and values, < 60 min |

Targets are wall-clock on a fanless M1 Air, so they include thermal throttling. Measure them in
A0 and rewrite [00-feasibility.md](00-feasibility.md) with real numbers.

Three levers, in order of impact:

1. **Batch the policy pass.** One forward pass for all agents, not N passes
   *(→ [04-intelligence.md](04-intelligence.md#architecture-one-shared-network-not-ten-thousand))*.
2. **Worlds as a batch axis.** The reason a 32-seed sweep is one run, not thirty-two.
3. ~~Level of detail~~ — **cut** *(→ [D-049](DECISIONS.md#d-049))*. Only pays above ~10k agents,
   and it was the most likely way determinism breaks.

Two memory traps, on 8 GB:

**`known_mask`** at `bool[W, N, H, W]` is 295 MB at the default scale. Pack it to bits (37 MB) or
coarsen it to a region-level map (~24²). Do this before it is a problem.

**The Chronicle is the binding constraint**, not the simulation
*(→ [D-047](DECISIONS.md#d-047))*. A naive log is ~2 GB per world-run. Tiered logging — always /
sampled / aggregated / snapshot — is mandatory, and **every detector must be computable from
sampled and aggregated data.** Check that when writing the detector, not after.

### What depth costs

Depth is not free, and the costs land in different places than intuition suggests:

| Depth | Where it costs | Mitigation |
|---|---|---|
| P1ᴸ¹⁻ᴸ² multiple resource kinds | `[R, H, W]` fields scale linearly in R | keep R modest; quality fields at lower resolution |
| P2ᴸ¹⁻ᴸ² beliefs | the belief table can exceed the agent table | cap beliefs per agent; evict by confidence × recency |
| P5ᴸ² rights vector | observation width, not storage | gate it — most slots stay unpopulated *(D-022)* |
| P8ᴸ² modulators | recomputing the active set each tick | cache; recompute only on discovery/loss events |
| P11ᴸ² accumulators | negligible storage, real checkpoint size | they must be checkpointed regardless |

**The one to watch is beliefs.** Every agent holding graded, provenanced beliefs about many
propositions turns an N-row table into an N×M one, and M grows with world complexity. Cap it
early and treat eviction policy as a modelled quantity — what a civilization forgets *because
it ran out of room* is itself a Chronicle Gap result.

---

## Testing strategy

| Level | What it covers |
|---|---|
| **Unit** | each primitive's state transition in isolation |
| **Detector** | fires on a synthetic positive log, silent on a synthetic negative |
| **Determinism** | the CI gate above |
| **Regression** | each version keeps its own observable suite; C2 must not silently break B1 |
| **Viability** | a nightly scan confirming frozen configs still land in the viable band |

The regression suite is what prevents "complexity collapse"
*(→ [12-risks.md](12-risks.md))*. Every version's exit criteria become permanent tests, run on
every commit thereafter.

---

## Conventions

- **No phenomenon names in `src/core/`.** No `war.py`, no `Alliance`, no `revolution()`. Those
  words live only in `src/lens/`, where they name measurements.
- **No strings in the core.** Enums as integers. Strings are an analysis-layer concern.
- **Events are append-only.** Never mutate an emitted event; correction means a new event.
- **Config over code.** If it's a number that might be swept, it belongs in YAML.
- **Every detector ships with its null.** A PR adding a detector without a null model is
  incomplete.
- **Negative results are committed.** `experiments/<name>/result.md` exists whether the
  hypothesis survived or not.

---

## LLM usage

Historian and Analyst only *(→ [05-architecture.md](05-architecture.md#component-contracts))*.

- Cost scales with corpus size — batch Historian calls per era, not per event.
- Cache aggressively; narrative for a completed era never changes.
- Prompts are versioned artifacts in the repo; a narrative records the prompt version that
  produced it.
- **Historian output is never an input to the Analyst.** Prose about a world is not evidence
  about a world.

**A3 built this and one thing about it was not obvious.** The model choice is free precisely
*because* the output is never evidence — this is the only component in the project where a worse
model produces a worse artifact and moves nothing downstream, which is why it is the one running on
a free tier *(→ [D-067](DECISIONS.md#d-067))*.

The containment is structural rather than editorial. The model never sees the Chronicle, the digest
or a grid: it sees a numbered table of facts computed in Python, and
[`verify.py`](../src/historian/verify.py) deletes any sentence that is uncited, cites an id that
does not exist, contains a number not derivable from its cited facts, names a phenomenon this world
does not contain, or asserts a cause *(→ [D-068](DECISIONS.md#d-068))*.

```bash
uv sync --group historian                        # google-genai, NOT installed by --all-extras
GEMINI_API_KEY=... in a git-ignored .env
uv run python -m historian.build corpus/runs/<id>
```

`google-genai` is a dependency **group** rather than an extra on purpose: CI runs
`uv sync --all-extras`, which installs extras and leaves groups alone, so the determinism gate never
pulls a network SDK. Every test runs against `historian.client.ReplayClient`.

**Nothing in the gate asserts anything about the text.** Prose is the one artifact here that is not
a pure function of `(config, seed)` — which is also why generated narrative is committed under
`experiments/` rather than left in the git-ignored corpus. It cannot be regenerated from a seed, so
if it is not committed it is gone.
