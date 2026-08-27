"""S1 — a small evolved network per lineage, with the genome as an embedding.

S0 hands the agents a rule. `gradient_ascent` firing at S0 is the policy working,
not evolution happening, because someone wrote the line that weighs the resource
gradient. S1 deletes that line: the map from perception to action is a network
whose weights nothing hand-tunes, and the question becomes whether selection can
**rediscover** the competence S0 was given.

    input  = local patch (2r+1)^2 . genome (G) . scalars (3)
    hidden = tanh(input @ W1 + b1)
    logits = hidden @ W2 + b2                     -> 4 actions
    action = softmax_sample(logits, temperature=1.0)

**One shared network per lineage, not one per agent** (D-004). The arithmetic is
identical either way — the same MACs happen — but per-agent weights mean
streaming [W, N, n_in, H] floats every tick, which is 470 MB per tick at corpus
scale on a machine with 8 GB. Sharing is what makes 32,000 agents affordable.

**Where the variants come from, since weights are no longer inherited per agent
(D-071).** A lineage is a heritable clade: a child normally takes its parent's
lineage, and with probability `speciation_rate` it claims a free lineage slot
carrying its parent's weights plus Gaussian noise. A lineage whose last member
dies frees its slot. There is no generation clock, no fitness function and no
scoring window — selection over weights *is* birth and death, so D-007 holds
literally rather than by analogy, and phase 10 stays the no-op it was at S0.

Four choices in here that are decisions rather than details:

**Every lineage slot is seeded independently, and the founding cohort is spread
across all of them.** The tempting alternative — seed one lineage, let
speciation fill the rest — was tried and is a trap twice over. A zero or shared
output layer makes the founding lineage *structurally inert*: with `W2` at zero
the logits are zero whatever `W1` says, so `W1` is invisible to selection and
the parent lineage can never improve, only be replaced. And a single founding
policy makes S1's starting population far less varied than S0's, whose eight
genes are drawn uniformly per agent — selection would have nothing to act on
until the first speciation, which begins from one agent and is mostly drift.

Seeding all `L` slots gives each world a population of `L` policies under
selection from tick zero, which is what neuroevolution actually means, and
leaves speciation doing the job it is good at: supplying new variants around
whatever survived.

**Temperature is fixed at 1.0.** The network scales its own logits, so
confidence is something it can evolve rather than a knob someone set. Per-agent
variation still reaches the sampler, through the embedding.

**Genes 4, 5 and 6 stay structural.** `reproduce_threshold`,
`offspring_investment` and `metabolic_rate` are read by phases 6 and 7, outside
the policy, and `s0_reactive.decode` is unchanged. The other five genes are fed
to the network as embedding and have no S0 meaning here — at S1 they mean
whatever selection makes them mean, which is why anything that *labels* genes
has to know the stage.

**Sector scores are still computed, for the Chronicle only.** The network sees
the raw patch and never sees a sector score. Computing them anyway keeps
`PERCEIVE` carrying `chosen / mean / best` at both stages, which is what lets
`gradient_ascent` answer the actual question — did the evolved net rediscover
gradient-following? — instead of merely being unavailable at S1.
"""

from __future__ import annotations

import numpy as np

from core.policy.s0_reactive import sector_scores
from core.policy.sampling import softmax_sample
from core.state import N_ACTIONS

# energy, age, local density. Scaled to roughly unit range before they reach a
# tanh: raw energy in the tens and age in the hundreds would saturate the hidden
# layer at init and leave the patch inputs invisible.
N_SCALARS = 3
ENERGY_SCALE = np.float32(1.0 / 50.0)
AGE_SCALE = np.float32(1.0 / 400.0)
DENSITY_SCALE = np.float32(1.0 / 4.0)

TEMPERATURE = 1.0


def n_inputs(view_radius: int, genome_size: int, extra: int = 0) -> int:
    """Input width. `extra` is the fog channel count, 0 until P2 is built."""
    return (2 * view_radius + 1) ** 2 + genome_size + N_SCALARS + extra


def initial_weights(
    world,
    rng_policy_init: np.random.Generator,
    *,
    gain: float = 1.0,
) -> None:
    """Seed every lineage slot of every world with an independent network.

    Drawn from `policy_init` rather than `generator` so that the landscape and
    the founding cohort a seed produces are **identical** at S0 and S1 (D-072).
    That is what makes the two arms of the B0 experiment paired by world rather
    than merely drawn from the same distribution.
    """
    W, L, n_in, H = world.w1.shape
    if L == 0:
        return

    # Xavier: enough signal to reach tanh's linear region, not enough to
    # saturate it at init and hide the patch inputs behind a flat gradient.
    s_in = np.float32(gain / np.sqrt(max(n_in, 1)))
    s_hid = np.float32(gain / np.sqrt(max(H, 1)))
    world.w1[:] = rng_policy_init.standard_normal((W, L, n_in, H), dtype=np.float32) * s_in
    world.b1[:] = rng_policy_init.standard_normal((W, L, H), dtype=np.float32) * np.float32(0.01)
    world.w2[:] = rng_policy_init.standard_normal(
        (W, L, H, N_ACTIONS), dtype=np.float32) * s_hid
    # Output bias stays zero: a nonzero one is a standing preference for a
    # compass direction that no input can argue with, which is the one form of
    # arbitrary initial bias worth refusing.
    world.lineage_alive[:] = True


def assign_founders(world) -> None:
    """Spread the founding cohort across the lineage slots, round-robin by slot.

    `slot % L` rather than a draw: it is a pure function of the slot index, so
    it consumes no randomness, divides the cohort evenly, and is identical on a
    fork. Which agent gets which network is arbitrary — that it is arbitrary in
    a *fixed* way is the requirement.
    """
    if world.lineages == 0:
        return
    idx = np.arange(world.n_agents, dtype=np.int64) % world.lineages
    world.lineage[:] = idx.astype(np.uint16)[None, :]


def build_inputs(world, density: np.ndarray, extra: np.ndarray | None = None) -> np.ndarray:
    """Fill and return the flat `[W*N, n_in]` policy input buffer.

    Filled for every slot including dead ones. Compacting to the living would
    make the matrix shape depend on the population, which is the one thing
    determinism forbids — and it would buy nothing, because the row count is a
    memory cost, not a decision.
    """
    W, N = world.n_worlds, world.n_agents
    buf = world._policy_in.reshape(W, N, -1)
    patch = world._obs.shape[2]

    buf[:, :, :patch] = world._obs
    cursor = patch
    buf[:, :, cursor : cursor + world.genome_size] = world.genome
    cursor += world.genome_size
    buf[:, :, cursor] = world.energy * ENERGY_SCALE
    buf[:, :, cursor + 1] = world.age * AGE_SCALE
    buf[:, :, cursor + 2] = density * DENSITY_SCALE
    cursor += N_SCALARS
    if extra is not None:
        buf[:, :, cursor : cursor + extra.shape[2]] = extra
    return world._policy_in


def choose_action(
    world,
    density: np.ndarray,
    masks,
    rng_policy: np.random.Generator,
    extra: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return `(action, sector)` for every agent slot, living or not.

    `sector` is not an input to anything here — see the module docstring. It is
    computed so the Chronicle can record what was on offer at both stages.
    """
    W, N = world.n_worlds, world.n_agents
    x = build_inputs(world, density, extra)
    h = world._hidden_buf
    logits = np.zeros((W * N, N_ACTIONS), dtype=np.float32)

    lineage = world.lineage.reshape(-1)
    world_of = np.repeat(np.arange(W, dtype=np.int64), N)

    # Grouped by (world, lineage): weights differ on both axes, so the group key
    # has to carry both. Empty groups are skipped, which is free and does not
    # affect the result — grouping is a pure function of state, so a fork
    # reproduces it exactly and only the *cost* varies with occupancy.
    key = world_of * world.lineages + lineage.astype(np.int64)
    order = np.argsort(key, kind="stable")
    bounds = np.searchsorted(key[order], np.arange(W * world.lineages + 1))

    w1f = world.w1.reshape(-1, world.n_inputs, world.hidden)
    b1f = world.b1.reshape(-1, world.hidden)
    w2f = world.w2.reshape(-1, world.hidden, N_ACTIONS)
    b2f = world.b2.reshape(-1, N_ACTIONS)

    for k in range(W * world.lineages):
        idx = order[bounds[k] : bounds[k + 1]]
        if idx.size == 0:
            continue
        m = idx.size
        np.matmul(x[idx], w1f[k], out=h[:m])
        np.add(h[:m], b1f[k], out=h[:m])
        np.tanh(h[:m], out=h[:m])
        logits[idx] = np.matmul(h[:m], w2f[k]) + b2f[k]

    action = softmax_sample(logits.reshape(W, N, N_ACTIONS), TEMPERATURE, rng_policy)
    return action, sector_scores(world._obs, masks)


def speciation_draws(
    n_worlds: int,
    birth_cap: int,
    n_in: int,
    hidden: int,
    rate: float,
    scale: float,
    rng_lineage: np.random.Generator,
) -> dict[str, np.ndarray]:
    """All of a tick's speciation randomness, at shapes fixed by config alone.

    Every shape here comes from the config — never the living population, never
    the number of births that actually occur. That is the whole discipline: the
    stream must advance identically whatever happens in the world, or a fork
    silently stops matching its parent (D-053).

    **One candidate perturbation per world per tick, not one per birth slot.**
    Drawing `[W, birth_cap, n_in, H]` would be the honest shape for "any birth
    may found a lineage" and it costs 885,000 gaussians per tick to serve an
    event that happens about 0.04 times per world-tick — the same arithmetic
    that sized `s0_reactive.mutation_noise` by `birth_cap` instead of capacity.
    So at most one lineage is founded per world per tick, by the lowest-slot
    candidate, and the cap is a fixed rule rather than a state-dependent one.
    The rate it forgoes is negligible: two candidates in one world on one tick
    is a ~0.1% event, and the second simply stays in its parent's lineage.
    """
    scale32 = np.float32(scale)
    return {
        # Which birth slots would found, if the world has room. [W, birth_cap]
        # so the mask lines up with the birth loop's parent ordering.
        "founds": rng_lineage.random((n_worlds, birth_cap), dtype=np.float32) < rate,
        "w1": rng_lineage.standard_normal((n_worlds, n_in, hidden), dtype=np.float32) * scale32,
        "b1": rng_lineage.standard_normal((n_worlds, hidden), dtype=np.float32) * scale32,
        "w2": rng_lineage.standard_normal((n_worlds, hidden, N_ACTIONS),
                                          dtype=np.float32) * scale32,
        "b2": rng_lineage.standard_normal((n_worlds, N_ACTIONS), dtype=np.float32) * scale32,
    }


def free_lineage_slot(world, w: int) -> int:
    """The lowest unoccupied lineage slot in world `w`, or -1 if the bank is full.

    Lowest-first for the same reason `World.free_slots` allocates lowest-first:
    it makes slot assignment a pure function of the occupancy mask, with no
    iteration-order dependence and nothing to reproduce on a fork but the mask.
    """
    free = np.flatnonzero(~world.lineage_alive[w])
    return int(free[0]) if free.size else -1


def reap_lineages(world) -> None:
    """Free the slots of lineages whose last member died.

    Consumes no randomness and reads only the alive mask, so it is bookkeeping
    rather than a rule. Extinction is not a decision anything makes here — it is
    what has already happened by the time this runs.
    """
    if world.lineages == 0:
        return
    W, L = world.n_worlds, world.lineages
    flat = (np.arange(W, dtype=np.int64)[:, None] * L + world.lineage.astype(np.int64))
    counts = np.bincount(flat[world.alive], minlength=W * L).reshape(W, L)
    world.lineage_alive &= counts > 0
