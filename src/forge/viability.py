"""The headroom precheck — does the array regulate this world, or does the world?

D-065. `population.capacity` has been mis-set in every experiment that has run:
`a1-patchiness` at 500 put its low-patchiness arm at 86–88% of the ceiling,
`a1-gradient-ascent` at 900 pinned 2 worlds in 80, and `a2-wall` at 1,200 pinned
4 in 102 — the last projected from A1's measured mean of 344, a number that was
still climbing at 15k ticks. Three experiments, three wrong settings, three
manual catches after a full run had completed.

**A population regulated by the array is not regulated by the world**, and the
damage is worse in a picture than in a table: pinned worlds render as identical
full-height bars, which reads as convergence the array alone produced.

The register already prescribed "an automated viability sweep before every
experiment". One exists, and it tests for extinction — the *other* wall. This
tests both.

**It measures rather than projects,** because projecting is the mistake it
exists to prevent. The pilot runs the real config for the real number of ticks
with a handful of worlds; it does not extrapolate a growth curve from a short
prefix, which is precisely how capacity 1,200 came to look like 3x headroom.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

# Verdict thresholds, calibrated against the three known failures above.
#
#   a2 @ 1200  ->  worst world mean 1198/1200 = 1.00  ->  FAIL   (correct)
#   a2 @ 2000  ->  worst world mean 1423/2000 = 0.71  ->  WARN   (correct: 3
#                  worlds clipped peaks for 1.4-3.2% of frames, and it shipped
#                  with that stated)
#   a1 @ 900   ->  worst world mean ~900/900  = 1.00  ->  FAIL   (correct)
MEAN_FAIL = 0.80   # a world whose *average* sits here is regulated by the array
PEAK_WARN = 0.95   # a world that touches here has clipped peaks, not trajectories
PILOT_WORLDS = 4


class HeadroomError(RuntimeError):
    """Raised before a sweep runs. Never caught by the runner — like a gate
    violation, a bad ceiling stops the experiment rather than degrading it."""


def headroom(cfg, seed: int = 0, *, worlds: int = PILOT_WORLDS,
             out_root: Path = Path("corpus/pilots")) -> dict:
    """Run `worlds` worlds at full length and report how close they get to the ceiling.

    Returns a dict with a `verdict` of "ok", "warn" or "fail". Costs roughly
    `worlds / (seeds x run.worlds)` of the sweep it guards — about 8% for a
    typical 3-seed, 16-world experiment.
    """
    from core.config import resolve
    from forge.run import run

    capacity = int(cfg.get("population.capacity"))
    raw = {k: (dict(v) if isinstance(v, dict) else v) for k, v in cfg.data.items()}
    raw["run"] = {
        **raw["run"],
        "worlds": int(worlds),
        # A pilot is thrown away: no checkpoints, no per-agent events. Only the
        # aggregate tier is read, and it is written at every tier.
        "log_tier": "aggregated",
        "checkpoint_every": 10**9,
    }
    pilot = resolve(raw, source=f"{cfg.source}::headroom-pilot")
    meta = run(pilot, seed, out_root=out_root, progress=False)

    import duckdb

    run_dir = out_root / "runs" / meta["run_id"]
    rows = duckdb.connect().sql(
        f"select world_id, population from read_parquet('{run_dir}/aggregate.parquet')"
    ).fetchnumpy()

    ids = np.unique(rows["world_id"])
    series = [rows["population"][rows["world_id"] == w].astype(np.float64) for w in ids]
    # The second half only: the founding cohort overshoots in every world, and a
    # startup transient is not the array regulating anything.
    means = np.array([s[len(s) // 2:].mean() for s in series])
    peak = float(max(s.max() for s in series))

    worst_mean = float(means.max()) if means.size else 0.0
    mean_frac, peak_frac = worst_mean / capacity, peak / capacity

    if mean_frac >= MEAN_FAIL:
        verdict = "fail"
    elif peak_frac >= PEAK_WARN:
        verdict = "warn"
    else:
        verdict = "ok"

    return {
        "verdict": verdict,
        "capacity": capacity,
        "worst_world_mean": round(worst_mean, 1),
        "worst_world_mean_frac": round(mean_frac, 3),
        "peak_population": round(peak, 1),
        "peak_frac": round(peak_frac, 3),
        "pilot_worlds": int(worlds),
        "ticks": int(meta["ticks_completed"]),
        "suggested_capacity": int(np.ceil(worst_mean / 0.5 / 50.0) * 50),
        "run_id": meta["run_id"],
    }


def enforce(report: dict, label: str = "") -> None:
    """Stop on `fail`, print and continue on `warn`."""
    where = f" [{label}]" if label else ""
    line = (
        f"    headroom{where}: worst world mean {report['worst_world_mean']:.0f} "
        f"({report['worst_world_mean_frac']:.0%} of {report['capacity']}), "
        f"peak {report['peak_population']:.0f} ({report['peak_frac']:.0%})"
    )
    if report["verdict"] == "fail":
        raise HeadroomError(
            f"{line}\n"
            f"    The array is regulating this world, not the world regulating itself.\n"
            f"    Raise population.capacity to about {report['suggested_capacity']} and re-run,\n"
            f"    or pass --skip-precheck if a pinned ceiling is genuinely what you are studying."
        )
    print(line + ("   WARN: peaks clip the ceiling" if report["verdict"] == "warn" else "   ok"),
          flush=True)
