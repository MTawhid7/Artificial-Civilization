"""Scheduled effects and threshold accumulators — one structure, many timescales.

D-025: delayed effects, accumulators, threshold crossings, and generational
consequences are all served by a single scheduled-effects queue rather than by
per-primitive special cases. The tick loop otherwise assumes everything resolves
within the current tick, which makes slow causation impossible to express.

**Nothing in A0 uses this.** It is built now anyway, because a checkpoint that
omits the queue produces forks that diverge from their parents with no visible
symptom — the most dangerous bug class in the project (docs/06-data-model.md).
`test_pending_fork` is the only thing that catches it, and it cannot be written
against a structure that does not exist.

Ordering is `(fire_tick, insertion_id)` and never heap tie-break order: two effects
scheduled for the same tick must resolve in the order they were created, in every
replay, on every machine.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Effect types. Integers, never strings, inside core.
EFFECT_NONE = 0
EFFECT_RESOURCE_DELTA = 1  # a: magnitude applied to resource at target cell
EFFECT_ENERGY_DELTA = 2    # a: magnitude applied to agent energy
EFFECT_PARAM_SET = 3       # a: new value for a parameter named by target_ref

_FIELDS: tuple[tuple[str, type], ...] = (
    ("fire_tick", np.uint32),
    ("insertion_id", np.uint64),
    ("effect_type", np.uint8),
    ("world", np.uint16),
    ("target_ref", np.uint32),  # agent id, flat cell index, or parameter id
    ("magnitude", np.float32),
    ("origin_event", np.uint32),
)


@dataclass(slots=True)
class PendingQueue:
    """Append-ordered store of effects due at future ticks.

    Small by design: a queue large enough for arrays-of-structs to matter would
    mean the world is scheduling more than it resolves, which is a modelling bug
    rather than a performance one.
    """

    fire_tick: np.ndarray
    insertion_id: np.ndarray
    effect_type: np.ndarray
    world: np.ndarray
    target_ref: np.ndarray
    magnitude: np.ndarray
    origin_event: np.ndarray
    _next_insertion: int = 0

    @classmethod
    def empty(cls) -> "PendingQueue":
        return cls(**{name: np.empty(0, dtype=dt) for name, dt in _FIELDS})

    def __len__(self) -> int:
        return int(self.fire_tick.size)

    def schedule(
        self,
        fire_tick: int,
        effect_type: int,
        *,
        world: int = 0,
        target_ref: int = 0,
        magnitude: float = 0.0,
        origin_event: int = 0,
    ) -> int:
        """Register one effect. Returns its insertion id, which fixes tie order."""
        ins = self._next_insertion
        self._next_insertion += 1
        values = {
            "fire_tick": fire_tick,
            "insertion_id": ins,
            "effect_type": effect_type,
            "world": world,
            "target_ref": target_ref,
            "magnitude": magnitude,
            "origin_event": origin_event,
        }
        for name, dt in _FIELDS:
            setattr(self, name, np.append(getattr(self, name), np.array([values[name]], dtype=dt)))
        return ins

    def pop_due(self, tick: int) -> dict[str, np.ndarray]:
        """Remove and return every effect due at or before `tick`, in fire order.

        `np.lexsort` puts the last key first, so this sorts by fire_tick then by
        insertion_id — the ordering the whole determinism argument rests on.
        """
        due = self.fire_tick <= np.uint32(tick)
        if not due.any():
            return {name: np.empty(0, dtype=dt) for name, dt in _FIELDS}

        idx = np.flatnonzero(due)
        order = idx[np.lexsort((self.insertion_id[idx], self.fire_tick[idx]))]
        fired = {name: getattr(self, name)[order].copy() for name, _ in _FIELDS}

        keep = ~due
        for name, _ in _FIELDS:
            setattr(self, name, getattr(self, name)[keep])
        return fired

    # --- checkpointing --------------------------------------------------------

    def to_arrays(self, prefix: str = "pending_") -> dict[str, np.ndarray]:
        out = {f"{prefix}{name}": getattr(self, name) for name, _ in _FIELDS}
        out[f"{prefix}_next"] = np.array([self._next_insertion], dtype=np.uint64)
        return out

    @classmethod
    def from_arrays(cls, data: dict[str, np.ndarray], prefix: str = "pending_") -> "PendingQueue":
        q = cls(**{name: np.asarray(data[f"{prefix}{name}"], dtype=dt) for name, dt in _FIELDS})
        q._next_insertion = int(data[f"{prefix}_next"][0])
        return q


@dataclass(slots=True)
class Accumulators:
    """Slowly-filling quantities that fire an effect when they cross a threshold.

    The point of these is not the crossing but the filling: a bar quietly rising
    for two thousand years before anything visible happens is the honest shape of
    most historical causation, and the agents cannot see it either.
    """

    value: np.ndarray
    threshold: np.ndarray
    on_cross_effect: np.ndarray
    scope_ref: np.ndarray
    fired: np.ndarray

    @classmethod
    def empty(cls) -> "Accumulators":
        return cls(
            value=np.empty(0, dtype=np.float32),
            threshold=np.empty(0, dtype=np.float32),
            on_cross_effect=np.empty(0, dtype=np.uint8),
            scope_ref=np.empty(0, dtype=np.uint32),
            fired=np.empty(0, dtype=np.bool_),
        )

    def __len__(self) -> int:
        return int(self.value.size)

    def add(self, threshold: float, on_cross_effect: int, scope_ref: int = 0) -> int:
        self.value = np.append(self.value, np.float32(0.0))
        self.threshold = np.append(self.threshold, np.float32(threshold))
        self.on_cross_effect = np.append(self.on_cross_effect, np.uint8(on_cross_effect))
        self.scope_ref = np.append(self.scope_ref, np.uint32(scope_ref))
        self.fired = np.append(self.fired, False)
        return len(self) - 1

    def step(self, deltas: np.ndarray) -> np.ndarray:
        """Advance every accumulator; return the mask of those crossing this tick.

        A crossing fires once. Without the `fired` latch an accumulator sitting at
        its threshold would fire every tick forever, which is a runaway rather
        than a tipping point.
        """
        if len(self) == 0:
            return np.empty(0, dtype=np.bool_)
        self.value += deltas.astype(np.float32)
        crossing = (~self.fired) & (self.value >= self.threshold)
        self.fired |= crossing
        return crossing

    def to_arrays(self, prefix: str = "acc_") -> dict[str, np.ndarray]:
        return {
            f"{prefix}value": self.value,
            f"{prefix}threshold": self.threshold,
            f"{prefix}on_cross": self.on_cross_effect,
            f"{prefix}scope": self.scope_ref,
            f"{prefix}fired": self.fired,
        }

    @classmethod
    def from_arrays(cls, data: dict[str, np.ndarray], prefix: str = "acc_") -> "Accumulators":
        return cls(
            value=np.asarray(data[f"{prefix}value"], dtype=np.float32),
            threshold=np.asarray(data[f"{prefix}threshold"], dtype=np.float32),
            on_cross_effect=np.asarray(data[f"{prefix}on_cross"], dtype=np.uint8),
            scope_ref=np.asarray(data[f"{prefix}scope"], dtype=np.uint32),
            fired=np.asarray(data[f"{prefix}fired"], dtype=np.bool_),
        )
