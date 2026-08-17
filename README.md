# Artificial Civilization

**A comparative history laboratory.**

It is not a world you watch; it is a machine that produces thousands of divergent histories from
controlled initial conditions, plus the tooling to ask causal questions of them. Agents are
numeric, not LLMs. They want one thing — energy above zero, and offspring — and every social
structure from trade to government must earn its place by being a better way of not dying.
Twelve primitives generate everything; no phenomenon is ever implemented directly. There is no
`war.py`, no collapse routine, no plague module — only primitives rich enough to make those
happen, and detectors that notice when they do.

The simulation is the instrument. The histories are the data. The science is comparative.

---

## Status

**Stage A0 — Skeleton.** Building the deterministic core: array-based world, event log,
checkpoints, forking, and the determinism test gate. No results yet.

Design is frozen and lives in [`docs/`](docs/). Start with
[docs/README.md](docs/README.md) for the reading order — or
[docs/00-feasibility.md](docs/00-feasibility.md) if you want to know what this can and cannot do
on the hardware it targets (an 8 GB M1 Air).

---

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) and Python 3.13.

```bash
uv sync --all-extras          # exact versions from uv.lock
uv run pytest                 # the determinism gate — must be green before anything else
uv run python -m bench.bench_tick --scales all
```

---

## Layout

```
docs/          canonical design — 17 documents, the single source of truth
src/
  core/        the world. no strings, no phenomenon names, no I/O beyond event emission
  chronicle/   event log, sharding, checkpoints
  lens/        detectors and their null models — one file per detector
  forge/       runs, sweeps, forks
configs/       frozen defaults and experiment configs
experiments/   spec.yaml + result.md per experiment, including negative results
schemas/       versioned event and digest schemas
tests/         the determinism gate
bench/         performance measurement; cost-per-world-year is a tracked metric
```

## The rules that shape the code

Four invariants hold from commit #1, because retrofitting any of them is agony:

1. **Determinism** — a run is a pure function of `(config, seed)`; replay is bit-identical.
2. **Event sourcing** — if a fact isn't in the Chronicle, it does not exist for analysis.
3. **Forkability** — rewind to tick T, change one thing, re-run.
4. **Array state** — agents are columns, not objects; worlds are a batch axis.

And two conventions worth knowing before reading `src/`:

- **No phenomenon names in `src/core/`.** Words like *war*, *trade*, and *revolution* live only in
  `src/lens/`, where they name measurements rather than mechanisms.
- **No detector without a null model.** A measurement without one is a plot, not a result.

See [docs/DECISIONS.md](docs/DECISIONS.md) for every design decision and what was rejected.
