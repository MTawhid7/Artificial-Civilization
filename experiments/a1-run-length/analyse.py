"""Score A1's committed runs at several observation windows.

    uv run python experiments/a1-run-length/analyse.py

No new simulation. `gradient_ascent` takes `max_tick`, so the 30 runs of
a1-gradient-ascent — already on disk, 15,000 ticks each — can be scored at 3,750 /
7,500 / 11,250 / 15,000 and compared **paired**: same worlds, same seeds, same
landscapes, only the window differs.

That pairing is the whole design. Comparing two experiments of different lengths
would confound window with everything that differs between two sets of worlds,
and between-world spread in this project is roughly ten to one.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from lens import gradient_ascent
from lens.base import ChronicleReader

HERE = Path(__file__).parent
SOURCE = HERE.parent / "a1-gradient-ascent" / "results.json"
WINDOWS = (3750, 7500, 11250, 15000)


def main() -> None:
    src = json.loads(SOURCE.read_text())
    runs = [r for r in src["results"] if (Path("corpus/runs") / r["run_id"] / "meta.json").exists()]
    if not runs:
        raise SystemExit(
            "a1-gradient-ascent runs are not in corpus/. Regenerate with\n"
            "  uv run python -m forge.sweep experiments/a1-gradient-ascent/spec.yaml"
        )
    print(f"  {len(runs)}/{len(src['results'])} runs on disk, scoring at {len(WINDOWS)} windows")

    rows = []
    for r in runs:
        with ChronicleReader(Path("corpus/runs") / r["run_id"]) as reader:
            for w in WINDOWS:
                # Same RNG seeding as forge.sweep.score, so these numbers are
                # comparable with the committed a1-gradient-ascent results.
                f = gradient_ascent.compute(
                    reader, rng=np.random.default_rng(r["seed"] * 1000 + 1), max_tick=w
                )
                rows.append({
                    "patchiness": r["params"]["world.patchiness"], "seed": r["seed"],
                    "window": w, "advantage": f.magnitude, "z": f.effect_size,
                    "selection_gain": f.detail.get("advantage_delta"),
                    "n_moves": f.n_observations,
                })

    patches = sorted({r["patchiness"] for r in rows})
    seeds = sorted({r["seed"] for r in rows})

    def cell(field, w, p, s):
        return next(r[field] for r in rows if r["window"] == w and r["patchiness"] == p
                    and r["seed"] == s)

    summary = []
    for w in WINDOWS:
        per_seed = [np.corrcoef(patches, [cell("advantage", w, p, s) for p in patches])[0, 1]
                    for s in seeds]
        means = [float(np.mean([cell("advantage", w, p, s) for s in seeds])) for p in patches]
        gains = [float(np.mean([cell("selection_gain", w, p, s) for s in seeds])) for p in patches]
        summary.append({
            "window": w,
            "advantage_by_patchiness": [round(v, 4) for v in means],
            "gain_by_patchiness": [round(v, 4) for v in gains],
            "corr_pooled": round(float(np.corrcoef(patches, means)[0, 1]), 4),
            "corr_per_seed": [round(float(c), 4) for c in per_seed],
            "all_seeds_negative": bool(all(c < 0 for c in per_seed)),
            "rank_order": [int(x) for x in np.argsort(np.argsort([-m for m in means]))],
        })

    payload = {"source": str(SOURCE), "patchiness": patches, "seeds": seeds,
               "windows": list(WINDOWS), "summary": summary, "rows": rows}
    (HERE / "results.json").write_text(json.dumps(payload, indent=2) + "\n")

    print(f"\n  {'window':>7}" + "".join(f"{p:>8}" for p in patches) + "     corr   all-neg   ranks")
    for e in summary:
        ranks = "".join(str(r + 1) for r in e["rank_order"])
        print(f"  {e['window']:>7}" + "".join(f"{v:>8.3f}" for v in e["advantage_by_patchiness"])
              + f"  {e['corr_pooled']:>+7.3f}   {str(e['all_seeds_negative']):>5}   {ranks}")
    first, last = summary[0], summary[-1]
    print(f"\n  rank order stable across a {WINDOWS[-1] // WINDOWS[0]}x window range: "
          f"{first['rank_order'] == last['rank_order']}")
    print(f"  wrote {HERE / 'results.json'}")


if __name__ == "__main__":
    main()
