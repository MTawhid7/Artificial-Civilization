"""The detector contract.

> No new mechanism without a detector.

Every detector is a **pure function over the Chronicle**. No detector reads live
state, and no detector is allowed to be merely a plot: it ships a definition, a
null model, a threshold, and two unit tests — a synthetic log on which it must
fire, and one on which it must stay silent.

The null model is the part that does the work. It should be the *most flattering*
alternative explanation available: if the claim survives the best case for chance,
it survives. A detector without one is not evidence of anything.

Firing has three conditions, all of which must hold (docs/07-detectors.md):

    1. effect size exceeds the threshold against the null
    2. it holds across at least three seeds under identical config
    3. it is not an artifact of a config change made in the same commit

Anything failing (2) is a **candidate**, never a result. Candidates are where
hypotheses come from, and reporting one as a finding is how a project starts
believing things that are not true.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np


@dataclass(slots=True)
class Firing:
    """A detector's verdict on one run."""

    detector: str
    magnitude: float          # the observed statistic
    null_mean: float          # what chance produces
    null_std: float
    effect_size: float        # (magnitude - null_mean) / null_std
    threshold: float
    fired: bool
    tick_range: tuple[int, int]
    n_observations: int
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def __str__(self) -> str:
        verdict = "FIRED" if self.fired else "silent"
        return (
            f"{self.detector:<22} {verdict:>7}  "
            f"obs={self.magnitude:+.4f}  null={self.null_mean:+.4f}±{self.null_std:.4f}  "
            f"z={self.effect_size:+.2f}  (n={self.n_observations:,})"
        )


class ChronicleReader:
    """Read-only access to one run's Chronicle, via DuckDB over Parquet.

    DuckDB is imported here and nowhere in `src/core/`. The core writes; the lens
    reads. Nothing in the analysis layer may ever be imported by the simulation,
    because a dependency in that direction is how a measurement quietly starts
    influencing the thing it measures.
    """

    def __init__(self, run_dir: str | Path) -> None:
        import duckdb

        self.run_dir = Path(run_dir)
        self.events_glob = str(self.run_dir / "chronicle" / "*.parquet")
        self.aggregate_path = self.run_dir / "aggregate.parquet"
        self._db = duckdb.connect()

    @property
    def meta(self) -> dict:
        return json.loads((self.run_dir / "meta.json").read_text())

    def events(self, event_type: int | None = None, columns: str = "*"):
        where = f"where event_type = {int(event_type)}" if event_type is not None else ""
        return self._db.sql(
            f"select {columns} from read_parquet('{self.events_glob}') {where}"
        )

    def aggregate(self):
        if not self.aggregate_path.exists():
            raise FileNotFoundError(
                f"no aggregate.parquet in {self.run_dir}. Population-level detectors read "
                "the aggregated tier, which must be enabled for the run."
            )
        return self._db.sql(f"select * from read_parquet('{self.aggregate_path}')")

    def sql(self, query: str):
        """`{events}` and `{aggregate}` expand to the relevant read_parquet calls."""
        return self._db.sql(
            query.format(
                events=f"read_parquet('{self.events_glob}')",
                aggregate=f"read_parquet('{self.aggregate_path}')",
            )
        )

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "ChronicleReader":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def wrapped_delta(a: np.ndarray, b: np.ndarray, size: int) -> np.ndarray:
    """Shortest signed step from `a` to `b` on a torus of width `size`.

    The world wraps, so an agent stepping from x=95 to x=0 moved +1, not -95.
    Getting this wrong makes every wrap look like a huge jump and inflates path
    length, which would show up as agents being far less directed than they are.
    """
    d = (b.astype(np.int64) - a.astype(np.int64)) % size
    return np.where(d > size // 2, d - size, d)


def summarize(firings: list[Firing]) -> str:
    lines = [str(f) for f in firings]
    n_fired = sum(f.fired for f in firings)
    lines.append(f"\n{n_fired}/{len(firings)} fired")
    return "\n".join(lines)
