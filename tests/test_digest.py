"""The digest contract — docs/06-data-model.md, schemas/digest.md.

The digest is what the Atlas reads and the Chronicle is not (D-013), which makes
it a published interface with a version number. These tests pin the three
properties that a future change could break without anything visibly failing: the
builder is a pure function of a run directory, quantization is lossy only within
its declared bound, and unimplemented fields stay declared-absent rather than
quietly acquiring plausible values.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.config import resolve
from digest import build as builder
from digest import schema as D
from forge.run import run

from conftest import TINY


@pytest.fixture(scope="module")
def digest_run(tmp_path_factory) -> "object":
    """One small run with enough aggregate frames to be worth digesting.

    TINY aggregates every 50 ticks over 200, which is four frames — enough for
    determinism, not enough for a series. This tightens the aggregate interval
    without touching anything else.
    """
    raw = {**TINY, "run": {**TINY["run"], "aggregate_every": 5, "checkpoint_every": 50}}
    cfg = resolve(raw, source="tests/test_digest.py")
    root = tmp_path_factory.mktemp("corpus")
    meta = run(cfg, seed=5, out_root=root, progress=False)
    return root / "runs" / meta["run_id"]


def test_digest_is_pure(digest_run):
    """Building twice from one run directory must give the same bytes.

    Not a cross-platform golden: the aggregate values underneath are float32 sums
    that differ in the last ulp between NEON and AVX (D-057). Purity is the
    property that makes a digest citable; cross-ISA identity is a settled
    question this must not reopen.
    """
    a = builder.build(digest_run)
    b = builder.build(digest_run)
    assert a["digest_hash"] == b["digest_hash"]
    assert D.canonical_json(a) == D.canonical_json(b)


def test_digest_roundtrip_within_one_bin(digest_run):
    d = builder.build(digest_run)
    for name, _ in D.SERIES:
        field = d["series"][name]
        back = D.decode(field)
        assert back.shape == tuple(field["shape"])
        assert back.min() >= field["min"] - 1e-9
        assert back.max() <= field["max"] + 1e-9
        # Every stored value must sit within half a bin of a representable level,
        # which is what makes the loss bounded rather than merely small.
        span = D.bin_width(field)
        if span > 0:
            offsets = (back - field["min"]) / span
            assert np.allclose(offsets, np.rint(offsets))


def test_population_is_stored_exactly(digest_run):
    """The strip's bar height is population, and a 1,200-slot capacity spread
    over 255 levels would visibly step. It is `u2` for that reason."""
    d = builder.build(digest_run)
    field = d["series"]["population"]
    assert field["bits"] == 16
    assert field["min"] == 0.0 and field["max"] == float(d["capacity"])
    back = D.decode(field)
    assert np.allclose(back, np.rint(back), atol=0.05)


def test_quantization_range_is_run_wide(digest_run):
    """One range for every world, or the wall compares nothing.

    Normalizing each world to its own extremes would rescale every strip
    independently and manufacture a similarity that is not in the data. The
    encoded form has exactly one min/max per series, which is the structural
    guarantee that it cannot happen.
    """
    d = builder.build(digest_run)
    for name, _ in D.SERIES:
        field = d["series"][name]
        assert isinstance(field["min"], float) and isinstance(field["max"], float)
        assert len(field["shape"]) == 2 and field["shape"][0] == d["n_worlds"]


def test_digest_declares_reserved(digest_run):
    """Absent fields are named as absent.

    docs/06-data-model.md specifies territory, belief layers, tech level and the
    rest. None has an S0 meaning. Filling them with plausible zeros would make a
    subset indistinguishable from a complete digest, and the Atlas would render
    them as facts.
    """
    d = builder.build(digest_run)
    for name in D.RESERVED:
        assert name in d["reserved"]
        assert name not in d["series"]
        assert name not in d.get("rasters", {}).get("layers", {})


def test_digest_survives_the_aggregated_tier(tmp_path):
    """A run with no per-agent events at all must still digest completely.

    D-047's tiering claim, as a test. The wall run logs at `aggregated`, so if
    this ever stops holding the picture stops being buildable.
    """
    raw = {
        **TINY,
        "run": {**TINY["run"], "aggregate_every": 5, "checkpoint_every": 50,
                "log_tier": "aggregated"},
    }
    cfg = resolve(raw, source="tests/test_digest.py")
    meta = run(cfg, seed=6, out_root=tmp_path, progress=False)
    d = builder.build(tmp_path / "runs" / meta["run_id"])
    assert d["frames"]["n"] > 0
    assert D.decode(d["series"]["population"]).max() > 0


def test_digest_has_rasters_from_checkpoints(digest_run):
    d = builder.build(digest_run)
    r = d["rasters"]
    assert r["ticks"], "checkpoints are the snapshot tier the map view reads"
    size = r["size"][0]
    assert TINY["world"]["grid"] % size == 0, "blocks must divide the grid exactly"
    for name in D.RASTER_LAYERS:
        arr = D.decode(r["layers"][name])
        assert arr.shape == (len(r["ticks"]), len(r["worlds"]), size, size)


def test_digest_markers_come_from_the_detector(digest_run):
    """Chapter markers are detector output, never hand-authored.

    docs/09-visualization.md calls this the best reuse in the design; the test is
    what keeps it true when someone is tempted to hard-code an interesting tick.
    """
    d = builder.build(digest_run)
    assert "collapse" in d["detectors"]
    for m in d["markers"]:
        assert m["detector"] == "collapse"
        assert m["world"] in d["world_ids"]


def test_raster_size_divides_the_grid():
    for grid in (24, 48, 64, 96, 128):
        assert grid % builder._raster_size(grid) == 0
        assert builder._raster_size(grid) <= min(D.RASTER_SIZE, grid)
