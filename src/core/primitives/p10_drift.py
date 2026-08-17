"""P10 — Drift, at L0.

Constant slow drift of carrying capacity. L1 opens this up into a spectrum of
processes — trends, cycles, and heavy-tailed shocks — which is where P10 starts
mattering: the world must contain both historical continuity and genuine
discontinuity. At L0 there is only the slow part.

Drift is applied to *capacity*, not to stock. Moving the ceiling changes what a
place can support without instantly taking anything away, so populations meet the
change through the resource dynamics rather than through a sudden loss. The
distinction matters later, when a detector has to separate adaptation from shock.
"""

from __future__ import annotations

import numpy as np


def drift_capacity(capacity: np.ndarray, rate: float, tick: int, period: int = 10_000) -> None:
    """Apply one tick of slow drift to carrying capacity, in place.

    A very long cosine rather than a random walk: at L0 the point is a world that
    is not stationary, while remaining reproducible and bounded. Random-walk
    capacity would wander into degenerate worlds over 100k ticks, which is a
    viability problem rather than a source of history.
    """
    if rate == 0.0:
        return
    phase = 2.0 * np.pi * (tick % period) / period
    factor = np.float32(1.0 + rate * np.cos(phase))
    np.multiply(capacity, factor, out=capacity)
    np.clip(capacity, 1e-3, None, out=capacity)
