"""The determinism gate — docs/11-engineering.md.

Invariant I1 is the easiest to break and the most expensive to repair, and every
one of these tests exists because the corresponding bug is invisible without it.
A run that silently stops being reproducible does not crash; it produces plausible
history that means nothing.

The order below is roughly the order the bugs appear in practice.
"""

from __future__ import annotations

import json
import platform
from pathlib import Path

import numpy as np
import pytest

from chronicle import checkpoint
from chronicle.writer import ChronicleWriter
from core.config import ConfigError, resolve
from core.generators import world_gen
from core.pending import EFFECT_ENERGY_DELTA, EFFECT_RESOURCE_DELTA, Accumulators, PendingQueue
from core.rng import RngStreams
from core.tick import TickContext, step
from forge.run import init_world, run

from conftest import GOLDEN_DIR, TINY


def _fresh(cfg, seed=7):
    rng = RngStreams(seed)
    world = init_world(cfg, rng)
    return world, TickContext.build(cfg, world), rng, PendingQueue.empty(), Accumulators.empty()


def _advance(state, n, chronicle=None):
    world, ctx, rng, pending, acc = state
    for _ in range(n):
        step(world, ctx, rng, pending, acc, chronicle)
    return world


# --- I1: replay ---------------------------------------------------------------


def test_determinism_same_seed_same_history(tiny_config):
    """1,000 ticks twice from the same seed produce identical state."""
    a = _advance(_fresh(tiny_config), 1000)
    b = _advance(_fresh(tiny_config), 1000)
    assert a.state_hash() == b.state_hash()


def test_determinism_chronicle_digest(tiny_config, corpus):
    """Identical inputs produce an identical event log, event for event."""
    m1 = run(tiny_config, seed=3, out_root=corpus / "a", progress=False)
    m2 = run(tiny_config, seed=3, out_root=corpus / "b", progress=False)
    assert m1["chronicle_digest"] == m2["chronicle_digest"]
    assert m1["final_state_hash"] == m2["final_state_hash"]


def test_different_seeds_diverge(tiny_config):
    """The corollary: seeds must actually matter, or the corpus has N=1."""
    a = _advance(_fresh(tiny_config, seed=1), 300)
    b = _advance(_fresh(tiny_config, seed=2), 300)
    assert a.state_hash() != b.state_hash()


# --- I3: forking --------------------------------------------------------------


def test_noop_fork_reproduces_parent(tiny_config, tmp_path):
    """A fork with no intervention must reproduce its parent exactly.

    The test people skip, and the one that pays. A fork that does not reproduce
    its parent means determinism is already broken somewhere upstream, and every
    counterfactual built on it is measuring the bug rather than the intervention.
    """
    state = _fresh(tiny_config)
    world, ctx, rng, pending, acc = state
    _advance(state, 120)

    ckpt = checkpoint.save(tmp_path / "ckpt.npz", world, rng, pending, acc)
    _advance(state, 80)
    parent_hash = world.state_hash()

    f_world, f_rng, f_pending, f_acc = checkpoint.load(ckpt)
    f_ctx = TickContext.build(tiny_config, f_world)
    for _ in range(80):
        step(f_world, f_ctx, f_rng, f_pending, f_acc, None)

    assert f_world.state_hash() == parent_hash


def test_pending_fork_reproduces_parent(tiny_config, tmp_path):
    """Same, with effects scheduled across the checkpoint boundary.

    The most dangerous bug class in the project: a checkpoint that omits the
    pending queue produces forks that diverge from their parents with no visible
    symptom (docs/06-data-model.md).
    """
    state = _fresh(tiny_config)
    world, ctx, rng, pending, acc = state
    _advance(state, 60)

    # Effects landing after the checkpoint, in both directions, on both targets.
    pending.schedule(world.tick + 30, EFFECT_RESOURCE_DELTA, world=0, target_ref=17, magnitude=5.0)
    pending.schedule(world.tick + 30, EFFECT_RESOURCE_DELTA, world=0, target_ref=17, magnitude=-2.0)
    pending.schedule(world.tick + 45, EFFECT_ENERGY_DELTA, world=1,
                     target_ref=int(world.id[1][world.alive[1]][0]), magnitude=25.0)
    acc.add(threshold=10.0, on_cross_effect=EFFECT_RESOURCE_DELTA, scope_ref=3)

    ckpt = checkpoint.save(tmp_path / "ckpt.npz", world, rng, pending, acc)
    assert len(pending) == 3, "effects must still be queued at checkpoint time"

    _advance(state, 60)
    parent_hash = world.state_hash()

    f_world, f_rng, f_pending, f_acc = checkpoint.load(ckpt)
    assert len(f_pending) == 3, "checkpoint dropped the pending queue"
    assert len(f_acc) == 1, "checkpoint dropped the accumulators"

    f_ctx = TickContext.build(tiny_config, f_world)
    for _ in range(60):
        step(f_world, f_ctx, f_rng, f_pending, f_acc, None)

    assert f_world.state_hash() == parent_hash


def test_pending_order_is_insertion_not_heap(tiny_config):
    """Effects due on the same tick fire in the order they were scheduled."""
    q = PendingQueue.empty()
    for mag in (3.0, 1.0, 2.0):
        q.schedule(50, EFFECT_RESOURCE_DELTA, magnitude=mag)
    q.schedule(49, EFFECT_RESOURCE_DELTA, magnitude=9.0)

    due = q.pop_due(50)
    assert due["fire_tick"].tolist() == [49, 50, 50, 50]
    assert due["magnitude"].tolist() == [9.0, 3.0, 1.0, 2.0]
    assert len(q) == 0


# --- generators ---------------------------------------------------------------


def test_generator_repro(tiny_config):
    """Same (config, seed) produces byte-identical world structure."""
    a = world_gen.generate_resource_field(tiny_config, RngStreams(11))
    b = world_gen.generate_resource_field(tiny_config, RngStreams(11))
    c = world_gen.generate_resource_field(tiny_config, RngStreams(12))
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


def test_generator_independent_of_other_streams(tiny_config):
    """Consuming policy or mutation randomness must not move the landscape.

    Streams are spawned per purpose precisely so that adding a draw in the tick
    loop cannot silently change which worlds a seed generates.
    """
    r1 = RngStreams(11)
    baseline = world_gen.generate_resource_field(tiny_config, r1)

    r2 = RngStreams(11)
    r2.policy.random(5000)
    r2.mutation.standard_normal(5000)
    assert np.array_equal(world_gen.generate_resource_field(tiny_config, r2), baseline)


def test_rng_stream_identity_survives_new_streams():
    """Adding a stream name must not renumber the existing ones."""
    base = RngStreams(5).world.random(8)
    extended = RngStreams(5, names=("generator", "world", "policy", "mutation", "future")).world
    assert np.array_equal(extended.random(8), base)


# --- logging must not perturb the simulation ----------------------------------


def test_log_tier_invariance(tiny_config, corpus, tmp_path):
    """Two runs of one seed at different log tiers must be identical simulations.

    Not in the documented CI list, added here because the failure it catches is
    silent and total: if sampling drew from an RNG stream, how much history you
    wrote down would change what happened. Observation would alter the observed.
    """
    quiet = run(tiny_config, seed=4, out_root=corpus / "agg", progress=False,
                log_tier="aggregated")
    loud = run(tiny_config, seed=4, out_root=corpus / "always", progress=False,
               log_tier="always")

    assert quiet["final_state_hash"] == loud["final_state_hash"]
    assert quiet["chronicle_rows"] < loud["chronicle_rows"], "tiers must actually differ"


def test_sample_mask_is_stable_and_selective():
    """Sampling is a pure function of agent id: reproducible and roughly 1-in-K."""
    from chronicle.schema import sample_mask

    ids = np.arange(20_000, dtype=np.uint32)
    m1 = sample_mask(77, ids, 64)
    assert np.array_equal(m1, sample_mask(77, ids, 64))
    assert 0.008 < m1.mean() < 0.024, f"1-in-64 sampling kept {m1.mean():.4f}"


def test_sample_cohort_is_stable_across_ticks():
    """The same agents are sampled every tick, so trajectories stay whole.

    Regression test for a measured failure: keying the sample on (tick, id) gave
    ~5 isolated positions per agent across a 191-tick life, which no path-based
    detector can use. Keying on id alone follows a cohort from birth to death at
    the same row cost.
    """
    from chronicle.schema import sample_mask

    ids = np.arange(20_000, dtype=np.uint32)
    first = sample_mask(0, ids, 64)
    for tick in (1, 17, 5000, 99_999):
        assert np.array_equal(sample_mask(tick, ids, 64), first)
    assert first.sum() > 100, "cohort must be large enough to measure anything"


# --- config gates -------------------------------------------------------------


def test_gate_enforcement_rejects_deep_primitive():
    """A primitive past its intelligence gate fails at load, not at runtime."""
    bad = {**TINY, "primitives": {"p1": {"level": 2}}}
    with pytest.raises(ConfigError, match="L2 but stage S0 allows at most L1"):
        resolve(bad)


def test_gate_enforcement_rejects_ungated_primitive():
    bad = {**TINY, "primitives": {"p1": {"level": 0}, "p8": {"level": 1}}}
    with pytest.raises(ConfigError, match="P8 is not available"):
        resolve(bad)


def test_gate_allows_primitive_once_stage_rises():
    ok = {**TINY, "intelligence": {**TINY["intelligence"], "stage": "S4"},
          "primitives": {"p1": {"level": 2}, "p8": {"level": 1}}}
    assert resolve(ok).stage == "S4"


def test_config_hash_ignores_key_order():
    """Two YAML spellings of one config must be the same run, not two."""
    a = resolve({"run": {"ticks": 10, "worlds": 2}, "world": {"grid": 16}})
    b = resolve({"world": {"grid": 16}, "run": {"worlds": 2, "ticks": 10}})
    assert a.config_hash == b.config_hash


# --- cross-machine ------------------------------------------------------------


GOLDEN = GOLDEN_DIR / "tiny_s0.json"


def _platform_tag() -> str:
    return f"{platform.system().lower()}-{platform.machine().lower()}"


def _stage_hashes(tiny_config) -> dict:
    """Hashes at three points, so a divergence can be located rather than guessed.

    `world_init` is taken straight after the generators and before any tick. If it
    already differs across machines, the cause is in world generation — which is
    where `np.exp` lives — and no amount of care in the tick loop will help.
    """
    rng = RngStreams(7)
    world = init_world(tiny_config, rng)
    out = {"config_hash": tiny_config.config_hash, "world_init": world.state_hash()}

    ctx = TickContext.build(tiny_config, world)
    pending, acc = PendingQueue.empty(), Accumulators.empty()
    for _ in range(10):
        step(world, ctx, rng, pending, acc, None)
    out["tick_10"] = world.state_hash()
    for _ in range(490):
        step(world, ctx, rng, pending, acc, None)
    out["tick_500"] = world.state_hash()
    return out


def test_cross_machine(tiny_config):
    """State hashes must match the golden recorded for THIS platform.

    Determinism is guaranteed within a platform, not across instruction sets
    *(→ D-057)*. Bit-identical float across ISAs would mean giving up `np.exp`,
    and every forking, checkpointing, and replay operation this project performs
    happens on one machine.

    The golden therefore holds one entry per platform, and the test still does the
    job that matters: catching the day a code change silently alters results on the
    machine you are actually using. Cross-platform differences are reported for
    information, and the per-stage hashes say where they begin.
    """
    tag = _platform_tag()
    actual = _stage_hashes(tiny_config)

    golden = json.loads(GOLDEN.read_text()) if GOLDEN.exists() else {}
    if tag not in golden:
        golden[tag] = actual
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(golden, indent=2, sort_keys=True) + "\n")
        pytest.skip(f"recorded golden for {tag}; commit it")

    expected = golden[tag]
    assert actual["config_hash"] == expected["config_hash"], "the tiny config itself changed"
    for stage in ("world_init", "tick_10", "tick_500"):
        assert actual[stage] == expected[stage], f"{tag} diverged from its own golden at {stage}"

    # Informational: where do platforms first disagree?
    for other, ref in sorted(golden.items()):
        if other == tag or ref.get("config_hash") != actual["config_hash"]:
            continue
        first = next(
            (s for s in ("world_init", "tick_10", "tick_500") if ref.get(s) != actual[s]), None
        )
        print(f"  vs {other}: {'identical' if first is None else f'first differs at {first}'}")
