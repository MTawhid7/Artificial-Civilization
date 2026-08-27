"""Full-state snapshots — what makes forking possible.

Invariant I3: rewind to tick T, change one thing, re-run. That affordance is the
whole basis of causal inference here, and it costs nothing at runtime but exacts
one absolute requirement:

    A checkpoint must capture EVERYTHING.

World arrays, RNG stream positions, the pending-effects queue, and every
accumulator value. An incomplete checkpoint does not fail loudly; it produces
forks that diverge from their parents gradually and silently, and the results look
plausible. `test_noop_fork` and `test_pending_fork` are the only things standing
between that bug and months of wasted analysis.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from core.pending import Accumulators, PendingQueue
from core.rng import RngStreams
from core.state import World

# v2 (B0): agent columns gained `lineage` and the world gained the S1 weight
# banks. A v1 checkpoint has neither, so forking one at S1 would silently give
# every agent lineage 0 and a bank of zeros — a policy that always picks north.
# The version refuses instead.
FORMAT_VERSION = 2


def save(
    path: str | Path,
    world: World,
    rng: RngStreams,
    pending: PendingQueue,
    accumulators: Accumulators,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload: dict[str, np.ndarray] = {"_format": np.array([FORMAT_VERSION], dtype=np.int32)}
    payload.update(world.to_arrays())
    payload.update(pending.to_arrays())
    payload.update(accumulators.to_arrays())
    # RNG state is JSON: PCG64 counters are 128-bit and no numpy dtype holds them.
    payload["_rng"] = np.array(rng.get_state())

    np.savez(path, **payload)
    return path


def load(path: str | Path) -> tuple[World, RngStreams, PendingQueue, Accumulators]:
    with np.load(Path(path), allow_pickle=False) as data:
        fmt = int(data["_format"][0])
        if fmt != FORMAT_VERSION:
            raise ValueError(
                f"checkpoint format v{fmt}, expected v{FORMAT_VERSION}. Forking across "
                "format versions is not supported — re-run the parent instead."
            )
        arrays = {k: data[k] for k in data.files}

    world = World.from_arrays(arrays)
    rng = RngStreams.from_state(str(arrays["_rng"]))
    pending = PendingQueue.from_arrays(arrays)
    accumulators = Accumulators.from_arrays(arrays)
    return world, rng, pending, accumulators


def digest(path: str | Path) -> str:
    """Hash of a checkpoint's contents, in canonical key order.

    Used by test_log_tier_invariance: two runs of the same seed at different log
    tiers must produce identical checkpoints. If they do not, logging is
    perturbing the simulation.
    """
    h = hashlib.blake2b(digest_size=16)
    with np.load(Path(path), allow_pickle=False) as data:
        for key in sorted(data.files):
            h.update(key.encode())
            h.update(np.ascontiguousarray(data[key]).tobytes())
    return h.hexdigest()


def nearest_before(checkpoint_dir: str | Path, tick: int) -> tuple[Path, int] | None:
    """The latest checkpoint at or before `tick`.

    Fork cost is `load(nearest) + replay to fork_tick`, which is why
    `run.checkpoint_every` trades disk against fork latency.
    """
    best: tuple[Path, int] | None = None
    for p in sorted(Path(checkpoint_dir).glob("ckpt_*.npz")):
        t = int(p.stem.split("_")[1])
        if t <= tick and (best is None or t > best[1]):
            best = (p, t)
    return best
