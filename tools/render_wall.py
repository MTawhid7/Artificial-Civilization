"""The fingerprint wall — a hundred histories from identical conditions, stacked.

    K-4471  ▓▓▒▒░░ ▓▓▓▓ ██ ▒▒▒▒▒ ░░░ ████ ▒▒▒ ░ ██████ ▒▒
    K-4472  ▓▓▓▒▒▒ ░░ ▓▓▓▓▓▓ ▒▒ ███ ░░░░░░░░ ✕
    K-4473  ▓▒░ ✕
                              ↑
              same starting conditions. every one of them.

Reads digests and nothing else — never the Chronicle, never live state (D-013).
Given the same digests it produces the same pixels, which is what makes a
screenshot citable.

**Strip encoding v0.1**, one world per band, one column per frame:

    bar height     population
    bar color      the chosen channel, default energy_gini
    red column     a drawdown marker from the detector suite
    dark tail      extinction — population reached zero and stayed there

Two rendering choices are load-bearing enough to be options rather than
constants, with the honest setting as the default:

**Order is world order, never outcome order** (D-063). Sorting a hundred strips by
final population produces a smooth gradient, and a smooth gradient reads as a
finding — but it is an artifact of sorting, and the identical picture appears if
the outcomes are pure noise.

**Scales are pooled across every world in the image.** Per-world normalization
would rescale each strip independently and manufacture a similarity that is not in
the data. That is the same rule the digest enforces for quantization
(schemas/digest.md), applied again here because decoding and re-normalizing would
quietly undo it.

Usage:
    python tools/render_wall.py corpus/runs/<id>/digest.json [more...] -o wall.png
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from digest import schema as D

STRIP_HEIGHT = 16
GUTTER = 2
BACKGROUND = (0.09, 0.10, 0.12)
MARKER = (0.96, 0.28, 0.24)
MARKER_WIDTH = 3
DPI = 150
EXTINCT = (0.16, 0.05, 0.06)
COLOR_CHANNELS = ("energy_gini", "energy_mean", "resource_total", "births", "deaths")


def load(paths: list[Path], channel: str) -> dict:
    """Pool several digests into one wall.

    A run is 34 worlds; a wall is every world in the experiment. Values are
    decoded to real units first and re-normalized over the pool, so digests with
    different internal quantization ranges still land on one shared scale.
    """
    pops, colors, labels, markers, meta = [], [], [], [], []
    row = 0
    for path in paths:
        d = json.loads(Path(path).read_text())
        if d["digest_version"] != D.DIGEST_VERSION:
            raise SystemExit(
                f"{path}: digest_version {d['digest_version']}, this renderer speaks "
                f"{D.DIGEST_VERSION}. Rebuild the digest rather than guessing."
            )
        pop = D.decode(d["series"]["population"])
        col = D.decode(d["series"][channel])
        pops.append(pop)
        colors.append(col)

        frames = d["frames"]
        start, step = frames["tick_start"], frames["tick_step"]
        index = {int(w): i for i, w in enumerate(d["world_ids"])}
        for w in d["world_ids"]:
            labels.append(f"{d['run_id'][:4]}-{int(w):02d}")
        for m in d["markers"]:
            f = int(round((m["tick"] - start) / max(step, 1)))
            if 0 <= f < pop.shape[1]:
                markers.append((row + index[int(m["world"])], f))
        row += pop.shape[0]
        meta.append(d)

    n_frames = min(p.shape[1] for p in pops)
    return {
        "population": np.concatenate([p[:, :n_frames] for p in pops]),
        "color": np.concatenate([c[:, :n_frames] for c in colors]),
        "labels": labels,
        "markers": markers,
        "channel": channel,
        "meta": meta,
    }


def build_wall(
    data: dict,
    *,
    height: int = STRIP_HEIGHT,
    gutter: int = GUTTER,
    cmap: str = "viridis",
    scale: str = "max",
    sort: str = "world",
) -> np.ndarray:
    """Pure array → RGB float array. No text, no matplotlib figure, no state."""
    from matplotlib import colormaps

    pop, col = data["population"], data["color"]
    n_worlds, n_frames = pop.shape

    order = _order(pop, sort)
    pop, col = pop[order], col[order]
    rank = np.empty(n_worlds, dtype=np.intp)
    rank[order] = np.arange(n_worlds)

    ceiling = float(pop.max()) if scale == "max" else float(data["meta"][0]["capacity"])
    filled = np.rint(np.clip(pop / max(ceiling, 1e-9), 0, 1) * height).astype(int)

    lo, hi = float(col.min()), float(col.max())
    norm = (col - lo) / (hi - lo) if hi > lo else np.zeros_like(col)
    rgb = colormaps[cmap](norm)[..., :3]  # [W, F, 3]

    row_h = height + gutter
    canvas = np.tile(np.asarray(BACKGROUND, dtype=np.float64), (n_worlds * row_h, n_frames, 1))

    # Bars grow from the bottom of each band, so a row of strips reads as a row of
    # histograms rather than as an arbitrary ribbon.
    depth = np.arange(height)[::-1][:, None]  # distance above the band floor
    for w in range(n_worlds):
        top = w * row_h
        band = canvas[top : top + height]
        mask = depth < filled[w][None, :]
        band[mask] = np.broadcast_to(rgb[w][None, :, :], (height, n_frames, 3))[mask]

        # Extinction: population hit zero and never recovered. Not a drawdown —
        # an ending, and it should not be confused with one.
        zero = pop[w] <= 0
        if zero.any() and zero[-1]:
            first = int(np.argmax(np.cumprod(zero[::-1])[::-1] > 0))
            band[:, first:] = EXTINCT

    # Markers are drawn wider than one column on purpose. A 1-pixel line does not
    # survive the resampling any display does between a 2,000-column raster and
    # the width it is shown at — it blends with its neighbours and arrives as a
    # grey smudge. Width is a legibility decision about a mark, not a measurement:
    # the tick it points at is exact either way.
    for world_row, frame in data["markers"]:
        top = rank[world_row] * row_h
        lo = max(frame - MARKER_WIDTH // 2, 0)
        canvas[top : top + height, lo : lo + MARKER_WIDTH] = MARKER

    return np.clip(canvas, 0, 1)


def _order(pop: np.ndarray, sort: str) -> np.ndarray:
    if sort == "world":
        return np.arange(pop.shape[0])
    if sort == "final_pop":
        return np.argsort(-pop[:, -1], kind="stable")
    if sort == "survival":
        alive = (pop > 0).sum(axis=1)
        return np.argsort(-alive, kind="stable")
    raise SystemExit(f"unknown sort: {sort}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("digests", nargs="+")
    p.add_argument("-o", "--out", default="wall.png")
    p.add_argument("--color", default="energy_gini", choices=COLOR_CHANNELS)
    p.add_argument("--cmap", default="viridis")
    p.add_argument("--scale", default="max", choices=("max", "capacity"),
                   help="bar height relative to the tallest world, or to array capacity")
    p.add_argument("--sort", default="world", choices=("world", "final_pop", "survival"),
                   help="world order is the default on purpose — see D-063")
    p.add_argument("--height", type=int, default=STRIP_HEIGHT)
    p.add_argument("--bare", action="store_true", help="the raster alone, no labels or axes")
    args = p.parse_args()

    data = load([Path(x) for x in args.digests], args.color)
    wall = build_wall(data, height=args.height, cmap=args.cmap,
                      scale=args.scale, sort=args.sort)
    out = Path(args.out)

    if args.bare:
        from matplotlib import image
        image.imsave(out, wall)
    else:
        _annotated(wall, data, args).savefig(out, dpi=DPI, facecolor=BACKGROUND)

    n_worlds = data["population"].shape[0]
    print(
        f"  {n_worlds} worlds x {data['population'].shape[1]} frames  "
        f"-> {out}  ({wall.shape[1]}x{wall.shape[0]} px)\n"
        f"  color={args.color}  sort={args.sort}  markers={len(data['markers']):,}"
    )


def _annotated(wall: np.ndarray, data: dict, args) -> "object":
    """The raster plus the things a viewer needs to not misread it.

    A caption stating what the color means and what the detector concluded is not
    decoration: the strip draws every drawdown it was given, and only the
    detector's z says whether there are more of them than chance produces.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import colormaps
    from matplotlib.cm import ScalarMappable
    from matplotlib.colors import Normalize

    meta = data["meta"][0]
    n_worlds, n_frames = data["population"].shape
    ticks_total = meta["ticks_completed"]
    years = ticks_total / 12.0  # docs/00-feasibility.md: 1 tick ~ 1 month

    # Sized so one canvas row lands on one output row. Downsampling a wall is
    # not a cosmetic loss: bar height is the population channel, and a resampler
    # averaging two bands together invents heights neither world had.
    band_inches = n_worlds * (args.height + GUTTER) / DPI
    fig, ax = plt.subplots(figsize=(13, band_inches + 1.9))
    fig.patch.set_facecolor(BACKGROUND)
    ax.set_facecolor(BACKGROUND)
    ax.imshow(wall, aspect="auto", interpolation="nearest")

    row_h = args.height + GUTTER
    show = range(0, n_worlds, max(n_worlds // 12, 1))
    order = _order(data["population"], args.sort)
    ax.set_yticks([i * row_h + args.height / 2 for i in show])
    ax.set_yticklabels([data["labels"][order[i]] for i in show], fontsize=6, color="#9aa0a6")
    ax.set_xticks(np.linspace(0, n_frames - 1, 6))
    ax.set_xticklabels([f"{y:,.0f}" for y in np.linspace(0, years, 6)],
                       fontsize=7, color="#9aa0a6")
    ax.set_xlabel("simulated years", fontsize=8, color="#9aa0a6")
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)

    # Across every digest in the image, not just the first. The wall pools runs;
    # a caption quoting one of them would describe a different picture than the
    # one it sits above.
    zs = [d.get("detectors", {}).get("collapse", {}).get("effect_size")
          for d in data["meta"]]
    zs = [z for z in zs if z is not None]
    fired = any(d.get("detectors", {}).get("collapse", {}).get("fired") for d in data["meta"])
    span = f" (z={np.mean(zs):+.1f}" + (f", range {min(zs):+.1f}…{max(zs):+.1f}" if len(zs) > 1 else "") + ")"
    verdict = (
        f"red marks: drawdowns >35% — {'above' if fired else 'not above'} "
        f"the volatility-matched null{span if zs else ''}"
    )
    ceiling = (data["population"].max() if args.scale == "max" else meta["capacity"])
    ax.set_title(
        f"{n_worlds} worlds · identical configuration · "
        f"patchiness {meta['patchiness']} · {years:,.0f} simulated years\n"
        f"bar height: population, 0–{ceiling:,.0f} on one scale shared by every world"
        f"   ·   color: {args.color}\n{verdict}",
        fontsize=9, color="#e8eaed", pad=12, linespacing=1.7,
    )

    col = data["color"]
    bar = fig.colorbar(
        ScalarMappable(norm=Normalize(float(col.min()), float(col.max())),
                       cmap=colormaps[args.cmap]),
        ax=ax, fraction=0.015, pad=0.01,
    )
    bar.set_label(args.color, fontsize=7, color="#9aa0a6")
    bar.ax.tick_params(labelsize=6, colors="#9aa0a6")
    bar.outline.set_visible(False)

    fig.text(0.5, 0.005,
             "same starting conditions. every one of them.",
             ha="center", fontsize=8, color="#9aa0a6", style="italic")
    fig.tight_layout(rect=(0, 0.015, 1, 1))
    return fig


if __name__ == "__main__":
    main()
