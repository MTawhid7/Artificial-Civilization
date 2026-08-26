"""Chronicle event schema — the fixed-width envelope and the event enum.

Schema version 0.1.0. docs/06-data-model.md is canonical; this file must agree
with it and with schemas/events.md, and all three move together.

Two rules that outlive any particular event:

**No event is named after a phenomenon.** There is no `WAR_DECLARED`. War is a
pattern of COERCE events that a detector finds. The moment the log names the
phenomenon, the analysis is circular.

**Enum values are permanent.** A recorded Chronicle stores integers; renumbering
them silently reinterprets every run already in the corpus. Append only.
"""

from __future__ import annotations

import numpy as np
import pyarrow as pa

SCHEMA_VERSION = "0.1.0"

# --- event types -------------------------------------------------------------
# Grouped by decade so a group can grow without renumbering its neighbours.

# vitals
BIRTH = 1
DEATH = 2
MUTATION = 3
# space
MOVE = 10
EXPLORE_CELL = 11
PERCEIVE = 12
# resource
GATHER = 20
DEPLETE = 21
REGROW = 22
# exchange
TRANSFER = 30
CLAIM_MAKE = 31
CLAIM_BREAK = 32
# social
SIGNAL = 40
TEACH = 41
IMITATE = 42
# Reserved at A2, emitted at B2. Reception is a separate event from emission
# because the two carry different choice sets, and a detector that cannot
# separate "what was said" from "who heard it" cannot run the remap test.
# See schemas/events.md and D-066.
SIGNAL_HEARD = 43
# commitment
PLEDGE_MAKE = 50
PLEDGE_HONOR = 51
PLEDGE_BREAK = 52
DELEGATE = 53
REVOKE = 54
# conflict
COERCE = 60
DEFEND = 61
SEIZE = 62
# knowledge
RECIPE_DISCOVER = 70
RECIPE_TRANSMIT = 71
RECIPE_LOST = 72
HYPOTHESIS_FORM = 73
# contagion
INFECT = 80
RECOVER = 81
CONTAGION_MUTATE = 82
# belief
BELIEF_FORM = 90
BELIEF_TRANSMIT = 91
BELIEF_DECAY = 92
BELIEF_CONTRADICTED = 93
# world
SHOCK = 100
CLIMATE_STEP = 101

EVENT_NAMES: dict[int, str] = {
    BIRTH: "BIRTH", DEATH: "DEATH", MUTATION: "MUTATION",
    MOVE: "MOVE", EXPLORE_CELL: "EXPLORE_CELL", PERCEIVE: "PERCEIVE",
    GATHER: "GATHER", DEPLETE: "DEPLETE", REGROW: "REGROW",
    TRANSFER: "TRANSFER", CLAIM_MAKE: "CLAIM_MAKE", CLAIM_BREAK: "CLAIM_BREAK",
    SIGNAL: "SIGNAL", TEACH: "TEACH", IMITATE: "IMITATE",
    SIGNAL_HEARD: "SIGNAL_HEARD",
    PLEDGE_MAKE: "PLEDGE_MAKE", PLEDGE_HONOR: "PLEDGE_HONOR",
    PLEDGE_BREAK: "PLEDGE_BREAK", DELEGATE: "DELEGATE", REVOKE: "REVOKE",
    COERCE: "COERCE", DEFEND: "DEFEND", SEIZE: "SEIZE",
    RECIPE_DISCOVER: "RECIPE_DISCOVER", RECIPE_TRANSMIT: "RECIPE_TRANSMIT",
    RECIPE_LOST: "RECIPE_LOST", HYPOTHESIS_FORM: "HYPOTHESIS_FORM",
    INFECT: "INFECT", RECOVER: "RECOVER", CONTAGION_MUTATE: "CONTAGION_MUTATE",
    BELIEF_FORM: "BELIEF_FORM", BELIEF_TRANSMIT: "BELIEF_TRANSMIT",
    BELIEF_DECAY: "BELIEF_DECAY", BELIEF_CONTRADICTED: "BELIEF_CONTRADICTED",
    SHOCK: "SHOCK", CLIMATE_STEP: "CLIMATE_STEP",
}

# --- logging tiers -----------------------------------------------------------
# D-047: tiered logging is a requirement, not an optimization. A naive log is
# ~2 GB per world-run and the Chronicle, not the tick loop, is what runs out
# of room first.

TIER_ALWAYS = 0      # rare and decisive: births, deaths, discoveries, pledges
TIER_SAMPLED = 1     # routine and voluminous: movement, gathering
TIER_AGGREGATED = 2  # never per-agent: binned totals per region per M ticks

EVENT_TIER: dict[int, int] = {
    BIRTH: TIER_ALWAYS, DEATH: TIER_ALWAYS, MUTATION: TIER_SAMPLED,
    MOVE: TIER_SAMPLED, EXPLORE_CELL: TIER_SAMPLED, PERCEIVE: TIER_SAMPLED,
    GATHER: TIER_SAMPLED, DEPLETE: TIER_ALWAYS, REGROW: TIER_AGGREGATED,
    SIGNAL: TIER_SAMPLED, SIGNAL_HEARD: TIER_SAMPLED,
    TEACH: TIER_ALWAYS, IMITATE: TIER_SAMPLED,
    RECIPE_DISCOVER: TIER_ALWAYS, RECIPE_TRANSMIT: TIER_ALWAYS,
    RECIPE_LOST: TIER_ALWAYS, SHOCK: TIER_ALWAYS,
}

# --- the envelope ------------------------------------------------------------
# Fixed-width rows: cheap to write, trivial to scan, and the same shape for every
# event type. The meaning of a/b/c is per-event-type and lives in
# schemas/events.md.

ENVELOPE: tuple[tuple[str, type], ...] = (
    ("tick", np.uint32),
    ("world_id", np.uint16),
    ("event_type", np.uint8),
    ("subject", np.uint32),
    ("object", np.uint32),
    ("a", np.float32),
    ("b", np.float32),
    ("c", np.float32),
)

ARROW_SCHEMA = pa.schema(
    [
        ("tick", pa.uint32()),
        ("world_id", pa.uint16()),
        ("event_type", pa.uint8()),
        ("subject", pa.uint32()),
        ("object", pa.uint32()),
        ("a", pa.float32()),
        ("b", pa.float32()),
        ("c", pa.float32()),
    ]
)

AGGREGATE_SCHEMA = pa.schema(
    [
        ("tick", pa.uint32()),
        ("world_id", pa.uint16()),
        ("population", pa.uint32()),
        ("births", pa.uint32()),
        ("deaths", pa.uint32()),
        ("resource_total", pa.float32()),
        ("energy_mean", pa.float32()),
        ("energy_gini", pa.float32()),
        ("gene_mean", pa.list_(pa.float32())),
    ]
)


def sample_mask(tick: int, subject: np.ndarray, rate: int) -> np.ndarray:
    """Deterministic 1-in-`rate` selection of **agents**, consuming no randomness.

    Two properties, both load-bearing.

    **It consumes no randomness.** If the sampled tier drew from an RNG stream,
    changing `log_tier` would shift every subsequent draw, and the simulation
    would produce different history depending on how much of it was written down.
    Observation would alter the observed. A splitmix64 mix gives a
    well-distributed, exactly reproducible integer with no RNG state at all.

    **It keys on the agent, not on (agent, tick).** This is the difference between
    a usable log and a useless one, and it was measured rather than assumed.
    Keying on both gave 4.83 samples per agent scattered across a 191-tick
    lifespan — isolated snapshots from which no trajectory can be reconstructed,
    which makes `directed_foraging` and every other path-based detector
    uncomputable. Keying on the agent alone logs 1-in-K agents *completely, for
    their whole lives*, at identical row cost. A cohort you can follow beats a
    scatter you cannot.

    The cost is that the sampled cohort is fixed rather than fresh each tick, so
    rare events among unsampled agents are missed. That is what the ALWAYS tier
    and the aggregate tier are for: population-level rates never come from this
    sample.

    `tick` is retained in the signature because the tiering policy is the writer's
    to decide, not its callers' — see D-047.
    """
    if rate <= 1:
        return np.ones(subject.shape, dtype=bool)

    # Wraparound is the point of a mixing function, so every multiply below is an
    # intentional overflow. Kept as array ops rather than scalar ops because
    # numpy wraps arrays silently and warns on scalars — same arithmetic, and
    # nothing here should look like an accident to a future reader.
    z = subject.astype(np.uint64) * np.uint64(0x9E3779B97F4A7C15)
    z ^= z >> np.uint64(30)
    z *= np.uint64(0xBF58476D1CE4E5B9)
    z ^= z >> np.uint64(27)
    z *= np.uint64(0x94D049BB133111EB)
    z ^= z >> np.uint64(31)
    return (z % np.uint64(rate)) == np.uint64(0)
