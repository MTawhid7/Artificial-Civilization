"""S1 — the neural policy, its lineages, and the ways they break silently.

Every test here exists because the corresponding failure produces plausible
history rather than a crash. The determinism tests in `test_determinism.py`
cover S0's version of the same hazards; these cover what B0 added: a batched
matmul whose grouping depends on state, a weight bank that has to survive a
checkpoint, and a birth-time draw that must not notice how many agents are
alive.
"""

from __future__ import annotations

import numpy as np
import pytest

from chronicle import checkpoint
from core.config import ConfigError, resolve
from core.pending import Accumulators, PendingQueue
from core.policy import s1_neural as s1
from core.rng import RngStreams
from core.tick import TickContext, step
from forge.run import init_world, run

from conftest import TINY, TINY_S1


def _fresh(cfg, seed=7):
    rng = RngStreams(seed)
    world = init_world(cfg, rng)
    return world, TickContext.build(cfg, world), rng, PendingQueue.empty(), Accumulators.empty()


def _advance(state, n, chronicle=None):
    world, ctx, rng, pending, acc = state
    for _ in range(n):
        step(world, ctx, rng, pending, acc, chronicle)
    return world


# --- the grouped forward pass -------------------------------------------------


def test_forward_pass_is_batch_invariant():
    """A row's logits must not depend on how many siblings share its lineage.

    The S1 forward pass groups agents by (world, lineage) and runs one matmul
    per group, so a group's *size* is a function of world state. If BLAS blocked
    its reduction differently at different M, an agent's action would depend on
    the population — the tick would stop being a pure function of (config, seed)
    with no symptom beyond histories quietly failing to replay.

    This is the same hazard `s0_reactive.sector_masks` documents, where a
    matmul's platform-chosen summation order produced a real cross-machine
    mismatch. Measured clean on darwin-arm64 / numpy 2.5.2; CI is what checks
    linux-x86_64 and OpenBLAS.
    """
    rng = np.random.default_rng(0)
    n_in, hidden, n = 36, 48, 20_000
    x = rng.standard_normal((n, n_in), dtype=np.float32)
    w = rng.standard_normal((n_in, hidden), dtype=np.float32) * np.float32(0.1)
    b = rng.standard_normal(hidden, dtype=np.float32)

    full = np.tanh(np.matmul(x, w) + b)

    for size in (1, 2, 7, 137, 1892, n - 1):
        part = np.tanh(np.matmul(x[:size], w) + b)
        assert np.array_equal(part, full[:size]), f"batch of {size} differs from the full batch"

    # Scattered rows, which is what grouping by lineage actually produces.
    idx = np.sort(rng.choice(n, size=3_137, replace=False))
    gathered = np.tanh(np.matmul(x[idx], w) + b)
    assert np.array_equal(gathered, full[idx])


# --- determinism at S1 --------------------------------------------------------


def test_s1_determinism_same_seed(tiny_s1_config):
    a = _advance(_fresh(tiny_s1_config), 400)
    b = _advance(_fresh(tiny_s1_config), 400)
    assert a.state_hash() == b.state_hash()


def test_s1_noop_fork(tiny_s1_config, tmp_path):
    """I3 at S1: the fork carries weight banks and lineage ids, or it is not a fork.

    A checkpoint that dropped `w1` would replay with a bank of zeros — every
    agent picking uniformly — and the divergence would look like a policy that
    failed to evolve rather than a checkpoint that lost the brains.
    """
    state = _fresh(tiny_s1_config)
    world, *_ = state
    _advance(state, 120)

    ckpt = checkpoint.save(tmp_path / "ckpt.npz", world, state[2], state[3], state[4])
    _advance(state, 80)
    parent_hash = world.state_hash()

    f_world, f_rng, f_pending, f_acc = checkpoint.load(ckpt)
    assert f_world.lineages == world.lineages
    assert f_world.hidden == world.hidden
    f_ctx = TickContext.build(tiny_s1_config, f_world)
    for _ in range(80):
        step(f_world, f_ctx, f_rng, f_pending, f_acc, None)

    assert f_world.state_hash() == parent_hash


def test_lineage_stream_advances_by_fixed_shape(tiny_s1_config):
    """Speciation must draw at a config-fixed shape, not per birth.

    D-053, and the failure with no symptom: a draw sized by how many agents were
    born makes the stream position depend on the population, so a fork diverges
    from its parent as soon as their populations differ by one. Two runs with
    deliberately different populations must leave the `lineage` stream in the
    same place after the same number of ticks.
    """
    # The same seed, so the streams start in the same place, and a config change
    # that moves the population without touching any draw shape: `birth_cap`,
    # `n_inputs`, `hidden` and `lineages` are all identical between the two.
    # Comparing across *seeds* would prove nothing — different seeds are
    # different PCG64 streams, with a different increment, from the first byte.
    lean = resolve({**TINY_S1, "agent": {**TINY_S1["agent"], "metabolism": 1.4}}, source="t")

    def position_after(cfg, ticks=150):
        state = _fresh(cfg, seed=7)
        _advance(state, ticks)
        return state[2].lineage.bit_generator.state["state"], int(state[0].population.sum())

    a_state, a_pop = position_after(tiny_s1_config)
    b_state, b_pop = position_after(lean)

    assert a_pop != b_pop, "the two arms must actually differ in population, or this proves nothing"
    assert a_state == b_state, "the lineage stream moved by a population-dependent amount"


def test_speciation_off_leaves_the_mutation_stream_untouched(tiny_s1_config):
    """An S1 run with speciation off reproduces S0's mutation sequence.

    The reason `lineage` is its own stream rather than a few extra draws from
    `mutation`: when an S1 arm diverges from its S0 twin, the genome stream is
    not one of the candidate causes.
    """
    quiet = resolve({**TINY_S1, "intelligence": {**TINY_S1["intelligence"],
                                                 "speciation_rate": 0.0}}, source="t")
    s0_state = _fresh(resolve(TINY, source="t"), seed=7)
    s1_state = _fresh(quiet, seed=7)
    _advance(s0_state, 60)
    _advance(s1_state, 60)
    assert (s0_state[2].mutation.bit_generator.state["state"]
            == s1_state[2].mutation.bit_generator.state["state"])


# --- lineage bookkeeping ------------------------------------------------------


def test_founders_spread_across_lineages(tiny_s1_config):
    """Every seeded lineage starts with members, or selection has nothing to act on.

    Seeding one lineage and letting speciation fill the rest was tried and is a
    trap: a shared founding policy leaves S1's starting population far less
    varied than S0's, whose eight genes are drawn uniformly per agent.
    """
    world = init_world(tiny_s1_config, RngStreams(7))
    for w in range(world.n_worlds):
        living = world.lineage[w][world.alive[w]]
        assert len(np.unique(living)) == world.lineages
        assert world.lineage_alive[w].all()

    # Independent networks, not one network copied into every slot.
    assert not np.allclose(world.w1[0, 0], world.w1[0, 1])
    assert not np.allclose(world.w2[0, 0], world.w2[0, 1])


def test_lineage_slots_are_reaped_and_reused(tiny_s1_config):
    """A lineage with no living members frees its slot; occupancy stays truthful."""
    state = _fresh(tiny_s1_config)
    world = _advance(state, 300)

    W, L = world.n_worlds, world.lineages
    flat = np.arange(W, dtype=np.int64)[:, None] * L + world.lineage.astype(np.int64)
    counts = np.bincount(flat[world.alive], minlength=W * L).reshape(W, L)
    assert np.array_equal(world.lineage_alive, counts > 0), (
        "lineage_alive disagrees with who is actually alive"
    )


def test_no_agent_runs_an_unoccupied_lineage(tiny_s1_config):
    """Every living agent's lineage slot is marked occupied.

    The inverse of the reap test, and the one that catches a founder written
    into a slot that was never marked alive — an agent running a bank of zeros.
    """
    world = _advance(_fresh(tiny_s1_config), 300)
    for w in range(world.n_worlds):
        for k in np.unique(world.lineage[w][world.alive[w]]):
            assert world.lineage_alive[w, int(k)]


# --- the pairing that makes the B0 experiment a paired comparison -------------


def test_s0_and_s1_share_landscape_and_founders():
    """One seed gives both arms the same world and the same founding cohort.

    D-072. S1's draws come from `policy_init` and `lineage`, so the `generator`
    stream is untouched and world w of seed s is the *same landscape with the
    same founders* in both arms. Without this the B0 comparison would be two
    samples from a distribution; with it, it is paired by world.
    """
    a = init_world(resolve(TINY, source="t"), RngStreams(7))
    b = init_world(resolve(TINY_S1, source="t"), RngStreams(7))

    assert np.array_equal(a.capacity, b.capacity)
    assert np.array_equal(a.resource, b.resource)
    assert np.array_equal(a.genome, b.genome)
    assert np.array_equal(a.x, b.x) and np.array_equal(a.y, b.y)
    assert np.array_equal(a.alive, b.alive)


def test_s0_config_hash_is_unchanged_by_s1_defaults():
    """Adding S1 config surface must not renumber the corpus.

    `run_id` is a hash of `config_hash`, so merging the S1 keys into DEFAULTS
    would change the id of every run ever made — including the ones cited by
    name in the committed experiments/ results.
    """
    cfg = resolve(TINY, source="t")
    for key in ("hidden", "lineages", "speciation_rate", "cognition_cost"):
        assert key not in cfg.data["intelligence"], f"{key} leaked into an S0 config"
    assert resolve(TINY_S1, source="t").get("intelligence.hidden") == 16


# --- config gates -------------------------------------------------------------


@pytest.mark.parametrize(
    "override, match",
    [
        ({"hidden": 0}, "hidden must be positive"),
        ({"lineages": 0}, "lineages must be at least 1"),
        ({"speciation_rate": 1.5}, "speciation_rate must be in"),
    ],
)
def test_s1_config_validation(override, match):
    bad = {**TINY_S1, "intelligence": {**TINY_S1["intelligence"], **override}}
    with pytest.raises(ConfigError, match=match):
        resolve(bad)


def test_s0_ignores_s1_keys():
    """An S0 config carrying leftover S1 keys is not rejected for values nothing reads."""
    ok = {**TINY, "intelligence": {**TINY["intelligence"], "hidden": 0, "lineages": 0}}
    assert resolve(ok).stage == "S0"


# --- what a gene may be called ------------------------------------------------


def test_gene_labels_are_stage_aware():
    """S0's trait names are a claim about the world that S1 does not make.

    The failure this prevents is the only one A3's verifier structurally cannot
    catch: every check it runs is about the number — that it exists, that it is
    derivable, that it is cited — and the number is real. Only the name is
    wrong, so "gradient sensitivity rose" about an S1 run would pass the gate
    carrying a citation and still be untrue.
    """
    from historian.facts import GENE_LABELS, gene_labels

    assert gene_labels("S0") == GENE_LABELS

    s1_labels = gene_labels("S1")
    # The three the tick loop still reads outside the policy keep their names.
    assert s1_labels[4] == "reproduce_threshold"
    assert s1_labels[5] == "offspring_investment"
    assert s1_labels[6] == "metabolic_rate"
    # The five the network consumes as an embedding lose theirs.
    for i in (0, 1, 2, 3, 7):
        assert s1_labels[i] == f"gene_{i}"


def test_meta_records_the_stage(tiny_s1_config, corpus):
    """A run says which stage it ran at, so a reader never has to infer it."""
    meta = run(tiny_s1_config, seed=1, out_root=corpus, progress=False)
    assert meta["stage"] == "S1"


# --- the tick actually runs ---------------------------------------------------


def test_s1_run_writes_a_chronicle(tiny_s1_config, corpus):
    """PERCEIVE must still carry sector scores at S1, or `gradient_ascent` goes dark.

    The network never sees a sector score. They are computed anyway so the same
    detector can ask, of both stages, whether the policy ascends the gradient —
    which at S1 is the question, since nothing told it to.
    """
    meta = run(tiny_s1_config, seed=3, out_root=corpus, progress=False)
    assert meta["chronicle_rows"] > 0

    from chronicle import schema as S
    from lens.base import ChronicleReader

    with ChronicleReader(corpus / "runs" / meta["run_id"]) as reader:
        n = reader.sql(
            f"select count(*) as n from {{events}} where event_type = {S.PERCEIVE}"
        ).fetchnumpy()["n"][0]
    assert n > 0, "no PERCEIVE events at S1"


def test_cognition_cost_is_charged_per_hidden_unit(tiny_s1_config):
    """Brains cost energy when the knob is on, and cost nothing when it is off.

    Off at B0 by default: charging for cognition answers a different question
    than "can a brain be evolved at all", and E7 is where the sweep belongs.
    """
    assert tiny_s1_config.get("intelligence.cognition_cost") == 0.0

    costly = resolve({**TINY_S1, "intelligence": {**TINY_S1["intelligence"],
                                                  "cognition_cost": 0.05}}, source="t")
    free_world = _advance(_fresh(tiny_s1_config), 5)
    paid_world = _advance(_fresh(costly), 5)
    assert paid_world.energy[paid_world.alive].mean() < free_world.energy[free_world.alive].mean()
