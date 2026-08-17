# 05 — Architecture

## Component map

```text
        ┌──────────────────────────────────────────────────┐
        │  FORGE — experiment runner                       │
        │  sweeps · seeds · forks · scheduling             │
        └───────────────┬──────────────────────────────────┘
                        │ (config, seed)
                        ↓
        ┌──────────────────────────────────────────────────┐
        │  CORE — the world                                │
        │  deterministic · vectorized · batched            │
        │  no strings, no English, no LLM                  │
        └───────────────┬──────────────────────────────────┘
                        │ append-only events
                        ↓
        ┌──────────────────────────────────────────────────┐
        │  CHRONICLE — the event log                       │
        │  columnar · immutable · replayable               │
        └───────────────┬──────────────────────────────────┘
                        │
            ┌───────────┼───────────┬──────────────┐
            ↓           ↓           ↓              ↓
        ┌───────┐  ┌─────────┐  ┌──────────┐  ┌─────────┐
        │ LENS  │  │HISTORIAN│  │ ANALYST  │  │  ATLAS  │
        │metrics│  │ (LLM)   │  │  (LLM)   │  │ viewer  │
        │+ nulls│  │narrative│  │hypotheses│  │ digest  │
        └───────┘  └─────────┘  └────┬─────┘  └─────────┘
                                     │
                                     └── proposes experiments ──┐
                                                                │
                        ┌───────────────────────────────────────┘
                        ↓
                   back into FORGE   ← the loop closes here
```

## Component contracts

| Component | Reads | Writes | May use an LLM |
|---|---|---|---|
| **Forge** | configs, corpus index | run specs, fork specs | no |
| **Core** | config + seed (+ fork checkpoint) | Chronicle events, checkpoints | **never** |
| **Chronicle** | — | Parquet shards, index | no |
| **Lens** | Chronicle | metrics tables, detector firings | no |
| **Historian** | Chronicle, Lens | narrative text | yes |
| **Analyst** | Lens metrics across corpus | hypotheses as *runnable experiment specs* | yes |
| **Atlas** | viz digest only | — | no |

Two contracts are load-bearing:

- **Core never reads Lens/Historian/Analyst output.** Information flows one way. Anything else
  is a feedback path that makes results uninterpretable.
- **Atlas never reads live Core state.** It reads a pre-rendered digest. Nothing rendered can
  ever slow a run. *(→ [09-visualization.md](09-visualization.md))*

---

## The four invariants

These must hold from commit #1. Retrofitting any of them is agony.

### I1 — Determinism

A run is a pure function of `(config, seed)`. Replay is **bit-identical**.

Engineering consequences *(→ [11-engineering.md](11-engineering.md#determinism-rules))*:
- One explicit RNG stream, split by purpose, never a global default
- No wall-clock, no `dict` iteration order dependence, no unordered parallel reduction
- Fixed-order float reductions; pinned library versions
- A CI test that runs 1,000 ticks twice and compares hashes

### I2 — Event sourcing

World state at tick T is reconstructible from the log alone. If a fact matters and isn't in
the Chronicle, it does not exist for analysis.

### I3 — Forkability

Rewind to tick T, change one thing, re-run. This is the affordance that makes causal inference
possible and it is the single most under-used capability of simulation
*(→ [08-experiments.md](08-experiments.md#fork-based-causal-inference))*.

Requires periodic checkpoints: full state snapshots at a fixed cadence, so a fork costs
`checkpoint_load + replay_to_T` rather than a full re-run.

### I4 — Array state

Agents are columns, not objects. Worlds are a batch dimension. This is what makes 10k agents ×
1,000 worlds feasible. Design the state as arrays in A1 even when a list of objects would be
easier — it is the load-bearing decision. See [D-005](DECISIONS.md#d-005).

---

## The tick loop

Phase order is part of the spec: changing it changes results, so it is versioned alongside the
schema.

```text
for each tick:
  0. PENDING  fire scheduled effects due this tick; step accumulators;
              apply threshold crossings                               (P10ᴸ², P11ᴸ¹⁻ᴸ²)
  1. WORLD    drift, regrowth, contagion spread, exogenous shocks     (P1, P9, P10)
  2. MODULATE recompute active modulator set; apply to parameters     (D-021)
  3. OBSERVE  build observation tensors for all agents                (P2)
  4. DECIDE   one batched forward pass → actions for all agents       (S0–S6)
  5. RESOLVE  actions applied in fixed priority order:
                a. movement
                b. gather / craft                                     (P1, P8)
                c. transfer / trade                                   (P5)
                d. signal / teach                                     (P9, S6)
                e. pledge / delegate / revoke                         (P4, P6)
                f. coercion  ← last, so it resolves against final state (P7)
  6. METABOLISM  energy costs incl. cognition cost; health updates
  7. VITALS      death, birth, mutation
  8. AGGREGATE   global stocks updated from individual actions        (P11)
                 actions may enqueue delayed effects into PENDING
  9. EMIT        append events to Chronicle
 10. LEARN       plastic updates (S2+); evolution runs at generation boundary
```

Phase 0 runs **before** phase 1 so a scheduled effect and this tick's drift compose in a fixed
order. Phase 2 runs after the world updates and before observation, so agents always perceive
post-modulation parameters — otherwise a discovery would appear to take effect a tick late,
inconsistently.

**Conflict resolution** (two agents grabbing the same cell) is resolved by a deterministic
tiebreak on agent id, never by iteration order.

---

## Where the primitives live

| Primitive | Phase | Notes |
|---|---|---|
| P1 Scarcity | 1, 4b | resource grid, regrowth kernel |
| P2 Fog | 2 | per-agent known-map mask |
| P3 Identity | 4d, 6 | stable ids across life; reputation in episodic memory |
| P4 Pledge | 4e | public ledger of commitments + violations |
| P5 Claim | 4c | transferable claim table |
| P6 Delegation | 4e | delegation graph, revocation cost |
| P7 Coercion | 4f | resolved last, against post-action state |
| P8 Recipe | 4b | latent rule table, discovery via combination |
| P9 Contagion | 1, 4d | one implementation, many instances |
| P10 Drift | 1 | scheduled + stochastic shocks |
| P11 Coupling | 7 | individual → global aggregation, feeds next tick's payoffs |

---

## Scale strategy

Two decisions make 1,000 agents × 100k ticks × 32 worlds tractable on an 8 GB M1
*(→ [00-feasibility.md](00-feasibility.md))*:

1. **Structure-of-arrays from day one.** A tick is array ops. See I4.
2. **Worlds as a batch dimension.** Once state is arrays, 32 worlds is one extra axis, which
   turns a 32-seed sweep into a single run instead of thirty-two.

**Level of detail is cut** *(→ [D-049](DECISIONS.md#d-049))*. It only pays above ~10k agents,
which this hardware cannot reach, and it was the most likely way invariant I1 breaks. Removing it
deletes a whole class of determinism bug for free.

The binding constraint at this scale is **not** the tick loop — it is the Chronicle
*(→ [D-047](DECISIONS.md#d-047))*.
