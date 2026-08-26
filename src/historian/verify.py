"""The grounding gate. Offline, no model involved, and the reason A3 has criteria.

[10-roadmap.md § A3](../../docs/10-roadmap.md#a3--first-story) requires that *every
claim in generated prose is traceable to an event range or an aggregate row*. As
written that is a rule for the reader, and readers do not cross-check prose against
Parquet. This file makes it a property of the file on disk instead: a sentence that
cannot be traced never reaches one.

Five checks, all of which must pass:

1. **cited** — at least one fact id
2. **ids resolve** — every id is in this era's brief
3. **numbers ground** — every numeral in the sentence is derivable from a cited fact
4. **lexicons** — no phenomenon vocabulary, no causal connectives
5. **verdict discipline** — no significance language on a detector that came out silent

Check 2 catches the failure that looks most like rigor. A model that invents `f31`
produces prose which is *formatted* as cited work, and a reader who does not open
the sidecar cannot tell the difference.

**Check 3 was expected to do most of the work and does none of it.** Across 263
sentences in both arms of A3 — the shipped run and its unguarded control — the
numeric check has never once fired. With a fact table in context the model does
not invent statistics; it invents connective tissue. Every rejection so far has
been a lexicon failure. The check stays, because its cost is nothing and its
absence would be unprovable, but it is not what makes this work.

**Check 4 is what makes this work.** It is [D-002](../../docs/DECISIONS.md#d-002)
— *no phenomenon names* — pointed at the one component whose entire job is to
sound like history. CI greps `src/core/` for those words; this greps the prose.
Banning causation is not excessive caution either: strip the rules from the prompt
and the model writes *"this severe depletion forced a drastic biological
adaptation"* over a fact table that says only that two numbers fell in sequence.
A causal claim about a world is something the Lens makes with a null and a control
*(→ [D-064](../../docs/DECISIONS.md#d-064))*, or nobody makes. The Historian orders
events in time. *After* is allowed; *because* is not.

The lexicons are split into words that are causal alone and phrases that are
causal only in combination, and both match on word boundaries. Neither distinction
was in the first version, and both were found by running it over real prose:
`produced` deleted "the agents produced 0 offspring", and a substring search for
`led to` deleted "births settled to 38".

**Rejections are returned, not discarded.** They are written into the sidecar and
counted in the acceptance rate, because a narrative that quietly dropped its
failures would report 100% grounding by construction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field

# Numerals, with thousands separators and an optional percent sign. Bare years in
# prose ("year 1,000") come out of the same pattern.
_NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?\s*(%)?")

# Ordinal words and small counts that name structure rather than measurement:
# "the fourth era", "both halves". They are not claims about the world and there
# is nothing in the fact table for them to match.
_STRUCTURAL_WORDS = re.compile(
    r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"both|half|halves|twice|once)\b", re.I
)

# Phenomena the S0 world does not contain. It contains food, movement, birth and
# death; everything below names a structure that would have to be built out of
# primitives that do not exist yet. A word here is not "risky phrasing", it is a
# claim about a mechanism.
BANNED_PHENOMENA: tuple[str, ...] = (
    "war", "wars", "warfare", "battle", "battles", "conflict", "raid", "raids",
    "army", "armies", "soldier", "soldiers", "weapon", "weapons",
    "city", "cities", "town", "towns", "village", "villages", "settlement",
    "settlements", "capital", "border", "borders", "territory", "territories",
    "king", "queen", "ruler", "rulers", "empire", "empires", "kingdom",
    "dynasty", "tribe", "tribes", "clan", "clans", "nation", "nations",
    "government", "law", "laws", "council", "elder", "elders",
    "religion", "religious", "ritual", "rituals", "temple", "priest", "myth",
    "belief", "beliefs", "culture", "cultural", "custom", "customs",
    "trade", "traded", "trading", "market", "markets", "merchant", "wealth",
    "invention", "invented", "technology", "technological", "discovery",
    "tool", "tools", "craft", "farming", "farm", "harvest", "crop", "crops",
    "revolution", "uprising", "rebellion", "alliance", "treaty", "pledge",
    "plague", "disease", "epidemic", "famine", "drought", "flood", "winter",
    "language", "word", "words", "story", "stories", "song", "name", "named",
)

# Causation, as single words. The Historian sequences; it does not explain.
#
# Every word here is causal on its own. Words that are causal only in a phrase
# live in `BANNED_CAUSAL_PHRASES` instead — a distinction this list did not make
# at first, and the run that found it rejected "the agents produced 0 offspring"
# for the word `produced`. A gate with false positives teaches the writer to
# avoid ordinary English, which is a worse failure than the one it prevents.
BANNED_CAUSAL: tuple[str, ...] = (
    "because", "caused", "causes", "causing", "cause",
    "therefore", "thus", "consequently", "hence",
    "drove", "driven", "drives", "triggered", "triggering", "trigger",
    "forced", "forcing", "provoked", "prompted", "spurred",
    "explains", "explained", "why", "reason", "reasons",
)

# Causal only in combination. "The world produced 40 agents" is a count;
# "produced by scarcity" is a claim about mechanism.
BANNED_CAUSAL_PHRASES: tuple[str, ...] = (
    "led to", "leads to", "leading to",
    "resulted in", "results in", "resulting in", "resulting from",
    "produced by", "driven by", "caused by",
    "due to", "owing to", "as a result", "brought about", "thanks to",
    "in response to", "gave rise to", "gives rise to", "so that",
)

# Significance. Permitted only when a cited detector actually fired.
BANNED_SIGNIFICANCE: tuple[str, ...] = (
    "significant", "significantly", "unusual", "unusually", "anomalous",
    "anomaly", "exceptional", "exceptionally", "remarkable", "remarkably",
    "extraordinary", "rare", "rarely", "abnormal", "striking", "strikingly",
    "improbable", "unlikely", "chance",
)

_MATCH_EPS = 1e-6


@dataclass(slots=True)
class Sentence:
    text: str
    cites: list[str] = dc_field(default_factory=list)

    @classmethod
    def parse(cls, raw: object) -> "Sentence":
        if isinstance(raw, dict):
            cites = raw.get("cites") or []
            return cls(str(raw.get("text", "")).strip(),
                       [str(c).strip() for c in cites if str(c).strip()])
        return cls(str(raw).strip(), [])


@dataclass(slots=True)
class Rejection:
    text: str
    reasons: list[str]
    stage: str = "first"

    def to_dict(self) -> dict:
        return {"text": self.text, "reason": "; ".join(self.reasons), "stage": self.stage}


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


def _phrases(text: str) -> list[str]:
    """Multi-word causal markers, on word boundaries.

    A plain substring test is wrong here and the real run proved it: *"births
    settled to 38"* contains the letters of `led to` and was deleted for a causal
    claim it does not make. Word boundaries cost one regex and remove a whole
    class of rejection that would be impossible for a writer to predict.
    """
    flat = " ".join(text.lower().split())
    return sorted(
        p for p in BANNED_CAUSAL_PHRASES
        if re.search(r"\b" + r"\s+".join(map(re.escape, p.split())) + r"\b", flat)
    )


def _numbers(text: str) -> list[tuple[float, int]]:
    """Every numeral in `text`, as `(value, decimal places written)`.

    The decimal count is what makes matching fair in both directions: a sentence
    saying `52%` should match a stored `-52.1`, and a sentence saying `52.7%`
    should not.
    """
    out = []
    for whole, frac, _pct in _NUMBER.findall(text):
        value = float(whole.replace(",", "") + ("." + frac if frac else ""))
        out.append((value, len(frac)))
    return out


def _pool(cites: list[str], facts: dict[str, dict]) -> list[float]:
    """Every number a set of cited facts makes available.

    Not only `values`: a fact's own labels are numbers too. `world=1` and
    `gene_index=3` are the subject of the sentence rather than a measurement of
    it, and a gate that rejected "World 1 ended with 992 agents" for the `1`
    would be rejecting the sentence for naming what it is about.
    """
    values: list[float] = []
    for cid in cites:
        fact = facts.get(cid)
        if not fact:
            continue
        values.extend(float(v) for v in fact.get("values", {}).values())
        values.extend(
            float(v) for k, v in fact.items()
            if k != "values" and isinstance(v, (int, float)) and not isinstance(v, bool)
        )
    return values


def _grounded(value: float, decimals: int, pool: list[float]) -> bool:
    """Is `value` in `pool` at the precision it was written to?

    Magnitude is compared without sign: a fact holding `delta: -423` supports the
    sentence "fell by 423". Direction is carried by the verb, which is prose, and
    the fact is what says how far.
    """
    target = round(abs(value), decimals)
    return any(abs(round(abs(v), decimals) - target) <= _MATCH_EPS for v in pool)


def check(sentence: Sentence, facts: dict[str, dict]) -> list[str]:
    """Reasons this sentence fails. Empty means it passes all five checks."""
    reasons: list[str] = []
    text = sentence.text

    if not text:
        return ["empty sentence"]

    # 1 — cited
    if not sentence.cites:
        reasons.append("uncited")

    # 2 — ids resolve
    unknown = [c for c in sentence.cites if c not in facts]
    if unknown:
        reasons.append(f"unknown fact id: {', '.join(sorted(unknown))}")

    known = [c for c in sentence.cites if c in facts]

    # 3 — numbers ground
    pool = _pool(known, facts)
    stripped = _STRUCTURAL_WORDS.sub(" ", text)
    ungrounded = [
        f"{value:g}" for value, decimals in _numbers(stripped)
        if not _grounded(value, decimals, pool)
    ]
    if ungrounded:
        reasons.append(f"ungrounded number: {', '.join(ungrounded)}")

    # 4 — lexicons
    words = _words(text)
    banned = sorted(words & set(BANNED_PHENOMENA))
    if banned:
        reasons.append(f"phenomenon not in this world: {', '.join(banned)}")
    causal = sorted(words & set(BANNED_CAUSAL)) + _phrases(text)
    if causal:
        reasons.append(f"causal claim: {', '.join(causal)}")

    # 5 — verdict discipline
    silent = [c for c in known
              if facts[c].get("kind") == "marker"
              and facts[c].get("detector_verdict") != "fired"]
    if silent:
        significance = sorted(words & set(BANNED_SIGNIFICANCE))
        if significance:
            reasons.append(
                f"significance language on a silent detector: {', '.join(significance)}"
            )

    return reasons


def verify(sentences: list[object], brief: dict, *, stage: str = "first"
           ) -> tuple[list[Sentence], list[Rejection]]:
    """Split a model's sentences into what may be published and what may not."""
    facts = {f["id"]: f for f in brief.get("facts", [])}
    accepted, rejected = [], []
    for raw in sentences:
        s = Sentence.parse(raw)
        reasons = check(s, facts)
        (accepted if not reasons else rejected).append(
            s if not reasons else Rejection(s.text, reasons, stage)
        )
    return accepted, rejected


def title_reasons(title: str) -> list[str]:
    """Titles get the lexicons but not the citation checks.

    A title is a label, not a claim, so requiring it to cite a row would produce
    "Population 812 to 389" as a chapter heading. It still may not name a
    phenomenon or assert a cause — *"The War Years"* over a demographic decline is
    the failure this whole file exists to prevent, and it is the line a reader
    sees first.
    """
    words = _words(title or "")
    reasons = []
    banned = sorted(words & set(BANNED_PHENOMENA))
    if banned:
        reasons.append(f"phenomenon not in this world: {', '.join(banned)}")
    causal = sorted(words & set(BANNED_CAUSAL)) + _phrases(title or "")
    if causal:
        reasons.append(f"causal claim: {', '.join(causal)}")
    return reasons


def repair_note(rejections: list[Rejection]) -> str:
    """The message sent back for the one repair round.

    Naming the reason rather than saying "try again" is the difference between a
    round that fixes something and a round that re-rolls. Most rejections are a
    single word or a single number.
    """
    lines = [f"- {r.text!r}\n  rejected: {'; '.join(r.reasons)}" for r in rejections]
    return "\n".join(lines)
