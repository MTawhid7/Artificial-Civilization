"""The scope — one world, stepped through its checkpoints.

A4 tier 1 *(→ [docs/10-roadmap.md § A4](../docs/10-roadmap.md#a4--the-viewer-optional-tiered))*.
This is a debugging instrument, not a result, and it is allowed to stay small.

**Why it exists before B0.** Everything a policy can get wrong — circling, clumping,
never leaving the birth cell — looks identical in `aggregate.parquet` to bad luck.
Population falls either way, because the aggregate tier is precisely what threw the
positions away. Two hours of matplotlib buys the ability to tell those apart for the
whole of Phase B.

**It never attaches** *(→ D-070)*. There is no live feed and no simulation running
behind this window: a checkpoint is a keyframe, and the whole history is already on
disk. `meta.json` keeps `live_viewer: false`, and nothing here writes into the run
directory.

**Three panels, all from data already recorded:**

    map      resource / capacity — harvest pressure, dark where a swarm has been
             through — with living agents scattered on top, coloured by energy
    trace    population for the whole run, with a playhead at the current frame
    genes    mean genome over living agents, against its value at tick 0

`resource / capacity` is the one channel here that no other picture in this project
shows. The strip and the wall carry `resource_total`, a scalar; the ratio is where
it went.

**Scales are pooled across every frame**, the same rule the wall enforces across
worlds. Per-frame energy normalization would paint a starving population in exactly
the colours of a healthy one, which is a presentation choice that manufactures a
finding *(→ D-054, D-063)*.

Usage:
    uv run python tools/scope.py corpus/runs/<id>                 # window; drag, or space to play
    uv run python tools/scope.py corpus/runs/<id> --world 3 --frame 14 --play
    uv run python tools/scope.py corpus/runs/<id> -o sheet.png    # every keyframe on one page
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from matplotlib import colors as mcolors
from matplotlib import pyplot as plt
from matplotlib.widgets import Slider

from chronicle import checkpoint

# Mirrored once, in the Historian, where `test_gene_labels_match_the_core` reads
# the core's own docstring table and fails if the mirror drifts. A third copy
# here would be a third thing to keep in sync, which is the bug that test exists
# to prevent. TICKS_PER_YEAR is imported for the same reason: one definition.
#
# `gene_labels` rather than the raw table because naming a gene is a claim, and
# which claims are true depends on the stage the run was written at.
from historian.facts import TICKS_PER_YEAR, gene_labels

INK = "#0b0f19"
PAPER = "#e8edf5"
MUTED = "#7d8798"
ACCENT = "#3fe0b0"

# Dark where a cell has been stripped, bright where it is untouched. The floor is
# not pure black: a fully depleted cell and the area outside the plot must not
# render as the same thing.
HARVEST = mcolors.LinearSegmentedColormap.from_list(
    "harvest",
    ["#121826", "#153042", "#12564f", "#1a9b6c", "#5fe0a0", "#c8ffe4"],
)
# Energy: starving reads red, sated reads pale cyan. Ordered so that the eye finds
# the hungry agents, which are the ones a policy bug shows up in first.
VITALITY = mcolors.LinearSegmentedColormap.from_list(
    "vitality",
    ["#ff4d3d", "#ff9a3c", "#ffd76e", "#bff7ea", "#ffffff"],
)


@dataclass(slots=True)
class Frame:
    """One checkpoint, reduced to just what the three panels draw.

    Reduced rather than retained on purpose: a checkpoint holds every world at
    full capacity, and keeping twenty-one of them alive would cost hundreds of
    megabytes on a machine that has eight gigabytes total. Everything below is a
    few tens of KB per frame.
    """

    tick: int
    harvest: np.ndarray      # [G, G] resource / capacity, in [0, 1]
    x: np.ndarray            # living agents only
    y: np.ndarray
    energy: np.ndarray
    gene_mean: np.ndarray    # [G_SIZE], mean over living agents
    population: int

    @property
    def year(self) -> float:
        return self.tick / TICKS_PER_YEAR


def scan(run_dir: Path, world: int) -> list[Frame]:
    """Every checkpoint in the run, reduced to one world's frames.

    Loads and discards one checkpoint at a time. `checkpoint.load` is used rather
    than reading the `.npz` directly so that a format bump fails loudly here
    instead of silently mis-reading an array.
    """
    paths = sorted((run_dir / "checkpoints").glob("ckpt_*.npz"))
    if not paths:
        raise SystemExit(
            f"no checkpoints in {run_dir / 'checkpoints'}. The scope reads keyframes; "
            "a run with checkpointing disabled has nothing to show."
        )

    frames: list[Frame] = []
    for i, path in enumerate(paths, 1):
        print(f"\r  reading {i}/{len(paths)} {path.name}", end="", file=sys.stderr, flush=True)
        w, _, _, _ = checkpoint.load(path)
        if not 0 <= world < w.n_worlds:
            raise SystemExit(f"--world {world} out of range; this run has {w.n_worlds}")
        alive = w.alive[world]
        cap = w.capacity[world]
        frames.append(
            Frame(
                tick=int(path.stem.split("_")[1]),
                # Guard the divide rather than the data: a zero-capacity cell is
                # legal terrain, and it is untouched rather than stripped bare.
                harvest=np.divide(w.resource[world], cap, out=np.ones_like(cap),
                                  where=cap > 0).clip(0.0, 1.0),
                x=w.x[world][alive].astype(np.float32),
                y=w.y[world][alive].astype(np.float32),
                energy=w.energy[world][alive].astype(np.float32),
                gene_mean=(w.genome[world][alive].mean(axis=0)
                           if alive.any() else np.zeros(w.genome_size, np.float32)),
                population=int(alive.sum()),
            )
        )
    print(f"\r  read {len(frames)} checkpoints" + " " * 24, file=sys.stderr)
    return frames


def population_trace(run_dir: Path, world: int) -> tuple[np.ndarray, np.ndarray] | None:
    """The full-resolution population series, or None if the run has no aggregate tier.

    The trace is not reconstructed from the frames. Twenty-one keyframes over
    30,000 ticks would draw a straight line through every crash between them, and
    the aggregate rows are already on disk at one row per fifteen ticks.
    """
    if not (run_dir / "aggregate.parquet").exists():
        return None
    from lens.base import ChronicleReader

    with ChronicleReader(run_dir) as reader:
        rows = reader.sql(
            f"select tick, population from {{aggregate}} "
            f"where world_id = {int(world)} order by tick"
        ).fetchnumpy()
    return np.asarray(rows["tick"]), np.asarray(rows["population"])


def _style(ax) -> None:
    ax.set_facecolor(INK)
    for spine in ax.spines.values():
        spine.set_color("#232c3d")
    ax.tick_params(colors=MUTED, labelsize=7, length=2)


def render(
    frames: list[Frame],
    trace: tuple[np.ndarray, np.ndarray] | None,
    run_id: str,
    world: int,
    *,
    stage: str = "S0",
    start: int = 0,
    play: bool = False,
) -> None:
    """The window: three panels and a slider over the checkpoints.

    `stage` decides what the gene panel is allowed to call its rows. At S1 five
    of the eight genes are an embedding, and printing S0's trait names beside
    them would put a false label on a true number.
    """
    grid = frames[0].harvest.shape[0]
    # Pooled, not per-frame. See the module docstring.
    e_max = float(max(np.percentile(f.energy, 99) if f.population else 1.0 for f in frames))
    gene0 = frames[0].gene_mean

    fig = plt.figure(figsize=(13.0, 7.2), facecolor=INK)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.5, 1.0], height_ratios=[1.0, 1.0],
                          left=0.04, right=0.975, top=0.875, bottom=0.13,
                          wspace=0.16, hspace=0.32)
    ax_map = fig.add_subplot(gs[:, 0])
    ax_pop = fig.add_subplot(gs[0, 1])
    ax_gene = fig.add_subplot(gs[1, 1])
    for ax in (ax_map, ax_pop, ax_gene):
        _style(ax)

    title = fig.text(0.04, 0.955, "", color=PAPER, fontsize=13, family="monospace")
    sub = fig.text(0.04, 0.925, "", color=MUTED, fontsize=8.5, family="monospace")
    fig.text(0.975, 0.955, "scope · a4 tier 1 · not evidence", color="#4a5468",
             fontsize=7.5, ha="right", family="monospace")

    # --- map ---------------------------------------------------------------
    img = ax_map.imshow(frames[0].harvest, cmap=HARVEST, vmin=0.0, vmax=1.0,
                        origin="upper", interpolation="nearest",
                        extent=(-0.5, grid - 0.5, grid - 0.5, -0.5))
    dots = ax_map.scatter(frames[0].x, frames[0].y, c=frames[0].energy, cmap=VITALITY,
                          vmin=0.0, vmax=e_max, s=16, linewidths=0.0, alpha=0.95)
    ax_map.set_xlim(-0.5, grid - 0.5)
    ax_map.set_ylim(grid - 0.5, -0.5)
    ax_map.set_xticks([])
    ax_map.set_yticks([])
    ax_map.set_title("harvest field · resource / capacity, agents by energy",
                     color=MUTED, fontsize=8.5, pad=6)

    # --- population --------------------------------------------------------
    if trace is not None:
        ticks, pop = trace
        ax_pop.plot(ticks, pop, color=ACCENT, linewidth=0.9)
        ax_pop.fill_between(ticks, pop, color=ACCENT, alpha=0.13)
        ax_pop.set_xlim(float(ticks[0]), float(ticks[-1]))
        ax_pop.set_ylim(0, float(pop.max()) * 1.08 + 1)
        playhead = ax_pop.axvline(frames[0].tick, color="#ff9a3c", linewidth=1.1)
        ax_pop.set_title("population", color=MUTED, fontsize=8.5, pad=4, loc="left")
    else:
        playhead = None
        ax_pop.text(0.5, 0.5, "no aggregate.parquet\n(run logged below the aggregate tier)",
                    color=MUTED, fontsize=8, ha="center", va="center", family="monospace")
        ax_pop.set_xticks([])
        ax_pop.set_yticks([])

    # --- genes -------------------------------------------------------------
    labels = gene_labels(stage)
    ypos = np.arange(len(labels))
    bars = ax_gene.barh(ypos, frames[0].gene_mean, color=ACCENT, alpha=0.75, height=0.62)
    ax_gene.scatter(gene0, ypos, marker="|", s=90, color="#ff9a3c", linewidths=1.4,
                    zorder=3, label="at tick 0")
    ax_gene.set_yticks(ypos)
    ax_gene.set_yticklabels(labels, fontsize=7.5, color=PAPER, family="monospace")
    ax_gene.invert_yaxis()
    ax_gene.set_xlim(0.0, 1.0)
    ax_gene.set_title("mean genome over living agents · orange = tick 0",
                      color=MUTED, fontsize=8.5, pad=4, loc="left")

    # --- slider ------------------------------------------------------------
    ax_slider = fig.add_axes((0.04, 0.045, 0.60, 0.028), facecolor="#161d2c")
    start = min(max(start, 0), len(frames) - 1)
    slider = Slider(ax_slider, "", 0, max(len(frames) - 1, 1), valinit=start, valstep=1,
                    color=ACCENT, track_color="#1b2334", initcolor="none")
    slider.valtext.set_visible(False)
    ax_slider.set_xticks([])

    def show(i: int) -> None:
        f = frames[int(i)]
        img.set_data(f.harvest)
        dots.set_offsets(np.column_stack([f.x, f.y]) if f.population
                         else np.empty((0, 2), np.float32))
        dots.set_array(f.energy)
        for bar, v in zip(bars, f.gene_mean):
            bar.set_width(float(v))
        if playhead is not None:
            playhead.set_xdata([f.tick, f.tick])
        title.set_text(f"{run_id[:12]} · world {world:02d} · year {f.year:,.0f}")
        sub.set_text(
            f"tick {f.tick:,}  ·  frame {int(i) + 1}/{len(frames)}  ·  "
            f"population {f.population:,}  ·  "
            f"harvest {f.harvest.mean():.2f} of capacity"
        )
        fig.canvas.draw_idle()

    slider.on_changed(show)
    show(start)

    state = {"playing": play}

    def advance() -> None:
        if state["playing"]:
            slider.set_val((int(slider.val) + 1) % len(frames))

    timer = fig.canvas.new_timer(interval=220)
    timer.add_callback(advance)
    timer.start()

    def on_key(event) -> None:
        if event.key == " ":
            state["playing"] = not state["playing"]
        elif event.key in ("right", "left"):
            step = 1 if event.key == "right" else -1
            state["playing"] = False
            slider.set_val((int(slider.val) + step) % len(frames))

    fig.canvas.mpl_connect("key_press_event", on_key)
    fig.text(0.665, 0.052, "space play/pause   ←/→ step   drag to scrub",
             color="#4a5468", fontsize=7.5, family="monospace")
    plt.show()


def contact_sheet(frames: list[Frame], run_id: str, world: int, out: Path,
                  *, stage: str = "S0", columns: int = 7) -> None:
    """Every keyframe at once — the whole history on one page.

    Better than the window for two jobs: comparing frame 3 with frame 17, and
    attaching to an issue.
    """
    grid = frames[0].harvest.shape[0]
    e_max = float(max(np.percentile(f.energy, 99) if f.population else 1.0 for f in frames))
    rows = -(-len(frames) // columns)
    fig, axes = plt.subplots(rows, columns, figsize=(columns * 1.9, rows * 2.05),
                             facecolor=INK)
    for ax, f in zip(np.ravel(axes), frames):
        ax.imshow(f.harvest, cmap=HARVEST, vmin=0.0, vmax=1.0, origin="upper",
                  interpolation="nearest", extent=(-0.5, grid - 0.5, grid - 0.5, -0.5))
        ax.scatter(f.x, f.y, c=f.energy, cmap=VITALITY, vmin=0.0, vmax=e_max,
                   s=3.2, linewidths=0.0, alpha=0.95)
        ax.set_title(f"y{f.year:,.0f} · n={f.population:,}", color=MUTED,
                     fontsize=6.5, pad=2.5, family="monospace")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color("#232c3d")
    for ax in np.ravel(axes)[len(frames):]:
        ax.set_visible(False)
    fig.suptitle(f"{run_id[:12]} · world {world:02d} · {stage} · {len(frames)} keyframes"
                 f"  —  scope, a4 tier 1, not evidence",
                 color=PAPER, fontsize=9, family="monospace", y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.975))
    fig.savefig(out, dpi=150, facecolor=INK)
    print(f"wrote {out}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--world", type=int, default=0)
    ap.add_argument("--frame", type=int, default=0, help="checkpoint index to open on")
    ap.add_argument("--play", action="store_true", help="start the window playing")
    ap.add_argument("-o", "--out", type=Path,
                    help="write a contact sheet PNG instead of opening a window")
    args = ap.parse_args(argv)

    run_dir = args.run_dir
    meta_path = run_dir / "meta.json"
    if not meta_path.exists():
        raise SystemExit(f"{run_dir} is not a run directory (no meta.json)")
    # The scope reads. Nothing below writes into run_dir, and --out defaults
    # nowhere near it.
    run_id = run_dir.name
    # Pre-B0 runs have no `stage` key, and S0 is the right reading for all of
    # them — S1 did not exist when they were written.
    stage = str(json.loads(meta_path.read_text()).get("stage", "S0"))

    frames = scan(run_dir, args.world)
    if args.out:
        contact_sheet(frames, run_id, args.world, args.out, stage=stage)
    else:
        render(frames, population_trace(run_dir, args.world), run_id, args.world,
               stage=stage, start=args.frame, play=args.play)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
