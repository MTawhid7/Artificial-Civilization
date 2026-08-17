"""Chronicle writer — buffered, sharded, tiered.

The Chronicle is the binding constraint on this project (D-047). At 1,000 agents
over 100k ticks a naive log is roughly 2 GB *per world*, and the target is 50 MB.
Tiering is how the gap closes, and the writer enforces it rather than trusting
callers to remember.

Every detector must be computable from what survives sampling. That is a
constraint on detector design, applied when the detector is written rather than
discovered when the disk fills.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from chronicle import schema as S


class ChronicleWriter:
    """Append-only event sink for one run.

    Events accumulate in memory and flush to Parquet at shard boundaries. Shards
    are named by their starting tick so the corpus can be scanned by tick range
    without opening every file.
    """

    def __init__(
        self,
        run_dir: str | Path,
        *,
        tier: str = "sampled",
        sample_rate: int = 64,
        shard_ticks: int = 5000,
        compression: str = "zstd",
    ) -> None:
        self.run_dir = Path(run_dir)
        self.events_dir = self.run_dir / "chronicle"
        self.events_dir.mkdir(parents=True, exist_ok=True)

        self.tier = tier
        self.sample_rate = int(sample_rate)
        self.shard_ticks = int(shard_ticks)
        self.compression = compression

        self._cols: dict[str, list[np.ndarray]] = {name: [] for name, _ in S.ENVELOPE}
        self._agg: list[dict] = []
        self._shard_index = 0
        self._shard_start = 0
        self._rows = 0
        self.total_rows = 0

        # A rolling digest of everything written, in write order. This is what
        # test_determinism and test_cross_machine compare, and it is cheaper and
        # stricter than diffing Parquet files, whose bytes depend on the
        # compressor's version.
        self._digest = hashlib.blake2b(digest_size=16)

    # --- emission -------------------------------------------------------------

    def emit(
        self,
        tick: int,
        event_type: int,
        world_id: np.ndarray,
        subject: np.ndarray,
        obj: np.ndarray | None = None,
        a: np.ndarray | None = None,
        b: np.ndarray | None = None,
        c: np.ndarray | None = None,
    ) -> None:
        """Append a batch of one event type, applying the tier policy.

        Arrays are 1-D and parallel. Callers pass whole vectorized batches; there
        is no per-agent path, because at 32 worlds x 1,000 agents there cannot be.
        """
        n = subject.size
        if n == 0:
            return

        event_tier = S.EVENT_TIER.get(event_type, S.TIER_SAMPLED)
        if not self._should_write(event_tier):
            return
        if event_tier == S.TIER_SAMPLED and self.tier == "sampled":
            keep = S.sample_mask(tick, subject, self.sample_rate)
            if not keep.any():
                return
            world_id, subject = world_id[keep], subject[keep]
            obj = obj[keep] if obj is not None else None
            a = a[keep] if a is not None else None
            b = b[keep] if b is not None else None
            c = c[keep] if c is not None else None
            n = subject.size

        zeros_f = np.zeros(n, dtype=np.float32)
        batch = {
            "tick": np.full(n, tick, dtype=np.uint32),
            "world_id": world_id.astype(np.uint16, copy=False),
            "event_type": np.full(n, event_type, dtype=np.uint8),
            "subject": subject.astype(np.uint32, copy=False),
            "object": (obj.astype(np.uint32, copy=False) if obj is not None
                       else np.zeros(n, dtype=np.uint32)),
            "a": a.astype(np.float32, copy=False) if a is not None else zeros_f,
            "b": b.astype(np.float32, copy=False) if b is not None else zeros_f,
            "c": c.astype(np.float32, copy=False) if c is not None else zeros_f,
        }
        for name, _ in S.ENVELOPE:
            arr = batch[name]
            self._cols[name].append(arr)
            self._digest.update(np.ascontiguousarray(arr).tobytes())

        self._rows += n
        self.total_rows += n
        if tick - self._shard_start >= self.shard_ticks:
            self.flush(tick)

    def _should_write(self, event_tier: int) -> bool:
        if self.tier == "always":
            return True
        if self.tier == "sampled":
            return event_tier in (S.TIER_ALWAYS, S.TIER_SAMPLED)
        return event_tier == S.TIER_ALWAYS  # "aggregated": only the decisive events

    def emit_aggregate(self, tick: int, rows: list[dict]) -> None:
        """Binned per-world totals. Never per-agent, at any tier.

        These are what most population-level detectors actually read, which is why
        they survive every tier including the most aggressive one.
        """
        for row in rows:
            self._agg.append({"tick": np.uint32(tick), **row})
            self._digest.update(
                json.dumps(
                    {k: (round(float(v), 6) if isinstance(v, (float, np.floating))
                         else (list(np.round(np.asarray(v, dtype=np.float64), 6))
                               if isinstance(v, (list, np.ndarray)) else int(v)))
                     for k, v in row.items()},
                    sort_keys=True,
                ).encode()
            )

    # --- output ---------------------------------------------------------------

    def flush(self, tick: int) -> None:
        if self._rows:
            table = pa.table(
                {name: np.concatenate(self._cols[name]) for name, _ in S.ENVELOPE},
                schema=S.ARROW_SCHEMA,
            )
            path = self.events_dir / f"events_{self._shard_start:09d}.parquet"
            pq.write_table(table, path, compression=self.compression)
            self._cols = {name: [] for name, _ in S.ENVELOPE}
            self._rows = 0
            self._shard_index += 1
        self._shard_start = tick

    def close(self) -> None:
        self.flush(self._shard_start + self.shard_ticks)
        if self._agg:
            cols = {
                key: [row[key] for row in self._agg]
                for key in self._agg[0]
            }
            table = pa.table(cols, schema=S.AGGREGATE_SCHEMA)
            pq.write_table(
                table, self.run_dir / "aggregate.parquet", compression=self.compression
            )
            self._agg = []

    @property
    def digest(self) -> str:
        """Hash of every event written, in write order."""
        return self._digest.hexdigest()

    def size_bytes(self) -> int:
        total = sum(p.stat().st_size for p in self.events_dir.glob("*.parquet"))
        agg = self.run_dir / "aggregate.parquet"
        return total + (agg.stat().st_size if agg.exists() else 0)


def gini(values: np.ndarray) -> float:
    """Gini coefficient of a non-negative 1-D array; 0.0 for fewer than two values.

    Sorted before summing, so the reduction order is a function of the data rather
    than of array layout (determinism rule 4).
    """
    v = np.sort(values[values >= 0].astype(np.float64))
    n = v.size
    if n < 2:
        return 0.0
    total = v.sum()
    if total <= 0:
        return 0.0
    index = np.arange(1, n + 1, dtype=np.float64)
    return float((2.0 * (index * v).sum()) / (n * total) - (n + 1.0) / n)
