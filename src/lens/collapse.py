"""`collapse` — do populations crash more often than their own volatility explains?

**Definition.** A collapse is a *drawdown episode*: population falls more than
`DROP` below its running peak, and the episode ends when a new peak is reached.
The statistic is episodes per 1,000 frames, computed **per world and then averaged
over worlds** — the world is the replication unit, and pooling within-world
observations as if they were independent is what once inflated `gradient_ascent`'s
z from 4.93 to 90.8 (D-058).

**Null: shuffled steps.** Surrogates take exactly the steps the real series took,
in a shuffled order — same volatility, same step-size distribution, same start and
end points, and no correspondence between where the population is and what it does
next. This is the flattering alternative, and it is the only honest way to ask the
question: a >35% drawdown is not rare. Measured across the 480 world-instances of
the A1 sweep, roughly 90% show one. A detector that counted them without a null
would fire on essentially every run and mean nothing.

**The expected sign is not obvious, and both answers are informative.** A regulated
population reverts to its mean, which *suppresses* deep drawdowns relative to a
random walk with the same steps — so a strongly negative z is the signature of
regulation, not a failed detector, and it is consistent with `pop_stability`
firing. A positive z would mean crashes cluster beyond what volatility alone
produces, which is what a real collapse dynamic looks like.

**Burn-in is excluded.** The founding cohort overshoots and crashes in the first
few hundred ticks of every world. A running peak starting at tick 0 would count
that transient as a collapse almost everywhere, turning a startup artifact into a
finding. The post-burn-in tail is scored, matching `pop_stability`.

Reads the aggregated tier only, so it survives the most aggressive logging setting
(D-047). `detail["events"]` carries the individual episodes, which is what the viz
digest renders as markers — the detector suite doubling as the narrative UI
(docs/09-visualization.md). Those marks are *drawdowns*, and the strip's legend
says so; whether there are more of them than chance is what the z answers.
"""

from __future__ import annotations

import numpy as np

from lens.base import ChronicleReader, Firing

THRESHOLD = 3.0
DROP = 0.35          # fraction below the running peak that counts as a collapse
N_SURROGATES = 400
MIN_SAMPLES = 20
MAX_EVENTS = 4000    # cap on what goes into detail; the statistic uses all of them


def compute(
    reader: ChronicleReader,
    rng: np.random.Generator | None = None,
) -> Firing:
    rng = rng or np.random.default_rng(0)

    rows = reader.sql(
        "select world_id, tick, population from {aggregate} order by world_id, tick"
    ).fetchnumpy()
    if rows["tick"].size == 0:
        return _empty("aggregate tier is empty")

    world_ids = np.unique(rows["world_id"])
    series, ticks, kept = [], [], []
    for w in world_ids:
        m = rows["world_id"] == w
        pop = rows["population"][m].astype(np.float64)
        if pop.size < MIN_SAMPLES:
            continue
        cut = pop.size // 2  # burn-in
        series.append(pop[cut:])
        ticks.append(rows["tick"][m][cut:])
        kept.append(int(w))
    if not series:
        return _empty("too few aggregate samples per world")

    per_world = np.array([_rate(s) for s in series])
    observed = float(per_world.mean())

    null = np.empty(N_SURROGATES, dtype=np.float64)
    for i in range(N_SURROGATES):
        null[i] = float(np.mean([_rate(_shuffle_steps(s, rng)) for s in series]))
    null_mean, null_std = float(null.mean()), float(null.std())
    z = (observed - null_mean) / max(null_std, 1e-12)

    events = []
    for w, pop, tk in zip(kept, series, ticks):
        for start, depth in _episodes(pop):
            events.append({"world": w, "tick": int(tk[start]), "depth": round(float(depth), 4)})
    events.sort(key=lambda e: (e["world"], e["tick"]))

    return Firing(
        detector="collapse",
        magnitude=observed,
        null_mean=null_mean,
        null_std=null_std,
        effect_size=z,
        threshold=THRESHOLD,
        fired=bool(z > THRESHOLD),
        tick_range=(int(min(t[0] for t in ticks)), int(max(t[-1] for t in ticks))),
        n_observations=len(series),
        detail={
            "episodes_per_1000_frames": observed,
            "drop_threshold": DROP,
            "n_episodes": len(events),
            "worlds_with_any": int((per_world > 0).sum()),
            "n_worlds": len(series),
            "deepest": round(float(max((e["depth"] for e in events), default=0.0)), 4),
            # Whole episodes, for the digest to place as markers. Trimmed only so
            # a pathological run cannot write a 100 MB results.json; the statistic
            # above always uses every episode.
            "events": events[:MAX_EVENTS],
            "events_truncated": len(events) > MAX_EVENTS,
        },
    )


def _episodes(pop: np.ndarray) -> list[tuple[int, float]]:
    """(start index, max depth) for each drawdown episode below `DROP`.

    An episode opens the first frame the drawdown crosses `DROP` and closes when
    population makes a new peak. Counting frames instead would score one long
    crash as hundreds of collapses, which would make the statistic a measure of
    how slowly a world recovers rather than how often it falls.
    """
    peak = np.maximum.accumulate(pop)
    drawdown = 1.0 - pop / np.maximum(peak, 1e-9)

    out: list[tuple[int, float]] = []
    open_at: int | None = None
    deepest = 0.0
    for i, dd in enumerate(drawdown):
        if dd >= DROP and open_at is None:
            open_at, deepest = i, float(dd)
        elif open_at is not None:
            deepest = max(deepest, float(dd))
            if dd <= 0.0:  # new peak: the episode is over
                out.append((open_at, deepest))
                open_at = None
    if open_at is not None:
        out.append((open_at, deepest))
    return out


def _rate(pop: np.ndarray) -> float:
    """Collapse episodes per 1,000 frames."""
    if pop.size == 0:
        return 0.0
    return 1000.0 * len(_episodes(pop)) / pop.size


def _shuffle_steps(pop: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """The same steps in a shuffled order — `pop_stability`'s null, reused.

    Deliberately the identical surrogate: two detectors reading the same series
    should disagree about the world, not about what chance looks like.
    """
    steps = np.diff(pop)
    if steps.size == 0:
        return pop.copy()
    return pop[0] + np.concatenate([[0.0], np.cumsum(rng.permutation(steps))])


def _empty(reason: str) -> Firing:
    return Firing(
        detector="collapse",
        magnitude=0.0, null_mean=0.0, null_std=0.0, effect_size=0.0,
        threshold=THRESHOLD, fired=False, tick_range=(0, 0), n_observations=0,
        detail={"skipped": reason, "events": []},
    )
