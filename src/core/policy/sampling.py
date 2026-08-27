"""Action sampling, shared by every policy stage.

One implementation, because the alternative is two — and two implementations of
a softmax drift apart in their last ulp long before anyone notices, at which
point S0 and S1 are no longer running the same experiment with a different brain.

The property that has to hold across stages is narrower and more important than
"both sample a softmax":

    every stage draws exactly one [W, N] float32 from the `policy` stream,
    once per tick, at a shape fixed by config.

That is determinism rule 1 applied across the stage ladder. It means the policy
stream sits at the same position after tick T whichever policy ran, so a
checkpoint written at S0 is a legal starting point for an S1 fork, and adding a
stage never perturbs a stream. Drawing per living agent, or drawing a different
number of values at different stages, would break both (D-053).
"""

from __future__ import annotations

import numpy as np

MIN_TEMPERATURE = 1e-3


def softmax_sample(
    logits: np.ndarray,
    temperature: np.ndarray | float,
    rng_policy: np.random.Generator,
) -> np.ndarray:
    """Sample one action per agent slot from `logits`. Returns `[W, N]` int8.

    Args:
        logits: `[W, N, A]` — one score per action, for every slot, living or not.
        temperature: `[W, N]` per-agent (S0, where it is a gene) or a scalar
            (S1, where the network scales its own logits). Clamped below.
        rng_policy: the `policy` stream.

    **Inverse CDF, not Gumbel-max.** The two sample the same distribution.
    Gumbel-max is the more familiar spelling and needs four random numbers and
    two logarithms per agent; this needs one uniform and one exponential.
    Measured at 4.3 -> 1.9 ms/tick at W=32, N=1000, a fifth of the whole tick.

    **The draw is taken for every slot, including dead ones.** Drawing only for
    the living would make the stream's position depend on the population, and a
    fork would then diverge from its parent with no symptom — the whole reason
    `test_noop_fork` exists.
    """
    # float32 explicitly, and not as tidiness. `np.maximum(1.0, MIN_TEMPERATURE)`
    # returns a numpy float64 *scalar*, and under NEP 50 a numpy scalar promotes
    # a float32 array — so a scalar temperature would silently run the whole
    # softmax in double precision while a per-agent float32 one ran in single.
    # Nothing would fail: both are deterministic, both are reasonable, and the
    # two stages of an experiment built to compare them would differ in
    # arithmetic nobody chose.
    temp = np.maximum(temperature, MIN_TEMPERATURE, dtype=np.float32)
    if temp.ndim == logits.ndim - 1:
        temp = temp[..., None]

    scaled = logits / temp
    # Subtracting the row max is the standard overflow guard, in place so the
    # tick allocates one array here rather than three.
    np.subtract(scaled, scaled.max(axis=-1, keepdims=True), out=scaled)
    weights = np.exp(scaled)
    cumulative = np.cumsum(weights, axis=-1)
    draw = rng_policy.random(logits.shape[:-1], dtype=np.float32) * cumulative[..., -1]
    return np.count_nonzero(cumulative < draw[..., None], axis=-1).astype(np.int8)
