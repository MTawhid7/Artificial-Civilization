"""`exploration_rate` — does an agent visit more of the world than its own walk explains?

**Definition.** Reconstruct each sampled agent's path from `MOVE`, reduce every
position to the P2 block containing it, and count the **distinct blocks** the
path touches. Divide by the number of steps: new blocks per agent-tick.

**Null: shuffled-step, and it controls the one thing that would otherwise
manufacture this result.** Novelty is mechanically higher for an agent that
simply moves *further*, so a detector comparing a traveller against a sitter
would be measuring distance and calling it curiosity. The surrogate takes the
agent's own per-tick displacements, shuffles their order, and re-walks from the
same start. It has the same number of steps, the same step-size distribution,
the same total path length, and the same saturation dynamics over the same
lifetime — everything except the *correspondence between where the agent has
been and where it goes next*, which is exactly the quantity of interest. Path
length is held fixed by construction rather than controlled for statistically.

Same construction as `pop_stability` and `collapse`, and the rule of thumb it
comes from: the null should be the most flattering alternative available.

**Replication unit: the world** *(→ [D-058](../../docs/DECISIONS.md#d-058))*.
Sampled agents in one world share a landscape and each contributes hundreds of
correlated steps, so they are not independent observations. The statistic is
averaged within a world and the spread is taken across worlds — `n` is the
number of worlds, not the number of agents, and not the number of steps. Getting
that wrong once turned `gradient_ascent`'s z of 4.93 into 90.8.

**Nothing here conditions on a variable the behaviour influences**
*(→ [D-056](../../docs/DECISIONS.md#d-056))*. There is no split by energy, age,
health or success — all of them are downstream of where an agent chose to walk,
which is the thing being measured.

**Observed and surrogate are computed by the same function.** The simulation
marks blocks by *view*, so an agent learns slightly more than its position
implies; this detector marks by *position*, for both arms. Mixing the two —
`EXPLORE_CELL` for the observed value and a path simulation for the null — would
make the difference between them partly a difference between two pieces of code,
which is not a null model. `EXPLORE_CELL` is read only as a cross-check, and
reported in `detail`.

Reads the sampled tier: 1-in-K agents are logged for their whole lives (D-052),
so a path is a whole life rather than a scatter of snapshots.
"""

from __future__ import annotations

import numpy as np

from chronicle import schema as S
from lens.base import ChronicleReader, Firing, wrapped_delta

THRESHOLD = 3.0
N_SURROGATES = 64
MIN_STEPS = 40        # shorter than this and "distinct blocks" is mostly the start
MIN_AGENTS = 20       # per run, across all worlds
MIN_WORLDS = 4        # fewer and the across-world spread is meaningless


def _distinct_blocks(by: np.ndarray, bx: np.ndarray, n_blocks: int) -> np.ndarray:
    """Distinct blocks visited per row of a `[S, T]` block-coordinate path."""
    ids = by * n_blocks + bx
    ids = np.sort(ids, axis=1)
    changed = np.ones_like(ids, dtype=bool)
    changed[:, 1:] = ids[:, 1:] != ids[:, :-1]
    return changed.sum(axis=1)


def compute(
    reader: ChronicleReader,
    rng: np.random.Generator | None = None,
    max_tick: int | None = None,
) -> Firing:
    rng = rng or np.random.default_rng(0)

    block, grid = _fog_geometry(reader)
    if not block:
        return _empty(
            "the run has no P2 fog: exploration is not defined without a known map"
        )

    where = f" and tick < {int(max_tick)}" if max_tick is not None else ""
    rows = reader.sql(
        f"""
        select tick, world_id, subject, a as x, b as y
        from {{events}} where event_type = {S.MOVE}{where}
        order by world_id, subject, tick
        """
    ).fetchnumpy()

    if rows["x"].size == 0:
        return _empty(
            "no MOVE events: the run was logged below the sampled tier, "
            "so no path can be reconstructed"
        )

    n_blocks = (grid + block - 1) // block
    world = rows["world_id"].astype(np.int64)
    subject = rows["subject"].astype(np.int64)
    x = rows["x"].astype(np.int64)
    y = rows["y"].astype(np.int64)

    # Rows arrive ordered by (world, subject, tick), so agent boundaries are
    # where either key changes.
    key = world * (subject.max() + 1) + subject
    starts = np.flatnonzero(np.r_[True, key[1:] != key[:-1]])
    ends = np.r_[starts[1:], key.size]

    per_agent_world: list[int] = []
    excess: list[float] = []
    observed_rate: list[float] = []
    null_rate: list[float] = []

    for lo, hi in zip(starts, ends):
        n = hi - lo
        if n < MIN_STEPS:
            continue
        ax, ay = x[lo:hi], y[lo:hi]

        # Steps on a torus: 95 -> 0 is +1, not -95. Getting this wrong turns
        # every wrap into a huge jump and inflates the surrogate's reach.
        dx = wrapped_delta(ax[:-1], ax[1:], grid)
        dy = wrapped_delta(ay[:-1], ay[1:], grid)

        obs = int(_distinct_blocks(
            (ay % grid)[None, :] // block, (ax % grid)[None, :] // block, n_blocks
        )[0])

        # Surrogates: same steps, shuffled order, same start. `permuted` with
        # axis=1 shuffles each row independently.
        tiled = np.broadcast_to(np.arange(dx.size), (N_SURROGATES, dx.size))
        perm = rng.permuted(tiled, axis=1)
        sx = (ax[0] + np.cumsum(dx[perm], axis=1)) % grid
        sy = (ay[0] + np.cumsum(dy[perm], axis=1)) % grid
        sx = np.c_[np.full(N_SURROGATES, ax[0]), sx]
        sy = np.c_[np.full(N_SURROGATES, ay[0]), sy]
        sur = _distinct_blocks(sy // block, sx // block, n_blocks).mean()

        per_agent_world.append(int(world[lo]))
        observed_rate.append(obs / n)
        null_rate.append(float(sur) / n)
        excess.append((obs - float(sur)) / n)

    if len(excess) < MIN_AGENTS:
        return _empty(f"only {len(excess)} agents with >= {MIN_STEPS} logged steps")

    aw = np.array(per_agent_world)
    ex = np.array(excess)
    obs_r = np.array(observed_rate)
    null_r = np.array(null_rate)

    worlds = np.unique(aw)
    if worlds.size < MIN_WORLDS:
        return _empty(f"only {worlds.size} worlds; need {MIN_WORLDS} to estimate a spread")

    # Average within world, then spread across worlds. See the module docstring.
    per_world = np.array([ex[aw == w].mean() for w in worlds], dtype=np.float64)
    observed = float(per_world.mean())
    se = float(per_world.std(ddof=1) / np.sqrt(per_world.size))
    z = observed / max(se, 1e-12)

    lo_t, hi_t = int(rows["tick"].min()), int(rows["tick"].max())
    return Firing(
        detector="exploration_rate",
        magnitude=observed,
        # Zero by construction: the statistic is already a paired difference
        # between an agent and its own shuffled walk, so the null's centre is not
        # estimated.
        null_mean=0.0,
        null_std=se,
        effect_size=z,
        threshold=THRESHOLD,
        fired=bool(z > THRESHOLD and observed > 0.0),
        tick_range=(lo_t, hi_t),
        n_observations=int(ex.size),
        detail={
            "excess_blocks_per_tick": observed,
            "observed_blocks_per_tick": float(obs_r.mean()),
            "shuffled_blocks_per_tick": float(null_r.mean()),
            "n_agents": int(ex.size),
            "n_worlds": int(worlds.size),
            "block": int(block),
            "null": f"shuffled-step ({N_SURROGATES} surrogates per agent)",
            **_explore_cell_crosscheck(reader, where),
        },
    )


def _fog_geometry(reader: ChronicleReader) -> tuple[int, int]:
    """`(block, grid)` from the run's frozen config, or `(0, grid)` if fog is off."""
    import yaml

    cfg = yaml.safe_load((reader.run_dir / "config.yaml").read_text())
    grid = int(cfg["world"]["grid"])
    p2 = (cfg.get("primitives") or {}).get("p2")
    return (int(p2["block"]) if p2 else 0), grid


def _explore_cell_crosscheck(reader: ChronicleReader, where: str) -> dict:
    """What the simulation itself recorded learning, for comparison only.

    Never the statistic. The simulation marks by view and this detector marks by
    position, so the two do not have to agree — but a large divergence means one
    of them is wrong, and a reader should be able to see it.
    """
    try:
        got = reader.sql(
            f"select count(*) as n, sum(a) as blocks from {{events}} "
            f"where event_type = {S.EXPLORE_CELL}{where}"
        ).fetchnumpy()
    except Exception:
        return {}
    n = int(got["n"][0] or 0)
    return {
        "explore_cell_events": n,
        "explore_cell_blocks": float(got["blocks"][0] or 0.0),
    }


def _empty(reason: str) -> Firing:
    return Firing(
        detector="exploration_rate",
        magnitude=0.0, null_mean=0.0, null_std=0.0, effect_size=0.0,
        threshold=THRESHOLD, fired=False, tick_range=(0, 0), n_observations=0,
        detail={"skipped": reason},
    )
