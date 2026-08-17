"""Config loading, resolution, hashing, and gate enforcement.

A run is a pure function of `(config, seed)`, so the config has to have exactly one
canonical form — otherwise two runs that differ only in YAML key order produce
different `run_id`s and the corpus index fills with phantom duplicates.

This module also enforces the depth gates from docs/04-intelligence.md. A config
that enables a primitive past what its intelligence stage can use **fails at load**
rather than running badly (D-022). The distinction matters: a world with rich
commitment structure and agents too simple to model each other does not produce
weak institutions, it produces noise that looks like a result.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = "0.1.0"

# Maximum depth level per primitive, by intelligence stage. Cumulative: a stage
# inherits everything the stage below it allows. Absent means the primitive may
# not be enabled at all at that stage.
#
# Transcribed from docs/04-intelligence.md, "Depth gates, not just breadth gates".
_GATE_STEPS: dict[str, dict[str, int]] = {
    "S0": {"p1": 1, "p2": 0, "p10": 0},
    "S1": {},
    "S2": {},
    "S3": {"p2": 1, "p3": 2, "p9": 2},
    "S4": {"p1": 2, "p5": 1, "p8": 1, "p11": 2},
    "S5": {"p2": 2, "p4": 2, "p5": 2, "p6": 2, "p7": 2, "p8": 2},
    "S6": {},
    "S7": {},
}

STAGES: tuple[str, ...] = tuple(_GATE_STEPS)


def _build_gates() -> dict[str, dict[str, int]]:
    gates: dict[str, dict[str, int]] = {}
    acc: dict[str, int] = {}
    for stage, step in _GATE_STEPS.items():
        acc = {**acc, **step}
        gates[stage] = dict(acc)
    return gates


GATES = _build_gates()

DEFAULTS: dict[str, Any] = {
    "world": {"grid": 96, "patchiness": 0.5, "regrowth": 0.02, "seed_rain": 0.002,
              "resource_capacity": 1.0},
    "primitives": {"p1": {"level": 0}, "p10": {"level": 0}},
    "intelligence": {"stage": "S0", "genome_size": 8, "view_radius": 2,
                     "sated_gradient_factor": 0.25},
    "population": {"initial": 200, "capacity": 1000, "mutation_rate": 0.02,
                   "mutation_scale": 0.05, "birth_cap": 64},
    "agent": {"metabolism": 0.5, "max_age": 400, "birth_energy": 20.0,
              "gather_efficiency": 10.0, "start_energy": 50.0},
    "run": {"worlds": 32, "ticks": 50_000, "checkpoint_every": 2000,
            "log_tier": "sampled", "sample_rate": 64, "shard_ticks": 5000},
}


class ConfigError(ValueError):
    """Raised at load time. Never caught by the runner — a bad config stops the run."""


@dataclass(frozen=True, slots=True)
class Config:
    data: dict[str, Any]
    config_hash: str
    source: str = "<inline>"

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def get(self, path: str, default: Any = None) -> Any:
        """Dotted lookup: `cfg.get("run.ticks")`."""
        node: Any = self.data
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    @property
    def stage(self) -> str:
        return self.data["intelligence"]["stage"]

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.data, sort_keys=True, default_flow_style=False)


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        out[k] = _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def canonical_json(data: dict) -> str:
    """The one true serialization. Sorted keys, no whitespace slack, no floats
    rendered differently on different platforms."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def compute_hash(data: dict) -> str:
    return hashlib.blake2b(canonical_json(data).encode(), digest_size=16).hexdigest()


def check_gates(data: dict) -> None:
    """Raise if any primitive is enabled past what the intelligence stage allows."""
    stage = data["intelligence"]["stage"]
    if stage not in GATES:
        raise ConfigError(f"unknown intelligence stage {stage!r}; expected one of {list(GATES)}")

    allowed = GATES[stage]
    for prim, spec in sorted(data.get("primitives", {}).items()):
        level = int(spec.get("level", 0))
        if prim not in allowed:
            raise ConfigError(
                f"primitive {prim.upper()} is not available at intelligence stage {stage}. "
                f"Available here: {', '.join(p.upper() for p in sorted(allowed))}. "
                f"See docs/04-intelligence.md for the gate table."
            )
        if level > allowed[prim]:
            raise ConfigError(
                f"{prim.upper()} is configured at L{level} but stage {stage} allows at most "
                f"L{allowed[prim]}. Richness the policy cannot use is not richness; "
                f"raise the intelligence stage or lower the depth (D-022)."
            )


def resolve(raw: dict[str, Any], *, source: str = "<inline>") -> Config:
    """Merge over defaults, validate, hash. The only way to build a Config."""
    data = _deep_merge(DEFAULTS, raw or {})
    data["schema_version"] = SCHEMA_VERSION

    check_gates(data)

    run, pop = data["run"], data["population"]
    if pop["initial"] > pop["capacity"]:
        raise ConfigError(
            f"population.initial ({pop['initial']}) exceeds population.capacity "
            f"({pop['capacity']}); capacity is the fixed array width, not a soft limit"
        )
    if run["log_tier"] not in ("always", "sampled", "aggregated"):
        raise ConfigError(f"unknown run.log_tier {run['log_tier']!r}")
    if run["checkpoint_every"] <= 0:
        raise ConfigError("run.checkpoint_every must be positive — forking depends on it")

    return Config(data=data, config_hash=compute_hash(data), source=source)


def load(path: str | Path) -> Config:
    path = Path(path)
    raw = yaml.safe_load(path.read_text()) or {}
    return resolve(raw, source=str(path))


def run_id(config_hash: str, seed: int, code_version: str) -> str:
    """docs/06-data-model.md: run_id = hash(config_hash, seed, code_version)."""
    h = hashlib.blake2b(digest_size=12)
    h.update(f"{config_hash}|{seed}|{code_version}".encode())
    return h.hexdigest()
