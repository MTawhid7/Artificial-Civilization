"""`pop_stability` — is the population regulated, or merely lucky?

**Definition.** The regulation coefficient: the negative correlation between how
far population sits from its mean and what it does next. A regulated population
falls when it is high and rises when it is low, so the coefficient is positive.
An unregulated one has no such relationship and scores zero. Boundedness — never
extinct, never pinned against the array capacity, and non-monotonic — is checked
separately as a precondition, and reported in `detail`.

**Null: drift-only.** Surrogates take exactly the steps the real series took, in a
shuffled order. That preserves the volatility, the step-size distribution, the
start and end points, and removes only the correspondence between *where the
population is* and *what it does next*. It is the flattering alternative: if the
population merely happened to stay in range, the surrogates do too.

An earlier version of this detector scored boundedness directly and had to be
replaced. Shuffled surrogates turned out to stay bounded 95.5% of the time over a
200-sample window, so the statistic could not discriminate at all — the detector
would have fired on any series that did not crash, which is exactly the
"emergence theater" the detector suite exists to prevent.

Reads the aggregated tier only, so it survives even the most aggressive logging
setting (D-047).
"""

from __future__ import annotations

import numpy as np

from lens.base import ChronicleReader, Firing

THRESHOLD = 3.0
N_SURROGATES = 400
MIN_SAMPLES = 20


def compute(
    reader: ChronicleReader,
    capacity: int | None = None,
    rng: np.random.Generator | None = None,
) -> Firing:
    rng = rng or np.random.default_rng(0)
    if capacity is None:
        import yaml

        cfg = yaml.safe_load((reader.run_dir / "config.yaml").read_text())
        capacity = int(cfg["population"]["capacity"])

    rows = reader.sql(
        "select world_id, tick, population from {aggregate} order by world_id, tick"
    ).fetchnumpy()
    if rows["tick"].size == 0:
        return _empty("aggregate tier is empty")

    series = [
        rows["population"][rows["world_id"] == w].astype(np.float64)
        for w in np.unique(rows["world_id"])
    ]
    series = [s for s in series if s.size >= MIN_SAMPLES]
    if not series:
        return _empty("too few aggregate samples per world")

    observed = float(np.mean([_regulation(s) for s in series]))

    null = np.empty(N_SURROGATES, dtype=np.float64)
    for i in range(N_SURROGATES):
        null[i] = np.mean([_regulation(_shuffle_steps(s, rng)) for s in series])

    null_mean, null_std = float(null.mean()), float(null.std())
    z = (observed - null_mean) / max(null_std, 1e-12)

    bounded = [_is_bounded(s, capacity) for s in series]
    bounded_fraction = float(np.mean(bounded))

    return Firing(
        detector="pop_stability",
        magnitude=observed,
        null_mean=null_mean,
        null_std=null_std,
        effect_size=z,
        threshold=THRESHOLD,
        # Both conditions: regulation must be real *and* the worlds must actually
        # be in the viable band. A strongly regulated population regulated around
        # zero is still extinct.
        fired=bool(z > THRESHOLD and bounded_fraction > 0.9),
        tick_range=(int(rows["tick"].min()), int(rows["tick"].max())),
        n_observations=len(series),
        detail={
            "regulation_coefficient": observed,
            "bounded_fraction": bounded_fraction,
            "bounded_worlds": int(sum(bounded)),
            "n_worlds": len(series),
            "mean_population": float(np.mean([s[len(s) // 2:].mean() for s in series])),
            "capacity": capacity,
        },
    )


def _regulation(pop: np.ndarray) -> float:
    """-corr(deviation from mean, next change). Positive means self-correcting."""
    tail = pop[len(pop) // 2:]
    if tail.size < 4:
        return 0.0
    deviation = tail[:-1] - tail[:-1].mean()
    change = np.diff(tail)
    if deviation.std() < 1e-9 or change.std() < 1e-9:
        return 0.0
    return float(-np.corrcoef(deviation, change)[0, 1])


def _shuffle_steps(pop: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    steps = np.diff(pop)
    if steps.size == 0:
        return pop.copy()
    return pop[0] + np.concatenate([[0.0], np.cumsum(rng.permutation(steps))])


def _is_bounded(pop: np.ndarray, capacity: int) -> bool:
    """Never extinct, never pinned at capacity, and goes both ways."""
    tail = pop[len(pop) // 2:]
    if tail.size < 4 or tail.min() <= 0 or tail.mean() >= 0.95 * capacity:
        return False
    steps = np.diff(tail)
    up, down = (steps > 0).mean(), (steps < 0).mean()
    return bool(min(up, down) > 0.2)


def _empty(reason: str) -> Firing:
    return Firing(
        detector="pop_stability",
        magnitude=0.0, null_mean=0.0, null_std=0.0, effect_size=0.0,
        threshold=THRESHOLD, fired=False, tick_range=(0, 0), n_observations=0,
        detail={"skipped": reason},
    )
