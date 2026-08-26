"""The Historian's containment — schemas/narrative.md, 10-roadmap.md § A3.

A3 is the only stage that ships no detector, because its output is never evidence.
Its ship criteria are therefore about containment, and these tests are those
criteria: the Historian writes only under `narrative/`, never opens a checkpoint,
never touches the simulation, and cannot publish a sentence that is not traceable
to an aggregate row.

**Nothing here asserts anything about the text.** Prose is the one artifact in this
project that is not a pure function of `(config, seed)`, and a test that pinned the
model's wording would be pinning the wrong thing. Every test runs against
`ReplayClient`, so the gate needs no API key, no network, and no `google-genai`
install.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from core.config import resolve
from digest import build as digest_builder
from digest import schema as D
from forge.run import run
from historian import build as historian
from historian import facts, verify
from historian.client import ReplayClient

from conftest import TINY


def _canned(sentences, title="An era"):
    return {"title": title, "sentences": sentences}


@pytest.fixture(scope="module")
def narrated_run(tmp_path_factory) -> Path:
    """One small run, digested, ready to narrate.

    Deliberately tiny. Containment is a property of the machinery, not of scale,
    and the same conftest convention applies here as everywhere else in the gate.
    """
    raw = {**TINY, "run": {**TINY["run"], "aggregate_every": 5, "checkpoint_every": 50}}
    cfg = resolve(raw, source="tests/test_historian.py")
    root = tmp_path_factory.mktemp("corpus")
    meta = run(cfg, seed=11, out_root=root, progress=False)
    run_dir = root / "runs" / meta["run_id"]
    (run_dir / "digest.json").write_text(
        D.canonical_json(digest_builder.build(run_dir))
    )
    return run_dir


def _hash_tree(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.blake2b(p.read_bytes(), digest_size=16).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


# --- containment -------------------------------------------------------------


def test_writes_only_under_narrative(narrated_run, tmp_path):
    """Ship criterion: `narrative/`, never `metrics/`, and the run untouched.

    Also the fourth criterion — *a run with the Historian attached produces a
    byte-identical Chronicle to one without*. The Historian is never attached; it
    is a command over a finished directory. This is what makes that true rather
    than merely intended.
    """
    # A private copy, so the assertion is about the Historian rather than about
    # which other test in this module happened to run first.
    work = tmp_path / "run"
    shutil.copytree(narrated_run, work)

    before = _hash_tree(work)
    meta_before = json.loads((work / "meta.json").read_text())

    client = ReplayClient([_canned([]) for _ in range(200)])
    historian.build(work, client, n_worlds=2, n_eras=3, progress=False)

    after = _hash_tree(work)
    added = set(after) - set(before)
    changed = {k for k in before if after.get(k) != before[k]}

    assert changed == set(), f"the Historian modified existing files: {sorted(changed)}"
    assert added, "the Historian wrote nothing at all"
    assert all(p.startswith("narrative/") for p in added), sorted(added)
    assert not any(p.startswith("metrics/") for p in added)

    meta_after = json.loads((work / "meta.json").read_text())
    assert meta_after["chronicle_digest"] == meta_before["chronicle_digest"]
    assert meta_after["final_state_hash"] == meta_before["final_state_hash"]


def test_runs_without_checkpoints(narrated_run, tmp_path):
    """Ship criterion: the digest and aggregate tier only — never a checkpoint.

    Moving `checkpoints/` away is a blunter check than reading imports, and it
    catches the case imports miss: a path opened through the digest builder or a
    glob rather than through `chronicle.checkpoint`.
    """
    checkpoints = narrated_run / "checkpoints"
    parked = tmp_path / "checkpoints_parked"
    checkpoints.rename(parked)
    try:
        data = facts.load(narrated_run)
        brief = facts.era_brief(data, int(data.world_ids[0]), 0, n_eras=3)
        assert brief["facts"], "the fact table must survive without checkpoints"
    finally:
        parked.rename(checkpoints)


def test_historian_imports_nothing_from_core():
    """Mirrors the CI grep. The arrow runs one way: core writes, prose reads.

    A dependency the other direction would be a path from generated narrative into
    the simulation — the one feedback loop that would make every result in the
    corpus uninterpretable.
    """
    root = Path(__file__).resolve().parent.parent / "src" / "historian"
    for path in root.rglob("*.py"):
        text = path.read_text()
        for line in text.splitlines():
            stripped = line.strip()
            assert not stripped.startswith(("import core", "from core")), \
                f"{path.name}: {stripped}"
            assert "chronicle.checkpoint" not in stripped, f"{path.name}: {stripped}"


def test_facts_are_pure(narrated_run):
    """Same run directory twice → the same brief hash.

    The cache key is built from this, so a drifting hash would silently re-bill
    every era on every run.
    """
    a = facts.load(narrated_run)
    b = facts.load(narrated_run)
    world = int(a.world_ids[0])
    assert (facts.brief_hash(facts.era_brief(a, world, 0))
            == facts.brief_hash(facts.era_brief(b, world, 0)))
    assert (facts.brief_hash(facts.preface_brief(a))
            == facts.brief_hash(facts.preface_brief(b)))


def test_eras_partition_the_run_exactly():
    """Fixed windows, computed here and never chosen by the model (D-069).

    Equal windows are the point: two worlds' fourth eras cover the same ticks, so
    "these two diverged" stays a statement about the worlds rather than about
    where an LLM decided a chapter began.
    """
    for n_frames in (7, 100, 2000):
        for n_eras in (1, 3, 10):
            bounds = facts.era_bounds(n_frames, n_eras)
            assert bounds[0][0] == 0
            assert bounds[-1][1] == n_frames
            for (_, end), (start, _) in zip(bounds, bounds[1:]):
                assert end == start, "eras must tile without gaps or overlap"


def test_narrative_is_labelled_generated(narrated_run, tmp_path):
    """Every `.md` opens by naming itself as generated.

    In the file, not only in the viewer: a markdown file gets pasted into a chat
    or an issue, and the label has to travel with the bytes.
    """
    client = ReplayClient([
        _canned([{"text": "The population held steady.", "cites": ["f00"]}])
        for _ in range(200)
    ])
    out = tmp_path / "narrative"
    historian.build(narrated_run, client, n_worlds=1, n_eras=2,
                    out_dir=out, progress=False)

    written = list(out.glob("*.md"))
    assert written
    for path in written:
        assert "Generated narrative — not evidence." in path.read_text()


def test_cache_prevents_a_second_call(narrated_run, tmp_path):
    """A completed era is never re-billed (docs/11-engineering.md § LLM usage)."""
    canned = [_canned([{"text": "Nothing changed.", "cites": ["f00"]}])
              for _ in range(200)]

    out = tmp_path / "narrative"
    first = ReplayClient(list(canned))
    historian.build(narrated_run, first, n_worlds=1, n_eras=2,
                    out_dir=out, progress=False)
    assert first.calls, "the first pass must actually call the model"

    second = ReplayClient([])   # zero responses: any call at all raises
    historian.build(narrated_run, second, n_worlds=1, n_eras=2,
                    out_dir=out, progress=False)
    assert second.calls == []


def test_cache_survives_a_model_change(narrated_run, tmp_path):
    """The cache is keyed on what was asked, not on who answered.

    This is not a micro-optimization. Free-tier quota is per-model and capped per
    day, so a long run legitimately continues on a different model — and a
    model-keyed cache answers that by re-requesting every era it already had,
    which is the one thing the cache exists to prevent. Found the hard way, with
    twenty briefs already paid for.
    """
    out = tmp_path / "narrative"
    first = ReplayClient([_canned([{"text": "It held.", "cites": ["f00"]}])
                          for _ in range(50)])
    first.name = "model-a"
    historian.build(narrated_run, first, n_worlds=1, n_eras=2,
                    out_dir=out, progress=False)
    assert first.calls

    later = ReplayClient([])          # a different model, no responses available
    later.name = "model-b"
    historian.build(narrated_run, later, n_worlds=1, n_eras=2,
                    out_dir=out, progress=False)
    assert later.calls == [], "a model change must not re-bill finished eras"


# --- the five checks ---------------------------------------------------------


def _brief(*facts_):
    return {"facts": list(facts_)}


POP = {"id": "f01", "kind": "series_change", "series": "population",
       "values": {"start": 812.0, "end": 389.0, "delta": -423.0, "delta_pct": -52.1},
       "source": "aggregate.parquet world=3 tick 12000..15000"}

SILENT_MARK = {"id": "f02", "kind": "marker", "detector": "collapse", "tick": 12840,
               "values": {"depth_pct": 54.0, "tick": 12840.0, "year": 1070.0},
               "detector_verdict": "silent", "source": "lens.collapse"}

FIRED_MARK = {**SILENT_MARK, "id": "f03", "detector_verdict": "fired"}


def test_uncited_sentence_rejected():
    ok, bad = verify.verify([{"text": "The world grew.", "cites": []}], _brief(POP))
    assert not ok and "uncited" in bad[0].reasons[0]


def test_unknown_fact_id_rejected():
    """The failure that looks most like rigor.

    An invented id produces prose formatted as cited work, and a reader who does
    not open the sidecar cannot tell it from the real thing.
    """
    ok, bad = verify.verify([{"text": "The world grew.", "cites": ["f99"]}], _brief(POP))
    assert not ok and "unknown fact id: f99" in bad[0].reasons


def test_invented_number_rejected():
    ok, bad = verify.verify(
        [{"text": "Population fell to 12.", "cites": ["f01"]}], _brief(POP))
    assert not ok and "ungrounded number: 12" in bad[0].reasons


def test_sourced_numbers_accepted():
    """Both the stored precision and a rounder form of it must pass.

    A gate that rejected "fell 52%" against a stored -52.1 would push the model
    toward false precision — writing 52.1% everywhere — which reads as more
    certainty than a quantized series has.
    """
    ok, bad = verify.verify([
        {"text": "Population fell from 812 to 389, a drop of 423.", "cites": ["f01"]},
        {"text": "That is 52% of the era's opening count.", "cites": ["f01"]},
        {"text": "The population roughly halved.", "cites": ["f01"]},
    ], _brief(POP))
    assert not bad, [r.reasons for r in bad]
    assert len(ok) == 3


def test_banned_phenomenon_rejected():
    """D-002 pointed at the component whose job is to sound like history."""
    ok, bad = verify.verify(
        [{"text": "The war of year 1070 emptied the cities.", "cites": ["f02"]}],
        _brief(POP, SILENT_MARK))
    assert not ok
    assert any("phenomenon not in this world" in r for r in bad[0].reasons)


def test_causal_connective_rejected():
    """The Historian sequences. It does not explain (D-064)."""
    ok, bad = verify.verify(
        [{"text": "Population fell because the resource thinned.", "cites": ["f01"]}],
        _brief(POP))
    assert not ok and any("causal claim: because" in r for r in bad[0].reasons)


def test_temporal_connective_accepted():
    """*After* is allowed; *because* is not. The line has to be usable."""
    ok, bad = verify.verify(
        [{"text": "After the drawdown, the population settled.", "cites": ["f02"]}],
        _brief(POP, SILENT_MARK))
    assert not bad, [r.reasons for r in bad]
    assert len(ok) == 1


def test_silent_marker_not_narrated_as_significant():
    """A mark records that something happened; only the effect size says whether
    it happened more often than chance (D-063)."""
    text = "A remarkable drawdown of 54% struck in year 1070."
    ok, bad = verify.verify([{"text": text, "cites": ["f02"]}], _brief(POP, SILENT_MARK))
    assert not ok
    assert any("significance language on a silent detector" in r for r in bad[0].reasons)

    ok, bad = verify.verify([{"text": text, "cites": ["f03"]}], _brief(POP, FIRED_MARK))
    assert not bad, [r.reasons for r in bad]


def test_title_gets_the_lexicons_but_not_the_cites():
    assert verify.title_reasons("The long decline") == []
    assert verify.title_reasons("The War Years")
    assert verify.title_reasons("Why the herds thinned")


def test_rejections_are_reported_not_dropped(narrated_run):
    """A narrative that hid its failures would report perfect grounding."""
    bad_sentence = [{"text": "The empire fell.", "cites": ["f00"]}]
    client = ReplayClient([_canned(bad_sentence) for _ in range(200)])
    data = facts.load(narrated_run)
    brief = facts.era_brief(data, int(data.world_ids[0]), 0, n_eras=3)

    out = historian.narrate(brief, client)
    assert out["accepted"] == 0
    assert out["generated"] == 2, "one first pass plus one repair round"
    assert len(out["rejected"]) == 2
    assert "empire" in out["rejected"][0]["reason"]


def test_marker_facts_carry_the_detector_verdict(narrated_run):
    """The verdict travels with the marks, or the verifier has nothing to read."""
    data = facts.load(narrated_run)
    seen = 0
    for world in map(int, data.world_ids):
        for era in range(3):
            for f in facts.era_brief(data, world, era, n_eras=3)["facts"]:
                if f["kind"] == "marker":
                    assert f["detector_verdict"] in ("fired", "silent")
                    seen += 1
    # Not asserting markers exist: a tiny run may have none, and inventing one to
    # make a test pass is exactly the tuning trap the suite exists to prevent.
    assert seen >= 0


def test_gene_labels_match_the_core():
    """The trait names are copied, so this is what stops the copy drifting.

    `src/historian/` imports nothing from `src/core/` — the same convention
    `src/lens/` and `src/digest/` follow — so the S0 genome's names are mirrored
    by hand. A duplicate nobody checks becomes wrong; this reads the core's own
    table and fails when it does.
    """
    import re

    src = (Path(__file__).resolve().parent.parent
           / "src" / "core" / "policy" / "s0_reactive.py").read_text()
    table = dict(re.findall(r"^\s{4}(\d)\s{2}(\w+)\s{2,}", src, re.M))
    assert table, "the S0 genome table is no longer parseable from its docstring"
    assert len(table) == len(facts.GENE_LABELS)
    for i, name in enumerate(facts.GENE_LABELS):
        assert table[str(i)] == name, f"gene {i}: core says {table[str(i)]!r}"


def test_api_keys_reads_lists_and_siblings(monkeypatch, tmp_path):
    """Several keys, however they were written down, with duplicates dropped.

    A key set both as a list entry and as a numbered sibling would otherwise
    appear twice in the rotation and halve it — and the symptom would be a run
    that gives up at half the quota it was supposed to have.
    """
    from historian import client as C

    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        for name in (var, *(f"{var}_{i}" for i in range(1, C.MAX_KEYS + 1))):
            monkeypatch.delenv(name, raising=False)

    monkeypatch.chdir(tmp_path)          # so no real .env is picked up
    monkeypatch.setenv("GEMINI_API_KEY", "a, b")
    monkeypatch.setenv("GEMINI_API_KEY_2", "c")
    monkeypatch.setenv("GEMINI_API_KEY_3", "a")

    assert C.api_keys() == ["a", "b", "c"]
    assert C.api_key() == "a"


def test_rate_limit_is_recognised_by_message_not_class():
    """The SDK has already renamed its error types once this session.

    Matching on the class would make the retry silently stop working after an
    upgrade, and a rate limit that no longer retries looks exactly like the API
    being down.
    """
    from historian import client as C

    assert C._retry_after(RuntimeError("Error code: 429 ... retry in 52.9s")) == 54.9
    assert C._retry_after(RuntimeError("quota exceeded")) == C.RETRY_FALLBACK_S
    assert C._retry_after(RuntimeError("connection reset")) is None


def test_a_dead_key_is_retired_not_retried():
    """One misconfigured key out of five must not end the run.

    A 403 — a project never enabled, or denied access — fails identically
    forever, so treating it as a rate limit would burn the entire backoff budget
    discovering that. Found with a real key whose project had been denied.
    """
    from historian import client as C

    assert C._is_dead_key(RuntimeError(
        "Error code: 403 - {'error': {'code': 'permission_denied'}}"))
    assert C._is_dead_key(RuntimeError("API key not valid"))
    assert not C._is_dead_key(RuntimeError("Error code: 429 - quota exceeded"))
    assert not C._is_dead_key(RuntimeError("connection reset"))

    # A bare substring match retires working keys. Both of these are rate limits
    # that happen to contain the digits of an auth status, and the first is a
    # real message this run produced.
    assert not C._is_dead_key(RuntimeError(
        "Error code: 429 - quota exceeded. Please retry in 52.403s"))
    assert not C._is_dead_key(RuntimeError("429 - request id 4031a9f2"))


def test_causal_words_do_not_over_trigger():
    """A gate with false positives teaches the writer to avoid ordinary English.

    Found in the committed run: "the agents produced 0 offspring" was deleted for
    the word `produced`. Bare `produced` is a count; `produced by` is a claim
    about mechanism, and only the second is a causal claim.
    """
    ok, bad = verify.verify([
        {"text": "The agents produced 812 offspring.", "cites": ["f01"]},
        {"text": "The era results are recorded at 389.", "cites": ["f01"]},
    ], _brief(POP))
    assert not bad, [r.reasons for r in bad]
    assert len(ok) == 2

    ok, bad = verify.verify([
        {"text": "The decline was produced by 423 fewer births.", "cites": ["f01"]},
        {"text": "The fall to 389 resulted in a thinner population.", "cites": ["f01"]},
    ], _brief(POP))
    assert len(ok) == 0 and len(bad) == 2
    assert "produced by" in bad[0].reasons[0]
    assert "resulted in" in bad[1].reasons[0]


def test_causal_phrases_match_on_word_boundaries():
    """`settled to` is not `led to`.

    From the committed run: "births settled to 38" was deleted for a causal claim
    it does not make, because the phrase test was a plain substring search. A
    rejection a writer cannot predict is worse than no rejection at all.
    """
    ok, bad = verify.verify([
        {"text": "Births settled to 389 by the close.", "cites": ["f01"]},
        {"text": "The count dwindled to 389.", "cites": ["f01"]},
    ], _brief(POP))
    assert not bad, [r.reasons for r in bad]
    assert len(ok) == 2
