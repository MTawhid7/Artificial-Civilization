"""P2 — Fog / Information, at L0.

Not "agents cannot see beyond radius X" — the view radius is already a fact of
the observation gather and needs no primitive. **P2 is that two agents in the
same world inhabit different perceived worlds**, and at L0 the only thing that
differs between them is where each has already been.

    L0  per-agent view radius, binary known/unknown map     <- this
    L1  beliefs carry (value, confidence, age, provenance, source); decay
    L2  partial propositions; contradictory beliefs; information as a good

**The known map is coarse, and that is a decision, not a shortcut** (D-073).
`docs/06-data-model.md` specifies `known_mask` as `bool[N, H, W]` and flags it as
"the expensive one". It is: at corpus scale that is 278 MB resident, and because
invariant I3 requires a checkpoint to capture everything, it is also 278 MB per
keyframe — which ends forking, which ends causal inference. Bit-packing gets it
to 35 MB and costs more than it saves: the update is a scatter, `bitwise_or.at`
is an unbuffered ufunc, and 1.7M of them per tick is tens of milliseconds.

So knowledge is stored per **block** of `block x block` cells. At the default
block 4 on a 64 grid that is a 16x16 map per agent — 8 MB at B0's scale, small
enough to checkpoint without thinking about it.

The coarsening is not only cheaper, it is more honest about what is being
claimed. "I have been in this region" is a memory an agent could plausibly hold;
"I have seen this exact 1x1 cell and not the one beside it" is a database. It
also fixes what `exploration_rate` measures: novelty per region rather than
novelty per step, which is the difference between a statement about territory
and a restatement of how far something walked.

**Marking is by view, not by position.** An agent marks every block its view
patch touches, so knowledge is what it *saw*, not where it stood. Marking only
the occupied block would make the known map a trail, and a trail is not fog.
"""

from __future__ import annotations

import numpy as np

# Unknown-share north/east/south/west. Four because the action set is four
# (core.state.N_ACTIONS) and the direction order is shared with the tick loop.
N_FOG_INPUTS = 4


def n_blocks(grid: int, block: int) -> int:
    """Blocks per side. `block` need not divide `grid` — the last one is short."""
    return (grid + block - 1) // block


def mark_seen(
    known: np.ndarray,
    y: np.ndarray,
    x: np.ndarray,
    alive: np.ndarray,
    view_radius: int,
    grid: int,
    block: int,
) -> np.ndarray:
    """Mark the blocks each living agent can see. Returns newly-known counts, [W, N].

    `known` is `[W, N, B, B]` uint8 and is modified in place. The return value is
    how many blocks each agent learned *this tick*, which is what `EXPLORE_CELL`
    records and what `exploration_rate` reads.

    The view patch is a rectangle, so the blocks it overlaps are the rectangle
    of blocks between its corner blocks. A run of `L` consecutive cells touches
    at most `(L + block - 2) // block + 1` of them — worst case when the run
    starts one cell before a boundary. At view_radius 2 and block 4 that is 2
    per axis, so the loop below runs a fixed four times regardless of
    population: a shape fixed by config, exactly like every RNG draw.

    Getting that bound loose is not merely wasteful. Marking a block the agent
    cannot see credits it with knowledge it never acquired, which inflates the
    known map and silently deflates everything `exploration_rate` measures.
    """
    W, N = y.shape
    B = known.shape[2]
    d = view_radius

    # Block coordinates of the patch's top-left and bottom-right corners. The
    # world is a torus, so the patch can wrap; taking the corners modulo the
    # grid first and then walking `span` steps covers the wrap without a branch.
    y0 = ((y.astype(np.int64) - d) % grid) // block
    x0 = ((x.astype(np.int64) - d) % grid) // block
    span = (2 * d + block - 1) // block + 1  # max blocks a (2d+1)-cell run touches

    world_idx = np.arange(W, dtype=np.int64)[:, None]
    newly = np.zeros((W, N), dtype=np.int64)

    for dy in range(span):
        for dx in range(span):
            by = (y0 + dy) % B
            bx = (x0 + dx) % B
            was = known[world_idx, np.arange(N, dtype=np.int64)[None, :], by, bx]
            # Only the living learn. Dead slots are written with their own
            # existing value, which is a no-op, rather than skipped — the write
            # has to happen at full [W, N] shape either way.
            gained = alive & (was == 0)
            known[world_idx, np.arange(N, dtype=np.int64)[None, :], by, bx] = np.where(
                gained, np.uint8(1), was
            )
            newly += gained
    return newly


def unknown_by_sector(
    known: np.ndarray,
    y: np.ndarray,
    x: np.ndarray,
    block: int,
    radius: int,
    masks,
) -> np.ndarray:
    """Share of blocks that are unknown in each direction, `[W, N, 4]`.

    This is what the policy actually perceives of its own ignorance, and it is
    the only P2 signal S1 gets at L0. Computed by running the **existing**
    `s0_reactive.sector_masks` over a block-space patch rather than a
    cell-space one: a second sector implementation would be a second thing to
    keep consistent with the direction order N/E/S/W, and that order is shared
    with the tick loop's movement deltas.

    Returns unknown-share, not known-share, so that "there is something out
    there I have not seen" is a positive number. Nothing forces the network to
    treat it as attractive; whether curiosity pays is what the detector asks.
    """
    W, N = y.shape
    B = known.shape[2]
    side = 2 * radius + 1

    by = (y.astype(np.int64) // block)[:, :, None]
    bx = (x.astype(np.int64) // block)[:, :, None]
    off = np.arange(-radius, radius + 1, dtype=np.int64)

    rows = (by + off[None, None, :]) % B          # [W, N, side]
    cols = (bx + off[None, None, :]) % B

    # [W, N, side, side] gather of the block patch around each agent.
    w_idx = np.arange(W, dtype=np.int64)[:, None, None, None]
    n_idx = np.arange(N, dtype=np.int64)[None, :, None, None]
    patch = known[w_idx, n_idx, rows[:, :, :, None], cols[:, :, None, :]]

    unknown = (patch == 0).astype(np.float32).reshape(W, N, side * side)
    from core.policy.s0_reactive import sector_scores

    return sector_scores(unknown, masks)
