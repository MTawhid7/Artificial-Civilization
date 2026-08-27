"""Does a sense of one's own ignorance change how agents move, or whether they live?

    uv run python experiments/b0-fog/analyse.py

No new simulation. The fog arm is this experiment's three runs; the **no-fog arm
is b0-neural's S1 at `gather_efficiency` 2.5**, already on disk, whose resolved
config differs from this one in exactly one key — the presence of `primitives.p2`.
Re-using it rather than re-running it is the a1-run-length pattern, and it makes
the two arms identical in every parameter that is not fog by construction rather
than by care.

**Paired by landscape, not by network.** Fog consumes no randomness, so the
`generator` stream is untouched and world *w* of seed *s* is the same terrain
with the same founding cohort in both arms. The initial *weights* are not
shared: fog widens the input layer from 36 to 40, so `initial_weights` draws a
different shape from `policy_init`. The arms share a world; they do not share a
starting brain.

**Two questions, and only the first is B0's ship criterion.**

1. Does `exploration_rate` beat its shuffled-step null on the fog arm? That is a
   statement about one arm against chance.
2. Does fog *change* coverage or survival? That is the between-arm comparison,
   and it is made on raw effects rather than z *(→ D-060)*.

For (2) the fogless arm is scored with an explicit `block`, because without a
known map the same number is heading persistence rather than exploration. The
detector records that choice in `detail["block_source"]`; so does this file.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from lens import exploration_rate
from lens.base import ChronicleReader

HERE = Path(__file__).parent
CORPUS = Path("corpus/runs")
NO_FOG = HERE.parent / "b0-neural" / "results.json"
BLOCK = 4          # the fog arm's geometry, applied to both for comparability
BURN_IN = 0.5


def _population(run_dir: Path) -> dict[int, float]:
    with ChronicleReader(run_dir) as reader:
        rows = reader.sql(
            "select world_id, population from {aggregate} order by world_id, tick"
        ).fetchnumpy()
    world = np.asarray(rows["world_id"])
    pop = np.asarray(rows["population"], dtype=np.float64)
    return {
        int(w): float(pop[world == w][int((world == w).sum() * BURN_IN):].mean())
        for w in np.unique(world)
    }


def _score(run_dir: Path, seed: int) -> tuple:
    with ChronicleReader(run_dir) as reader:
        # Same RNG seeding as forge.sweep.score, so the fog arm's numbers here
        # match the ones its own results.json reports.
        f = exploration_rate.compute(reader, rng=np.random.default_rng(seed * 1000 + 3),
                                     block=BLOCK)
    return f, _population(run_dir)


def main() -> None:
    fog_res = HERE / "results.json"
    if not fog_res.exists():
        raise SystemExit(f"no {fog_res}; run the sweep first")
    if not NO_FOG.exists():
        raise SystemExit(f"no {NO_FOG}; b0-fog's control arm is b0-neural's S1 gather-2.5 runs")

    fog = {int(r["seed"]): r["run_id"] for r in json.loads(fog_res.read_text())["results"]}
    nofog = {
        int(r["seed"]): r["run_id"]
        for r in json.loads(NO_FOG.read_text())["results"]
        if r["params"]["intelligence.stage"] == "S1"
        and r["params"]["agent.gather_efficiency"] == 2.5
    }
    seeds = sorted(set(fog) & set(nofog))
    missing = [rid for rid in (*fog.values(), *nofog.values())
               if not (CORPUS / rid / "meta.json").exists()]
    if missing:
        raise SystemExit(f"{len(missing)} runs are not in corpus/; regenerate them")

    print(f"\n  b0-fog — S1 with P2 at L0 against S1 without, {len(seeds)} seeds\n")
    print("  1. exploration_rate against its own shuffled-step null  [the ship criterion]\n")
    print(f"    {'arm':>8}{'seed':>6}{'excess/tick':>13}{'observed':>11}{'shuffled':>11}"
          f"{'z':>8}{'verdict':>10}{'agents':>8}")

    rows, pops = [], {}
    for label, index in (("fog", fog), ("no fog", nofog)):
        for seed in seeds:
            f, pop = _score(CORPUS / index[seed], seed)
            pops[(label, seed)] = pop
            d = f.detail
            rows.append({"arm": label, "seed": seed, **f.to_dict()})
            print(f"    {label:>8}{seed:>6}{f.magnitude:>13.5f}"
                  f"{d.get('observed_blocks_per_tick', float('nan')):>11.4f}"
                  f"{d.get('shuffled_blocks_per_tick', float('nan')):>11.4f}"
                  f"{f.effect_size:>8.2f}{'FIRED' if f.fired else 'silent':>10}"
                  f"{d.get('n_agents', 0):>8}")

    fired = sum(r["fired"] for r in rows if r["arm"] == "fog")
    print(f"\n    fog arm fires in {fired}/{len(seeds)} seeds — the firing rule needs 3")

    print("\n  2. does fog change anything?  [raw effects, never z — D-060]\n")
    print(f"    {'quantity':>26}{'fog':>11}{'no fog':>11}{'delta':>11}")

    def arm(key, label):
        return np.array([r[key] if key in r else r["detail"][key]
                         for r in rows if r["arm"] == label], dtype=float)

    out = {"seeds": seeds, "block": BLOCK, "detectors": rows}
    for key, name in (("magnitude", "excess blocks/tick"),
                      ("observed_blocks_per_tick", "observed blocks/tick"),
                      ("shuffled_blocks_per_tick", "shuffled blocks/tick")):
        a, b = arm(key, "fog"), arm(key, "no fog")
        print(f"    {name:>26}{a.mean():>11.4f}{b.mean():>11.4f}{a.mean() - b.mean():>+11.4f}")
        out[key] = {"fog": round(float(a.mean()), 5), "no_fog": round(float(b.mean()), 5),
                    "delta": round(float(a.mean() - b.mean()), 5)}

    # Survival, paired by (seed, world) exactly as b0-neural does it.
    delta = np.array([pops[("fog", s)][w] - pops[("no fog", s)][w]
                      for s in seeds for w in sorted(pops[("fog", s)])])
    fog_mean = np.mean([v for s in seeds for v in pops[("fog", s)].values()])
    nofog_mean = np.mean([v for s in seeds for v in pops[("no fog", s)].values()])
    se = delta.std(ddof=1) / np.sqrt(delta.size)
    print(f"    {'mean population':>26}{fog_mean:>11.1f}{nofog_mean:>11.1f}"
          f"{delta.mean():>+11.1f}")
    print(f"\n    paired over {delta.size} (seed, world) pairs — same landscape, same founders,")
    print(f"    different brains: t = {delta.mean() / max(se, 1e-12):+.2f}, "
          f"fog ahead in {int((delta > 0).sum())}/{delta.size}")

    out["survival"] = {
        "n_pairs": int(delta.size),
        "fog_mean": round(float(fog_mean), 2),
        "no_fog_mean": round(float(nofog_mean), 2),
        "paired_delta": round(float(delta.mean()), 2),
        "paired_t": round(float(delta.mean() / max(se, 1e-12)), 3),
        "fog_win_share": round(float((delta > 0).mean()), 3),
    }
    (HERE / "fog.json").write_text(json.dumps(out, indent=2) + "\n")
    print(f"\n  wrote {HERE / 'fog.json'}\n")


if __name__ == "__main__":
    main()
