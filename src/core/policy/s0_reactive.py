"""S0 — a reactive rule driven by an eight-float genome. No within-life learning.

Every gene is continuous and every gene is under selection, and nothing here
forces any particular behavior. Directed foraging is *available* to this policy;
whether it appears depends on whether agents that do it leave more offspring than
agents that do not, which is the only fitness there is (D-007). A genome with
`gradient_sensitivity` near zero and `exploration_temp` high is a random walker,
and it is a legal, reachable solution. That is what makes the A1 result a finding
rather than a restatement of this file.

Genes are stored in [0, 1] and mapped to behavioral ranges here, so mutation is a
single scale everywhere and no gene silently dominates because it happens to be
measured in larger units.

    0  hunger_threshold      energy below which foraging becomes directed
    1  heading_persistence   weight on continuing the current heading
    2  gradient_sensitivity  weight on the perceived resource gradient
    3  exploration_temp      randomness in the heading choice
    4  reproduce_threshold   energy at which reproduction is attempted
    5  offspring_investment  share of energy passed to the offspring
    6  metabolic_rate        movement vigour, paid for in energy
    7  crowd_avoidance       tendency to disperse when the local cell is crowded
"""

from __future__ import annotations

import numpy as np

GENOME_SIZE = 8

(
    G_HUNGER,
    G_PERSISTENCE,
    G_GRADIENT,
    G_TEMP,
    G_REPRODUCE,
    G_INVESTMENT,
    G_METABOLIC,
    G_CROWD,
) = range(GENOME_SIZE)

# Direction order is fixed and shared with the tick loop: N, E, S, W.
DELTA_Y = np.array([-1, 0, 1, 0], dtype=np.int16)
DELTA_X = np.array([0, 1, 0, -1], dtype=np.int16)


def sector_masks(view_radius: int) -> list[tuple[tuple[slice, slice], np.float32]]:
    """Slices selecting the cells in each direction, plus a 1/count weight.

    Sectors overlap on the diagonals and exclude the centre row/column. Overlapping
    is deliberate: a rich patch to the north-east should raise the score of both
    north and east rather than being arbitrarily assigned to one.

    **Not a `[4, P]` float mask, and deliberately not a matmul.** The obvious
    implementation is `obs @ masks.T`, which dispatches to BLAS — and BLAS picks
    its own summation order per platform. That produced a real cross-machine hash
    mismatch between arm64/Accelerate and x86_64/OpenBLAS: a last-ulp difference in
    one sector score flips an occasional action choice, and two runs of the same
    seed diverge within a few hundred ticks. Determinism rule 4 — fixed-order float
    reductions — is not satisfied by anything that dispatches to a tuned kernel.

    Slices rather than index arrays because slices are *views*: fancy indexing
    copies each sector out of the patch, which measured 32% slower over the whole
    tick. The weight makes each score a mean rather than a sum, so widening
    `view_radius` does not silently amplify `gradient_sensitivity`.
    """
    d = view_radius
    side = 2 * d + 1
    all_ = slice(None)
    # (rows, cols) into a [side, side] patch — N, E, S, W, matching DELTA_Y/X.
    regions = [
        (slice(0, d), all_),        # north: rows above centre
        (all_, slice(d + 1, side)), # east:  columns right of centre
        (slice(d + 1, side), all_), # south
        (all_, slice(0, d)),        # west
    ]
    counts = [d * side, d * side, d * side, d * side]
    return [(r, np.float32(1.0 / max(c, 1))) for r, c in zip(regions, counts)]


def decode(genome: np.ndarray) -> dict[str, np.ndarray]:
    """Map genes in [0, 1] onto behavioral ranges. [W, N, G] -> named [W, N]."""
    g = genome
    return {
        "hunger_threshold": g[..., G_HUNGER] * 60.0,
        "persistence": g[..., G_PERSISTENCE] * 4.0,
        "gradient": g[..., G_GRADIENT] * 8.0,
        "temperature": 0.05 + g[..., G_TEMP] * 2.0,
        "reproduce_at": 30.0 + g[..., G_REPRODUCE] * 120.0,
        "investment": 0.15 + g[..., G_INVESTMENT] * 0.45,
        "metabolic": 0.5 + g[..., G_METABOLIC] * 1.5,
        "crowd": g[..., G_CROWD] * 6.0,
    }


def choose_action(
    obs: np.ndarray,
    energy: np.ndarray,
    heading: np.ndarray,
    genome: np.ndarray,
    density: np.ndarray,
    masks: np.ndarray,
    rng_policy: np.random.Generator,
    sated_gradient_factor: float = 0.25,
) -> np.ndarray:
    """Return an action in 0..3 for every agent slot, living or not.

    Args:
        obs:      [W, N, P] resource values in the local patch.
        energy:   [W, N]
        heading:  [W, N] last direction, 0..3.
        genome:   [W, N, G] genes in [0, 1].
        density:  [W, N] agents sharing this agent's cell, including itself.
        masks:    [4, P] from `sector_masks`.
        rng_policy: the `policy` stream.

    The Gumbel-max draw is taken at [W, N, 4] for every slot, including dead ones.
    Drawing only for the living would make the stream's position depend on the
    population, and a fork would then diverge from its parent silently — the whole
    reason `test_noop_fork` exists.
    """
    p = decode(genome)

    # Perceived resource in each direction, [W, N, 4]. Summed over slice views in
    # a fixed order rather than by matmul — see `sector_masks` for why this is not
    # `obs @ masks.T`.
    side = int(round(obs.shape[2] ** 0.5))
    patch = obs.reshape(obs.shape[0], obs.shape[1], side, side)
    sector = np.empty(obs.shape[:2] + (4,), dtype=np.float32)
    for d, (region, weight) in enumerate(masks):
        np.multiply(patch[:, :, region[0], region[1]].sum(axis=(2, 3)), weight,
                    out=sector[:, :, d])

    hungry = energy < p["hunger_threshold"]
    # Hunger sharpens the gradient response rather than switching it on. A hard
    # switch would put a discontinuity in the fitness landscape that selection
    # would sit exactly on top of.
    #
    # `sated_gradient_factor` is the one piece of hunger-conditioned behavior that
    # is *structural* rather than evolved: at 0.25 a sated agent weighs the
    # gradient a quarter as much as a hungry one, and at 1.0 hunger does not
    # affect gradient-following at all. It is a parameter rather than a constant
    # because it turns out to drive the sign of `directed_foraging`, and a
    # detector must never be measuring a number hidden in the policy — see
    # experiments/a1-patchiness/result.md.
    gradient_weight = np.where(
        hungry, p["gradient"], p["gradient"] * np.float32(sated_gradient_factor)
    )
    logits = gradient_weight[..., None] * sector

    onehot = np.equal(np.arange(4, dtype=np.int8)[None, None, :], heading[..., None])
    crowding = p["crowd"] * np.maximum(density.astype(np.float32) - 1.0, 0.0)
    # Crowding erodes the tendency to hold a heading, which is what turns a
    # locally dense population into a dispersing one.
    persistence = np.maximum(p["persistence"] - crowding, 0.0)
    logits = logits + persistence[..., None] * onehot

    # Softmax sample by inverse CDF. Gumbel-max is the more familiar spelling and
    # samples the same distribution, but it needs four random numbers and two
    # logarithms per agent; this needs one uniform and one exponential. Measured
    # at 4.3 -> 1.9 ms/tick at W=32, N=1000, which is a fifth of the whole tick.
    temperature = np.maximum(p["temperature"], 1e-3)[..., None]
    scaled = logits / temperature
    np.subtract(scaled, scaled.max(axis=2, keepdims=True), out=scaled)
    weights = np.exp(scaled)
    cumulative = np.cumsum(weights, axis=2)
    draw = rng_policy.random(logits.shape[:2], dtype=np.float32) * cumulative[:, :, -1]
    return np.count_nonzero(cumulative < draw[..., None], axis=2).astype(np.int8)


def mutation_noise(
    shape: tuple[int, int, int],
    rate: float,
    scale: float,
    rng_mutation: np.random.Generator,
) -> np.ndarray:
    """Per-gene Gaussian perturbation, drawn at a shape fixed by config alone.

    `shape` is `[worlds, birth_cap, genes]` — a config constant, never the living
    population and never the number of births that actually occur. That is the
    whole discipline: the stream must advance identically whatever happens in the
    world, or a fork silently stops matching its parent.

    Sizing it by `birth_cap` rather than by agent capacity is what makes the rule
    affordable. Drawing at full `[W, N, G]` cost 2.3 ms per tick to produce
    256,000 numbers for roughly sixty births — a sixth of the entire tick budget
    spent on noise nobody used.
    """
    hits = rng_mutation.random(shape, dtype=np.float32) < rate
    delta = rng_mutation.standard_normal(shape, dtype=np.float32) * scale
    return np.where(hits, delta, np.float32(0.0))


def apply_mutation(parent_genes: np.ndarray, noise: np.ndarray) -> np.ndarray:
    """Genes are clipped to [0, 1] rather than wrapped or reflected.

    Clipping makes the boundary absorbing, so selection can park a trait at its
    limit and keep it there — the honest representation of a trait that has hit a
    physical ceiling. Reflection would push it back down and read as stabilizing
    selection that nothing in the world is applying.
    """
    return np.clip(parent_genes + noise, 0.0, 1.0)
