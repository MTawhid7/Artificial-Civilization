"""What does an S1 forward pass cost, and what does it do to the tick budget?

Run this **before** B0, not during it. At S0 the observation gather is ~40% of a
tick and `decide` is ~9%; a neural policy is the first thing that can invert that,
and the answer sets hidden width, view radius and agents-per-world rather than
being discovered after they are chosen
(docs/10-roadmap.md#b0--neural-policy, docs/00-feasibility.md#the-constraint-moved).

Synthetic, like `bench_tick`: real shapes, real arithmetic, no simulation
semantics. The policy is D-004's — **one shared network per lineage**, with a
per-agent genome embedding supplying individuality:

    input  = local patch (2r+1)^2  +  genome embedding d  +  scalars
    hidden = tanh(input @ W1 + b1)
    logits = hidden @ W2 + b2                    -> 4 actions

Lineage count matters and is easy to overlook. One shared network is a single
batched matmul; L lineages is L smaller matmuls over ragged groups, and the
grouping is not free. Both are measured, because the difference decides whether
lineages can be a swept variable or have to be a fixed small number.

    uv run python -m bench.bench_policy
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

RESULTS_DIR = Path(__file__).resolve().parent / "results"

# Measured at A0/A2 on the target machine — the baseline this is compared against.
S0_MS_PER_TICK = 11.0        # full loop, W=32 x N=1000, docs/00-feasibility.md
S0_DECIDE_MS = 0.8           # the S0 reactive policy alone
S0_OBSERVE_MS = 3.6          # the gather, at view_radius 2
N_ACTIONS = 4
EXTRA_INPUTS = 3             # energy, age, local density


def _fwd(x, w1, b1, w2, b2, h):
    """One batched forward pass, written the way the core would write it.

    Preallocated output buffers and in-place tanh: a tick must not allocate, and
    a benchmark that allocates measures the allocator.
    """
    np.matmul(x, w1, out=h)
    np.add(h, b1, out=h)
    np.tanh(h, out=h)
    return np.matmul(h, w2) + b2


def measure(worlds: int, agents: int, hidden: int, view_radius: int,
            lineages: int, ticks: int = 200, warmup: int = 30, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    n = worlds * agents
    patch = (2 * view_radius + 1) ** 2
    embed = 8
    n_in = patch + embed + EXTRA_INPUTS

    x = rng.standard_normal((n, n_in), dtype=np.float32)
    h = np.empty((n, hidden), dtype=np.float32)

    # One parameter set per lineage. Shared weights are the whole reason 32,000
    # agents is affordable (D-004).
    w1 = [rng.standard_normal((n_in, hidden), dtype=np.float32) * 0.1 for _ in range(lineages)]
    b1 = [rng.standard_normal(hidden, dtype=np.float32) for _ in range(lineages)]
    w2 = [rng.standard_normal((hidden, N_ACTIONS), dtype=np.float32) * 0.1 for _ in range(lineages)]
    b2 = [rng.standard_normal(N_ACTIONS, dtype=np.float32) for _ in range(lineages)]

    lineage_of = rng.integers(0, lineages, size=n)
    # Grouping is done once per tick in the real loop too: agents do not change
    # lineage within a tick, so the argsort is the honest cost to include.
    def one_tick():
        if lineages == 1:
            _fwd(x, w1[0], b1[0], w2[0], b2[0], h)
            return
        order = np.argsort(lineage_of, kind="stable")
        bounds = np.searchsorted(lineage_of[order], np.arange(lineages + 1))
        for k in range(lineages):
            idx = order[bounds[k]:bounds[k + 1]]
            if idx.size:
                xi = x[idx]
                np.matmul(xi, w1[k], out=h[:idx.size])
                np.add(h[:idx.size], b1[k], out=h[:idx.size])
                np.tanh(h[:idx.size], out=h[:idx.size])
                _ = np.matmul(h[:idx.size], w2[k]) + b2[k]

    # Generous warmup on purpose. The first matmul in a process pays for lazy
    # BLAS initialization, and measuring that instead of the policy produced a
    # 55% spread across identical configs before this was raised.
    for _ in range(warmup):
        one_tick()
    start = time.perf_counter()
    for _ in range(ticks):
        one_tick()
    ms = (time.perf_counter() - start) * 1000 / ticks

    # Observation cost scales linearly in patch cells — measured at A0: 9 cells
    # -> 1.4 ms, 25 -> 3.5 ms, 49 -> 6.9 ms at the default scale.
    observe_ms = S0_OBSERVE_MS * (patch / 25.0) * (n / 32000.0)
    rest_ms = (S0_MS_PER_TICK - S0_DECIDE_MS - S0_OBSERVE_MS) * (n / 32000.0)
    tick_ms = ms + observe_ms + rest_ms

    macs = n * (n_in * hidden + hidden * N_ACTIONS)
    return {
        "worlds": worlds, "agents": agents, "hidden": hidden,
        "view_radius": view_radius, "lineages": lineages,
        "n_agents": n, "n_in": n_in,
        "decide_ms": round(ms, 3),
        "observe_ms_projected": round(observe_ms, 3),
        "tick_ms_projected": round(tick_ms, 2),
        "decide_share": round(ms / tick_ms, 3),
        "vs_s0_decide": round(ms / (S0_DECIDE_MS * n / 32000.0), 1),
        "gflops": round(macs * 2 / (ms / 1000) / 1e9, 1),
        "min_per_30k_ticks": round(tick_ms * 30_000 / 1000 / 60, 1),
        "min_per_30k_throttled": round(tick_ms * 30_000 / 1000 / 60 * 1.88, 1),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--worlds", type=int, default=32)
    p.add_argument("--agents", type=int, default=1000)
    p.add_argument("--ticks", type=int, default=200)
    p.add_argument("--out", default=None)
    args = p.parse_args()

    W, N = args.worlds, args.agents
    print(f"  S1 forward pass, {W} worlds x {N} agents = {W*N:,} agents")
    print(f"  baseline: S0 tick {S0_MS_PER_TICK} ms, of which decide {S0_DECIDE_MS} "
          f"and observe {S0_OBSERVE_MS}\n")

    rows = []

    print("  hidden width (view_radius 2, one shared network)")
    print(f"    {'hidden':>7}{'decide ms':>11}{'tick ms':>10}{'decide%':>9}"
          f"{'x S0':>7}{'GFLOP/s':>9}{'min/30k*':>10}")
    for hidden in (16, 32, 48, 64, 128, 256):
        r = measure(W, N, hidden, 2, 1, ticks=args.ticks)
        rows.append(r)
        print(f"    {hidden:>7}{r['decide_ms']:>11.2f}{r['tick_ms_projected']:>10.2f}"
              f"{r['decide_share']:>8.0%}{r['vs_s0_decide']:>7.0f}{r['gflops']:>9.1f}"
              f"{r['min_per_30k_throttled']:>10.1f}")

    print("\n  view radius (hidden 48, one shared network)")
    print(f"    {'radius':>7}{'cells':>7}{'decide ms':>11}{'observe ms':>12}{'tick ms':>10}{'min/30k*':>10}")
    for r_ in (1, 2, 3, 4):
        r = measure(W, N, 48, r_, 1, ticks=args.ticks)
        rows.append(r)
        print(f"    {r_:>7}{(2*r_+1)**2:>7}{r['decide_ms']:>11.2f}"
              f"{r['observe_ms_projected']:>12.2f}{r['tick_ms_projected']:>10.2f}"
              f"{r['min_per_30k_throttled']:>10.1f}")

    print("\n  lineages (hidden 48, view_radius 2) — D-004 shares one network per lineage")
    print(f"    {'lineages':>9}{'decide ms':>11}{'tick ms':>10}{'vs 1 lineage':>14}")
    base = None
    for L in (1, 2, 4, 8, 16, 32):
        r = measure(W, N, 48, 2, L, ticks=args.ticks)
        rows.append(r)
        base = base or r["decide_ms"]
        print(f"    {L:>9}{r['decide_ms']:>11.2f}{r['tick_ms_projected']:>10.2f}"
              f"{r['decide_ms']/base:>13.2f}x")

    print("\n  * min/30k includes the 1.88x sustained-load throttle factor")

    payload = {"baseline": {"s0_ms_per_tick": S0_MS_PER_TICK,
                            "s0_decide_ms": S0_DECIDE_MS,
                            "s0_observe_ms": S0_OBSERVE_MS},
               "target": "synthetic-s1", "rows": rows}
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else RESULTS_DIR / "bench_policy_s1.json"
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"\n  wrote {out}")


if __name__ == "__main__":
    main()
