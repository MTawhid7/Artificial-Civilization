"""World state as structure-of-arrays, with worlds as a batch axis.

D-005: agents are columns, not objects — even now, when a list of objects would be
easier. Once state is arrays, running 32 worlds is one extra leading dimension,
which turns a 32-seed sweep into a single run instead of thirty-two. On this
hardware that is the difference between minutes and an afternoon.

Two layout rules that everything else depends on:

**Fixed capacity, tombstoned death.** `alive` is a mask; dead agents are never
removed. Compacting the arrays would renumber every agent, invalidating episodic
memory, genealogy, and every index held anywhere else.

**Canonical order is slot order, always.** Arrays are never sorted in place. Any
operation whose result depends on order sorts a *copy* of the indices and breaks
ties on agent id (determinism rule 3).

Fields not yet used are deliberately absent rather than zero-filled: health,
inventory, lineage, culture, and the neural columns (embed, plastic, hidden)
arrive with the stages that need them, per docs/06-data-model.md.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np

# Agent columns and their dtypes. Order is canonical: it fixes the hash and the
# checkpoint layout, so append new columns at the end, never insert.
AGENT_COLUMNS: tuple[tuple[str, type], ...] = (
    ("id", np.uint32),       # stable for life, never reused within a run
    ("alive", np.bool_),     # tombstone, not deletion
    ("x", np.int16),
    ("y", np.int16),
    ("energy", np.float32),  # death at <= 0
    ("age", np.uint32),      # ticks
    ("parent", np.uint32),   # genealogy; 0 for the founding cohort
    ("heading", np.int8),    # last movement direction, 0..3
)

N_ACTIONS = 4  # N, E, S, W — P1/P2 at L0 need no more


@dataclass(slots=True)
class World:
    """A batch of worlds sharing a config, differing only in seed-driven structure."""

    n_worlds: int
    n_agents: int  # capacity, not population
    grid: int
    genome_size: int
    view_radius: int

    tick: int = 0

    # Agent columns, all [W, N]
    id: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]
    alive: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]
    x: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]
    y: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]
    energy: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]
    age: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]
    parent: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]
    heading: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]
    genome: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]  # [W, N, G]

    next_id: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]  # [W]

    # World fields, [W, H, W] except static terrain
    resource: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]
    capacity: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]
    terrain: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]

    # --- derived scratch, excluded from state identity ------------------------
    # These are recomputed every tick and never checkpointed. Including them in
    # the hash would make identity depend on buffer contents that carry no
    # information, and checkpointing them would bloat snapshots for nothing.
    _padded: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]
    _idx_buf: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]
    _obs: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]

    @classmethod
    def allocate(
        cls,
        n_worlds: int,
        n_agents: int,
        grid: int,
        genome_size: int,
        view_radius: int,
    ) -> "World":
        w = cls(
            n_worlds=n_worlds,
            n_agents=n_agents,
            grid=grid,
            genome_size=genome_size,
            view_radius=view_radius,
        )
        shape = (n_worlds, n_agents)
        for name, dtype in AGENT_COLUMNS:
            setattr(w, name, np.zeros(shape, dtype=dtype))
        w.genome = np.zeros((n_worlds, n_agents, genome_size), dtype=np.float32)
        w.next_id = np.ones(n_worlds, dtype=np.uint32)  # id 0 reserved for "none"

        w.resource = np.zeros((n_worlds, grid, grid), dtype=np.float32)
        w.capacity = np.ones((n_worlds, grid, grid), dtype=np.float32)
        w.terrain = np.zeros((grid, grid), dtype=np.uint8)

        d, gp = view_radius, grid + 2 * view_radius
        patch = (2 * d + 1) ** 2
        w._padded = np.zeros((n_worlds, gp, gp), dtype=np.float32)
        w._idx_buf = np.empty((n_worlds, n_agents, patch), dtype=np.intp)
        w._obs = np.empty((n_worlds, n_agents, patch), dtype=np.float32)
        return w

    # --- population -----------------------------------------------------------

    @property
    def population(self) -> np.ndarray:
        """Living agents per world, [W]."""
        return self.alive.sum(axis=1)

    def spawn(self, world: int, slots: np.ndarray, parent_ids: np.ndarray) -> np.ndarray:
        """Occupy `slots` in one world, assigning fresh ids. Returns the new ids.

        Ids come from a per-world counter so they are unique within a run and
        independent of how many agents happen to be alive — an id that depended
        on population would make forks diverge.
        """
        k = slots.size
        if k == 0:
            return np.empty(0, dtype=np.uint32)
        start = int(self.next_id[world])
        new_ids = np.arange(start, start + k, dtype=np.uint32)
        self.next_id[world] = start + k
        self.id[world, slots] = new_ids
        self.alive[world, slots] = True
        self.age[world, slots] = 0
        self.parent[world, slots] = parent_ids
        return new_ids

    def free_slots(self, world: int, count: int) -> np.ndarray:
        """The lowest `count` unoccupied slots in a world.

        `np.flatnonzero` returns ascending indices, so allocation is a pure
        function of the alive mask — no iteration-order dependence.
        """
        if count <= 0:
            return np.empty(0, dtype=np.intp)
        return np.flatnonzero(~self.alive[world])[:count]

    # --- identity -------------------------------------------------------------

    def state_hash(self) -> str:
        """A digest of everything that defines this state.

        Used by test_determinism and test_log_tier_invariance. Scratch buffers are
        excluded by construction: they hold no information not derivable from the
        fields above.
        """
        h = hashlib.blake2b(digest_size=16)
        h.update(
            np.array(
                [self.tick, self.n_worlds, self.n_agents, self.grid, self.genome_size],
                dtype=np.int64,
            ).tobytes()
        )
        for name, _ in AGENT_COLUMNS:
            arr = getattr(self, name)
            h.update(np.ascontiguousarray(arr).tobytes())
        for name in ("genome", "next_id", "resource", "capacity", "terrain"):
            h.update(np.ascontiguousarray(getattr(self, name)).tobytes())
        return h.hexdigest()

    # --- checkpointing --------------------------------------------------------

    def to_arrays(self) -> dict[str, np.ndarray]:
        """Everything a checkpoint must persist, minus RNG/pending (added by caller)."""
        out = {name: getattr(self, name) for name, _ in AGENT_COLUMNS}
        out.update(
            genome=self.genome,
            next_id=self.next_id,
            resource=self.resource,
            capacity=self.capacity,
            terrain=self.terrain,
            _dims=np.array(
                [
                    self.tick,
                    self.n_worlds,
                    self.n_agents,
                    self.grid,
                    self.genome_size,
                    self.view_radius,
                ],
                dtype=np.int64,
            ),
        )
        return out

    @classmethod
    def from_arrays(cls, data: dict[str, np.ndarray]) -> "World":
        tick, nw, na, grid, gs, vr = (int(v) for v in data["_dims"])
        w = cls.allocate(nw, na, grid, gs, vr)
        w.tick = tick
        for name, _ in AGENT_COLUMNS:
            getattr(w, name)[...] = data[name]
        for name in ("genome", "next_id", "resource", "capacity", "terrain"):
            getattr(w, name)[...] = data[name]
        return w
