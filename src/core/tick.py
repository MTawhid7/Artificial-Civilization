"""The tick loop. Phase order is part of the spec.

Changing the order changes results, so it is versioned alongside the schema and
transcribed here exactly as docs/05-architecture.md states it:

     0. PENDING     fire scheduled effects; step accumulators
     1. WORLD       drift, regrowth, contagion, shocks
     2. MODULATE    recompute the active modulator set
     3. OBSERVE     build observation tensors
     4. DECIDE      one batched forward pass for all agents
     5. RESOLVE     movement, gather, transfer, signal, pledge, coercion
     6. METABOLISM  energy costs including cognition
     7. VITALS      death, birth, mutation
     8. AGGREGATE   individual actions into global stocks
     9. EMIT        append to the Chronicle
    10. LEARN       plastic updates; evolution at generation boundary

Phases 2 and 10 are explicit no-ops at S0 rather than absent. Keeping them in
place means the order never has to be renegotiated when they acquire content, and
a reader can see what is not yet implemented instead of inferring it.

Phase 0 runs before phase 1 so a scheduled effect and this tick's drift compose in
a fixed order. Phase 2 runs after the world updates and before observation, so
agents always perceive post-modulation parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from chronicle import schema as S
from chronicle.writer import ChronicleWriter, gini
from core.config import Config
from core.pending import Accumulators, PendingQueue
from core.policy import s0_reactive as s0
from core.policy import s1_neural as s1
from core.primitives import p01_scarcity as p1
from core.primitives import p02_fog as p2
from core.primitives import p10_drift as p10
from core.rng import RngStreams
from core.state import World


@dataclass(slots=True)
class TickContext:
    """Constants and scratch buffers derived once from the config.

    A tick must not read the config dict or allocate: at 8.9 ms of real work,
    dictionary lookups and temporary arrays are a measurable fraction.
    """

    metabolism: float
    max_age: int
    birth_energy: float
    gather_efficiency: float
    regrowth: float
    seed_rain: float
    drift_rate: float
    mutation_rate: float
    mutation_scale: float
    birth_cap: int
    inherit: bool
    sated_gradient_factor: float
    aggregate_every: int

    # S1. `stage` is read once here rather than per tick: a string comparison in
    # the hot path is cheap, and a dict lookup in the hot path is not.
    stage: str
    speciation_rate: float
    weight_mutation_scale: float
    cognition_cost: float

    # P2 at L0. `fog_block` is 0 when fog is off, which is the only check any
    # caller needs — the known map is then zero-width too.
    fog_block: int
    fog_radius: int
    fog_masks: np.ndarray | None  # sector slices over the BLOCK patch, not the cell patch

    masks: np.ndarray  # [4, P] direction sectors
    world_offset: np.ndarray  # [W, 1] flat-index base per world
    n_cells: int

    density_flat: np.ndarray = field(repr=False)  # [W * G * G] int32 scratch
    births_this_window: np.ndarray = field(repr=False)  # [W]
    deaths_this_window: np.ndarray = field(repr=False)  # [W]

    @classmethod
    def build(cls, cfg: Config, world: World) -> "TickContext":
        w, g = world.n_worlds, world.grid
        return cls(
            metabolism=float(cfg.get("agent.metabolism")),
            max_age=int(cfg.get("agent.max_age")),
            birth_energy=float(cfg.get("agent.birth_energy")),
            gather_efficiency=float(cfg.get("agent.gather_efficiency")),
            regrowth=float(cfg.get("world.regrowth")),
            seed_rain=float(cfg.get("world.seed_rain")),
            drift_rate=float(cfg.get("primitives.p10.rate", 0.0) or 0.0),
            mutation_rate=float(cfg.get("population.mutation_rate")),
            mutation_scale=float(cfg.get("population.mutation_scale")),
            birth_cap=int(cfg.get("population.birth_cap")),
            inherit=bool(cfg.get("population.inherit")),
            sated_gradient_factor=float(cfg.get("intelligence.sated_gradient_factor")),
            aggregate_every=int(cfg.get("run.aggregate_every", 100) or 100),
            stage=str(cfg.stage),
            speciation_rate=float(cfg.get("intelligence.speciation_rate", 0.0) or 0.0),
            weight_mutation_scale=float(
                cfg.get("intelligence.weight_mutation_scale", 0.0) or 0.0
            ),
            cognition_cost=float(cfg.get("intelligence.cognition_cost", 0.0) or 0.0),
            fog_block=int((cfg.get("primitives.p2") or {}).get("block", 0)),
            fog_radius=int((cfg.get("primitives.p2") or {}).get("known_radius", 0)),
            # A second mask set, over the block patch. Same function, different
            # radius: the cell patch is view_radius wide and the block patch is
            # known_radius wide, and reusing one mask set for both would silently
            # read the wrong slice bounds.
            fog_masks=(
                s0.sector_masks(int(cfg.get("primitives.p2")["known_radius"]))
                if cfg.get("primitives.p2") else None
            ),
            masks=s0.sector_masks(world.view_radius),
            world_offset=(np.arange(w, dtype=np.int64) * (g * g))[:, None],
            n_cells=g * g,
            density_flat=np.zeros(w * g * g, dtype=np.int64),
            births_this_window=np.zeros(w, dtype=np.int64),
            deaths_this_window=np.zeros(w, dtype=np.int64),
        )


def step(
    world: World,
    ctx: TickContext,
    rng: RngStreams,
    pending: PendingQueue,
    accumulators: Accumulators,
    chronicle: ChronicleWriter | None = None,
) -> None:
    """Advance one tick, in place."""
    tick = world.tick
    W, N, G = world.n_worlds, world.n_agents, world.grid
    resource_flat = world.resource.reshape(W, -1)

    # --- 0. PENDING -----------------------------------------------------------
    due = pending.pop_due(tick)
    if due["fire_tick"].size:
        _apply_effects(world, due, resource_flat)
    accumulators.step(np.zeros(len(accumulators), dtype=np.float32))

    # --- 1. WORLD -------------------------------------------------------------
    p10.drift_capacity(world.capacity, ctx.drift_rate, tick)
    p1.regrow(world.resource, world.capacity, ctx.regrowth, ctx.seed_rain)

    # --- 2. MODULATE ----------------------------------------------------------
    # No modulators before P8 (stage E). The phase stays so its position in the
    # order is never renegotiated.

    # --- 3. OBSERVE -----------------------------------------------------------
    cell = (world.y.astype(np.int64) * G + world.x).astype(np.int64)
    density = _observe(world, cell, ctx)

    # 3b. P2 fog, still phase 3: this builds observation, so it is part of
    # OBSERVE rather than a new phase — the order is a spec and does not get
    # renegotiated for a primitive.
    #
    # Marking happens before the sector read, so an agent already knows where it
    # is standing when it chooses. Mark-after-decide would make the blocks under
    # its feet read as unexplored for one tick, and the policy would perceive
    # novelty it had already consumed.
    fog_extra = None
    if ctx.fog_block:
        newly = p2.mark_seen(world.known, world.y, world.x, world.alive,
                             world.view_radius, G, ctx.fog_block)
        fog_extra = p2.unknown_by_sector(world.known, world.y, world.x,
                                         ctx.fog_block, ctx.fog_radius, ctx.fog_masks)

    # --- 4. DECIDE ------------------------------------------------------------
    # `sector` is what each agent perceived in each direction. It is carried out of
    # the policy so the Chronicle can record the alternatives that were on offer:
    # whether a choice was good is a question about the options, not the outcome.
    #
    # Both branches draw exactly one [W, N] float32 from the policy stream, so
    # the stream sits at the same position after this phase whichever ran.
    if ctx.stage == "S0":
        action, sector = s0.choose_action(
            world._obs, world.energy, world.heading, world.genome, density, ctx.masks,
            rng.policy, ctx.sated_gradient_factor,
        )
    else:
        action, sector = s1.choose_action(world, density, ctx.masks, rng.policy, fog_extra)

    # --- 5. RESOLVE -----------------------------------------------------------
    # a. movement
    moved = world.alive
    dy = s0.DELTA_Y[action]
    dx = s0.DELTA_X[action]
    np.copyto(world.y, (world.y + dy) % G, where=moved)
    np.copyto(world.x, (world.x + dx) % G, where=moved)
    np.copyto(world.heading, action, where=moved)

    # b. gather — contention resolved by slot order, first-wins
    cell = (world.y.astype(np.int64) * G + world.x).astype(np.int64)
    gained = p1.extract(resource_flat, cell, world.alive, ctx.gather_efficiency)
    world.energy += gained

    # c-f. transfer / signal / pledge / coercion — no primitives at S0.

    # --- 6. METABOLISM --------------------------------------------------------
    # `decode` is S0's table, and genes 4-6 are read here and in phase 7 at every
    # stage: reproduction thresholds and movement vigour are structural, not
    # policy. What S1 changes is the meaning of the other five, which it consumes
    # as an embedding rather than as named traits.
    genes = s0.decode(world.genome)
    cost = ctx.metabolism * genes["metabolic"]
    if ctx.cognition_cost:
        # Thinking is paid for per tick, per hidden unit, and a larger brain is
        # therefore something selection can act *against* (04-intelligence.md).
        cost = cost + np.float32(ctx.cognition_cost * world.hidden)
    world.energy -= np.where(world.alive, cost, 0.0).astype(np.float32)
    world.age += world.alive

    # --- 7. VITALS ------------------------------------------------------------
    died = world.alive & ((world.energy <= 0.0) | (world.age > ctx.max_age))
    dead_ids = world.id[died]
    dead_worlds = np.broadcast_to(np.arange(W, dtype=np.uint16)[:, None], died.shape)[died]
    world.alive &= ~died

    born = _reproduce(world, ctx, genes, rng)
    if ctx.stage != "S0":
        # After births, so a lineage founded this tick is never reaped before it
        # has drawn breath, and a slot freed this tick is reusable from the next.
        s1.reap_lineages(world)

    # --- 8. AGGREGATE ---------------------------------------------------------
    ctx.births_this_window += born["count"]
    np.add.at(ctx.deaths_this_window, dead_worlds.astype(np.int64), 1)

    # --- 9. EMIT --------------------------------------------------------------
    if chronicle is not None:
        _emit(world, ctx, chronicle, tick, action, sector, gained, died, dead_ids,
              dead_worlds, born, newly if ctx.fog_block else None)

    # --- 10. LEARN ------------------------------------------------------------
    # Still a no-op at S1, and that is a result rather than an omission (D-071).
    # Neither stage has within-life learning, and neither has a generation
    # boundary: selection happens through birth and death, which already ran in
    # phase 7. At S0 the population *is* the population of policies; at S1 the
    # population of lineages is, and speciation at birth is what creates the
    # variants for it to select among. Plastic updates arrive at S2.

    world.tick += 1


def _observe(world: World, cell: np.ndarray, ctx: TickContext) -> np.ndarray:
    """Fill `world._obs` with each agent's local resource patch; return cell density.

    The halo-padded gather is the single most expensive operation in the tick
    (measured 3.6 ms of 8.9 at W=32, N=1000). It avoids per-agent modulo by
    wrapping the grid into a border ring once per tick instead.
    """
    d, G = world.view_radius, world.grid
    Gp = G + 2 * d
    padded = world._padded

    padded[:, d : d + G, d : d + G] = world.resource
    padded[:, :d, d : d + G] = world.resource[:, -d:, :]
    padded[:, -d:, d : d + G] = world.resource[:, :d, :]
    padded[:, :, :d] = padded[:, :, G : G + d]
    padded[:, :, -d:] = padded[:, :, d : 2 * d]

    offsets = _flat_offsets(d, Gp)
    base = (world.y.astype(np.intp) + d) * Gp + (world.x.astype(np.intp) + d)
    np.add(base[:, :, None], offsets[None, None, :], out=world._idx_buf)
    world._obs.reshape(world.n_worlds, -1)[:] = np.take_along_axis(
        padded.reshape(world.n_worlds, -1), world._idx_buf.reshape(world.n_worlds, -1), axis=1
    )

    # Occupancy per cell. bincount over integers is exact regardless of order, so
    # this needs no sorting to be deterministic.
    flat = (ctx.world_offset + cell)[world.alive]
    counts = np.bincount(flat, minlength=world.n_worlds * ctx.n_cells)
    ctx.density_flat[:] = counts
    per_world = ctx.density_flat.reshape(world.n_worlds, -1)
    return np.take_along_axis(per_world, cell, axis=1)


_OFFSET_CACHE: dict[tuple[int, int], np.ndarray] = {}


def _flat_offsets(d: int, padded_width: int) -> np.ndarray:
    key = (d, padded_width)
    if key not in _OFFSET_CACHE:
        oy, ox = np.mgrid[-d : d + 1, -d : d + 1]
        _OFFSET_CACHE[key] = oy.ravel().astype(np.intp) * padded_width + ox.ravel().astype(np.intp)
    return _OFFSET_CACHE[key]


def _reproduce(world: World, ctx: TickContext, genes: dict, rng: RngStreams) -> dict:
    """Birth with mutation. The only fitness there is (D-007).

    Both RNG draws happen at full [W, N, G] shape before any world is inspected,
    so the streams advance identically whatever the populations happen to be.

    At S1 this is also the entire evolutionary outer loop (D-071). A child takes
    its parent's lineage, and therefore its parent's network; occasionally it
    founds a new lineage carrying a perturbed copy. There is no generation
    boundary and no fitness function anywhere in the file, because offspring
    already are the fitness.
    """
    fertile = world.alive & (world.energy > genes["reproduce_at"])
    shape = (world.n_worlds, ctx.birth_cap, world.genome_size)
    noise = s0.mutation_noise(shape, ctx.mutation_rate, ctx.mutation_scale, rng.mutation)

    # Drawn unconditionally at S1, before any world is inspected, and drawn even
    # on a tick where nothing is born. A draw conditioned on there being a birth
    # would make the stream position depend on the population — the failure with
    # no symptom that `test_noop_fork` exists to catch.
    spec = (
        s1.speciation_draws(
            world.n_worlds, ctx.birth_cap, world.n_inputs, world.hidden,
            ctx.speciation_rate, ctx.weight_mutation_scale, rng.lineage,
        )
        if ctx.stage != "S0" and world.lineages
        else None
    )

    # Drawn only when inheritance is off. Drawing it unconditionally would be
    # tidier — the control would then consume the RNG identically to the treatment
    # and their worlds would stay matched — but it would also shift the mutation
    # stream for every heritable run ever recorded, invalidating results already in
    # hand. The matching buys little here anyway: random genomes make the two
    # trajectories diverge on the first birth regardless.
    orphan = None if ctx.inherit else rng.mutation.random(shape, dtype=np.float32)

    counts = np.zeros(world.n_worlds, dtype=np.int64)
    child_worlds: list[np.ndarray] = []
    child_ids: list[np.ndarray] = []
    parent_ids: list[np.ndarray] = []

    for w in range(world.n_worlds):
        candidates = np.flatnonzero(fertile[w])
        if candidates.size == 0:
            continue
        slots = world.free_slots(w, min(candidates.size, ctx.birth_cap))
        if slots.size == 0:
            continue
        # More candidates than room: the lowest-slot candidates reproduce. An
        # arbitrary rule, but a fixed one — the alternative is a draw whose size
        # depends on population, which is exactly what breaks forks.
        parents = candidates[: slots.size]

        invest = genes["investment"][w, parents].astype(np.float32)
        dowry = (world.energy[w, parents] * invest).astype(np.float32)
        world.energy[w, parents] -= dowry

        ids = world.spawn(w, slots, world.id[w, parents])
        world.x[w, slots] = world.x[w, parents]
        world.y[w, slots] = world.y[w, parents]
        world.heading[w, slots] = world.heading[w, parents]
        world.energy[w, slots] = np.maximum(dowry, np.float32(ctx.birth_energy))
        # With inheritance off, a child's genes are drawn fresh rather than copied.
        # Population diversity stays at its founding distribution forever, so
        # nothing can accumulate — which is exactly what makes it a control for
        # "did selection do this, or did the world just change underneath us?"
        world.genome[w, slots] = (
            s0.apply_mutation(world.genome[w, parents], noise[w, : slots.size])
            if ctx.inherit
            else orphan[w, : slots.size]
        )

        if spec is not None:
            # A clade tag: the child runs its parent's network by default.
            world.lineage[w, slots] = world.lineage[w, parents]
            _speciate(world, w, slots, parents, spec)

        counts[w] = slots.size
        child_worlds.append(np.full(slots.size, w, dtype=np.uint16))
        child_ids.append(ids)
        parent_ids.append(world.id[w, parents].copy())

    empty_u32 = np.empty(0, dtype=np.uint32)
    return {
        "count": counts,
        "ids": np.concatenate(child_ids) if child_ids else empty_u32,
        "worlds": (np.concatenate(child_worlds) if child_worlds
                   else np.empty(0, dtype=np.uint16)),
        "parent_ids": np.concatenate(parent_ids) if parent_ids else empty_u32,
    }


def _speciate(world: World, w: int, slots: np.ndarray, parents: np.ndarray, spec: dict) -> None:
    """Found at most one new lineage in world `w`, from this tick's births.

    The founder is the **lowest-slot candidate**, and at most one per world per
    tick. Both are arbitrary rules and both are fixed ones — the same trade
    `_reproduce` makes when more agents are fertile than there is room for. The
    alternative, a draw sized by how many candidates there happen to be, is
    exactly what breaks forks.

    A full lineage bank means no speciation this tick. The child stays in its
    parent's clade rather than displacing a living lineage: eviction would be a
    selection rule, and the whole point of D-071 is that there isn't one.
    """
    candidates = np.flatnonzero(spec["founds"][w, : slots.size])
    if candidates.size == 0:
        return
    k = s1.free_lineage_slot(world, w)
    if k < 0:
        return

    i = int(candidates[0])
    src = int(world.lineage[w, parents[i]])
    world.w1[w, k] = world.w1[w, src] + spec["w1"][w]
    world.b1[w, k] = world.b1[w, src] + spec["b1"][w]
    world.w2[w, k] = world.w2[w, src] + spec["w2"][w]
    world.b2[w, k] = world.b2[w, src] + spec["b2"][w]
    world.lineage_alive[w, k] = True
    world.lineage[w, slots[i]] = k


def _apply_effects(world: World, due: dict, resource_flat: np.ndarray) -> None:
    """Fire scheduled effects in (fire_tick, insertion_id) order."""
    from core.pending import EFFECT_ENERGY_DELTA, EFFECT_RESOURCE_DELTA

    for i in range(due["fire_tick"].size):
        kind = int(due["effect_type"][i])
        w = int(due["world"][i])
        ref = int(due["target_ref"][i])
        mag = float(due["magnitude"][i])
        if kind == EFFECT_RESOURCE_DELTA:
            resource_flat[w, ref] = max(0.0, resource_flat[w, ref] + mag)
        elif kind == EFFECT_ENERGY_DELTA:
            hit = world.id[w] == np.uint32(ref)
            world.energy[w, hit] += mag


def _emit(
    world: World,
    ctx: TickContext,
    chronicle: ChronicleWriter,
    tick: int,
    action: np.ndarray,
    sector: np.ndarray,
    gained: np.ndarray,
    died: np.ndarray,
    dead_ids: np.ndarray,
    dead_worlds: np.ndarray,
    born: dict,
    newly_known: np.ndarray | None,
) -> None:
    if dead_ids.size:
        chronicle.emit(
            tick, S.DEATH, dead_worlds, dead_ids,
            a=world.age[died].astype(np.float32),
        )
    if born["ids"].size:
        chronicle.emit(tick, S.BIRTH, born["worlds"], born["ids"], obj=born["parent_ids"])

    alive = world.alive
    if alive.any():
        w_idx = np.broadcast_to(np.arange(world.n_worlds, dtype=np.uint16)[:, None], alive.shape)
        # MOVE carries position and heading so path straightness — the
        # directed_foraging detector — is computable from the sampled tier alone.
        chronicle.emit(
            tick, S.MOVE, w_idx[alive], world.id[alive],
            a=world.x[alive].astype(np.float32),
            b=world.y[alive].astype(np.float32),
            c=world.energy[alive].astype(np.float32),
        )
        got = alive & (gained > 0)
        if got.any():
            chronicle.emit(tick, S.GATHER, w_idx[got], world.id[got], a=gained[got])

        # EXPLORE_CELL — how much of the world became known this tick.
        #
        # `a` is a count of blocks, not a cell id, because P2 at L0 stores
        # knowledge per block (D-073). Emitting one row per newly-known block
        # would be the literal reading of the event name and would also be the
        # most voluminous event in the log; the count is what every question
        # about exploration actually asks of it.
        if newly_known is not None:
            learned = alive & (newly_known > 0)
            if learned.any():
                chronicle.emit(
                    tick, S.EXPLORE_CELL, w_idx[learned], world.id[learned],
                    a=newly_known[learned].astype(np.float32),
                )

        # PERCEIVE — the decision context, not the decision's consequences.
        #
        # Three numbers summarize what was on offer: the score of the direction
        # actually taken, the mean of the four, and the best of the four. The
        # choice of *those* three is what makes `gradient_ascent`'s null exact
        # rather than simulated. A direction-blind agent picks uniformly, so its
        # expected chosen score IS the mean — meaning `chosen - mean` has
        # expectation exactly zero, for any landscape whatsoever, with no
        # surrogate to generate. Dividing by `best - mean` puts perfect
        # gradient-following at 1.0, and `chosen == best` recovers the plain
        # "did it take the best option" share.
        #
        # Logging perception rather than a verdict keeps the core/lens split
        # intact. The Chronicle records what the agent saw; whether that adds up
        # to foraging is the lens's question to answer.
        chosen = np.take_along_axis(
            sector, action.astype(np.intp)[:, :, None], axis=2
        )[:, :, 0]
        chronicle.emit(
            tick, S.PERCEIVE, w_idx[alive], world.id[alive],
            obj=action[alive].astype(np.uint32),
            a=chosen[alive],
            b=sector.mean(axis=2)[alive],
            c=sector.max(axis=2)[alive],
        )

    if (tick + 1) % ctx.aggregate_every == 0:
        rows = []
        for w in range(world.n_worlds):
            mask = world.alive[w]
            energies = world.energy[w, mask]
            rows.append(
                {
                    "world_id": np.uint16(w),
                    "population": np.uint32(mask.sum()),
                    "births": np.uint32(ctx.births_this_window[w]),
                    "deaths": np.uint32(ctx.deaths_this_window[w]),
                    "resource_total": np.float32(world.resource[w].sum()),
                    "energy_mean": np.float32(energies.mean() if energies.size else 0.0),
                    "energy_gini": np.float32(gini(energies) if energies.size else 0.0),
                    "gene_mean": (
                        world.genome[w, mask].mean(axis=0).astype(np.float32).tolist()
                        if mask.any()
                        else [0.0] * world.genome_size
                    ),
                }
            )
        chronicle.emit_aggregate(tick, rows)
        ctx.births_this_window[:] = 0
        ctx.deaths_this_window[:] = 0
