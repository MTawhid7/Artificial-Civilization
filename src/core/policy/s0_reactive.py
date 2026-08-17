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


def sector_masks(view_radius: int) -> np.ndarray:
    """A [4, P] mask selecting the cells lying in each direction from the agent.

    Sectors overlap on the diagonals and exclude the centre cell. Overlapping is
    deliberate: a rich patch to the north-east should raise the score of both
    north and east rather than being arbitrarily assigned to one.
    """
    d = view_radius
    oy, ox = np.mgrid[-d : d + 1, -d : d + 1]
    oy, ox = oy.ravel(), ox.ravel()
    masks = np.stack([oy < 0, ox > 0, oy > 0, ox < 0]).astype(np.float32)
    # Normalize so sector score is a mean, not a sum: otherwise a larger view
    # radius would silently amplify gradient_sensitivity.
    return masks / np.maximum(masks.sum(axis=1, keepdims=True), 1.0)


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

    # Perceived resource in each direction: [W, N, P] @ [P, 4] -> [W, N, 4]
    sector = obs @ masks.T

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
