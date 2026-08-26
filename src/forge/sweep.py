"""Run a parameter sweep and score every run with the detector suite.

An experiment is a directory holding `spec.yaml` and, when it is finished,
`result.md` — **whether or not the hypothesis survived**. Negative results are
committed (docs/11-engineering.md). A sweep that only records its successes is a
way of accumulating false beliefs at a steady rate.

Worlds are the replicate axis: one run of 32 worlds is 32 independent world
instances, not one. Top-level seeds are then varied on top of that, because the
firing rule requires an effect to hold across at least three of them
(docs/07-detectors.md#firing-rules).
"""

from __future__ import annotations

import argparse
import itertools
import json
import time
from pathlib import Path

import numpy as np
import yaml

from core.config import Config, resolve
from forge import viability
from forge.run import run
from lens import collapse, gradient_ascent, pop_stability
from lens.base import ChronicleReader, Firing

# `directed_foraging` is deliberately absent: withdrawn under D-056, and a
# withdrawn detector must not keep producing numbers that end up in a table.
#
# APPEND ONLY. `score()` seeds each detector from its position in this dict, so
# inserting one in the middle would silently change the null draws of everything
# below it and make new z values incomparable with the results already committed
# under experiments/.
DETECTORS = {
    "pop_stability": pop_stability.compute,
    "gradient_ascent": gradient_ascent.compute,
    "collapse": collapse.compute,
}


def _set_path(data: dict, dotted: str, value) -> dict:
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in data.items()}
    node = out
    parts = dotted.split(".")
    for part in parts[:-1]:
        node[part] = dict(node.get(part, {}))
        node = node[part]
    node[parts[-1]] = value
    return out


def score(run_dir: Path, seed: int) -> list[Firing]:
    """Every detector gets its own RNG, seeded from the run.

    Null models are randomized, so scoring must be reproducible too: rerunning the
    analysis on the same Chronicle has to give the same z, or a borderline result
    changes verdict depending on when you looked at it.
    """
    firings = []
    with ChronicleReader(run_dir) as reader:
        for i, (name, fn) in enumerate(DETECTORS.items()):
            firings.append(fn(reader, rng=np.random.default_rng(seed * 1000 + i)))
    return firings


def sweep(spec: dict, out_root: Path, experiment_dir: Path,
          *, precheck: bool = True) -> dict:
    base = spec["base"]
    axes = spec.get("sweep", {})
    seeds = spec.get("seeds", [0, 1, 2])

    names = list(axes)
    combos = list(itertools.product(*(axes[n] for n in names))) or [()]

    def config_for(combo) -> Config:
        raw = base
        for name, value in zip(names, combo):
            raw = _set_path(raw, name, value)
        return resolve(raw, source=str(experiment_dir / "spec.yaml"))

    # D-065: every parameter point gets its own ceiling check, because the point
    # that pins is rarely the one you would have guessed. Costs ~8% of the sweep
    # and stops it before an hour is spent producing a number about the array.
    prechecks = []
    if precheck:
        print(f"  headroom precheck: {len(combos)} point(s), "
              f"{viability.PILOT_WORLDS} worlds each", flush=True)
        for combo in combos:
            label = ", ".join(f"{n}={v}" for n, v in zip(names, combo)) or "base"
            report = viability.headroom(config_for(combo), seeds[0], out_root=out_root / "pilots")
            report["params"] = dict(zip(names, combo))
            viability.enforce(report, label)
            prechecks.append(report)
        print(flush=True)

    results = []
    total = len(combos) * len(seeds)
    started = time.perf_counter()

    for i, (combo, seed) in enumerate(itertools.product(combos, seeds), start=1):
        cfg: Config = config_for(combo)

        label = ", ".join(f"{n}={v}" for n, v in zip(names, combo)) or "base"
        print(f"  [{i}/{total}] {label}  seed={seed}", flush=True)
        meta = run(cfg, seed, out_root=out_root, progress=False)

        firings = score(out_root / "runs" / meta["run_id"], seed)
        for f in firings:
            print(f"        {f}")

        results.append(
            {
                "params": dict(zip(names, combo)),
                "seed": seed,
                "run_id": meta["run_id"],
                "ms_per_tick": meta["ms_per_tick"],
                "chronicle_mb": round(meta["chronicle_bytes"] / 2**20, 2),
                "final_population": meta["final_population"],
                "firings": {f.detector: f.to_dict() for f in firings},
            }
        )

    payload = {
        "spec": spec,
        "wall_seconds": round(time.perf_counter() - started, 1),
        # Kept in the record: an experiment's ceiling is part of how it should be
        # read, and "no world approached capacity" is a claim that needs evidence
        # like any other.
        "headroom": prechecks,
        "results": results,
        "summary": _summarize(results, names),
    }
    (experiment_dir / "results.json").write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def _summarize(results: list[dict], axis_names: list[str]) -> list[dict]:
    """Per parameter point: mean effect size, and how many seeds fired.

    The seed count is the part that matters. An effect present in one seed of
    three is a candidate, not a finding, and the summary keeps that distinction
    visible rather than averaging it away.
    """
    keyed: dict[tuple, list[dict]] = {}
    for r in results:
        keyed.setdefault(tuple(r["params"].get(n) for n in axis_names), []).append(r)

    out = []
    for key, group in sorted(keyed.items(), key=lambda kv: [str(x) for x in kv[0]]):
        entry = {"params": dict(zip(axis_names, key)), "n_seeds": len(group)}
        for detector in DETECTORS:
            zs = [g["firings"][detector]["effect_size"] for g in group]
            mags = [g["firings"][detector]["magnitude"] for g in group]
            fired = sum(g["firings"][detector]["fired"] for g in group)
            skipped = [g["firings"][detector]["detail"].get("skipped") for g in group]
            entry[detector] = {
                "mean_effect_size": round(float(np.mean(zs)), 3),
                "mean_magnitude": round(float(np.mean(mags)), 5),
                "seeds_fired": fired,
                # docs/07-detectors.md: an effect in fewer than three seeds is a
                # candidate, never a result.
                #
                # "skipped" is kept distinct from "silent" on purpose. Silent
                # means measured and did not fire; skipped means the run does not
                # carry the data — a log tier without the events, too few worlds.
                # Reporting the second as the first is how a detector comes to be
                # believed tested when it was never run.
                "verdict": (
                    "skipped" if all(skipped)
                    else "FIRING" if fired >= 3
                    else "candidate" if fired
                    else "silent"
                ),
            }
            if all(skipped):
                entry[detector]["skipped"] = skipped[0]
        out.append(entry)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("spec", help="path to an experiment spec.yaml")
    p.add_argument("--out", default="corpus")
    p.add_argument("--skip-precheck", action="store_true",
                   help="skip the headroom pilot (D-065) — only when a pinned "
                        "ceiling is genuinely what you are studying")
    args = p.parse_args()

    spec_path = Path(args.spec)
    spec = yaml.safe_load(spec_path.read_text())
    payload = sweep(spec, Path(args.out), spec_path.parent,
                    precheck=not args.skip_precheck)

    print(f"\n  {spec.get('name', spec_path.parent.name)} — {payload['wall_seconds']}s\n")
    axis_names = list(spec.get("sweep", {}))
    header = "  " + "".join(f"{n.split('.')[-1]:>14}" for n in axis_names)
    print(header + "".join(f"{d:>22}" for d in DETECTORS))
    for entry in payload["summary"]:
        row = "  " + "".join(f"{entry['params'][n]:>14}" for n in axis_names)
        for d in DETECTORS:
            e = entry[d]
            row += f"{e['mean_effect_size']:>10.2f} {e['verdict']:>11}"
        print(row)
    print(f"\n  wrote {spec_path.parent / 'results.json'}")


if __name__ == "__main__":
    main()
