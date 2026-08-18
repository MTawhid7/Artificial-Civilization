# 06 — Data Model

**Schema version: 0.1.0** — this document is canonical. Bump the version on any change; never
silently redefine a field's meaning. Runs record the schema version they were produced under.

---

## Run identity

A run is fully described by:

```
run_id      = hash(config_hash, seed, code_version)
config_hash = hash of the resolved, frozen config
seed        = uint64
code_version = git sha of the core
```

Two runs with the same `run_id` must produce byte-identical Chronicles. This is invariant I1
made checkable.

A **fork** additionally carries:

```
parent_run_id, fork_tick, intervention (typed, see below)
```

---

## World state (structure-of-arrays)

Every field is a typed array. No Python objects in the hot path. Worlds add a leading batch
axis `[W, ...]`.

### Agent columns

| Field | Type | Notes |
|---|---|---|
| `id` | uint32 | stable for life; never reused within a run |
| `alive` | bool | tombstoning, not deletion — keeps indices stable |
| `x`, `y` | uint16 | position |
| `energy` | float32 | death at ≤ 0 |
| `age` | uint32 | ticks |
| `health` | float32 | reduced by contagion (P9), coercion (P7) |
| `genome` | float32[G] | includes plasticity coefficients from S2 |
| `embed` | float32[d] | individuality vector fed to the shared network |
| `plastic` | float32[P] | per-agent plastic layer weights |
| `hidden` | float32[H] | recurrent state (S3+) |
| `inventory` | float32[R] | per-resource-kind holdings |
| `lineage` | uint32 | which shared network governs this agent |
| `parent` | uint32 | for genealogy and inheritance-channel decomposition |
| `culture` | uint32 | current cultural cluster id (S6) |

### World arrays

| Field | Type | Notes |
|---|---|---|
| `resource` | float32[R, H, W] | per-kind stock per cell |
| `terrain` | uint8[H, W] | static |
| `climate` | float32[C, H, W] | drifts under P10 |
| `known_mask` | bool[N, H, W] | per-agent explored map (P2) — the expensive one; consider chunked or per-lineage |

### Relational tables (variable length, still columnar)

| Table | Key columns |
|---|---|
| `episodic` | `agent_id, tick, subject_id, valence, kind` — memory of who did what (P3) |
| `pledges` | `pledge_id, pledger, references_pledge, stake, terms_hash, tick_made, tick_broken` (P4) |
| `claims` | `claim_id, holder, object_ref, tick_acquired` (P5) |
| `delegations` | `from_agent, to_agent, scope, tick_made, tick_revoked, revocation_cost` (P6) |
| `recipes` | `recipe_id, inputs[], process, discovered_by, tick_discovered` (P8) |
| `knowledge` | `agent_id, recipe_id, confidence, source_agent` — who knows what (P8, S6) |
| `contagions` | `contagion_id, transmission_rate, incubation, duration, effect_channel, effect_magnitude, mutation_rate` (P9) |
| `infections` | `agent_id, contagion_id, tick_infected, state` |
| `beliefs` | `holder_id, proposition_id, confidence, provenance_hops, source_id, medium, decay_rate, first_hand` (mechanism A, P2ᴸ¹) |
| `propositions` | `proposition_id, type, slots[]` — slots fill independently, so "knows it exists but not where" is representable (P2ᴸ²) |
| `truth` | `proposition_id, actual_value, tick_became_true, tick_ceased` — **never readable by agents** |
| `modulators` | `mod_id, source_predicate, target_path, fn, magnitude, scope, bound_by` (D-021) |
| `pending` | `fire_tick, effect_type, target_ref, magnitude, origin_event` — scheduled effects (D-025) |
| `accumulators` | `acc_id, scope_ref, value, threshold, on_cross_effect` — tipping points (D-025) |

`first_hand` on `beliefs` is load-bearing: without separating direct experience from hearsay,
reputation-by-rumour cannot emerge and the Chronicle Gap has no grip on the social layer.

The `beliefs`/`truth` split is the entire basis of the Chronicle Gap
*(→ [03-mechanisms.md](03-mechanisms.md#a-the-chronicle-gap--belief-vs-truth-measured))*. Enforce
the separation at the type level if the language allows it — an accidental read here silently
invalidates the project's most distinctive result.

---

## Chronicle (the event log)

Append-only, columnar, immutable. Written as Parquet shards.

### Common envelope

```
tick        uint32
world_id    uint16
event_type  uint8      -- enum, never a string
subject     uint32     -- primary agent/entity
object      uint32     -- secondary, 0 if none
a, b, c     float32    -- event-specific payload
```

Fixed-width rows keep the log cheap to write and trivial to scan. Semantics of `a/b/c` per
event type are documented in `schemas/events.md` and versioned with this file.

### The sampled tier samples agents, not agent-ticks

*(→ [D-052](DECISIONS.md#d-052))* The 1-in-K decision is a hash of `agent_id` alone. A sampled
agent is logged **for its whole life**; an unsampled one is never logged.

Keying on `(tick, agent_id)` instead looks equivalent and is not. Measured in A0: 4.83 positions
per agent scattered across a 191-tick lifespan, no two consecutive — from which path straightness,
and every other trajectory detector, is uncomputable. Following a cohort costs exactly the same
number of rows.

The consequence is a rule about which tier answers which question: **population-level rates never
come from the sampled tier.** They come from the aggregated tier. The sampled tier answers
questions about *lives*, the aggregated tier answers questions about *populations*, and confusing
the two produces a biased estimate that looks fine.

### Event types (v0.1)

| Group | Events |
|---|---|
| vitals | `BIRTH`, `DEATH`, `MUTATION` |
| space | `MOVE`, `EXPLORE_CELL`, `PERCEIVE` |
| resource | `GATHER`, `DEPLETE`, `REGROW` |
| exchange | `TRANSFER`, `CLAIM_MAKE`, `CLAIM_BREAK` |
| social | `SIGNAL`, `TEACH`, `IMITATE` |
| commitment | `PLEDGE_MAKE`, `PLEDGE_HONOR`, `PLEDGE_BREAK`, `DELEGATE`, `REVOKE` |
| conflict | `COERCE`, `DEFEND`, `SEIZE` |
| knowledge | `RECIPE_DISCOVER`, `RECIPE_TRANSMIT`, `RECIPE_LOST`, `HYPOTHESIS_FORM` |
| contagion | `INFECT`, `RECOVER`, `CONTAGION_MUTATE` |
| belief | `BELIEF_FORM`, `BELIEF_TRANSMIT`, `BELIEF_DECAY`, `BELIEF_CONTRADICTED` |
| world | `SHOCK`, `CLIMATE_STEP` |

**Rule:** no event type is named after a phenomenon. There is no `WAR_DECLARED`. War is a
pattern of `COERCE` events that a detector finds
*(→ [07-detectors.md](07-detectors.md))*.

### On-disk layout

```
corpus/
  runs/<run_id>/
    config.yaml            resolved config, frozen
    meta.json              seed, code_version, schema_version, parent/fork info
    chronicle/*.parquet    sharded by tick range
    checkpoints/*.npz      full state, every C ticks (for forking)
    digest.msgpack         viz digest (see below)
    metrics/*.parquet      Lens output
  index.parquet            one row per run — the corpus index Forge and Analyst query
```

Queried with DuckDB directly over the Parquet files. No database server.

---

## Generated world structure

Per [D-020](DECISIONS.md#d-020), depth enters through generators. Generator output is **part of
world identity** and must be reconstructible from `(config, seed)` alone — never sampled lazily
mid-run, which would break I1.

```
generated at world init, from (config, seed):
  resource_kinds[]     regen class, extraction curve, quality field,
                       substitutability matrix, spatial clustering
  latent_rules         which combinations produce which outcomes (P8)
  modulator_set        which discoveries change which parameters (D-021)
  contagion_pool       available strains and their mutation topology
  climate_processes    trend / cyclical / heavy-tailed shock parameters
```

Written to `meta.json` at run start so the corpus is analyzable without re-running the
generator. Two worlds with identical generator hyper-parameters and different seeds have
genuinely different economies and different technological consequences — which is the point.

---

## Modulators

The single mechanism for cross-primitive influence.

```
Modulator {
  mod_id
  source_predicate   (primitive, state_test)   e.g. (P8, knows_recipe:smelting)
  target_path        (primitive, param)        e.g. (P1, resource[iron].extract_cost)
  fn                 multiply | add | replace | curve
  magnitude          float
  scope              agent | region | world
  bound_by           recipe_id | contagion_id
}
```

Resolution order is fixed and versioned: modulators are applied sorted by `mod_id` so a set of
active modulators always composes identically. Composition rule for multiple modulators on one
parameter is an **open question** — see the bottom of [DECISIONS.md](DECISIONS.md).

---

## Checkpoints

Full state snapshot every `C` ticks (default 500). Fork cost = load nearest checkpoint +
replay to `fork_tick`. Trade-off: smaller `C` costs disk, larger `C` costs fork latency.

A checkpoint must capture **everything** including RNG stream state, the **pending-effects
queue**, and all **accumulator values** — an incomplete checkpoint breaks I1 in a way that is
very hard to detect later.

The pending queue is the most dangerous omission: a fork missing scheduled effects diverges
from its parent with no visible symptom, and the no-op fork test is the only thing that catches
it *(→ [10-roadmap.md](10-roadmap.md#a0--skeleton))*.

---

## Config

Hierarchical YAML, fully resolved and hashed before a run. Frozen defaults live in
`configs/frozen/` per the freeze protocol
*(→ [02-primitives.md](02-primitives.md#the-freeze-protocol))*.

```yaml
world:      { size, terrain_seed, resource_kinds, patchiness, regrowth }
primitives: { p1: {...}, p2: {...}, ... }   # only enabled ones present
intelligence: { stage: S2, hidden: 48, memory_slots: 8, cognition_cost: 0.02 }
population: { initial, max, mutation_rate }
run:        { ticks, checkpoint_every, log_level }
```

A config that enables a primitive past its intelligence gate must **fail loudly at load**, not
run badly *(→ [02-primitives.md](02-primitives.md#gating-primitives-and-depth-are-both-gated-by-policy))*.

---

## Interventions (typed)

Forks apply a typed intervention, never arbitrary code — otherwise counterfactuals aren't
reproducible.

```
RESOURCE_SHOCK   { kind, region, magnitude }
CONTAGION_INTRO  { contagion_spec, seed_agents }
GRANT_RECIPE     { recipe_id, agents }
KILL_COHORT      { predicate }
SET_TRUTH        { proposition_id, value }     -- e.g. silently un-poison the river
PARAM_SET        { path, value }
```

`SET_TRUTH` is what makes the Chronicle Gap experiment possible.

---

## Viz digest

A separate, tiny output alongside the Chronicle — the contract between sim and Atlas
*(→ [09-visualization.md](09-visualization.md))*. Target ≤ 5 MB for a 10,000-year run.

**Wire format is `digest.json`, not `digest.msgpack`** *(→ [D-061](DECISIONS.md#d-061))*: scalar
series quantized to one or two bytes, base64-encoded, each block carrying its own
`{bits, min, max, shape}`. The viewer must work from `file://` with no network access, and a page
that cannot fetch a digest cannot fetch a decoder either. Full wire spec:
[schemas/digest.md](../schemas/digest.md), versioned separately from this document.

### v0.1 — what is actually built

```
frames: ~2000, evenly spaced in ticks
series [n_worlds, n_frames]:
  population    uint16   exact, range fixed to [0, capacity]
  births, deaths, energy_mean, energy_gini, resource_total   uint8
genes  [n_worlds, n_frames/8, n_genes]  uint8   trait means, subsampled in time
rasters (first few worlds only, from checkpoints — the snapshot tier):
  resource      uint8[h, w]   physical stock, quantized
  density       uint8[h, w]   agents per cell
markers:   [(world, tick, detector_id, magnitude)]   ← from Lens, not hand-authored
detectors: {detector_id: {magnitude, null_mean, null_std, effect_size, fired}}
```

### Reserved — specified, and deliberately absent

```
territory · eff_scarcity · belief_layer · tech_level · cooperation_rate
active_contagions · modulators · accumulators · flows
```

None has an S0 meaning: there is no territory without claims, no belief layer without a belief
store, no tech level without recipes. They are listed in the digest's own `reserved` field rather
than filled with plausible zeros. **A subset that knows it is a subset can be extended; one that
pretends to be complete cannot** — and an Atlas reading zeros has no way to tell "nothing happened"
from "nothing was measured".

Moving a field out of `reserved` and into the body bumps `digest_version`.

`markers` come straight from the detector suite — the scientific instrumentation *is* the
narrative UI. Build detectors once, get chapter markers free. `detectors` travels beside them so
the verdict cannot be separated from the marks: a marker records that something happened, and only
the effect size says whether it happened more often than chance.

`accumulators` is what makes tipping points watchable: a bar quietly filling for two thousand
years before anything visible happens is better drama than the collapse itself — and it is
honest, because the agents cannot see it either.

**Quantization ranges are run-wide, never per-world.** The wall exists to compare worlds;
normalizing each to its own extremes would rescale every strip independently and manufacture a
similarity that is not in the data. The same rule applies again at render time, because decoding
and re-normalizing would quietly undo it.
