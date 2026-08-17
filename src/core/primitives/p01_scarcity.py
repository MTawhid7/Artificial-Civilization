"""P1 — Scarcity, at L0.

One resource kind, logistic regrowth, patchiness set by the generator. L1 adds
multiple kinds with per-kind regeneration classes and rising marginal extraction
cost; L2 adds substitution and extraction that alters future regeneration. Neither
is reachable at intelligence stage S0 (see the gate table in core/config.py).

The primitive to keep in view even at L0 is that effective scarcity is *derived*,
not stored. At L0 it happens to equal physical stock because there is nothing yet
to drive a wedge between them. Everything interesting about P1 lives in that
wedge, so nothing here should assume the two are the same.
"""

from __future__ import annotations

import numpy as np


def regrow(resource: np.ndarray, capacity: np.ndarray, rate: float, seed_rain: float) -> None:
    """Regrowth, in place: dR = (1 - R/K) * (rate * R + seed_rain * K).

    Logistic, plus a recolonization term. Logistic alone has the two properties
    that make depletion consequential — recovery is slowest when stock is low, and
    growth saturates at capacity — and one that makes the whole simulation
    degenerate: **zero is an absorbing state.** With `dR = rate * R * (1 - R/K)`,
    a cell stripped to zero has zero growth and stays empty forever.

    That is not a harsh world, it is a broken one. Measured at the default
    settings, 98% of cells hit zero within 50 ticks and total resource then never
    moved again; every world was a countdown to extinction and no parameter choice
    changed anything but the date.

    `seed_rain` is recolonization from beyond the cell — a seed bank, a
    neighbouring patch, a migrating population. It vanishes at capacity, so
    abundance is still bounded, but it makes recovery possible, which is what
    turns exhaustion into a setback rather than an ending.

    See D-051. At L1 this becomes per-kind: a `finite` regeneration class sets
    `seed_rain` to zero on purpose, and then exhaustion really is permanent —
    which is the point of having regeneration classes at all.
    """
    headroom = 1.0 - resource / np.maximum(capacity, 1e-6)
    np.add(resource, headroom * (rate * resource + seed_rain * capacity), out=resource)
    np.clip(resource, 0.0, None, out=resource)


def extract(
    resource_flat: np.ndarray,
    cell: np.ndarray,
    alive: np.ndarray,
    efficiency: float,
) -> np.ndarray:
    """Harvest one cell per living agent, first-wins on contention.

    Two agents on one cell is resolved by agent slot order, deterministically, and
    never by whatever order a scatter happens to visit them (determinism rule 6).
    `np.add.at` would give both agents a share; the semantics here are that the
    cell is taken, which needs an explicit sort.

    Args:
        resource_flat: [W, G*G], modified in place.
        cell: [W, N] flat cell index per agent.
        alive: [W, N] mask.
        efficiency: energy yielded per unit of resource.

    Returns:
        [W, N] energy gained per agent; zero for the dead and for losers.
    """
    n_worlds, n_agents = cell.shape
    slot = np.broadcast_to(np.arange(n_agents, dtype=np.int64), cell.shape)

    # Sort by (cell, slot). lexsort takes the primary key last.
    order = np.lexsort((slot, cell), axis=1)
    sorted_cell = np.take_along_axis(cell, order, axis=1)
    sorted_alive = np.take_along_axis(alive, order, axis=1)

    # First occurrence of each cell among the sorted, living agents.
    is_first = np.ones_like(sorted_cell, dtype=bool)
    is_first[:, 1:] = sorted_cell[:, 1:] != sorted_cell[:, :-1]
    wins_sorted = is_first & sorted_alive

    wins = np.zeros_like(alive)
    np.put_along_axis(wins, order, wins_sorted, axis=1)

    idx = cell.astype(np.intp)
    stock = np.take_along_axis(resource_flat, idx, axis=1)
    taken = np.where(wins, stock, np.float32(0.0)).astype(np.float32)
    np.put_along_axis(resource_flat, idx, stock - taken, axis=1)
    return taken * np.float32(efficiency)


def effective_scarcity(resource: np.ndarray) -> np.ndarray:
    """At L0 this is physical stock. It is a separate function anyway, because the
    divergence between the two is a detector at L2 and every caller should already
    be asking for the derived quantity rather than the raw field."""
    return resource
