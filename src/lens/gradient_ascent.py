"""`gradient_ascent` — does an agent's chosen direction point up the resource gradient?

Replacement for the withdrawn `directed_foraging`, and built to avoid the specific
way that one broke ([D-056](../../docs/DECISIONS.md#d-056)). It measures the
**decision** against the alternatives that were available at the moment of
deciding, and conditions on nothing downstream of the decision. Energy, age,
population, and success play no part.

**Definition.** For every logged move, the policy perceived four sector scores —
resource visible to the north, east, south and west. Let `chosen` be the score of
the direction actually taken, `mean` the average of the four, and `best` the
highest. The per-move statistic is

    advantage = (chosen - mean) / (best - mean)

which is **1.0** when the best direction was taken, **0.0** on average when
direction is ignored, and negative when the choice was worse than picking at
random. The detector's magnitude is the mean advantage over all logged moves on
non-flat ground.

**Null: blind-choice, and it is exact.** An agent that ignores the gradient picks
uniformly among four options, so its expected chosen score *is* the mean of the
four. `chosen - mean` therefore has expectation exactly zero — conditional on the
landscape, for any landscape, with no surrogate to simulate and no distributional
assumption. This is a designed control in the sense of
[07-detectors.md](../../docs/07-detectors.md), like `referential_validity`, rather
than a permutation.

The spread still has to come from somewhere, and **the unit it comes from is the
world, not the move.** A run of 16 worlds produces millions of moves, but they are
not millions of independent observations: agents within a world share one
landscape, and each agent contributes hundreds of correlated steps. Treating moves
as independent gave z ≈ 90 on a single run — a number that says far more about how
many rows were logged than about how the agents behaved, and the same error
[D-054](../../docs/DECISIONS.md#d-054) was written to prevent.

So the statistic is averaged within each world first, and the spread is taken
across worlds. `n` is 16, not 2.9 million. Worlds are the designed replicate axis
*(→ [00-feasibility.md](../../docs/00-feasibility.md))* — "seeds are the unit of
replication, not agents" — and this is that rule applied to a within-run statistic.

**Why the exact null matters here.** `directed_foraging` was killed by a confound
its permutation null could not see, and permutation nulls share that blind spot
generally — they preserve whatever structure the permutation does not disturb. A
null with a derived centre has no such structure to preserve.

**Firing is not evidence of evolution, and must not be reported as such.** At
stage S0 the policy *already* weighs the resource gradient, and the founding
cohort draws `gradient_sensitivity` uniformly, so agents ascend gradients from
tick zero. A positive magnitude means the mechanism works; it says nothing about
whether selection improved it.

The evolutionary question is answered by `advantage_delta` in `detail` — the same
statistic computed over the first and last tenth of the run. That comparison is a
**frozen-policy** null in the sense of the catalogue: the founding cohort is an
unselected population measured under identical conditions. A rise means selection
found something; a flat line means the trait was already where selection wanted it,
or that nothing was selecting on it.

Reads the sampled tier: 1-in-K agents are logged for their whole lives, so the
statistic is a within-cohort average over complete lives rather than a snapshot.
"""

from __future__ import annotations

import numpy as np

from chronicle import schema as S
from lens.base import ChronicleReader, Firing

THRESHOLD = 3.0
MIN_MOVES = 500
MIN_WORLDS = 4   # fewer than this and the across-world spread is meaningless
FLAT_EPS = 1e-6  # below this, all four directions look identical — no choice to make


def compute(reader: ChronicleReader, rng: np.random.Generator | None = None) -> Firing:
    rng = rng or np.random.default_rng(0)

    rows = reader.sql(
        f"""
        select tick, world_id, a as chosen, b as mean_score, c as best_score,
               object as direction
        from {{events}} where event_type = {S.PERCEIVE}
        """
    ).fetchnumpy()

    if rows["chosen"].size == 0:
        # Two ways to get here, and naming only one of them sends the reader
        # looking in the wrong place. The common case is a deliberate choice —
        # PERCEIVE is a sampled-tier event, so a run written at `log_tier:
        # aggregated` carries none by design and this detector is simply not
        # measurable on it. That is not the same as the detector being silent.
        return _empty(
            "no PERCEIVE events: the run was logged below the sampled tier, "
            "or predates the gradient_ascent schema"
        )

    tick = rows["tick"].astype(np.int64)
    world = rows["world_id"].astype(np.int64)
    chosen = rows["chosen"].astype(np.float64)
    mean_score = rows["mean_score"].astype(np.float64)
    best_score = rows["best_score"].astype(np.float64)
    direction = rows["direction"].astype(np.int64)

    # Flat ground offers no gradient to ascend, and dividing by zero headroom
    # would manufacture enormous advantages from rounding noise. Excluding these
    # is not cherry-picking: a choice among four identical options carries no
    # information about whether the agent can see a gradient at all.
    headroom = best_score - mean_score
    usable = headroom > FLAT_EPS
    if usable.sum() < MIN_MOVES:
        return _empty(f"only {int(usable.sum())} moves on non-flat ground; need {MIN_MOVES}")

    advantage = (chosen[usable] - mean_score[usable]) / headroom[usable]
    world_u = world[usable]

    # Average within world, then take the spread across worlds. See the module
    # docstring: moves are not independent observations, worlds are.
    per_world = np.array(
        [advantage[world_u == w].mean() for w in np.unique(world_u)], dtype=np.float64
    )
    observed = float(per_world.mean())
    n_worlds = per_world.size
    if n_worlds < MIN_WORLDS:
        return _empty(f"only {n_worlds} worlds; need {MIN_WORLDS} to estimate a spread")

    # Standard error of the mean across worlds. The null's centre is 0 by
    # derivation, not by simulation, so this is the only quantity estimated.
    null_std = float(per_world.std(ddof=1) / np.sqrt(n_worlds))
    z = observed / max(null_std, 1e-12)
    n = int(advantage.size)

    took_best = float(np.isclose(chosen[usable], best_score[usable]).mean())
    counts = np.bincount(direction[usable], minlength=4).astype(np.float64)
    direction_bias = float(counts.max() / max(counts.sum(), 1.0))

    # Did selection improve it? Compare the founding cohort against the last
    # generation, both measured the same way. See the module docstring: a positive
    # magnitude alone is the policy working, not evolution happening.
    usable_tick = tick[usable]
    lo, hi = int(usable_tick.min()), int(usable_tick.max())
    span = max(hi - lo, 1)
    early = usable_tick <= lo + span // 10
    late = usable_tick >= hi - span // 10
    evolution: dict[str, float] = {}
    if early.sum() >= MIN_MOVES // 10 and late.sum() >= MIN_MOVES // 10:
        # Paired by world: each world is its own before/after, which removes
        # between-world landscape variation from the comparison entirely.
        deltas, firsts, lasts = [], [], []
        for w in np.unique(world_u):
            in_w = world_u == w
            e, l = in_w & early, in_w & late
            if e.sum() and l.sum():
                firsts.append(advantage[e].mean())
                lasts.append(advantage[l].mean())
                deltas.append(lasts[-1] - firsts[-1])
        if len(deltas) >= MIN_WORLDS:
            d = np.array(deltas)
            evolution = {
                "advantage_early": float(np.mean(firsts)),
                "advantage_late": float(np.mean(lasts)),
                "advantage_delta": float(d.mean()),
                "advantage_delta_z": float(d.mean() / max(d.std(ddof=1) / np.sqrt(d.size), 1e-12)),
                "worlds_improved": int((d > 0).sum()),
                "n_worlds": int(d.size),
            }

    return Firing(
        detector="gradient_ascent",
        magnitude=observed,
        null_mean=0.0,  # derived, not estimated
        null_std=null_std,
        effect_size=z,
        threshold=THRESHOLD,
        fired=bool(z > THRESHOLD and observed > 0.0),
        tick_range=(lo, hi),
        n_observations=int(n),
        detail={
            "mean_advantage": observed,
            "took_best_share": took_best,
            "flat_share": float(1.0 - usable.mean()),
            # If one compass direction dominates, the agents are not ascending a
            # gradient, they are drifting; 0.25 is unbiased.
            "direction_bias": direction_bias,
            "null": "blind-choice (exact, E=0)",
            **evolution,
        },
    )


def _empty(reason: str) -> Firing:
    return Firing(
        detector="gradient_ascent",
        magnitude=0.0, null_mean=0.0, null_std=0.0, effect_size=0.0,
        threshold=THRESHOLD, fired=False, tick_range=(0, 0), n_observations=0,
        detail={"skipped": reason},
    )
