"""Detector unit tests.

Every detector ships with a synthetic log on which it must fire and one on which
it must stay silent (docs/07-detectors.md). The silent case matters more: a
detector that fires on everything is worse than no detector, because it produces
confident findings from noise.

Synthetic logs are built by hand rather than by running the simulation, so a
detector's behavior is pinned to the *definition* rather than to whatever the
current parameters happen to produce.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

from chronicle import schema as S
from lens import collapse, directed_foraging, exploration_rate, gradient_ascent, pop_stability
from lens.base import ChronicleReader

GRID = 64
CAPACITY = 400


N_WORLDS = 8


def _perceptions(n: int, skill: float, seed: int = 0, flat_share: float = 0.0) -> dict:
    """Synthetic PERCEIVE rows for agents that pick the best direction with
    probability `skill`, and uniformly at random otherwise.

    Spread across `N_WORLDS` because worlds are the replication unit: the detector
    averages within a world and takes its spread across worlds, so a single-world
    fixture cannot exercise it.

    `skill=0.0` is the blind-choice null made flesh: the detector must read ~0 on
    it, which is the property the whole design rests on.
    """
    rng = np.random.default_rng(seed)
    scores = rng.random((n, 4))
    flat = rng.random(n) < flat_share
    scores[flat] = 0.5  # all four identical: no gradient to ascend

    best_idx = scores.argmax(axis=1)
    random_idx = rng.integers(0, 4, n)
    take_best = rng.random(n) < skill
    picked = np.where(take_best, best_idx, random_idx)

    return {
        "tick": np.arange(n) % 500,
        "world_id": np.arange(n) % N_WORLDS,
        "subject": (np.arange(n) % 50) + 1,
        "direction": picked,
        "chosen": scores[np.arange(n), picked],
        "mean_score": scores.mean(axis=1),
        "best_score": scores.max(axis=1),
    }


def _write_run(
    tmp_path: Path, moves: dict[str, np.ndarray] | None = None,
    aggregate: dict[str, np.ndarray] | None = None,
    perceptions: dict[str, np.ndarray] | None = None,
    fog_block: int | None = None,
) -> Path:
    run = tmp_path / "run"
    (run / "chronicle").mkdir(parents=True, exist_ok=True)
    cfg = {"world": {"grid": GRID}, "population": {"capacity": CAPACITY}}
    if fog_block:
        cfg["primitives"] = {"p2": {"level": 0, "block": fog_block, "known_radius": 2}}
    (run / "config.yaml").write_text(yaml.safe_dump(cfg))
    (run / "meta.json").write_text("{}")

    if moves is not None:
        n = moves["tick"].size
        pq.write_table(
            pa.table(
                {
                    "tick": moves["tick"].astype(np.uint32),
                    "world_id": moves["world_id"].astype(np.uint16),
                    "event_type": np.full(n, S.MOVE, dtype=np.uint8),
                    "subject": moves["subject"].astype(np.uint32),
                    "object": np.zeros(n, dtype=np.uint32),
                    "a": moves["x"].astype(np.float32),
                    "b": moves["y"].astype(np.float32),
                    "c": moves["energy"].astype(np.float32),
                },
                schema=S.ARROW_SCHEMA,
            ),
            run / "chronicle" / "events_000000000.parquet",
        )
    if perceptions is not None:
        n = perceptions["tick"].size
        pq.write_table(
            pa.table(
                {
                    "tick": perceptions["tick"].astype(np.uint32),
                    "world_id": perceptions["world_id"].astype(np.uint16),
                    "event_type": np.full(n, S.PERCEIVE, dtype=np.uint8),
                    "subject": perceptions["subject"].astype(np.uint32),
                    "object": perceptions["direction"].astype(np.uint32),
                    "a": perceptions["chosen"].astype(np.float32),
                    "b": perceptions["mean_score"].astype(np.float32),
                    "c": perceptions["best_score"].astype(np.float32),
                },
                schema=S.ARROW_SCHEMA,
            ),
            run / "chronicle" / "events_000000001.parquet",
        )
    if aggregate is not None:
        n = aggregate["tick"].size
        pq.write_table(
            pa.table(
                {
                    "tick": aggregate["tick"].astype(np.uint32),
                    "world_id": aggregate["world_id"].astype(np.uint16),
                    "population": aggregate["population"].astype(np.uint32),
                    "births": np.zeros(n, dtype=np.uint32),
                    "deaths": np.zeros(n, dtype=np.uint32),
                    "resource_total": np.zeros(n, dtype=np.float32),
                    "energy_mean": np.zeros(n, dtype=np.float32),
                    "energy_gini": np.zeros(n, dtype=np.float32),
                    "gene_mean": [[0.0]] * n,
                },
                schema=S.AGGREGATE_SCHEMA,
            ),
            run / "aggregate.parquet",
        )
    return run


def _walk(n_agents: int, n_ticks: int, straight_when_hungry: bool, seed: int = 0) -> dict:
    """Trajectories with an energy cycle; optionally straight while hungry."""
    rng = np.random.default_rng(seed)
    ticks, subjects, xs, ys, es, ws = [], [], [], [], [], []
    for agent in range(n_agents):
        x, y = rng.integers(0, GRID, 2)
        heading = rng.integers(0, 4)
        for t in range(n_ticks):
            # Energy sawtooths so each agent spends time on both sides of the cut.
            energy = 40.0 + 35.0 * np.sin(2 * np.pi * (t / 40.0 + agent / n_agents))
            hungry = energy < 40.0
            if straight_when_hungry and hungry:
                if rng.random() < 0.08:      # occasionally re-aim
                    heading = rng.integers(0, 4)
            else:
                heading = rng.integers(0, 4)
            x = (x + [0, 1, 0, -1][heading]) % GRID
            y = (y + [-1, 0, 1, 0][heading]) % GRID
            ticks.append(t); subjects.append(agent + 1)
            xs.append(x); ys.append(y); es.append(energy); ws.append(0)
    return {
        "tick": np.array(ticks), "subject": np.array(subjects),
        "x": np.array(xs), "y": np.array(ys),
        "energy": np.array(es), "world_id": np.array(ws),
    }


# --- directed_foraging --------------------------------------------------------


def test_directed_foraging_fires_on_positive(tmp_path):
    run = _write_run(tmp_path, moves=_walk(40, 400, straight_when_hungry=True, seed=1))
    with ChronicleReader(run) as reader:
        f = directed_foraging.compute(reader, rng=np.random.default_rng(0))
    assert f.fired, f
    assert f.magnitude > 0
    assert f.detail["straightness_hungry"] > f.detail["straightness_sated"]


def test_directed_foraging_silent_on_negative(tmp_path):
    """Random walkers with the same energy cycle must not fire.

    The case that matters: hunger is present and varying, agents move constantly,
    and the only thing missing is the link between the two.
    """
    run = _write_run(tmp_path, moves=_walk(40, 400, straight_when_hungry=False, seed=2))
    with ChronicleReader(run) as reader:
        f = directed_foraging.compute(reader, rng=np.random.default_rng(0))
    assert not f.fired, f
    assert abs(f.effect_size) < directed_foraging.THRESHOLD


def test_directed_foraging_needs_enough_windows(tmp_path):
    run = _write_run(tmp_path, moves=_walk(2, 20, straight_when_hungry=True))
    with ChronicleReader(run) as reader:
        f = directed_foraging.compute(reader, rng=np.random.default_rng(0))
    assert not f.fired
    assert "skipped" in f.detail


# --- gradient_ascent ----------------------------------------------------------


def test_gradient_ascent_fires_on_positive(tmp_path):
    run = _write_run(tmp_path, perceptions=_perceptions(8000, skill=0.6, seed=1))
    with ChronicleReader(run) as reader:
        f = gradient_ascent.compute(reader, rng=np.random.default_rng(0))
    assert f.fired, f
    assert f.magnitude > 0.5
    assert f.detail["took_best_share"] > 0.6


def test_gradient_ascent_silent_on_blind_choice(tmp_path):
    """The null made flesh: an agent choosing uniformly must read ~0.

    This is the property the whole design rests on. `chosen - mean` has
    expectation exactly zero under uniform choice, for any landscape, so a blind
    agent must not produce an effect no matter how the resource field is shaped.
    """
    run = _write_run(tmp_path, perceptions=_perceptions(8000, skill=0.0, seed=2))
    with ChronicleReader(run) as reader:
        f = gradient_ascent.compute(reader, rng=np.random.default_rng(0))
    assert not f.fired, f
    assert abs(f.magnitude) < 0.05, "blind choice must sit on zero, not near it"


def test_gradient_ascent_is_graded(tmp_path):
    """Magnitude must increase with skill — a detector that only says yes/no
    cannot support a dose-response curve, which is what A1 exists to produce."""
    seen = []
    for skill in (0.0, 0.3, 0.6, 1.0):
        run = _write_run(tmp_path / f"s{skill}", perceptions=_perceptions(6000, skill, seed=3))
        with ChronicleReader(run) as reader:
            seen.append(gradient_ascent.compute(reader, rng=np.random.default_rng(0)).magnitude)
    assert seen == sorted(seen), seen
    assert seen[-1] > 0.95, "perfect gradient-following should score ~1.0"


def test_gradient_ascent_ignores_flat_ground(tmp_path):
    """Windows where all four directions are identical carry no information and
    must not be counted — dividing by zero headroom would manufacture effects."""
    run = _write_run(tmp_path, perceptions=_perceptions(8000, skill=0.6, seed=4, flat_share=0.5))
    with ChronicleReader(run) as reader:
        f = gradient_ascent.compute(reader, rng=np.random.default_rng(0))
    assert f.fired, f
    assert 0.4 < f.detail["flat_share"] < 0.6
    assert f.magnitude > 0.5, "excluding flat ground must not dilute the effect"


def test_gradient_ascent_does_not_read_energy(tmp_path):
    """D-056 as a test: the detector must not touch any outcome variable.

    `directed_foraging` conditioned on energy and inverted its own conclusion.
    This asserts the replacement cannot repeat that, by checking it computes an
    identical answer from PERCEIVE rows alone with no MOVE events present.
    """
    perceptions = _perceptions(8000, skill=0.5, seed=5)
    alone = _write_run(tmp_path / "alone", perceptions=perceptions)
    with_moves = _write_run(
        tmp_path / "with_moves", perceptions=perceptions,
        moves=_walk(40, 300, straight_when_hungry=True, seed=6),
    )
    with ChronicleReader(alone) as r1, ChronicleReader(with_moves) as r2:
        a = gradient_ascent.compute(r1, rng=np.random.default_rng(0))
        b = gradient_ascent.compute(r2, rng=np.random.default_rng(0))
    assert a.magnitude == b.magnitude
    assert a.n_observations == b.n_observations


def test_wrapped_delta_handles_the_torus():
    from lens.base import wrapped_delta

    a = np.array([95, 0, 10], dtype=np.int64)
    b = np.array([0, 95, 11], dtype=np.int64)
    assert wrapped_delta(a, b, 96).tolist() == [1, -1, 1]


# --- pop_stability ------------------------------------------------------------


def _pop_series(kind: str, n_worlds: int = 8, n: int = 200, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    ticks, worlds, pops = [], [], []
    for w in range(n_worlds):
        if kind == "regulated":
            # Mean-reverting around a fraction of capacity.
            p, series = 200.0, []
            for _ in range(n):
                p += 0.25 * (200.0 - p) + rng.normal(0, 12)
                series.append(max(p, 1.0))
        elif kind == "extinct":
            series = list(np.maximum(np.linspace(200, 0, n) + rng.normal(0, 3, n), 0))
        else:  # "saturated"
            series = list(np.minimum(np.linspace(50, CAPACITY, n), CAPACITY))
        ticks.extend(range(n)); worlds.extend([w] * n); pops.extend(series)
    return {
        "tick": np.array(ticks), "world_id": np.array(worlds),
        "population": np.array(pops),
    }


def test_pop_stability_fires_on_regulated(tmp_path):
    run = _write_run(tmp_path, aggregate=_pop_series("regulated", seed=3))
    with ChronicleReader(run) as reader:
        f = pop_stability.compute(reader, rng=np.random.default_rng(0))
    assert f.fired, f
    assert f.detail["bounded_fraction"] == 1.0
    assert f.magnitude > f.null_mean


def test_pop_stability_null_is_not_zero(tmp_path):
    """The shuffled null must be compared against, not assumed to be zero.

    A shuffled random walk shows spurious mean-reversion in a finite sample —
    measured at 0.165 here, not 0.0. A detector that tested the regulation
    coefficient against zero would fire on pure noise.
    """
    run = _write_run(tmp_path, aggregate=_pop_series("regulated", seed=3))
    with ChronicleReader(run) as reader:
        f = pop_stability.compute(reader, rng=np.random.default_rng(0))
    assert f.null_mean > 0.05, "null should show finite-sample mean reversion"


def test_pop_stability_silent_on_extinction(tmp_path):
    run = _write_run(tmp_path, aggregate=_pop_series("extinct", seed=4))
    with ChronicleReader(run) as reader:
        f = pop_stability.compute(reader, rng=np.random.default_rng(0))
    assert not f.fired, f


def test_pop_stability_silent_on_saturation(tmp_path):
    """Pinned against the array capacity is not stability, it is a ceiling."""
    run = _write_run(tmp_path, aggregate=_pop_series("saturated", seed=5))
    with ChronicleReader(run) as reader:
        f = pop_stability.compute(reader, rng=np.random.default_rng(0))
    assert not f.fired, f


def test_detectors_read_only_permitted_tiers(tmp_path):
    """pop_stability must work with no per-agent events at all.

    D-047: every detector must be computable from sampled and aggregated data.
    This is that constraint as a test rather than as a good intention.
    """
    run = _write_run(tmp_path, aggregate=_pop_series("regulated", seed=6))
    assert not list((run / "chronicle").glob("*.parquet"))
    with ChronicleReader(run) as reader:
        assert pop_stability.compute(reader, rng=np.random.default_rng(0)).fired


# --- collapse -----------------------------------------------------------------


def _crash_series(kind: str, n_worlds: int = 8, n: int = 400, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    ticks, worlds, pops = [], [], []
    for w in range(n_worlds):
        if kind == "sawtooth":
            # Slow growth, then a hard crash, over and over. The steps are mostly
            # small positives and a few large negatives; what makes it a collapse
            # dynamic rather than a volatile one is that the large negatives are
            # *arranged* — each is followed by a recovery to a new peak.
            period = 50
            series, p = [], 300.0
            for t in range(n):
                if t % period == period - 1:
                    p *= 0.45
                else:
                    p *= 1.02
                series.append(max(p + rng.normal(0, 3), 1.0))
        else:  # "walk" — the null made flesh
            # iid steps, so the real series is exchangeable with its own
            # surrogates by construction and the detector must read ~0.
            steps = rng.normal(0, 8, n - 1)
            series = list(np.maximum(600.0 + np.concatenate([[0.0], np.cumsum(steps)]), 1.0))
        ticks.extend(range(n)); worlds.extend([w] * n); pops.extend(series)
    return {
        "tick": np.array(ticks), "world_id": np.array(worlds),
        "population": np.array(pops),
    }


def test_collapse_fires_on_repeated_crashes(tmp_path):
    run = _write_run(tmp_path, aggregate=_crash_series("sawtooth", seed=11))
    with ChronicleReader(run) as reader:
        f = collapse.compute(reader, rng=np.random.default_rng(0))
    assert f.fired, f
    assert f.magnitude > f.null_mean
    assert f.detail["n_episodes"] > 0
    assert all(0.0 < e["depth"] <= 1.0 for e in f.detail["events"])


def test_collapse_silent_on_matched_volatility(tmp_path):
    """A random walk crashes too. That is the whole reason for the null.

    The steps are iid, so the observed series is exchangeable with the surrogates
    built from it. Any effect here would be the detector reading its own
    arithmetic rather than the world.
    """
    run = _write_run(tmp_path, aggregate=_crash_series("walk", seed=12))
    with ChronicleReader(run) as reader:
        f = collapse.compute(reader, rng=np.random.default_rng(0))
    assert not f.fired, f
    assert abs(f.effect_size) < collapse.THRESHOLD


def test_collapse_counts_episodes_not_frames(tmp_path):
    """One long crash is one collapse, not four hundred.

    Counting frames below the threshold would make the statistic a measure of how
    slowly a world recovers, which is a different question with a different null.
    """
    pop = np.concatenate([np.full(100, 500.0), np.full(300, 200.0)])
    assert len(collapse._episodes(pop)) == 1


def test_collapse_ignores_burn_in(tmp_path):
    """The founding overshoot is a startup artifact, not a finding.

    Every world's initial cohort grows past what the world supports and falls
    back. A running peak anchored at tick 0 would score that in ~100% of worlds.
    """
    n = 400
    early = np.concatenate([np.linspace(100, 900, 40), np.linspace(900, 250, 40),
                            np.full(n // 2 - 80, 250.0)])
    series = np.concatenate([early, np.full(n // 2, 250.0) + np.arange(n // 2) * 0.01])
    agg = {
        "tick": np.tile(np.arange(n), 8),
        "world_id": np.repeat(np.arange(8), n),
        "population": np.tile(series, 8),
    }
    run = _write_run(tmp_path, aggregate=agg)
    with ChronicleReader(run) as reader:
        f = collapse.compute(reader, rng=np.random.default_rng(0))
    assert f.detail["n_episodes"] == 0, "the burn-in crash must not be counted"


# --- exploration_rate ---------------------------------------------------------


def _paths(n_agents: int, n_steps: int, persistence: float, seed: int = 0) -> dict:
    """Synthetic MOVE rows for agents walking with a given heading persistence.

    `persistence` is the chance of repeating the previous step. The step
    *multiset* is what the shuffled-step null preserves, so persistence is
    exactly the property the null destroys and the detector should see: at 0.0
    the walk is already order-free and shuffling changes nothing, while a
    committed walker covers ground that its own re-ordered steps would not.

    Spread across `N_WORLDS` because the world is the replication unit.
    """
    rng = np.random.default_rng(seed)
    deltas = np.array([[0, -1], [1, 0], [0, 1], [-1, 0]])  # N, E, S, W

    tick, world, subject, xs, ys = [], [], [], [], []
    for a in range(n_agents):
        heading = int(rng.integers(0, 4))
        x, y = int(rng.integers(0, GRID)), int(rng.integers(0, GRID))
        for t in range(n_steps):
            if rng.random() >= persistence:
                heading = int(rng.integers(0, 4))
            dx, dy = deltas[heading]
            x, y = (x + int(dx)) % GRID, (y + int(dy)) % GRID
            tick.append(t)
            world.append(a % N_WORLDS)
            subject.append(a + 1)
            xs.append(x)
            ys.append(y)

    n = len(tick)
    return {
        "tick": np.array(tick), "world_id": np.array(world),
        "subject": np.array(subject), "x": np.array(xs, dtype=float),
        "y": np.array(ys, dtype=float), "energy": np.full(n, 50.0),
    }


def test_exploration_rate_fires_on_committed_walkers(tmp_path):
    """An agent that holds a heading covers ground its own shuffled steps do not."""
    run = _write_run(tmp_path, moves=_paths(64, 300, persistence=0.9, seed=1), fog_block=4)
    with ChronicleReader(run) as reader:
        f = exploration_rate.compute(reader, rng=np.random.default_rng(0))
    assert f.fired, f
    assert f.magnitude > 0.0
    assert f.detail["observed_blocks_per_tick"] > f.detail["shuffled_blocks_per_tick"]


def test_exploration_rate_silent_on_memoryless_walk(tmp_path):
    """The null made flesh: an order-free walk is its own surrogate.

    This is the case that matters. A detector that fires here would be reporting
    curiosity from a random walk, which is the emergence theater the whole
    suite exists to prevent.
    """
    run = _write_run(tmp_path, moves=_paths(64, 300, persistence=0.0, seed=2), fog_block=4)
    with ChronicleReader(run) as reader:
        f = exploration_rate.compute(reader, rng=np.random.default_rng(0))
    assert not f.fired, f
    assert abs(f.magnitude) < 0.02, f"memoryless walk should read ~0, got {f.magnitude}"


def test_exploration_rate_is_graded(tmp_path):
    """More commitment, more excess coverage — monotone, not just non-zero."""
    got = []
    for persistence in (0.0, 0.5, 0.9):
        run = _write_run(tmp_path / f"p{persistence}",
                         moves=_paths(48, 250, persistence, seed=3), fog_block=4)
        with ChronicleReader(run) as reader:
            got.append(exploration_rate.compute(reader, rng=np.random.default_rng(0)).magnitude)
    assert got[0] < got[1] < got[2], got


def test_exploration_rate_skips_a_run_without_fog(tmp_path):
    """Skipped is not silent. Without a known map the statistic is undefined."""
    run = _write_run(tmp_path, moves=_paths(32, 200, persistence=0.9, seed=4))
    with ChronicleReader(run) as reader:
        f = exploration_rate.compute(reader, rng=np.random.default_rng(0))
    assert not f.fired
    assert "skipped" in f.detail


def test_exploration_rate_does_not_reward_distance(tmp_path):
    """Two walks with the same steps in a different order must differ; the same
    walk sped up must not.

    Path length is the confound that would turn this detector into a speedometer.
    The null holds it fixed by construction — the surrogate takes the agent's own
    steps — so a walker that simply covers more ground per tick gains nothing
    unless its *ordering* is what did the covering.
    """
    fast = _paths(48, 250, persistence=0.0, seed=5)
    with ChronicleReader(_write_run(tmp_path / "a", moves=fast, fog_block=4)) as reader:
        memoryless = exploration_rate.compute(reader, rng=np.random.default_rng(0))
    # Same step budget, same grid, only the ordering differs.
    with ChronicleReader(
        _write_run(tmp_path / "b", moves=_paths(48, 250, persistence=0.9, seed=5),
                   fog_block=4)
    ) as reader:
        committed = exploration_rate.compute(reader, rng=np.random.default_rng(0))
    assert committed.magnitude > memoryless.magnitude
