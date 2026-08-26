"""The headroom precheck — D-065.

Calibration is the whole content of this module: thresholds that pass everything
are decoration. The three cases below are the three real mis-settings this
project has made, and the check has to reproduce the verdict that hindsight gave
each of them.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.config import resolve
from forge import viability

from conftest import TINY


def _verdict(worst_mean: float, peak: float, capacity: int) -> str:
    """The decision rule alone, without paying for a pilot run."""
    if worst_mean / capacity >= viability.MEAN_FAIL:
        return "fail"
    if peak / capacity >= viability.PEAK_WARN:
        return "warn"
    return "ok"


@pytest.mark.parametrize(
    "label, worst_mean, peak, capacity, expected",
    [
        # a2-wall, first attempt: 4 of 102 worlds pinned. Must be rejected.
        ("a2 @ 1200", 1198, 1200, 1200, "fail"),
        # a2-wall, shipped: nothing pinned, but 3 worlds clipped peaks for
        # 1.4-3.2% of frames — and that shipped with the clipping stated.
        ("a2 @ 2000", 1423, 2000, 2000, "warn"),
        # a1-gradient-ascent at patchiness 0.0: 11 of 80 world-instances pinned.
        ("a1 @ 900", 880, 900, 900, "fail"),
        # a2-wall as it should have been specified from the start.
        ("a2 @ 3000", 1423, 1900, 3000, "ok"),
    ],
)
def test_thresholds_reproduce_known_verdicts(label, worst_mean, peak, capacity, expected):
    assert _verdict(worst_mean, peak, capacity) == expected, label


def test_enforce_raises_on_fail():
    with pytest.raises(viability.HeadroomError) as exc:
        viability.enforce(
            {"verdict": "fail", "capacity": 1200, "worst_world_mean": 1198.0,
             "worst_world_mean_frac": 0.998, "peak_population": 1200.0,
             "peak_frac": 1.0, "suggested_capacity": 2400},
            "patchiness=0.6",
        )
    # The message has to say what to do, not only that something is wrong.
    assert "2400" in str(exc.value)
    assert "population.capacity" in str(exc.value)


def test_enforce_passes_warn_and_ok(capsys):
    for verdict in ("warn", "ok"):
        viability.enforce(
            {"verdict": verdict, "capacity": 2000, "worst_world_mean": 1423.0,
             "worst_world_mean_frac": 0.71, "peak_population": 2000.0,
             "peak_frac": 1.0, "suggested_capacity": 2900},
            verdict,
        )
    out = capsys.readouterr().out
    assert "WARN" in out and "ok" in out


def test_headroom_runs_and_reports(tmp_path):
    """End to end on a tiny config: the pilot must actually simulate and score."""
    cfg = resolve({**TINY, "run": {**TINY["run"], "aggregate_every": 5}},
                  source="tests/test_viability.py")
    report = viability.headroom(cfg, seed=3, worlds=2, out_root=tmp_path)

    assert report["verdict"] in {"ok", "warn", "fail"}
    assert report["capacity"] == TINY["population"]["capacity"]
    assert 0.0 <= report["worst_world_mean_frac"] <= 2.0
    assert report["pilot_worlds"] == 2
    assert report["ticks"] == TINY["run"]["ticks"]
    # The suggestion has to be actionable: strictly above what the pilot saw.
    assert report["suggested_capacity"] >= report["worst_world_mean"]


def test_pilot_does_not_pollute_the_corpus(tmp_path):
    """Pilots are thrown away and must not land beside real runs in corpus/runs."""
    cfg = resolve({**TINY, "run": {**TINY["run"], "aggregate_every": 5}},
                  source="tests/test_viability.py")
    viability.headroom(cfg, seed=4, worlds=2, out_root=tmp_path / "pilots")
    assert (tmp_path / "pilots" / "runs").exists()
    assert not (tmp_path / "runs").exists()
