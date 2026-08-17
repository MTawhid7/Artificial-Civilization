"""World structure sampled once at init from (config, seed).

D-020: depth enters through generators, not through config surface. `patchiness`
is one knob; what it produces is a whole resource landscape whose blob count,
placement, width, and amplitude all differ per seed. Two worlds sharing a
generator setting and differing in seed have genuinely different economies, which
is exactly what a corpus of comparable histories needs.

**Generators run once, at init, and never lazily.** A resource field that
materialized on first access would make world identity depend on the order agents
happened to look at it, which breaks I1 in a way no test would obviously catch
(determinism rule 9).

Blobs are summed explicitly rather than smoothed with an FFT. An FFT would be
shorter, but its floating-point reduction order is a library-and-platform detail,
and `test_cross_machine` compares hashes across machines.
"""

from __future__ import annotations

import numpy as np

from core.config import Config
from core.rng import RngStreams

# Blob count at the extremes of `patchiness`. Low patchiness scatters many small
# deposits into something near-uniform; high patchiness concentrates everything
# into a handful of rich sites worth travelling to and fighting over.
BLOBS_UNIFORM = 60
BLOBS_PATCHY = 5

# Blob width as a fraction of grid size, at those same extremes.
WIDTH_UNIFORM = 0.16
WIDTH_PATCHY = 0.07

FLOOR = 0.02  # a nonzero background, so no world is trivially unsurvivable


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def generate_resource_field(cfg: Config, rng: RngStreams) -> np.ndarray:
    """Return the carrying-capacity field, [W, G, G], normalized to a max of 1.

    Draws come from the `generator` stream so that changing anything about the
    per-tick simulation cannot shift the landscape a seed produces.
    """
    n_worlds = int(cfg.get("run.worlds"))
    grid = int(cfg.get("world.grid"))
    patchiness = float(cfg.get("world.patchiness"))
    if not 0.0 <= patchiness <= 1.0:
        raise ValueError(f"world.patchiness must be in [0, 1], got {patchiness}")

    gen = rng.generator
    n_blobs = int(round(_lerp(BLOBS_UNIFORM, BLOBS_PATCHY, patchiness)))
    sigma = _lerp(WIDTH_UNIFORM, WIDTH_PATCHY, patchiness) * grid

    # All draws up front, at fixed shape, so the stream advances identically
    # regardless of how the loop below is written.
    cy = gen.integers(0, grid, size=(n_worlds, n_blobs)).astype(np.float32)
    cx = gen.integers(0, grid, size=(n_worlds, n_blobs)).astype(np.float32)
    amp = (0.5 + gen.random((n_worlds, n_blobs), dtype=np.float32)).astype(np.float32)

    coords = np.arange(grid, dtype=np.float32)
    field = np.zeros((n_worlds, grid, grid), dtype=np.float32)

    half = grid / 2.0
    for b in range(n_blobs):  # fixed count, fixed order — deterministic
        dy = np.abs(coords[None, :] - cy[:, b : b + 1])
        dx = np.abs(coords[None, :] - cx[:, b : b + 1])
        # Toroidal distance: the world wraps, so the far way round may be shorter.
        dy = np.minimum(dy, grid - dy)
        dx = np.minimum(dx, grid - dx)
        gy = np.exp(-0.5 * (dy / sigma) ** 2)
        gx = np.exp(-0.5 * (dx / sigma) ** 2)
        field += amp[:, b, None, None] * gy[:, :, None] * gx[:, None, :]

    peak = field.max(axis=(1, 2), keepdims=True)
    np.divide(field, np.maximum(peak, 1e-6), out=field)
    np.add(field, FLOOR, out=field)
    return np.clip(field, 0.0, 1.0 + FLOOR).astype(np.float32)


def generate_terrain(cfg: Config, rng: RngStreams) -> np.ndarray:
    """Static terrain, [G, G]. Uniform at L0 — kept so the field exists in the
    schema and in checkpoints from the first run rather than being added later."""
    grid = int(cfg.get("world.grid"))
    return np.zeros((grid, grid), dtype=np.uint8)


def describe(cfg: Config) -> dict:
    """Generator parameters recorded in meta.json, so the corpus stays analyzable
    without re-running the generator."""
    patchiness = float(cfg.get("world.patchiness"))
    grid = int(cfg.get("world.grid"))
    return {
        "n_blobs": int(round(_lerp(BLOBS_UNIFORM, BLOBS_PATCHY, patchiness))),
        "sigma_cells": round(_lerp(WIDTH_UNIFORM, WIDTH_PATCHY, patchiness) * grid, 3),
        "floor": FLOOR,
        "patchiness": patchiness,
    }
