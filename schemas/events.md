# Event schema

**Version 0.1.0.** Canonical definition lives in
[docs/06-data-model.md](../docs/06-data-model.md); this file records the payload
semantics of `a`, `b`, `c` per event type. Both move together, and both are
versioned with the code that writes them.

## Envelope

Every event, of every type, is one fixed-width row:

| Field | Type | Meaning |
|---|---|---|
| `tick` | uint32 | when |
| `world_id` | uint16 | which world in the batch |
| `event_type` | uint8 | the enum below — never a string |
| `subject` | uint32 | primary agent or entity id |
| `object` | uint32 | secondary id, 0 if none |
| `a`, `b`, `c` | float32 | per-type payload, defined below |

**Enum values are permanent.** A recorded Chronicle stores integers; renumbering
silently reinterprets every run already in the corpus. Append only, and the
decade gaps exist so a group can grow without disturbing its neighbours.

## Implemented (A0/A1)

| Value | Event | Tier | `subject` | `object` | `a` | `b` | `c` |
|---|---|---|---|---|---|---|---|
| 1 | `BIRTH` | always | child id | parent id | — | — | — |
| 2 | `DEATH` | always | agent id | — | age at death | — | — |
| 10 | `MOVE` | sampled | agent id | — | x after moving | y after moving | energy |
| 12 | `PERCEIVE` | sampled | agent id | direction taken, 0..3 | score of chosen direction | mean of the four | best of the four |
| 20 | `GATHER` | sampled | agent id | — | energy gained | — | — |

`MOVE` carries position and energy so trajectories are reconstructable from the
sampled tier alone; a detector needing a join back to per-tick state would not
survive tiering.

### Reserved for B2 — the signal channel

Decided at A2, emitted at B2 *(→ [D-066](../docs/DECISIONS.md#d-066))*. Enum values are permanent
and the corpus outlives the code, so the payload is settled while it is still free to settle.

| Value | Event | Tier | `subject` | `object` | `a` | `b` | `c` |
|---|---|---|---|---|---|---|---|
| 40 | `SIGNAL` | sampled | emitter | symbol emitted | symbols available to this emitter | emitter's own action this tick | best option score available, on `PERCEIVE`'s scale |
| 43 | `SIGNAL_HEARD` | sampled | hearer | emitter | symbol heard | hearer's action after hearing | distance from emitter |

**Why two events and not one.** Emission and reception have different choice sets. A hearer chooses
among actions given a symbol; an emitter chooses among symbols given a world. One row cannot carry
both, and a detector that cannot separate *what was said* from *who heard it* cannot run the remap
test — which is the criterion that separates the first emergent word from a cute correlation
*(→ [10-roadmap.md § B2](../docs/10-roadmap.md#b2--first-word-))*.

**Why these three floats on `SIGNAL`.** Each closes a specific way the stage could produce a
confident wrong number:

- **symbols available** makes the chance baseline exact rather than estimated. Mutual information
  between signal and world is biased upward in finite samples, and the analytic correction depends
  on the alphabet size — which is only knowable if it is logged. Without it the null has to be a
  permutation, which is slower and weaker.
- **emitter's own action** separates *the signal describes the world* from *the signal describes
  what I am about to do*. Both produce signal–world correlation; only the first is communication.
  Without this column the two are indistinguishable and the stage would claim the wrong one.
- **best option score** is the world state a useful signal would be about, recorded on the same
  scale `PERCEIVE` already uses — so signal informativeness and gradient-following are measured
  against a common denominator instead of two incomparable ones.

**Why `SIGNAL_HEARD` carries the hearer's next action.** Referential validity is a claim about
whether hearing changed behavior. Reconstructing that from `MOVE` fails: `MOVE` is sampled 1-in-K
on the *agent*, so the hearer is usually not in the sampled cohort, and the join silently drops most
receptions *(→ [D-052](../docs/DECISIONS.md#d-052))*.

**Still open:** whether one context slot is enough for the remap test, or whether the referent needs
its own event once P2 fog exists and "what the emitter could see" stops being reconstructible from
position alone. Tracked at the bottom of [DECISIONS.md](../docs/DECISIONS.md).

`PERCEIVE` records **the decision context, not the decision's consequences**

`PERCEIVE` records **the decision context, not the decision's consequences** — what
the agent saw in each direction at the moment it chose. Those particular three
numbers are what make `gradient_ascent`'s null exact rather than simulated: an
agent ignoring its options picks uniformly, so its expected chosen score *is* the
mean, and `chosen − mean` has expectation zero for any landscape whatsoever.
Dividing by `best − mean` puts perfect gradient-following at 1.0.

Logging perception rather than a verdict is what keeps the core/lens split intact.
The Chronicle records what the agent saw; whether that adds up to foraging is the
lens's question. Contrast the withdrawn `directed_foraging`, which conditioned on
energy — an *outcome* of movement — and inverted its own conclusion
*(→ [D-056](../docs/DECISIONS.md#d-056))*.

## Declared, not yet emitted

Numbers are reserved so that logs written today stay readable when these arrive:
`MUTATION` 3, `EXPLORE_CELL` 11, `DEPLETE` 21, `REGROW` 22, `TRANSFER` 30,
`CLAIM_MAKE` 31, `CLAIM_BREAK` 32, `SIGNAL` 40, `TEACH` 41, `IMITATE` 42,
`PLEDGE_MAKE` 50, `PLEDGE_HONOR` 51, `PLEDGE_BREAK` 52, `DELEGATE` 53,
`REVOKE` 54, `COERCE` 60, `DEFEND` 61, `SEIZE` 62, `RECIPE_DISCOVER` 70,
`RECIPE_TRANSMIT` 71, `RECIPE_LOST` 72, `HYPOTHESIS_FORM` 73, `INFECT` 80,
`RECOVER` 81, `CONTAGION_MUTATE` 82, `BELIEF_FORM` 90, `BELIEF_TRANSMIT` 91,
`BELIEF_DECAY` 92, `BELIEF_CONTRADICTED` 93, `SHOCK` 100, `CLIMATE_STEP` 101.

## The aggregated tier

Written once per `run.aggregate_every` ticks to `aggregate.parquet`, never
per-agent:

| Field | Meaning |
|---|---|
| `tick`, `world_id` | binning keys |
| `population` | living agents |
| `births`, `deaths` | counts since the previous bin |
| `resource_total` | summed stock across the grid |
| `energy_mean`, `energy_gini` | distribution of energy among the living |
| `gene_mean` | per-gene mean across the living — how the genome drifts |

This tier survives every logging setting, so every population-level detector must
be computable from it *(→ [D-047](../docs/DECISIONS.md#d-047))*.

## The rule that outlives every entry here

**No event is named after a phenomenon.** There is no `WAR_DECLARED`, no
`ALLIANCE_FORMED`, no `COLLAPSE`. War is a pattern of `COERCE` events that a
detector finds. The moment the log names the phenomenon, the analysis of that
phenomenon is circular.
