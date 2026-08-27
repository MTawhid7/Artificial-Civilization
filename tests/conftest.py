"""Shared fixtures. Runs here are deliberately tiny — determinism is a property
of the machinery, not of scale, and a gate that takes ten minutes gets skipped."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.config import resolve

GOLDEN_DIR = Path(__file__).parent / "golden"

TINY = {
    "world": {"grid": 24, "patchiness": 0.6, "regrowth": 0.05},
    "primitives": {"p1": {"level": 0}, "p10": {"level": 0, "rate": 0.0}},
    "intelligence": {"stage": "S0", "genome_size": 8, "view_radius": 2},
    "population": {"initial": 40, "capacity": 120, "mutation_rate": 0.05,
                   "mutation_scale": 0.05},
    "agent": {"metabolism": 0.5, "max_age": 200, "birth_energy": 15.0,
              "gather_efficiency": 4.0, "start_energy": 40.0},
    "run": {"worlds": 4, "ticks": 200, "checkpoint_every": 25,
            "aggregate_every": 50, "log_tier": "sampled", "sample_rate": 8,
            "shard_ticks": 100},
}


# The same world with a brain. Deliberately identical outside `intelligence`:
# every draw from the `generator` stream then matches TINY's, so the two
# fixtures are the same landscape with the same founding cohort and any
# difference between them is the policy (D-072).
#
# hidden 16 and 4 lineages rather than the documented 48 and 8 for the same
# reason the rest of TINY is small — determinism is a property of the machinery,
# not of scale, and a gate that takes ten minutes gets skipped. `speciation_rate`
# is 25x the production value so a 200-tick test actually founds lineages.
TINY_S1 = {
    **TINY,
    "intelligence": {**TINY["intelligence"], "stage": "S1", "hidden": 16,
                     "lineages": 4, "speciation_rate": 0.05,
                     "weight_mutation_scale": 0.08},
}


@pytest.fixture
def tiny_config():
    return resolve(TINY, source="tests/conftest.py::TINY")


# The same again with P2 at L0. Fog is opt-in, so TINY_S1 stays fog-free and
# this is a third configuration rather than a change to the second — which keeps
# `tiny_s1.json` meaningful as "S1 without fog" and gives the fog path a golden
# of its own. `block: 4` on a 24 grid is a 6x6 known map per agent.
TINY_FOG = {
    **TINY_S1,
    "primitives": {**TINY_S1["primitives"], "p2": {"level": 0, "block": 4,
                                                   "known_radius": 2}},
}


@pytest.fixture
def tiny_s1_config():
    return resolve(TINY_S1, source="tests/conftest.py::TINY_S1")


@pytest.fixture
def tiny_fog_config():
    return resolve(TINY_FOG, source="tests/conftest.py::TINY_FOG")


@pytest.fixture
def corpus(tmp_path) -> Path:
    return tmp_path / "corpus"
