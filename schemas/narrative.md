# Narrative schema

**Version 0.1.0.** The contract between a finished run and the Historian's prose.
Producer is [`src/historian/build.py`](../src/historian/build.py), written to
`corpus/runs/<run_id>/narrative/`.

Two objects: the **brief**, which is the only thing the model is allowed to see,
and the **narrative**, which is what comes back and what is stored beside the
prose. Both are versioned with the code that writes them.

---

## Why this file exists at all

Every other schema in this project describes measurements. This one describes
prose, and prose is the one output that is **never evidence**
*(→ [docs/GLOSSARY.md](../docs/GLOSSARY.md), [docs/12-risks.md](../docs/12-risks.md))*.

The risk register names the failure mode directly — *"the Historian writes
beautiful nonsense"* — and its stated defense was that conclusions must cite
metrics rather than prose. That is a rule for the reader. It does nothing about
the prose itself, which will be read by people who are not going to cross-check
it against a Parquet file.

So the containment is structural instead. The model never sees the Chronicle, the
digest, or a grid. It sees a **numbered table of facts computed in Python**, and
it must return sentences that each name the facts they rest on. Everything else is
rejected before it reaches a file.

That is the whole design. The schema below is what makes it checkable.

---

## The brief — what the model is given

One brief per world per era, plus one for the run's preface.

```json
{
  "narrative_version": "0.1.0",
  "run_id": "d712b54d58fde26db2e9d1aa",
  "digest_hash": "1f0c…",
  "kind": "era",
  "world": 3,
  "era": {"index": 4, "tick_range": [12000, 15000], "year_range": [1000, 1250]},
  "facts": [
    {
      "id": "f07",
      "kind": "series_change",
      "series": "population",
      "values": {"start": 812.0, "end": 389.0, "min": 371.0, "max": 844.0,
                 "mean": 601.3, "delta": -423.0, "delta_pct": -52.1},
      "source": "aggregate.parquet world=3 tick 12000..15000"
    },
    {
      "id": "f12",
      "kind": "marker",
      "detector": "collapse",
      "tick": 12840,
      "values": {"depth_pct": 54.0},
      "detector_verdict": "silent",
      "source": "lens.collapse via digest.markers, world=3 tick 12840"
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `narrative_version` | this schema's version — check before reading anything else |
| `run_id`, `digest_hash` | provenance; prose that cannot be traced to a run is not even prose about a world |
| `kind` | `era` or `preface` |
| `world` | absent on a preface, which is about the whole run |
| `era` | tick range and the year range it converts to; absent on a preface |
| `facts` | the numbered table — **the entire universe of things that may be said** |

### Fact kinds

Every one is computed. None is hand-authored, and none is written by the model.

| `kind` | Where | What it carries |
|---|---|---|
| `era_window` | era | tick range, year range, frame count, and the era's index *and* its ordinal |
| `series_change` | era | start / end / min / max / mean of one series, plus `delta` and `delta_pct` |
| `extremum` | era | this era holds the run's max or min for a series |
| `marker` | era | a detector firing, its depth, **and the detector's verdict for the run** |
| `marker_count` | era | how many firings there were, when there are more than fit |
| `gene_shift` | era | mean trait drift across the era, for the two genes that moved most |
| `spatial` | era | resource-centroid drift in cells and compass bearing; density concentration |
| `run_summary` | preface | worlds, ticks, years, eras, capacity, patchiness, seed |
| `spread` | preface | lowest, highest, median and ratio of final populations |
| `divergence` | preface | between-world SD against within-world SD over the run's last quarter |
| `cross_world` | preface | one world's final population, peak, and rank among the run's worlds |

`era_window` carries `era_index` (from zero) and `era_number` (from one) because prose counts from
one. A gate that rejected *"the fifth era"* for not matching a stored `4` would be rejecting a
sentence for being written in English.

`values` is always a flat `{name: number}` map. That is not a stylistic choice: it
is what lets the verifier ask *"is this number in a cited fact?"* without knowing
anything about what the fact means.

### `source` is the traceability record

A literal description of where the number came from — the aggregate rows, or the
detector call. [10-roadmap.md § A3](../docs/10-roadmap.md#a3--first-story) requires
that *every claim in generated prose is traceable to an event range or an aggregate
row*. `source` is that requirement made into a string, and the citation chain
`sentence → fact id → source` is what carries it end to end.

### What the brief deliberately does not contain

- **No raw grids.** The rasters in the digest become `spatial` facts computed in
  Python — a centroid drift in cells and a bearing — and never reach the model as
  an array. A 48×48 float field handed to a language model is a field it will
  describe rather than measure.
- **No per-agent events.** The Historian reads the aggregate tier and the digest.
  It never opens a checkpoint and never touches live state.
- **No detector interpretation.** A `marker` fact carries `detector_verdict`
  alongside its depth, so a drawdown from a detector that came out *silent* cannot
  be narrated as a significant one *(→ [D-063](../docs/DECISIONS.md#d-063))*.

---

## The narrative — what comes back

```json
{
  "narrative_version": "0.1.0",
  "run_id": "d712b54d58fde26db2e9d1aa",
  "kind": "era", "world": 3, "era_index": 4,
  "title": "The long decline",
  "sentences": [
    {"text": "Population fell from 812 to 389 over the era.", "cites": ["f07"]}
  ],
  "rejected": [
    {"text": "The drought drove the settlements west.",
     "reason": "causal connective: 'drove'; ungrounded number: none; banned: none",
     "stage": "repair"}
  ],
  "model": "gemini-3.7-flash",
  "prompt_version": "0.1.0",
  "brief_hash": "9ab3…",
  "generated": 13, "accepted": 11,
  "usage": {"input_tokens": 2480, "output_tokens": 604}
}
```

| Field | Meaning |
|---|---|
| `sentences` | accepted prose, in order; every one carries ≥1 fact id |
| `rejected` | what was thrown away, with the reason, and whether it failed on the first pass or after the repair round |
| `model`, `prompt_version`, `brief_hash` | what produced this, and from which facts |
| `generated`, `accepted` | the acceptance rate, per era |
| `usage` | token counts; the corpus-scale cost of this stage is a real number |

**`rejected` ships.** A narrative that quietly dropped its failures would report a
100% acceptance rate by construction. Negative results are committed here for the
same reason they are committed for experiments
*(→ [docs/11-engineering.md](../docs/11-engineering.md))*.

---

## The five checks

Applied by [`src/historian/verify.py`](../src/historian/verify.py), offline, with
no model involved. A sentence must pass all five.

| # | Check | Catches |
|---|---|---|
| 1 | at least one cite | prose that rests on nothing |
| 2 | every cite id is in this brief | invented citations — the failure that looks most like rigor |
| 3 | every number is derivable from a cited fact | invented statistics — **has never yet fired**; see below |
| 4 | no banned vocabulary | phenomena the S0 world does not contain |
| 5 | no significance language on a silent detector | a mark read as a finding |

### Check 3 in detail

Every numeral, percentage and year in the sentence is extracted and must match
something in the cited facts: a value in `values`, or one of the fact's own
numeric labels (`world`, `gene_index`, `tick`). Matching is to the precision
written — a sentence saying `52%` matches `delta_pct: -52.1`, and a sentence
saying `52.7%` does not. Sign is ignored: a fact holding `delta: -423` supports
*"fell by 423"*, because direction is carried by the verb and the fact is what
says how far.

The labels are in the pool for a reason. `world=1` is what a sentence is *about*
rather than a measurement of it, and a gate that rejected *"World 1 ended with 992
agents"* over the `1` would be rejecting the sentence for naming its subject.

Sentences with no numerals pass this check trivially, which is intended:
*"the population roughly halved"* is a claim the cited fact supports, and forcing
a number into every sentence would produce worse prose without producing more
grounding.

**Measured: this check has never rejected a sentence.** Not in 263 across both
arms of [a3-historian](../experiments/a3-historian/result.md). It was designed as
the load-bearing one, on the assumption that inventing a number is how this
component fails. With a fact table in context that is not how it fails — the model
invents *connective tissue*, and every rejection so far has come from check 4.
The check is kept because it costs nothing and its absence could not be shown to
be safe, but it should not be described as the one that does the work.

### The two lexicons

**Phenomena** — `war`, `battle`, `city`, `king`, `empire`, `tribe`, `religion`,
`plague`, `trade`, `invention`, `revolution`, and the rest. This is
[D-002](../docs/DECISIONS.md#d-002) — *no phenomenon names in the core* — pointed
at the one component whose entire job is to sound like history. CI greps `src/core/`
for these words; the verifier greps the prose.

**Causation** — `because`, `caused`, `led to`, `drove`, `resulted in`, `due to`,
`therefore`. The Historian orders events in time and does not explain them.
*After* is allowed; *because* is not. A causal claim about a world is a claim the
Lens makes with a null and a control *(→ [D-064](../docs/DECISIONS.md#d-064))*, or
nobody makes.

---

## Files on disk

```
corpus/runs/<run_id>/narrative/
  preface.md          the whole run
  world_00.md         all eras for one world, generated banner at the top
  world_00.json       sentences, cites, rejections, usage
  cache/<key>.json    key = blake2b(brief, prompt_version, model)
```

**Never under `metrics/`.** `metrics/` is Lens output — evidence — and the
directory split is the first line of the containment
*(→ [docs/06-data-model.md](../docs/06-data-model.md))*.

Every `.md` opens with a banner naming the model and prompt version. It is in the
file rather than only in the viewer, because a file gets pasted somewhere the
viewer's label does not follow it.

The cache key includes the brief hash, so a completed era is never re-billed, and
rebuilding a digest that does not change the numbers costs nothing
*(→ [docs/11-engineering.md § LLM usage](../docs/11-engineering.md#llm-usage))*.

---

## What is not deterministic here, and why that is fine

Every other artifact in this project is a pure function of `(config, seed)`. This
one is not: the same brief can produce different prose, and no golden hash pins
it.

That is acceptable **only** because narrative is never evidence. It is also why
`narrative/` is committed under `experiments/` rather than left in the git-ignored
corpus — prose cannot be regenerated from a seed, so if it is not committed it is
gone. And it is why no test in the gate asserts anything about the *text*: the
tests assert the containment properties, which are deterministic, and say nothing
about what the model wrote.
