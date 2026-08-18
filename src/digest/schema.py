"""The viz digest — the versioned contract between the simulation and the Atlas.

D-013: the Atlas reads a digest, never live state. Ten gigabytes of events cannot
reach a browser; ~2,000 downsampled frames can. `schemas/digest.md` is canonical
and this file must agree with it.

**Format is JSON with base64-encoded integer payloads, not msgpack** (D-061). The
scalar series are the bulk, they quantize to one or two bytes without losing
anything a 16-pixel-tall strip could show, and base64 decodes in a browser with no
library at all — which is what keeps the viewer a single self-contained file with
no build step and no network access.

Three properties are load-bearing, and each is a way to be silently wrong:

**Quantization ranges are run-wide, never per-world.** The entire point of the wall
is comparing worlds against each other. Normalizing each world to its own range
would rescale every strip independently and manufacture a similarity that is not
in the data.

**`population` is `u2` and therefore exact** below 65,536; every other series is
`u1` and lossy by design, to within one part in 255 of the run-wide range. The
declared `min`/`max` make the loss bounded and inspectable rather than hidden.

**`reserved` is part of the contract.** `territory`, `belief_layer`, `tech_level`
and the rest of the fields in docs/06-data-model.md have no meaning at S0. They
are named as *absent* rather than filled with plausible zeros. A subset that knows
it is a subset can be extended; one that pretends to be complete cannot.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

import numpy as np

DIGEST_VERSION = "0.1.0"

# Series carried per world per frame, and the width each is stored at. Order is
# canonical: it fixes the hash, so append rather than insert.
SERIES: tuple[tuple[str, int], ...] = (
    ("population", 16),
    ("births", 8),
    ("deaths", 8),
    ("energy_mean", 8),
    ("energy_gini", 8),
    ("resource_total", 8),
)

# Gene means move slowly, so they are stored every `GENE_STRIDE` frames. At 2,000
# frames and 8 genes this is the difference between 2.1 MB and 267 KB.
GENE_STRIDE = 8

# Raster layers, and how many worlds get them. Rasters come from checkpoints (the
# snapshot tier), so their frame rate is `run.checkpoint_every`, not the series
# frame rate — they are for the map view that arrives at C3, not for the strip.
RASTER_LAYERS: tuple[str, ...] = ("resource", "density")
RASTER_SIZE = 48
RASTER_WORLDS = 4

# Declared absent. Every one of these is specified in docs/06-data-model.md and
# has no S0 meaning: there is no territory without claims, no belief layer without
# a belief store, no tech level without recipes.
RESERVED: tuple[str, ...] = (
    "territory",
    "eff_scarcity",
    "belief_layer",
    "tech_level",
    "cooperation_rate",
    "active_contagions",
    "modulators",
    "accumulators",
    "flows",
)

_DTYPE = {8: np.uint8, 16: np.uint16}


def encode(values: np.ndarray, bits: int, *, lo: float | None = None,
           hi: float | None = None) -> dict[str, Any]:
    """Quantize an array to `bits` and base64 it, carrying its range along.

    `lo`/`hi` default to the array's own extremes — which is correct here only
    because the array passed in is the whole run, every world at once. Passing a
    single world's slice would be the per-world normalization bug.
    """
    v = np.asarray(values, dtype=np.float64)
    lo = float(v.min()) if lo is None else float(lo)
    hi = float(v.max()) if hi is None else float(hi)
    span = hi - lo
    levels = (1 << bits) - 1

    if span <= 0:
        q = np.zeros(v.shape, dtype=_DTYPE[bits])
    else:
        q = np.rint((v - lo) / span * levels).clip(0, levels).astype(_DTYPE[bits])

    return {
        "bits": bits,
        "min": lo,
        "max": hi,
        "shape": list(v.shape),
        # Little-endian is stated rather than assumed: the browser reads this with
        # a DataView and has to be told.
        "endian": "little",
        "data": base64.b64encode(np.ascontiguousarray(q.astype(_DTYPE[bits], copy=False),
                                                     dtype=_DTYPE[bits]).tobytes()).decode(),
    }


def decode(field: dict[str, Any]) -> np.ndarray:
    """Inverse of `encode`, exact to within one quantization bin."""
    bits = int(field["bits"])
    raw = np.frombuffer(base64.b64decode(field["data"]), dtype=_DTYPE[bits])
    q = raw.reshape(tuple(field["shape"])).astype(np.float64)
    lo, hi = float(field["min"]), float(field["max"])
    span = hi - lo
    if span <= 0:
        return np.full(q.shape, lo)
    return lo + q * (span / ((1 << bits) - 1))


def bin_width(field: dict[str, Any]) -> float:
    """The maximum error `decode` can carry. Used by the round-trip test."""
    span = float(field["max"]) - float(field["min"])
    return span / ((1 << int(field["bits"])) - 1) if span > 0 else 0.0


def canonical_json(digest: dict[str, Any]) -> str:
    return json.dumps(digest, sort_keys=True, separators=(",", ":"))


def digest_hash(digest: dict[str, Any]) -> str:
    """Hash of the digest with its own hash field removed.

    Used to prove the builder is a pure function of the run directory. It is
    deliberately **not** a cross-platform golden: the aggregate values it derives
    from are float32 sums that differ in the last ulp between NEON and AVX
    (D-057), and quantization absorbs that almost always but not at a bin
    boundary. Purity on one machine is the property worth testing; cross-ISA
    identity is a settled question this must not reopen.
    """
    body = {k: v for k, v in digest.items() if k != "digest_hash"}
    return hashlib.blake2b(canonical_json(body).encode(), digest_size=16).hexdigest()
