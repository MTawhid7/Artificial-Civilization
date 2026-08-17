"""Plot a sweep's dose-response curve from results.json.

The last link in the chain the A1 stage exists to prove: sim → log → sweep →
detector → null → plot. Every step before this one is machinery; this is where a
parameter and an effect size get put on the same axes and the result becomes
something you can look at and argue with.

    uv run python tools/plot_sweep.py experiments/a1-patchiness

**Plots the raw effect and the z-score side by side, always.** Neither alone is
honest. A raw statistic plotted without a null invites the eye to read structure
into noise; a z-score plotted without the raw effect hides the fact that z depends
on sample size.

That second failure is not hypothetical here. In the A1 patchiness sweep, z traced
a clean monotonic curve against patchiness (r = 0.97) while the raw effect barely
moved (r = 0.77, and a total change of about one between-seed standard deviation).
The difference was population: patchy worlds support fewer agents, fewer agents
log fewer windows, fewer windows tighten the null, and z rises for reasons that
have nothing to do with behavior.

**Population is an outcome variable in this project**, so any parameter that moves
it moves every sample size and therefore every z. The pairing below is the
standing defense against that.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no display on a headless run; write files, never windows
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

VERDICT_COLOR = {"FIRING": "#1a7f37", "candidate": "#bf8700", "silent": "#8b949e"}


def plot(experiment_dir: Path) -> Path:
    payload = json.loads((experiment_dir / "results.json").read_text())
    summary = payload["summary"]
    results = payload["results"]
    axis = list(payload["spec"].get("sweep", {}))
    if not axis:
        raise SystemExit("no swept axis in this spec; nothing to plot against")
    axis_name = axis[0]

    detectors = [k for k in summary[0] if k not in ("params", "n_seeds")]
    x = [entry["params"][axis_name] for entry in summary]

    fig, axes = plt.subplots(
        len(detectors), 2, figsize=(12, 3.4 * len(detectors)), sharex=True, squeeze=False
    )

    for row, detector in enumerate(detectors):
        per_point = {
            entry["params"][axis_name]: [
                r["firings"][detector]
                for r in results
                if r["params"].get(axis_name) == entry["params"][axis_name]
            ]
            for entry in summary
        }
        colors = [VERDICT_COLOR[entry[detector]["verdict"]] for entry in summary]

        # --- left: the raw effect, which is the thing that was measured --------
        ax = axes[row, 0]
        for xv, firings in per_point.items():
            vals = [f["magnitude"] for f in firings]
            ax.scatter([xv] * len(vals), vals, s=18, alpha=0.45, color="#57606a", zorder=2)
        raw = [np.mean([f["magnitude"] for f in per_point[xv]]) for xv in x]
        ax.plot(x, raw, color="#24292f", lw=1.4, zorder=3)
        ax.scatter(x, raw, c=colors, s=90, zorder=4, edgecolors="white", linewidths=1.2)
        ax.axhline(0, color="#8b949e", lw=0.8, zorder=1)
        ax.set_ylabel(f"{detector}\nraw effect")
        ax.grid(alpha=0.2, zorder=0)
        if row == 0:
            ax.set_title("raw effect — what was measured", fontsize=10)

        # --- right: z, annotated with n so the dependence stays visible --------
        ax = axes[row, 1]
        for xv, firings in per_point.items():
            vals = [f["effect_size"] for f in firings]
            ax.scatter([xv] * len(vals), vals, s=18, alpha=0.45, color="#57606a", zorder=2)
        zs = [entry[detector]["mean_effect_size"] for entry in summary]
        ax.plot(x, zs, color="#24292f", lw=1.4, zorder=3)
        ax.scatter(x, zs, c=colors, s=90, zorder=4, edgecolors="white", linewidths=1.2)
        thr = results[0]["firings"][detector]["threshold"]
        ax.axhspan(-thr, thr, color="#8b949e", alpha=0.13, zorder=1)
        ax.axhline(0, color="#8b949e", lw=0.8, zorder=1)
        ax.set_ylabel("z vs null")
        ax.grid(alpha=0.2, zorder=0)
        if row == 0:
            ax.set_title("z — depends on sample size; read with the left panel", fontsize=10)

        for entry, xv, z in zip(summary, x, zs):
            n = int(np.mean([f["n_observations"] for f in per_point[xv]]))
            ax.annotate(
                f"{entry[detector]['seeds_fired']}/{entry['n_seeds']}\nn={n:,}",
                (xv, z), textcoords="offset points", xytext=(0, 9),
                ha="center", fontsize=7, color="#57606a",
            )

    for ax in axes[-1, :]:
        ax.set_xlabel(axis_name)
    handles = [
        plt.Line2D([], [], marker="o", ls="", color=c, label=f"{v}  (n seeds firing)")
        for v, c in VERDICT_COLOR.items()
    ]
    handles.append(
        plt.Line2D([], [], color="#8b949e", lw=8, alpha=0.3, label="within null (|z| < threshold)")
    )
    axes[0, 0].legend(handles=handles, fontsize=8, loc="best", framealpha=0.9)
    fig.suptitle(
        f"{payload['spec'].get('name', experiment_dir.name)} — "
        f"{len(results)} runs, {payload['wall_seconds']:.0f}s",
        fontsize=11,
    )
    fig.tight_layout()

    out = experiment_dir / "dose_response.png"
    fig.savefig(out, dpi=150)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("experiment_dir")
    args = p.parse_args()
    print(f"  wrote {plot(Path(args.experiment_dir))}")


if __name__ == "__main__":
    main()
