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
from lens import directed_foraging, pop_stability
from lens.base import ChronicleReader

GRID = 64
CAPACITY = 400


def _write_run(
    tmp_path: Path, moves: dict[str, np.ndarray] | None = None,
    aggregate: dict[str, np.ndarray] | None = None,
) -> Path:
    run = tmp_path / "run"
    (run / "chronicle").mkdir(parents=True, exist_ok=True)
    (run / "config.yaml").write_text(
        yaml.safe_dump({"world": {"grid": GRID}, "population": {"capacity": CAPACITY}})
    )
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
