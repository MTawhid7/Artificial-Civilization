# Viz digest schema

**Version 0.1.0.** The contract between the simulation and the Atlas. Canonical
definition lives in [docs/06-data-model.md](../docs/06-data-model.md#viz-digest);
this file records the wire format. Both move together, and both are versioned with
the code that writes them.

[D-013](../docs/DECISIONS.md#d-013): the Atlas reads a digest, never live state.
Ten gigabytes of events cannot reach a browser; ~2,000 downsampled frames can.
Producer is [`src/digest/build.py`](../src/digest/build.py), written to
`corpus/runs/<run_id>/digest.json`.

**Target: ≤ 5 MB per run.** Measured at 34 worlds × 2,000 frames: ~1.1 MB.

## Format

**JSON with base64-encoded integer payloads, not msgpack**
*(→ [D-061](../docs/DECISIONS.md#d-061))*. The scalar series are the bulk, they
quantize to one or two bytes without losing anything a 16-pixel strip could show,
and base64 decodes in a browser with no library — which is what keeps the viewer a
single self-contained file with no build step and no network access.

Every quantized field is a self-describing block:

```json
{ "bits": 8, "min": 0.0, "max": 22.7, "shape": [34, 2000],
  "endian": "little", "data": "<base64>" }
```

Decode is `min + q * (max - min) / (2^bits - 1)`, exact to within one bin.

## Top level

| Field | Meaning |
|---|---|
| `digest_version` | this schema's version — **check it before reading anything else** |
| `run_id`, `config_hash`, `code_version`, `schema_version`, `seed` | provenance; a digest that cannot be traced to a run is not evidence |
| `n_worlds`, `world_ids`, `capacity`, `grid`, `patchiness` | what a strip needs to label itself |
| `ticks_completed` | from `meta.json`, not inferred from the frames |
| `frames` | `{n, tick_start, tick_step, uniform}`; an explicit `ticks[]` appears only when `uniform` is false |
| `series` | per-world per-frame scalars — see below |
| `genes` | trait means, `[W, F/stride, G]`, subsampled in time |
| `rasters` | downsampled fields for a subset of worlds |
| `markers` | detector firings, placed in time |
| `detectors` | each detector's verdict for the whole run |
| `reserved` | fields specified in 06-data-model with no meaning yet |
| `digest_hash` | blake2b-128 of the canonical JSON with this field removed |

## `series` — what the strip draws

Each is `[n_worlds, n_frames]`, from `aggregate.parquet`.

| Name | Bits | Note |
|---|---|---|
| `population` | 16 | **exact**, range fixed to `[0, capacity]` |
| `births`, `deaths` | 8 | per aggregate window, not per tick |
| `energy_mean` | 8 | |
| `energy_gini` | 8 | inequality; the strip's default color channel |
| `resource_total` | 8 | physical stock summed over the grid |

Three properties are load-bearing, and each is a way to be silently wrong.

**Quantization ranges are run-wide, never per-world.** The entire point of the
wall is comparing worlds against each other. Normalizing each world to its own
extremes would rescale every strip independently and manufacture a similarity that
is not in the data. There is exactly one `min`/`max` per series, which is the
structural guarantee that it cannot happen.

**`population` is stored exactly.** It is the strip's bar height, and a capacity of
1,200 spread over 255 levels would visibly step. Everything else is `u1` and lossy
by design, to within one part in 255 of the run-wide range.

**`reserved` is part of the contract.** `territory`, `eff_scarcity`,
`belief_layer`, `tech_level`, `cooperation_rate`, `active_contagions`,
`modulators`, `accumulators`, `flows` — all specified in 06-data-model, none with
an S0 meaning. They are named as *absent* rather than filled with plausible zeros.
A subset that knows it is a subset can be extended; one that pretends to be
complete cannot.

## `genes`

`[n_worlds, ceil(F/stride), n_genes]` at `stride: 8`. Trait means are the
slowest-moving thing in the digest — which is why they are an evolutionary signal
at all — so storing every frame would spend 2 MB encoding the same curve at eight
times the resolution any plot can show.

## `rasters`

From **checkpoints**, not from events: checkpoints are the snapshot tier, so no
new emission path exists and the core is unchanged.

```json
{ "worlds": [0,1,2,3], "size": [32,32], "ticks": [0,1500,...],
  "layers": { "resource": {...}, "density": {...} } }
```

Each layer is `[n_ticks, n_raster_worlds, size, size]`. The raster side length is
the **largest divisor of the grid at or below 48**, so downsampling is an exact
block mean with no interpolation and no resampling filter — a deterministic
function of the checkpoint.

Only the first few worlds get rasters. They are for the map view that arrives at
C3; carrying a hundred worlds' worth would blow the budget for a view that does not
exist yet.

## `markers` and `detectors`

```json
"markers":   [{"world": 3, "tick": 18255, "detector": "collapse", "magnitude": 0.62}]
"detectors": {"collapse": {"magnitude":…, "null_mean":…, "null_std":…,
                           "effect_size":…, "threshold":…, "fired":…, "n_worlds":…}}
```

Markers come straight from the detector suite and are **never hand-authored** — the
scientific instrumentation *is* the narrative UI
*(→ [docs/09-visualization.md](../docs/09-visualization.md#the-best-reuse-in-the-design))*.
Build detectors once, get chapter markers free.

`detectors` travels with them so the verdict cannot be separated from the marks. A
marker records that something happened; only `effect_size` says whether it happened
more often than chance, and a renderer that draws the first without reading the
second is claiming significance the data has not earned.

## `digest_hash`

Blake2b-128 over the canonical JSON (`sort_keys`, no whitespace) with the hash
field removed. It proves the builder is a **pure function of the run directory**.

It is deliberately **not** a cross-platform golden. The aggregate values underneath
are float32 sums that differ in the last ulp between NEON and AVX
*(→ [D-057](../docs/DECISIONS.md#d-057))*, and quantization absorbs that almost
always but not at a bin boundary. Purity on one machine is the property worth
testing; cross-ISA identity is a settled question this must not reopen.

## Changing this schema

Bump `digest_version` and never silently redefine a field's meaning — a digest
outlives the code that wrote it, and the Atlas has to be able to refuse one it does
not understand. Moving a field from `reserved` into the body is the expected kind
of change and still requires the bump.
