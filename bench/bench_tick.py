"""Per-phase tick cost measurement.

Stage A0 requires replacing the analytic estimates in docs/00-feasibility.md with
measured numbers, and every later scale decision depends on them.

This starts as a *synthetic* benchmark: it allocates arrays at the real shapes and
executes the operations a tick is made of, with no simulation semantics. That is
enough to learn the two things that decide the design — what the observation gather
costs, and where memory lands — before core/tick.py exists. Once it does, point
`--target real` at the actual loop and the numbers stay comparable.

Phases are timed separately on purpose. A single ms/tick number tells you whether
you can afford a run; the breakdown tells you what to fix if you cannot.

    uv run python -m bench.bench_tick --scales all
"""

from __future__ import annotations

import argparse
import json
import platform
import resource
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np

RESULTS_DIR = Path(__file__).parent / "results"

# Scales from docs/00-feasibility.md. The middle one is the recommended default;
# the outer two bracket the range the corpus might realistically use.
SCALES: dict[str, dict[str, int]] = {
    "small": {"worlds": 8, "agents": 500, "grid": 96},
    "default": {"worlds": 32, "agents": 1000, "grid": 96},
    "large": {"worlds": 64, "agents": 2000, "grid": 96},
}

VIEW_RADIUS = 2  # 5x5 local patch — P2 at L0 is a local view
GENOME_SIZE = 8  # S0 reactive, see docs/04-intelligence.md


@dataclass
class PhaseTimings:
    """Milliseconds per tick, per phase. Field order is the tick loop's order."""

    world: float = 0.0  # phase 1  — regrowth over the full grid
    observe: float = 0.0  # phase 3  — the gather; expected to dominate
    decide: float = 0.0  # phase 4  — S0 reactive policy
    resolve_move: float = 0.0  # phase 5a — movement
    resolve_gather: float = 0.0  # phase 5b — contention + extraction
    metabolism: float = 0.0  # phase 6
    vitals: float = 0.0  # phase 7  — death, birth, mutation
    emit: float = 0.0  # phase 9  — Chronicle append (sampled tier)

    def total(self) -> float:
        return sum(asdict(self).values())


class SyntheticWorld:
    """Arrays at the real shapes, exercised by operations of the real kind.

    Structure-of-arrays with a leading worlds axis, per D-005: state is
    [W, N] for agents and [W, H, W] for fields. Agent capacity is fixed and
    `alive` is a tombstone, so indices stay stable across births and deaths.
    """

    def __init__(self, worlds: int, agents: int, grid: int, seed: int = 0) -> None:
        self.W, self.N, self.G = worlds, agents, grid
        rng = np.random.default_rng(seed)

        # Agent columns
        self.alive = np.ones((worlds, agents), dtype=bool)
        self.x = rng.integers(0, grid, (worlds, agents), dtype=np.int16)
        self.y = rng.integers(0, grid, (worlds, agents), dtype=np.int16)
        self.energy = rng.random((worlds, agents), dtype=np.float32) * 100.0
        self.age = np.zeros((worlds, agents), dtype=np.uint32)
        self.genome = rng.random((worlds, agents, GENOME_SIZE), dtype=np.float32)
        self.heading = rng.integers(0, 4, (worlds, agents), dtype=np.int8)

        # World fields
        self.resource = rng.random((worlds, grid, grid), dtype=np.float32)
        self.capacity = np.ones((worlds, grid, grid), dtype=np.float32)

        # The grid carries a wrapped halo of width VIEW_RADIUS so the observation
        # gather needs no bounds arithmetic. Refreshing the halo costs ~0.1 ms;
        # the modulo it removes cost ~5. See the note in phase_observe.
        d = VIEW_RADIUS
        self.d = d
        self.Gp = grid + 2 * d
        self.padded = np.zeros((worlds, self.Gp, self.Gp), dtype=np.float32)
        self.padded_flat = self.padded.reshape(worlds, -1)

        # Offsets precomputed in *flat padded* coordinates, so a whole patch is
        # one broadcast add rather than two index arrays plus a modulo.
        oy, ox = np.mgrid[-d : d + 1, -d : d + 1]
        self.off_flat = (oy.ravel().astype(np.intp) * self.Gp + ox.ravel().astype(np.intp))
        self.patch = self.off_flat.size

        # Index and observation buffers, allocated once. A tick allocates nothing.
        self.idx_buf = np.empty((worlds, agents, self.patch), dtype=np.intp)
        self.obs = np.empty((worlds, agents, self.patch), dtype=np.float32)

        # Chronicle staging buffer: fixed-width rows, sampled tier
        self.event_buf = np.zeros((worlds * agents // 8, 8), dtype=np.float32)

    def bytes_resident(self) -> int:
        return sum(
            a.nbytes
            for a in (
                self.alive, self.x, self.y, self.energy, self.age, self.genome,
                self.heading, self.resource, self.capacity, self.padded,
                self.idx_buf, self.obs, self.event_buf,
            )
        )

    # --- phases ---------------------------------------------------------------

    def phase_world(self) -> None:
        """Logistic regrowth across every cell of every world (P1 at L0)."""
        r = self.resource
        np.add(r, 0.01 * r * (self.capacity - r), out=r)

    def phase_observe(self) -> None:
        """Gather a 5x5 patch around each agent. The dominant cost of a tick.

        Measured breakdown at W=32, N=1000: halo refresh 0.11 ms, index build
        0.52 ms, gather 2.9 ms. The gather is irreducible random-access memory
        traffic and scales linearly in patch cells (9 -> 1.4 ms, 25 -> 3.5 ms,
        49 -> 6.9 ms), which makes VIEW_RADIUS the single largest performance
        lever in the simulation.
        """
        d, G, Gp = self.d, self.G, self.Gp
        # Wrapped halo: copy the opposite edges into the border ring.
        self.padded[:, d : d + G, d : d + G] = self.resource
        self.padded[:, :d, d : d + G] = self.resource[:, -d:, :]
        self.padded[:, -d:, d : d + G] = self.resource[:, :d, :]
        self.padded[:, :, :d] = self.padded[:, :, G : G + d]
        self.padded[:, :, -d:] = self.padded[:, :, d : 2 * d]

        base = (self.y.astype(np.intp) + d) * Gp + (self.x.astype(np.intp) + d)
        np.add(base[:, :, None], self.off_flat[None, None, :], out=self.idx_buf)
        self.obs.reshape(self.W, -1)[:] = np.take_along_axis(
            self.padded_flat, self.idx_buf.reshape(self.W, -1), axis=1
        )

    def phase_decide(self) -> np.ndarray:
        """S0 reactive: a handful of elementwise ops over obs and genome."""
        hungry = self.energy < self.genome[:, :, 0] * 100.0
        grad = self.obs.reshape(self.W, self.N, self.patch)
        best = np.argmax(grad, axis=2).astype(np.int8)
        keep = self.heading
        return np.where(hungry, best % 4, keep)

    def phase_resolve_move(self, action: np.ndarray) -> None:
        dx = np.choose(action, [0, 1, 0, -1]).astype(np.int16)
        dy = np.choose(action, [-1, 0, 1, 0]).astype(np.int16)
        np.mod(self.x + dx, self.G, out=self.x, where=self.alive)
        np.mod(self.y + dy, self.G, out=self.y, where=self.alive)
        self.heading = action.astype(np.int8)

    def phase_resolve_gather(self) -> None:
        """Contention resolved by (cell, agent_id) sort, first-wins.

        Not np.add.at: the semantics here are first-wins, and the ordering
        guarantee has to come from the sort, never from iteration order.
        """
        cell = self.y.astype(np.int32) * self.G + self.x
        order = np.lexsort((np.arange(self.N)[None, :].repeat(self.W, 0), cell), axis=1)
        sorted_cell = np.take_along_axis(cell, order, axis=1)
        first = np.ones_like(sorted_cell, dtype=bool)
        first[:, 1:] = sorted_cell[:, 1:] != sorted_cell[:, :-1]
        take = np.zeros_like(self.energy)
        np.put_along_axis(take, order, first.astype(np.float32), axis=1)
        flat_res = self.resource.reshape(self.W, -1)
        amount = np.take_along_axis(flat_res, cell.astype(np.intp), axis=1) * take
        self.energy += amount * 10.0
        np.put_along_axis(
            flat_res,
            cell.astype(np.intp),
            np.take_along_axis(flat_res, cell.astype(np.intp), axis=1) - amount,
            axis=1,
        )

    def phase_metabolism(self) -> None:
        self.energy -= 0.5 + self.genome[:, :, 6] * 0.5
        self.age += 1

    def phase_vitals(self, rng: np.random.Generator) -> None:
        """Death, then birth into freed slots. Draws are full-shape by design.

        The RNG is drawn at [W, N] and masked afterwards, never drawn per living
        agent — stream position must not depend on population, or forks diverge
        from their parents with no visible symptom.
        """
        died = self.alive & (self.energy <= 0.0)
        self.alive &= ~died

        mutation = rng.standard_normal((self.W, self.N, GENOME_SIZE), dtype=np.float32)
        fertile = self.alive & (self.energy > self.genome[:, :, 4] * 100.0)
        free = ~self.alive
        n_new = np.minimum(fertile.sum(axis=1), free.sum(axis=1))
        self.genome += mutation * 0.01 * fertile[:, :, None]
        self.energy -= 20.0 * fertile
        # Slot allocation: lowest free index per world, deterministic by construction
        for w in range(self.W):
            k = int(n_new[w])
            if k:
                slots = np.flatnonzero(free[w])[:k]
                self.alive[w, slots] = True
                self.energy[w, slots] = 20.0
                self.age[w, slots] = 0

    def phase_emit(self) -> None:
        """Sampled-tier Chronicle append: a strided copy into a fixed buffer.

        Sampling is positional, never an RNG draw — see D-047 and the
        log-tier invariance test.
        """
        n = self.event_buf.shape[0]
        flat_e = self.energy.reshape(-1)[:n]
        self.event_buf[:, 4] = flat_e
        self.event_buf[:, 1] = self.x.reshape(-1)[:n]
        self.event_buf[:, 2] = self.y.reshape(-1)[:n]


def run_scale(
    name: str, cfg: dict[str, int], ticks: int, warmup: int, seed: int = 0
) -> dict:
    world = SyntheticWorld(cfg["worlds"], cfg["agents"], cfg["grid"], seed)
    rng = np.random.default_rng(seed + 1)

    for _ in range(warmup):
        world.phase_world()
        world.phase_observe()
        a = world.phase_decide()
        world.phase_resolve_move(a)
        world.phase_resolve_gather()
        world.phase_metabolism()
        world.phase_vitals(rng)
        world.phase_emit()

    t = PhaseTimings()
    wall_start = time.perf_counter()
    for _ in range(ticks):
        s = time.perf_counter(); world.phase_world(); t.world += time.perf_counter() - s
        s = time.perf_counter(); world.phase_observe(); t.observe += time.perf_counter() - s
        s = time.perf_counter(); a = world.phase_decide(); t.decide += time.perf_counter() - s
        s = time.perf_counter(); world.phase_resolve_move(a); t.resolve_move += time.perf_counter() - s
        s = time.perf_counter(); world.phase_resolve_gather(); t.resolve_gather += time.perf_counter() - s
        s = time.perf_counter(); world.phase_metabolism(); t.metabolism += time.perf_counter() - s
        s = time.perf_counter(); world.phase_vitals(rng); t.vitals += time.perf_counter() - s
        s = time.perf_counter(); world.phase_emit(); t.emit += time.perf_counter() - s
    wall = time.perf_counter() - wall_start

    per_tick = {k: round(v * 1000.0 / ticks, 4) for k, v in asdict(t).items()}
    ms_tick = wall * 1000.0 / ticks

    # A world-year is 12 ticks at 1 tick/month (docs/00-feasibility.md).
    world_years_per_s = (cfg["worlds"] * 1000.0 / ms_tick) / 12.0

    return {
        "scale": name,
        "config": cfg,
        "ticks_measured": ticks,
        "ms_per_tick": round(ms_tick, 3),
        "ms_per_tick_by_phase": per_tick,
        "state_mb": round(world.bytes_resident() / 2**20, 1),
        "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20, 1),
        "world_years_per_sec": round(world_years_per_s, 1),
        "projected_100k_ticks_min": round(ms_tick * 100_000 / 60_000.0, 1),
    }


def run_throttle(cfg: dict[str, int], seconds: float, seed: int = 0) -> dict:
    """Sustained load on a fanless M1 throttles after 10-15 minutes.

    Compare the first and last window: the ratio is the throttle factor that
    every long-run projection has to be multiplied by.
    """
    world = SyntheticWorld(cfg["worlds"], cfg["agents"], cfg["grid"], seed)
    rng = np.random.default_rng(seed + 1)
    windows: list[float] = []
    start = time.perf_counter()
    while time.perf_counter() - start < seconds:
        w0, n = time.perf_counter(), 0
        while time.perf_counter() - w0 < 10.0:
            world.phase_world()
            world.phase_observe()
            a = world.phase_decide()
            world.phase_resolve_move(a)
            world.phase_resolve_gather()
            world.phase_metabolism()
            world.phase_vitals(rng)
            world.phase_emit()
            n += 1
        windows.append((time.perf_counter() - w0) * 1000.0 / n)

    head = float(np.mean(windows[:3])) if len(windows) >= 3 else windows[0]
    tail = float(np.mean(windows[-3:])) if len(windows) >= 3 else windows[-1]
    return {
        "duration_s": round(seconds, 1),
        "windows_ms_per_tick": [round(w, 3) for w in windows],
        "first_ms_per_tick": round(head, 3),
        "last_ms_per_tick": round(tail, 3),
        "throttle_factor": round(tail / head, 3),
    }


def machine_info() -> dict:
    def sysctl(key: str) -> str:
        try:
            return subprocess.run(
                ["sysctl", "-n", key], capture_output=True, text=True, timeout=5
            ).stdout.strip()
        except Exception:
            return "unknown"

    blas = "unknown"
    try:
        blas = np.show_config("dicts")["Build Dependencies"]["blas"]["name"]
    except Exception:
        pass

    return {
        "cpu": sysctl("machdep.cpu.brand_string"),
        "arch": platform.machine(),
        "memory_gb": round(int(sysctl("hw.memsize") or 0) / 2**30, 1),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "blas": blas,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scales", default="default", help="all | small | default | large")
    p.add_argument("--ticks", type=int, default=300, help="measured ticks per scale")
    p.add_argument("--warmup", type=int, default=30)
    p.add_argument(
        "--throttle-seconds",
        type=float,
        default=0.0,
        help="sustained-load run at the default scale; use 900 for the real number",
    )
    p.add_argument("--out", default=None)
    args = p.parse_args()

    names = list(SCALES) if args.scales == "all" else args.scales.split(",")
    info = machine_info()
    print(f"{info['cpu']} · {info['memory_gb']} GB · numpy {info['numpy']} ({info['blas']})\n")

    results = []
    for name in names:
        print(f"  {name:8s} ...", end="", flush=True)
        r = run_scale(name, SCALES[name], args.ticks, args.warmup)
        results.append(r)
        print(
            f"  {r['ms_per_tick']:7.2f} ms/tick"
            f"   {r['projected_100k_ticks_min']:6.1f} min per 100k"
            f"   {r['state_mb']:6.1f} MB state"
        )

    throttle = None
    if args.throttle_seconds > 0:
        print(f"\n  sustained load for {args.throttle_seconds:.0f}s ...", flush=True)
        throttle = run_throttle(SCALES["default"], args.throttle_seconds)
        print(
            f"  {throttle['first_ms_per_tick']:.2f} -> {throttle['last_ms_per_tick']:.2f}"
            f" ms/tick  (x{throttle['throttle_factor']:.2f})"
        )

    print("\n  phase breakdown, ms/tick")
    phases = list(asdict(PhaseTimings()))
    print(f"    {'phase':16s}" + "".join(f"{r['scale']:>12s}" for r in results))
    for ph in phases:
        row = "".join(f"{r['ms_per_tick_by_phase'][ph]:12.3f}" for r in results)
        print(f"    {ph:16s}{row}")

    payload = {
        "machine": info,
        "target": "synthetic",
        "scales": results,
        "throttle": throttle,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else RESULTS_DIR / "bench_tick_synthetic.json"
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"\n  wrote {out}")


if __name__ == "__main__":
    main()
