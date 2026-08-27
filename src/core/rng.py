"""Named, independent random streams — invariant I1's foundation.

Determinism rule 1 (docs/11-engineering.md): one explicit RNG, split by purpose,
never the global default, never reseeded mid-run.

Two properties this module exists to guarantee:

**Streams are independent.** Adding a mutation draw must not shift what the world
draws. Each stream is spawned from the run seed under its own key, so they never
share a sequence.

**Stream identity is derived from the name, not from declaration order.** Spawning
by index means inserting a new stream renumbers every stream after it, silently
changing the results of every experiment already run. The key comes from a hash of
the name instead, so `STREAM_NAMES` can grow without invalidating the corpus.

The remaining hazard is not here but at every call site, and it is worth stating
where it will be read:

    Draw at fixed shape, then mask. Never draw per living agent.

A draw sized by the living population makes stream position depend on how many
agents happen to be alive, so a fork replayed from a checkpoint diverges from its
parent as soon as the populations differ by one. There is no visible symptom; the
histories simply stop matching. `test_noop_fork` is what catches it.
"""

from __future__ import annotations

import hashlib
import json
from typing import Iterator

import numpy as np

# Every stream the simulation may draw from. Add freely — names are hashed, so a
# new entry does not perturb the streams already here.
STREAM_NAMES: tuple[str, ...] = (
    "generator",    # world structure at init: terrain, resource fields, latent rules
    "world",        # per-tick world dynamics: drift, regrowth noise, shocks
    "policy",       # action sampling / exploration noise
    "mutation",     # genome perturbation at birth
    # Added at B0. Both exist so that S1's draws never touch `generator`, which
    # is what makes an S0 arm and an S1 arm of one seed the *same landscape with
    # the same founding cohort* — a paired comparison rather than two samples
    # (D-072). `lineage` is separate from `mutation` for the same reason one
    # step down: an S1 run with speciation off reproduces S0's mutation stream
    # exactly, so a divergence has one candidate cause instead of two.
    "policy_init",  # initial network weights, drawn once at world init (S1)
    "lineage",      # speciation draws and weight perturbation at birth (S1)
)


def _stream_key(name: str) -> int:
    """A stable 64-bit spawn key for a stream name.

    blake2b rather than hash(): Python's string hash is salted per process, so
    it would make runs irreproducible across invocations — the exact failure
    this module exists to prevent.
    """
    return int.from_bytes(hashlib.blake2b(name.encode(), digest_size=8).digest(), "big")


class RngStreams:
    """The run's random state. Construct once from the seed; never reseed.

    Access streams as attributes or by name:

        rng = RngStreams(seed=42)
        rng.mutation.standard_normal((W, N, G))
        rng["world"].random(...)
    """

    __slots__ = ("_seed", "_streams")

    def __init__(self, seed: int, *, names: tuple[str, ...] = STREAM_NAMES) -> None:
        self._seed = int(seed)
        self._streams: dict[str, np.random.Generator] = {
            name: np.random.Generator(
                np.random.PCG64(np.random.SeedSequence(self._seed, spawn_key=(_stream_key(name),)))
            )
            for name in names
        }

    @property
    def seed(self) -> int:
        return self._seed

    def __getattr__(self, name: str) -> np.random.Generator:
        try:
            return self._streams[name]
        except KeyError:
            raise AttributeError(
                f"no RNG stream {name!r}; add it to STREAM_NAMES "
                f"(known: {', '.join(sorted(self._streams))})"
            ) from None

    def __getitem__(self, name: str) -> np.random.Generator:
        return self._streams[name]

    def __iter__(self) -> Iterator[str]:
        return iter(self._streams)

    # --- checkpointing --------------------------------------------------------
    #
    # A checkpoint that omits RNG state produces forks that diverge from their
    # parents with no visible symptom (docs/06-data-model.md). State is stored as
    # JSON because PCG64's counters are 128-bit integers, which no numpy dtype
    # holds losslessly.

    def get_state(self) -> str:
        return json.dumps(
            {
                "seed": self._seed,
                "streams": {
                    name: _jsonable(gen.bit_generator.state)
                    for name, gen in sorted(self._streams.items())
                },
            },
            sort_keys=True,
        )

    def set_state(self, blob: str) -> None:
        data = json.loads(blob)
        self._seed = int(data["seed"])
        stored = data["streams"]
        missing = set(self._streams) - set(stored)
        if missing:
            raise ValueError(
                f"checkpoint is missing RNG streams {sorted(missing)}; it was written "
                "by an older code version and cannot be forked from safely"
            )
        for name, state in stored.items():
            if name in self._streams:
                self._streams[name].bit_generator.state = _from_jsonable(state)

    @classmethod
    def from_state(cls, blob: str) -> "RngStreams":
        data = json.loads(blob)
        rng = cls(int(data["seed"]), names=tuple(sorted(data["streams"])))
        rng.set_state(blob)
        return rng

    def __repr__(self) -> str:
        return f"RngStreams(seed={self._seed}, streams={sorted(self._streams)})"


def _jsonable(state: dict) -> dict:
    """PCG64 state holds ints wider than 64 bits; JSON handles them, numpy does not.

    Integers become digit strings so they survive the round trip exactly. The
    `bit_generator` field is already a name string and is left alone — hence the
    `isdigit` check on the way back.
    """
    out: dict = {}
    for k, v in state.items():
        if isinstance(v, dict):
            out[k] = _jsonable(v)
        elif isinstance(v, bool):
            out[k] = v
        elif isinstance(v, (int, np.integer)):
            out[k] = str(int(v))
        else:
            out[k] = v
    return out


def _from_jsonable(state: dict) -> dict:
    out: dict = {}
    for k, v in state.items():
        if isinstance(v, dict):
            out[k] = _from_jsonable(v)
        elif isinstance(v, str) and v.isdigit():
            out[k] = int(v)
        else:
            out[k] = v
    return out
