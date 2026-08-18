"""Chronicle → viz digest. The one place the Atlas's input is produced.

    Core ──→ Chronicle (GBs, columnar) ──→ Lens ──→ metrics
                     │                        │
                     └──── digest builder ←───┘
                                  ↓
                          digest.json (~3 MB)
                                  ↓
                               ATLAS

A pure function of one run directory: it reads, and never writes back into the
Chronicle. Rebuilding a digest is cheap and changes nothing about the run, which
is what lets the schema evolve without re-simulating anything.

Everything it needs survives the most aggressive log tier. The series come from
`aggregate.parquet`, the rasters from checkpoints — the snapshot tier — and the
markers from the detector suite. A run logged at `log_tier: aggregated`, with no
per-agent events at all, still produces a complete digest, which is the tiering
claim of D-047 demonstrated rather than asserted.

Usage:
    python -m digest.build corpus/runs/<run_id>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import yaml

from digest import schema as D

_MAX_BYTES = 5 * 2**20  # docs/06-data-model.md: "target <= 5 MB for a 10,000-year run"


def build(run_dir: str | Path, *, raster_worlds: int = D.RASTER_WORLDS) -> dict:
    from lens import collapse
    from lens.base import ChronicleReader

    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "meta.json").read_text())
    cfg = yaml.safe_load((run_dir / "config.yaml").read_text())

    with ChronicleReader(run_dir) as reader:
        agg = reader.sql(
            "select tick, world_id, population, births, deaths, resource_total, "
            "energy_mean, energy_gini, gene_mean from {aggregate} order by tick, world_id"
        ).fetchnumpy()
        firing = collapse.compute(reader, rng=np.random.default_rng(0))

    ticks = np.unique(agg["tick"])
    worlds = np.unique(agg["world_id"])
    ti = np.searchsorted(ticks, agg["tick"])
    wi = np.searchsorted(worlds, agg["world_id"])

    series = {}
    for name, bits in D.SERIES:
        grid = np.zeros((worlds.size, ticks.size), dtype=np.float64)
        grid[wi, ti] = np.asarray(agg[name], dtype=np.float64)
        # population is stored exactly rather than quantized: it is the strip's
        # bar height, and a capacity of 1,200 spread over 255 levels would visibly
        # step.
        lo, hi = (0.0, float(cfg["population"]["capacity"])) if name == "population" else (None, None)
        series[name] = D.encode(grid, bits, lo=lo, hi=hi)

    digest = {
        "digest_version": D.DIGEST_VERSION,
        "run_id": meta.get("run_id", run_dir.name),
        "config_hash": meta.get("config_hash"),
        "code_version": meta.get("code_version"),
        "schema_version": meta.get("schema_version"),
        "seed": meta.get("seed"),
        "n_worlds": int(worlds.size),
        "world_ids": [int(w) for w in worlds],
        "capacity": int(cfg["population"]["capacity"]),
        "grid": int(cfg["world"]["grid"]),
        "patchiness": float(cfg["world"]["patchiness"]),
        "ticks_completed": int(meta.get("ticks_completed", ticks[-1] + 1)),
        "frames": _frames(ticks),
        "series": series,
        "genes": _genes(agg["gene_mean"], wi, ti, worlds.size, ticks.size),
        "rasters": _rasters(run_dir, worlds, raster_worlds),
        "markers": _markers(firing),
        # The verdict travels with the marks. The strip draws every drawdown; only
        # this says whether there are more of them than chance produces, and the
        # legend reads it rather than implying significance the data has not
        # earned.
        "detectors": {
            firing.detector: {
                "magnitude": firing.magnitude,
                "null_mean": firing.null_mean,
                "null_std": firing.null_std,
                "effect_size": firing.effect_size,
                "threshold": firing.threshold,
                "fired": firing.fired,
                "n_worlds": firing.n_observations,
            }
        },
        "reserved": list(D.RESERVED),
    }
    digest["digest_hash"] = D.digest_hash(digest)
    return digest


def _frames(ticks: np.ndarray) -> dict:
    steps = np.diff(ticks)
    uniform = bool(steps.size == 0 or (steps == steps[0]).all())
    out = {
        "n": int(ticks.size),
        "tick_start": int(ticks[0]),
        "tick_step": int(steps[0]) if steps.size else 0,
        "uniform": uniform,
    }
    if not uniform:
        out["ticks"] = [int(t) for t in ticks]
    return out


def _genes(column, wi: np.ndarray, ti: np.ndarray, n_worlds: int, n_frames: int) -> dict:
    """Gene means, subsampled in time.

    Trait means are the slowest-moving thing in the digest — that is why they are
    an evolutionary signal at all — so storing every frame spends 2 MB to encode
    the same curve at eight times the resolution any plot can show.
    """
    stacked = np.stack([np.asarray(g, dtype=np.float64) for g in column])
    n_genes = stacked.shape[1]
    grid = np.zeros((n_worlds, n_frames, n_genes), dtype=np.float64)
    grid[wi, ti] = stacked

    keep = np.arange(0, n_frames, D.GENE_STRIDE)
    field = D.encode(grid[:, keep, :], 8)
    field["stride"] = D.GENE_STRIDE
    field["n_genes"] = int(n_genes)
    return field


def _raster_size(grid: int) -> int:
    """Largest divisor of `grid` at or below the target, so blocks are exact.

    Block means over an integer factor need no interpolation and no resampling
    filter, which keeps the raster a deterministic function of the checkpoint.
    """
    for f in range(min(D.RASTER_SIZE, grid), 0, -1):
        if grid % f == 0:
            return f
    return 1


def _rasters(run_dir: Path, worlds: np.ndarray, raster_worlds: int) -> dict:
    """Downsampled resource and agent-density fields, from checkpoints.

    Only the first few worlds get them: rasters are for the map view that arrives
    at C3, and carrying a hundred worlds' worth would blow the 5 MB budget for a
    view that does not exist yet.
    """
    from chronicle import checkpoint

    paths = sorted((run_dir / "checkpoints").glob("ckpt_*.npz"))
    picked = [int(w) for w in worlds[:raster_worlds]]
    if not paths or not picked:
        return {"worlds": picked, "size": [0, 0], "ticks": [], "layers": {}}

    ticks, stacks = [], {name: [] for name in D.RASTER_LAYERS}
    size = None
    for path in paths:
        world, _, _, _ = checkpoint.load(path)
        f = _raster_size(world.grid)
        size = f
        block = world.grid // f
        for w in picked:
            res = world.resource[w].reshape(f, block, f, block).mean(axis=(1, 3))
            alive = world.alive[w]
            counts = np.bincount(
                (world.y[w, alive].astype(np.intp) // block) * f
                + (world.x[w, alive].astype(np.intp) // block),
                minlength=f * f,
            ).reshape(f, f)
            stacks["resource"].append(res)
            stacks["density"].append(counts.astype(np.float64))
        ticks.append(int(path.stem.split("_")[1]))

    n_t, n_w = len(ticks), len(picked)
    layers = {
        name: D.encode(np.stack(arrs).reshape(n_t, n_w, size, size), 8)
        for name, arrs in stacks.items()
    }
    return {"worlds": picked, "size": [size, size], "ticks": ticks, "layers": layers}


def _markers(firing) -> list[dict]:
    """Detector firings become chapter markers.

    docs/09-visualization.md calls this the best reuse in the design: the
    instrumentation built for the science annotates the timeline for free, so
    nothing here is hand-authored.
    """
    return [
        {"world": e["world"], "tick": e["tick"],
         "detector": firing.detector, "magnitude": e["depth"]}
        for e in firing.detail.get("events", [])
    ]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run_dir")
    p.add_argument("--rasters", type=int, default=D.RASTER_WORLDS,
                   help="how many worlds get raster layers (0 to omit)")
    p.add_argument("-o", "--out", default=None, help="default: <run_dir>/digest.json")
    args = p.parse_args()

    run_dir = Path(args.run_dir)
    digest = build(run_dir, raster_worlds=args.rasters)
    out = Path(args.out) if args.out else run_dir / "digest.json"
    payload = D.canonical_json(digest)
    out.write_text(payload)

    mb = len(payload.encode()) / 2**20
    d = digest["detectors"]["collapse"]
    print(
        f"  {digest['n_worlds']} worlds x {digest['frames']['n']} frames  "
        f"-> {out}  ({mb:.2f} MB)\n"
        f"  markers {len(digest['markers']):,}   "
        f"collapse {d['magnitude']:.3f} vs null {d['null_mean']:.3f}"
        f"+-{d['null_std']:.3f}  z={d['effect_size']:+.2f}  "
        f"{'FIRED' if d['fired'] else 'silent'}\n"
        f"  digest_hash {digest['digest_hash']}"
    )
    if len(payload.encode()) > _MAX_BYTES:
        print(f"  WARNING: over the {_MAX_BYTES / 2**20:.0f} MB budget "
              f"(docs/06-data-model.md) — reduce --rasters or the frame count")


if __name__ == "__main__":
    main()
