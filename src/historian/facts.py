"""Run directory → the numbered fact table the Historian is allowed to draw on.

This file is the containment. Everything downstream — the prompt, the verifier,
the prose — operates on what comes out of here, and the model sees nothing else.
If a claim is not derivable from a fact in this table, the verifier throws the
sentence away, so the question *"what may the Historian say?"* has exactly one
answer and it is written here.

**Numbers come from `aggregate.parquet`, not from the digest.** The digest
quantizes five of its six series to 8 bits, which is invisible in a 16-pixel strip
and wrong in a sentence: prose that says "fell to 389" should mean 389. The
aggregate rows are also literally what the ship criterion names — *traceable to an
event range or an aggregate row* — so citing them is not a paraphrase of the
requirement, it is the requirement.

**Markers and detector verdicts come from the digest**, where `src/digest/build.py`
already put them, and a marker fact carries the detector's verdict for the whole
run beside its depth. A drawdown from a detector that came out silent must not be
narrated as a significant one; the fact table is where that constraint is made
available, and `verify.py` is where it is enforced *(→ D-063)*.

**Rasters become numbers, never arrays.** A 48x48 field handed to a language model
is a field it will describe rather than measure. The centroid drift and the
concentration share are computed here, in Python, on the torus — and they are what
buys the roadmap's *"the eastern settlements grew until…"* register honestly,
without the model ever having seen a grid.

No checkpoint is opened, no live state is read, and nothing in this module imports
`src/core/`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from digest import schema as D
from historian import NARRATIVE_VERSION

# docs/00-feasibility.md: 1 tick ~ 1 month. The Historian writes in years because
# people read in years; the citation chain stays in ticks because that is what an
# aggregate row is keyed by.
TICKS_PER_YEAR = 12.0

DEFAULT_ERAS = 10
DEFAULT_WORLDS = 4

# Order is canonical: it fixes the fact ids, which appear in committed prose.
SERIES: tuple[str, ...] = (
    "population", "births", "deaths", "energy_mean", "energy_gini", "resource_total",
)

# Counts are written as integers, rates and fractions are not. A sentence saying
# "812 agents" against a stored 812.0000001 should match, and one saying
# "gini 0.31" against 0.3142 should also match — the verifier compares at the
# precision written, so what matters here is only that nothing is stored at more
# precision than it has.
_INTEGER_SERIES = frozenset({"population", "births", "deaths"})

MAX_MARKERS_PER_ERA = 6   # a hundred drawdowns in one era is a bar chart, not a chapter
MAX_GENE_FACTS = 2        # the two that actually moved

# The S0 genome, mirrored from `src/core/policy/s0_reactive.py`.
#
# Copied rather than imported: nothing in the analysis layer imports `src/core/`,
# which is the same convention `src/lens/` and `src/digest/` follow. The cost of
# copying is drift, so `tests/test_historian.py` reads the core's own table and
# fails if these stop matching.
#
# They are here because "gene 6 rose from 0.048 to 0.001" is not a sentence about
# anything. "The agents were moving less vigorously" is, and it is the same
# measurement.
GENE_LABELS: tuple[str, ...] = (
    "hunger_threshold",
    "heading_persistence",
    "gradient_sensitivity",
    "exploration_temp",
    "reproduce_threshold",
    "offspring_investment",
    "metabolic_rate",
    "crowd_avoidance",
)

# At S1 only three of the eight genes keep those meanings. `reproduce_threshold`,
# `offspring_investment` and `metabolic_rate` are still read by the tick loop's
# metabolism and vitals phases, outside the policy; the other five are fed to
# the network as an embedding and mean whatever selection made them mean.
#
# This is the one falsehood A3's verifier cannot catch. Every check it runs is
# about the *number* — that the number exists, that it is derivable, that it is
# cited — and the number is real. Only the name is wrong, so a sentence saying
# "gradient sensitivity rose" about an S1 run would pass the gate, carry a
# citation, and be untrue.
STRUCTURAL_GENES: frozenset[int] = frozenset({4, 5, 6})


def gene_labels(stage: str) -> tuple[str, ...]:
    """Trait names for a run's genome, given the intelligence stage it ran at.

    Falls back to positional names for the genes a stage does not give meaning
    to. Naming a gene is a claim about the world, and a stage that does not make
    that claim should not have one made on its behalf.
    """
    if stage == "S0":
        return GENE_LABELS
    return tuple(
        GENE_LABELS[i] if i in STRUCTURAL_GENES else f"gene_{i}"
        for i in range(len(GENE_LABELS))
    )


@dataclass(slots=True)
class RunData:
    """Everything the fact builders read, loaded once."""

    run_dir: Path
    meta: dict
    digest: dict
    ticks: np.ndarray                  # [F] aggregate tick of each frame
    world_ids: np.ndarray              # [W]
    series: dict[str, np.ndarray]      # name -> [W, F], exact, from aggregate.parquet
    genes: np.ndarray                  # [W, F, G]
    markers: list[dict]
    detectors: dict
    rasters: dict                      # decoded layers, or {} when the digest has none

    @property
    def n_frames(self) -> int:
        return int(self.ticks.size)

    def world_index(self, world: int) -> int:
        hit = np.flatnonzero(self.world_ids == world)
        if not hit.size:
            raise KeyError(f"world {world} is not in this run; have {list(self.world_ids)}")
        return int(hit[0])


def load(run_dir: str | Path) -> RunData:
    """Read one finished run. Aggregate tier plus digest — nothing else.

    The digest must already exist: `python -m digest.build <run_dir>`. Requiring it
    rather than rebuilding it here keeps the Historian a reader, and keeps the
    detector verdict that annotates the prose identical to the one the wall drew.
    """
    from lens.base import ChronicleReader

    run_dir = Path(run_dir)
    digest_path = run_dir / "digest.json"
    if not digest_path.exists():
        raise FileNotFoundError(
            f"no digest.json in {run_dir}. Build it first:\n"
            f"    python -m digest.build {run_dir}"
        )

    meta = json.loads((run_dir / "meta.json").read_text())
    digest = json.loads(digest_path.read_text())

    with ChronicleReader(run_dir) as reader:
        agg = reader.sql(
            "select tick, world_id, " + ", ".join(SERIES) + ", gene_mean "
            "from {aggregate} order by tick, world_id"
        ).fetchnumpy()

    ticks = np.unique(agg["tick"]).astype(np.int64)
    world_ids = np.unique(agg["world_id"]).astype(np.int64)
    ti = np.searchsorted(ticks, agg["tick"])
    wi = np.searchsorted(world_ids, agg["world_id"])

    series = {}
    for name in SERIES:
        grid = np.zeros((world_ids.size, ticks.size), dtype=np.float64)
        grid[wi, ti] = np.asarray(agg[name], dtype=np.float64)
        series[name] = grid

    stacked = np.stack([np.asarray(g, dtype=np.float64) for g in agg["gene_mean"]])
    genes = np.zeros((world_ids.size, ticks.size, stacked.shape[1]), dtype=np.float64)
    genes[wi, ti] = stacked

    return RunData(
        run_dir=run_dir,
        meta=meta,
        digest=digest,
        ticks=ticks,
        world_ids=world_ids,
        series=series,
        genes=genes,
        markers=list(digest.get("markers", [])),
        detectors=dict(digest.get("detectors", {})),
        rasters=_decode_rasters(digest),
    )


def _decode_rasters(digest: dict) -> dict:
    """Decode the digest's raster layers, or return {} when there are none.

    A run digested with `--rasters 0` produces no spatial facts and the prose
    simply has no geography in it. That is the right failure: silence rather than
    a plausible bearing computed from nothing.
    """
    raw = digest.get("rasters") or {}
    layers = raw.get("layers") or {}
    if not layers or not raw.get("ticks"):
        return {}
    return {
        "worlds": [int(w) for w in raw["worlds"]],
        "ticks": [int(t) for t in raw["ticks"]],
        "size": int(raw["size"][0]),
        "layers": {name: D.decode(field) for name, field in layers.items()},
    }


# --- era segmentation --------------------------------------------------------


def era_bounds(n_frames: int, n_eras: int = DEFAULT_ERAS) -> list[tuple[int, int]]:
    """`n_eras` equal frame windows, as half-open `[start, end)` index pairs.

    **Eras are computed here and never chosen by the model** (D-069). Letting an
    LLM decide where an era begins would make "era" an interpretation that then
    determines the structure the interpretation is read off — and it would make
    worlds incomparable, which is the one thing a corpus of identical configs
    exists for. Equal windows are boring on purpose: two worlds' fourth eras cover
    the same ticks, so "these two diverged" is a statement about the worlds.
    """
    if n_frames <= 0:
        return []
    n_eras = max(1, min(int(n_eras), n_frames))
    edges = np.linspace(0, n_frames, n_eras + 1).round().astype(int)
    return [(int(a), int(b)) for a, b in zip(edges[:-1], edges[1:]) if b > a]


def _years(tick: float) -> float:
    return round(float(tick) / TICKS_PER_YEAR, 1)


def _round(name: str, value: float) -> float:
    if not np.isfinite(value):
        return 0.0
    if name in _INTEGER_SERIES:
        return float(round(value))
    return round(float(value), 4)


# --- fact construction -------------------------------------------------------


class _Facts:
    """Accumulator that hands out sequential ids.

    Ids are positional, so the table's construction order is part of the contract
    the same way `SERIES` order is: prose committed under `experiments/` cites
    `f07`, and `f07` has to keep meaning what it meant.
    """

    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, kind: str, source: str, values: dict[str, float], **extra) -> dict:
        fact = {
            "id": f"f{len(self.items):02d}",
            "kind": kind,
            **extra,
            "values": {k: float(v) for k, v in values.items()},
            "source": source,
        }
        self.items.append(fact)
        return fact


def era_brief(data: RunData, world: int, era_index: int,
              n_eras: int = DEFAULT_ERAS) -> dict:
    """The brief for one world's one era. See schemas/narrative.md."""
    bounds = era_bounds(data.n_frames, n_eras)
    if not 0 <= era_index < len(bounds):
        raise IndexError(f"era {era_index} of {len(bounds)}")

    lo, hi = bounds[era_index]
    w = data.world_index(world)
    t0, t1 = int(data.ticks[lo]), int(data.ticks[hi - 1])
    src = f"aggregate.parquet world={world} tick {t0}..{t1}"

    f = _Facts()
    f.add(
        "era_window",
        f"digest.frames + aggregate.parquet, world={world}",
        # Both the index and the ordinal: prose says "the fifth era", and a gate
        # that rejected the 5 for not matching the 4 would be rejecting a
        # sentence for counting from one.
        {"era_index": era_index, "era_number": era_index + 1, "of_eras": len(bounds),
         "tick_start": t0, "tick_end": t1,
         "year_start": _years(t0), "year_end": _years(t1),
         "frames": hi - lo},
    )

    for name in SERIES:
        window = data.series[name][w, lo:hi]
        if window.size == 0:
            continue
        start, end = float(window[0]), float(window[-1])
        values = {
            "start": _round(name, start),
            "end": _round(name, end),
            "min": _round(name, float(window.min())),
            "max": _round(name, float(window.max())),
            "mean": _round(name, float(window.mean())),
            "delta": _round(name, end - start),
        }
        if abs(start) > 1e-9:
            values["delta_pct"] = round((end - start) / abs(start) * 100.0, 1)
        f.add("series_change", src, values, series=name)

        # An era that holds the run's extreme is the only way the prose can say
        # "the highest it ever reached" without the model comparing eras it was
        # never shown. Each brief is sent alone; nothing else supplies this.
        whole = data.series[name][w]
        if window.max() >= whole.max() - 1e-9:
            f.add("extremum", src, {"value": _round(name, float(whole.max()))},
                  series=name, extreme="run_maximum")
        if window.min() <= whole.min() + 1e-9:
            f.add("extremum", src, {"value": _round(name, float(whole.min()))},
                  series=name, extreme="run_minimum")

    _add_gene_facts(f, data, w, lo, hi, world, src)
    _add_marker_facts(f, data, world, t0, t1)
    _add_spatial_facts(f, data, world, t0, t1)

    return {
        "narrative_version": NARRATIVE_VERSION,
        "run_id": data.meta.get("run_id", data.run_dir.name),
        "digest_hash": data.digest.get("digest_hash"),
        "kind": "era",
        "world": int(world),
        "era": {
            "index": era_index,
            "of": len(bounds),
            "tick_range": [t0, t1],
            "year_range": [_years(t0), _years(t1)],
        },
        "facts": f.items,
    }


def _add_gene_facts(f: _Facts, data: RunData, w: int, lo: int, hi: int,
                    world: int, src: str) -> None:
    """The traits that actually moved, and only those.

    Eight genes each contributing a fact would be eight sentences about numbers
    that did not change. The two largest movers are where a trait story is, if
    there is one.
    """
    window = data.genes[w, lo:hi]
    if window.size == 0:
        return
    # Pre-B0 runs carry no `stage` in meta.json, and S0 is the correct reading
    # for every one of them: S1 did not exist when they were written.
    labels = gene_labels(str(data.meta.get("stage", "S0")))
    deltas = window[-1] - window[0]
    for idx in np.argsort(-np.abs(deltas))[:MAX_GENE_FACTS]:
        i = int(idx)
        f.add(
            "gene_shift",
            src.replace("aggregate.parquet", "aggregate.parquet gene_mean"),
            {"start": round(float(window[0, i]), 4),
             "end": round(float(window[-1, i]), 4),
             "delta": round(float(deltas[i]), 4)},
            gene_index=i,
            trait=labels[i] if i < len(labels) else f"gene_{i}",
        )


def _add_marker_facts(f: _Facts, data: RunData, world: int, t0: int, t1: int) -> None:
    """Detector firings inside the era, each carrying the run's verdict.

    `detector_verdict` travels with the mark because a marker records that
    something happened and only the effect size says whether it happened more
    often than chance (D-063). The verifier reads this field to decide whether a
    sentence may use significance language at all.
    """
    hits = [m for m in data.markers
            if int(m.get("world", -1)) == world and t0 <= int(m["tick"]) <= t1]
    hits.sort(key=lambda m: -float(m.get("magnitude", 0.0)))

    for m in hits[:MAX_MARKERS_PER_ERA]:
        name = m.get("detector", "unknown")
        d = data.detectors.get(name, {})
        f.add(
            "marker",
            f"lens.{name} via digest.markers, world={world} tick {int(m['tick'])}",
            {"depth_pct": round(float(m.get("magnitude", 0.0)) * 100.0, 1),
             "tick": int(m["tick"]),
             "year": _years(int(m["tick"]))},
            detector=name,
            detector_verdict="fired" if d.get("fired") else "silent",
            detector_effect_size=round(float(d.get("effect_size", 0.0)), 2),
        )

    if len(hits) > MAX_MARKERS_PER_ERA:
        f.add(
            "marker_count",
            f"lens via digest.markers, world={world} tick {t0}..{t1}",
            {"count": len(hits)},
        )


def _centroid(field: np.ndarray) -> tuple[float, float]:
    """Circular centroid of a 2-D field on a torus, as (y, x) in cells.

    The world wraps, so an arithmetic mean of coordinates puts the centroid of a
    cluster straddling the seam in the middle of the map — the opposite side from
    where it is. Averaging unit vectors on each axis and taking the angle back is
    the wrapped-aware version, and it is the same reasoning as
    `lens.base.wrapped_delta`.
    """
    n = field.shape[0]
    total = float(field.sum())
    if total <= 0:
        return 0.0, 0.0
    ys = field.sum(axis=1)
    xs = field.sum(axis=0)
    out = []
    for weights in (ys, xs):
        ang = np.arange(n) * (2.0 * np.pi / n)
        mean = np.arctan2((weights * np.sin(ang)).sum(), (weights * np.cos(ang)).sum())
        out.append(float(mean % (2.0 * np.pi) * n / (2.0 * np.pi)))
    return out[0], out[1]


_COMPASS = ("north", "north-east", "east", "south-east",
            "south", "south-west", "west", "north-west")


def _bearing(dy: float, dx: float) -> str:
    """Compass name for a displacement. North is decreasing `y` — row 0 is the top."""
    angle = np.degrees(np.arctan2(dx, -dy)) % 360.0
    return _COMPASS[int(round(angle / 45.0)) % 8]


def _wrapped(a: float, b: float, size: int) -> float:
    d = (b - a) % size
    return d - size if d > size / 2 else d


def _add_spatial_facts(f: _Facts, data: RunData, world: int, t0: int, t1: int) -> None:
    """Geography as numbers: where the resource moved, how concentrated agents were.

    Rasters exist for the first few worlds only (digest `RASTER_WORLDS`), so most
    worlds get no spatial facts and their prose has no geography. That is the
    honest outcome — silence rather than a bearing invented to fill a slot.
    """
    r = data.rasters
    if not r or world not in r["worlds"]:
        return

    wi = r["worlds"].index(world)
    # Bracket the era rather than requiring both snapshots strictly inside it.
    # Checkpoints land every `run.checkpoint_every` ticks and era edges land
    # wherever ten equal windows fall, so the two almost never align: at
    # checkpoint_every 1500 and 3,000-tick eras, "strictly inside" finds one
    # snapshot per era and produces no geography at all. The state at the era's
    # start is the last snapshot at or before it.
    ticks = r["ticks"]
    at_or_before = [i for i, t in enumerate(ticks) if t <= t0]
    first = at_or_before[-1] if at_or_before else next(
        (i for i, t in enumerate(ticks) if t <= t1), None)
    within = [i for i, t in enumerate(ticks) if t <= t1]
    last = within[-1] if within else None
    if first is None or last is None or first >= last:
        return
    size = r["size"]
    src = (f"digest.rasters world={world} ticks "
           f"{r['ticks'][first]}..{r['ticks'][last]}")

    if "resource" in r["layers"]:
        layer = r["layers"]["resource"]
        y0, x0 = _centroid(layer[first, wi])
        y1, x1 = _centroid(layer[last, wi])
        dy, dx = _wrapped(y0, y1, size), _wrapped(x0, x1, size)
        cells = float(np.hypot(dy, dx))
        # Sub-cell drift on a 48-cell raster is rounding, not migration. Naming a
        # bearing for it would be the clearest possible way to manufacture a
        # geography that is not there.
        if cells >= 1.0:
            f.add("spatial", src, {"cells": round(cells, 1)},
                  layer="resource", measure="centroid_drift",
                  bearing=_bearing(dy, dx))

    if "density" in r["layers"]:
        layer = r["layers"]["density"]
        shares = []
        for i in (first, last):
            cell = np.sort(layer[i, wi].ravel())[::-1]
            top = max(1, cell.size // 10)
            total = float(cell.sum())
            shares.append(float(cell[:top].sum() / total * 100.0) if total > 0 else 0.0)
        f.add("spatial", src,
              {"start_pct": round(shares[0], 1), "end_pct": round(shares[1], 1),
               "delta_pct": round(shares[1] - shares[0], 1)},
              layer="density", measure="top_decile_share")


# --- the preface -------------------------------------------------------------


def preface_brief(data: RunData, worlds: list[int] | None = None,
                  n_eras: int = DEFAULT_ERAS) -> dict:
    """The brief for the run as a whole — what the wall shows, as facts.

    This is where the corpus claim lives: identical configuration, divergent
    outcomes. The between/within ratio is computed here rather than asserted,
    because it is the number a2-wall was built to produce and the one thing about
    a hundred strips that is worth a sentence.
    """
    cfg_worlds = list(map(int, data.world_ids))
    worlds = worlds or cfg_worlds[:DEFAULT_WORLDS]

    pop = data.series["population"]
    final = pop[:, -1]
    f = _Facts()

    f.add(
        "run_summary",
        f"meta.json + config.yaml, run {data.meta.get('run_id')}",
        {"worlds": len(cfg_worlds),
         "ticks": int(data.meta.get("ticks_completed", data.ticks[-1] + 1)),
         "years": _years(int(data.meta.get("ticks_completed", data.ticks[-1] + 1))),
         "eras": len(era_bounds(data.n_frames, n_eras)),
         "capacity": float(data.digest.get("capacity", 0)),
         "patchiness": float(data.digest.get("patchiness", 0.0)),
         "seed": float(data.meta.get("seed", 0))},
    )

    f.add(
        "spread",
        "aggregate.parquet population, final frame, all worlds",
        {"lowest": _round("population", float(final.min())),
         "highest": _round("population", float(final.max())),
         "median": _round("population", float(np.median(final))),
         "ratio": round(float(final.max() / max(final.min(), 1.0)), 1)},
        series="population",
    )

    # The a2-wall statistic. Between-world spread against within-world spread over
    # the last quarter of the run: a large spread with a large within-world
    # variance is just noisy worlds, and a large spread with a small one means
    # each world settled somewhere and the somewheres differ.
    tail = pop[:, (3 * data.n_frames) // 4:]
    if tail.shape[1] > 1 and tail.shape[0] > 1:
        between = float(tail.mean(axis=1).std(ddof=1))
        within = float(tail.std(axis=1, ddof=1).mean())
        f.add(
            "divergence",
            f"aggregate.parquet population, last quarter, {len(cfg_worlds)} worlds",
            {"between_world_sd": round(between, 1),
             "within_world_sd": round(within, 1),
             "ratio": round(between / max(within, 1e-9), 2)},
        )

    order = np.argsort(-final)
    for world in worlds:
        w = data.world_index(world)
        rank = int(np.flatnonzero(order == w)[0]) + 1
        f.add(
            "cross_world",
            f"aggregate.parquet population, final frame, world={world}",
            {"final_population": _round("population", float(final[w])),
             "rank": rank, "of": len(cfg_worlds),
             "peak": _round("population", float(pop[w].max()))},
            world=int(world),
        )

    return {
        "narrative_version": NARRATIVE_VERSION,
        "run_id": data.meta.get("run_id", data.run_dir.name),
        "digest_hash": data.digest.get("digest_hash"),
        "kind": "preface",
        "worlds": [int(x) for x in worlds],
        "facts": f.items,
    }


def brief_hash(brief: dict) -> str:
    """Content hash of a brief. Reuses the digest's canonical form.

    One hashing convention in the project, not two: the cache key, the digest's
    purity test, and this all go through `digest.schema.canonical_json`.
    """
    return D.digest_hash({k: v for k, v in brief.items() if k != "brief_hash"})
