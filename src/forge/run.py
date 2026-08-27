"""Run a batch of worlds from (config, seed).

A run is a pure function of its inputs and writes a self-describing directory:

    corpus/runs/<run_id>/
      config.yaml       the resolved, frozen config
      meta.json         seed, code version, schema version, generator params, digest
      chronicle/*.parquet
      checkpoints/*.npz
      aggregate.parquet

Everything needed to replay, fork, or analyze the run is inside it. Nothing
depends on the state of the working tree at analysis time.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

import numpy as np

from chronicle import checkpoint
from chronicle.writer import ChronicleWriter
from core.config import Config, load, run_id
from core.generators import world_gen
from core.pending import Accumulators, PendingQueue
from core.policy import s1_neural
from core.policy.s0_reactive import GENOME_SIZE
from core.rng import RngStreams
from core.state import World
from core.tick import TickContext, step

CORPUS = Path("corpus")


def code_version() -> str:
    """Git sha of the working tree, or 'nogit' outside a repo.

    A dirty tree is marked, because a run whose code cannot be recovered is not
    reproducible and should not be trusted as corpus data.
    """
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        return f"{sha}{'-dirty' if dirty else ''}" if sha else "nogit"
    except Exception:
        return "nogit"


def init_world(cfg: Config, rng: RngStreams) -> World:
    """Allocate and seed the world. Generators run exactly once, here."""
    n_worlds = int(cfg.get("run.worlds"))
    capacity = int(cfg.get("population.capacity"))
    grid = int(cfg.get("world.grid"))
    initial = int(cfg.get("population.initial"))

    genome_size = int(cfg.get("intelligence.genome_size", GENOME_SIZE))
    view_radius = int(cfg.get("intelligence.view_radius"))

    # Zero-width at S0: no lineages, no hidden layer, no input matrix. The
    # neural machinery is absent at that stage rather than allocated and unused.
    neural = cfg.stage != "S0"
    lineages = int(cfg.get("intelligence.lineages")) if neural else 0
    hidden = int(cfg.get("intelligence.hidden")) if neural else 0
    n_in = s1_neural.n_inputs(view_radius, genome_size) if neural else 0

    world = World.allocate(
        n_worlds=n_worlds,
        n_agents=capacity,
        grid=grid,
        genome_size=genome_size,
        view_radius=view_radius,
        lineages=lineages,
        hidden=hidden,
        n_inputs=n_in,
    )

    world.capacity[:] = generate = world_gen.generate_resource_field(cfg, rng)
    world.resource[:] = generate * float(cfg.get("world.resource_capacity"))
    world.terrain[:] = world_gen.generate_terrain(cfg, rng)

    # Founding cohort. Draws are full-shape so the stream position does not
    # depend on how many agents the config asks for at any later point.
    start_x = rng.generator.integers(0, grid, size=(n_worlds, capacity)).astype(np.int16)
    start_y = rng.generator.integers(0, grid, size=(n_worlds, capacity)).astype(np.int16)
    start_g = rng.generator.random((n_worlds, capacity, world.genome_size), dtype=np.float32)

    for w in range(n_worlds):
        slots = world.free_slots(w, initial)
        world.spawn(w, slots, np.zeros(slots.size, dtype=np.uint32))
        world.x[w, slots] = start_x[w, slots]
        world.y[w, slots] = start_y[w, slots]
        world.genome[w, slots] = start_g[w, slots]
        world.energy[w, slots] = np.float32(cfg.get("agent.start_energy"))

    # Last, and from its own stream. Everything above draws from `generator`, so
    # an S0 arm and an S1 arm of the same seed get the same landscape and the
    # same founding cohort down to the byte — which is what makes the B0
    # comparison paired by world rather than two independent samples (D-072).
    if neural:
        s1_neural.initial_weights(world, rng.policy_init)
        s1_neural.assign_founders(world)
    return world


def run(
    cfg: Config,
    seed: int,
    *,
    out_root: Path = CORPUS,
    progress: bool = True,
    log_tier: str | None = None,
) -> dict:
    version = code_version()
    rid = run_id(cfg.config_hash, seed, version)
    run_dir = out_root / "runs" / rid
    run_dir.mkdir(parents=True, exist_ok=True)

    rng = RngStreams(seed)
    world = init_world(cfg, rng)
    ctx = TickContext.build(cfg, world)
    pending = PendingQueue.empty()
    accumulators = Accumulators.empty()

    chronicle = ChronicleWriter(
        run_dir,
        tier=log_tier or str(cfg.get("run.log_tier")),
        sample_rate=int(cfg.get("run.sample_rate")),
        shard_ticks=int(cfg.get("run.shard_ticks")),
    )

    ticks = int(cfg.get("run.ticks"))
    every = int(cfg.get("run.checkpoint_every"))
    ckpt_dir = run_dir / "checkpoints"

    started = time.perf_counter()
    for t in range(ticks):
        if t % every == 0:
            checkpoint.save(ckpt_dir / f"ckpt_{t:09d}.npz", world, rng, pending, accumulators)
        step(world, ctx, rng, pending, accumulators, chronicle)
        if progress and t and t % max(ticks // 20, 1) == 0:
            pop = int(world.population.sum())
            elapsed = time.perf_counter() - started
            print(f"    tick {t:>7,}  pop {pop:>6,}  {elapsed * 1000 / t:6.2f} ms/tick")
        if world.population.sum() == 0:
            print(f"    all worlds extinct at tick {t}")
            break

    elapsed = time.perf_counter() - started
    checkpoint.save(ckpt_dir / f"ckpt_{world.tick:09d}.npz", world, rng, pending, accumulators)
    chronicle.close()

    meta = {
        "run_id": rid,
        "seed": seed,
        "code_version": version,
        "schema_version": cfg.data["schema_version"],
        # Recorded here as well as in config.yaml because the stage decides how
        # the run's own numbers should be *read*: at S0 the eight genes have the
        # names in s0_reactive's decode table, and at S1 five of them are an
        # embedding that means whatever selection made it mean. A reader that
        # labels an S1 gene "gradient_sensitivity" produces a sentence that is
        # cited, verified, and false.
        "stage": cfg.stage,
        "config_hash": cfg.config_hash,
        "config_source": cfg.source,
        "ticks_completed": world.tick,
        "generator": world_gen.describe(cfg),
        "chronicle_digest": chronicle.digest,
        "chronicle_rows": chronicle.total_rows,
        "chronicle_bytes": chronicle.size_bytes(),
        "final_state_hash": world.state_hash(),
        "final_population": world.population.tolist(),
        "wall_seconds": round(elapsed, 2),
        "ms_per_tick": round(elapsed * 1000 / max(world.tick, 1), 4),
        "live_viewer": False,  # D-048: viewer runs are excluded from the corpus
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    (run_dir / "config.yaml").write_text(cfg.to_yaml())
    return meta


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("config")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--ticks", type=int, default=None, help="override run.ticks")
    p.add_argument("--out", default=str(CORPUS))
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()

    cfg = load(args.config)
    if args.ticks is not None:
        from core.config import resolve
        raw = dict(cfg.data)
        raw["run"] = {**raw["run"], "ticks": args.ticks}
        cfg = resolve(raw, source=cfg.source)

    print(f"  {Path(args.config).name}  seed={args.seed}  hash={cfg.config_hash[:12]}")
    meta = run(cfg, args.seed, out_root=Path(args.out), progress=not args.quiet)
    mb = meta["chronicle_bytes"] / 2**20
    print(
        f"\n  {meta['ticks_completed']:,} ticks in {meta['wall_seconds']:.1f}s "
        f"({meta['ms_per_tick']:.2f} ms/tick)\n"
        f"  chronicle {mb:.1f} MB / {meta['chronicle_rows']:,} rows\n"
        f"  digest {meta['chronicle_digest']}\n"
        f"  -> corpus/runs/{meta['run_id']}"
    )


if __name__ == "__main__":
    main()
