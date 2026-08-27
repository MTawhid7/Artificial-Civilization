"""B0's survival criterion: does the evolved policy beat the reactive genome?

    uv run python experiments/b0-neural/analyse.py

No new simulation — this reads the aggregate tier of runs `forge.sweep` already
wrote.

**Why this is not a detector.** Every detector in `src/lens/` is a pure function
over *one* Chronicle, asking whether that run beats a null. This asks whether
one arm beats another arm, which is a comparison between runs and belongs to the
experiment rather than to the suite (07-detectors.md).

**Why it is paired.** S1's randomness comes from the `policy_init` and `lineage`
streams, so `generator` is untouched and world *w* of seed *s* is the same
landscape with the same founding cohort in both arms (D-072). The replicate is
therefore a **(seed, world) pair**, and the statistic is a within-pair
difference: between-world spread in this project runs about ten to one, and
pairing removes all of it.

**Why raw effect and not z.** D-060. A control arm that works shrinks
between-replicate variance and inflates its own z, so ranking the arms by z
would reward the arm with the tighter spread rather than the better outcome.
`sweep.py`'s printed table is a z table; this is the comparison that counts.

**What "survival" means here.** Mean population over the post-burn-in window,
per world. Population is the D-007 currency in aggregate form — a policy that
feeds itself and reproduces sustains more agents on the same landscape — and it
is available at the aggregated tier, which every run carries.

Nothing here conditions on a variable the policy influences. Energy, lifespan
and gather rate are all downstream of the behaviour being compared, and
splitting by any of them is the D-056 trap.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from lens.base import ChronicleReader

HERE = Path(__file__).parent
RESULTS = HERE / "results.json"
CORPUS = Path("corpus/runs")

# The founding cohort overshoots and crashes in the first few hundred ticks of
# every world, in both arms. Scoring from tick 0 would average a startup
# transient into the comparison; `pop_stability` and `collapse` drop it for the
# same reason.
BURN_IN = 0.5


def population_by_world(run_dir: Path) -> dict[int, float]:
    """Post-burn-in mean population per world."""
    with ChronicleReader(run_dir) as reader:
        rows = reader.sql(
            "select tick, world_id, population from {aggregate} order by world_id, tick"
        ).fetchnumpy()
    world = np.asarray(rows["world_id"])
    pop = np.asarray(rows["population"], dtype=np.float64)
    out = {}
    for w in np.unique(world):
        series = pop[world == w]
        out[int(w)] = float(series[int(len(series) * BURN_IN):].mean())
    return out


def main() -> None:
    if not RESULTS.exists():
        raise SystemExit(
            f"no {RESULTS}. Run the sweep first:\n"
            "  uv run python -m forge.sweep experiments/b0-neural/spec.yaml"
        )
    payload = json.loads(RESULTS.read_text())

    # (dose, seed, stage) -> run_id
    index: dict[tuple[float, int, str], str] = {}
    for r in payload["results"]:
        dose = float(r["params"]["agent.gather_efficiency"])
        index[(dose, int(r["seed"]), r["params"]["intelligence.stage"])] = r["run_id"]

    doses = sorted({d for d, _, _ in index})
    seeds = sorted({s for _, s, _ in index})
    missing = [k for k, rid in index.items() if not (CORPUS / rid / "meta.json").exists()]
    if missing:
        raise SystemExit(f"{len(missing)} runs are not in corpus/; regenerate the sweep")

    print(f"\n  b0-neural — survival, paired by (seed, world) within each dose\n")
    print(f"    {'gather':>7}{'pairs':>7}{'S0 mean':>10}{'S1 mean':>10}"
          f"{'delta':>10}{'t':>8}{'ratio':>8}{'S1 won':>10}{'seeds':>7}")

    rows = []
    for dose in doses:
        a_all, b_all, seed_col = [], [], []
        for seed in seeds:
            s0 = population_by_world(CORPUS / index[(dose, seed, "S0")])
            s1 = population_by_world(CORPUS / index[(dose, seed, "S1")])
            for w in sorted(set(s0) & set(s1)):
                a_all.append(s0[w])
                b_all.append(s1[w])
                seed_col.append(seed)

        a, b = np.array(a_all), np.array(b_all)
        delta = b - a
        sc = np.array(seed_col)
        # The spread across pairs, not across agents. A pair is one independent
        # observation of "this world, run with two policies" (D-058).
        se = delta.std(ddof=1) / np.sqrt(delta.size)
        # Per seed, because the firing rule needs an effect to hold across at
        # least three seeds, and averaging that away is how a one-seed effect
        # becomes a reported result (07-detectors.md).
        per_seed = np.array([delta[sc == s].mean() for s in seeds])

        print(f"    {dose:>7.1f}{delta.size:>7}{a.mean():>10.1f}{b.mean():>10.1f}"
              f"{delta.mean():>+10.1f}{delta.mean() / max(se, 1e-12):>+8.1f}"
              f"{b.mean() / max(a.mean(), 1e-9):>8.3f}"
              f"{int((delta > 0).sum()):>7}/{delta.size}"
              f"{int((per_seed > 0).sum()):>5}/{len(seeds)}")

        rows.append({
            "gather_efficiency": dose,
            "n_pairs": int(delta.size),
            "s0_mean": round(float(a.mean()), 2),
            "s1_mean": round(float(b.mean()), 2),
            "paired_delta": round(float(delta.mean()), 2),
            "paired_delta_se": round(float(se), 3),
            "paired_t": round(float(delta.mean() / max(se, 1e-12)), 3),
            "ratio_s1_over_s0": round(float(b.mean() / max(a.mean(), 1e-9)), 4),
            "s1_win_share": round(float((delta > 0).mean()), 3),
            "per_seed_delta": [round(float(x), 2) for x in per_seed],
            "seeds_with_s1_ahead": int((per_seed > 0).sum()),
        })

    print("\n    ratio < 1 means the hand-written S0 rule sustains more agents on the")
    print("    same landscape. The dose axis asks whether that lead depends on")
    print("    how much there is to find.\n")

    out = {
        "statistic": "post-burn-in mean population per world",
        "burn_in_fraction": BURN_IN,
        "replication_unit": "(seed, world) pair — paired by landscape, D-072",
        "comparison": "raw effect, not z (D-060)",
        "doses": rows,
    }
    (HERE / "survival.json").write_text(json.dumps(out, indent=2) + "\n")
    print(f"  wrote {HERE / 'survival.json'}\n")


if __name__ == "__main__":
    main()
