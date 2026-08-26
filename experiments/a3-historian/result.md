# a3-historian — result

**Status: the worlds have histories, and the histories are checkable.** 41 briefs, **230 of 231
sentences accepted**, 325 citations, one rejection. Spec: [spec.yaml](spec.yaml). Prose:
[narrative/](narrative/). Free tier, $0.08 at the published paid rate.

> **A3 ships no detector and produces no evidence.** Everything below is a measurement of the
> *instrument*, never of the worlds. The prose in `narrative/` is an interface
> *(→ [docs/GLOSSARY.md](../../docs/GLOSSARY.md))*.

---

## What was asked

[10-roadmap.md § A3](../../docs/10-roadmap.md#a3--first-story) asks for an LLM that reads a
finished run and writes narrative history per era, under four containment criteria. The one that
does the work:

> every claim in generated prose is traceable to an event range or an aggregate row

As written that is a rule for the reader, and readers do not cross-check prose against Parquet. The
stage's real question is whether it can be made a property of the file instead.

## What happened

The model never sees the world. It sees a numbered table of facts computed in Python from
`aggregate.parquet` and the digest, returns sentences carrying fact ids, and
[`verify.py`](../../src/historian/verify.py) deletes anything that fails five checks. What shipped:

| | |
|---|---|
| briefs | 41 — 4 worlds × 10 eras, plus a preface |
| sentences accepted | **230 of 231 (99.6%)** |
| citations | 325, an average of 1.4 per sentence |
| rejected | 1 |
| prose | 43 KB across 5 files |
| tokens | 61,750 in / 9,554 out |
| cost | **$0.00** — free tier; $0.08 at $0.75/$3.75 per 1M |

The one rejection, from world 2's sixth era:

> ~~Organisms spread further apart across **the territory** and avoided crowded spaces more
> consistently.~~ — *phenomenon not in this world: territory*

A true positive. There is no territory at S0 — that would require claims, and claims require a
primitive that does not exist yet. The sentence is otherwise correct and the deletion is right.

## The number that means nothing on its own

**99.6% is not a result.** A gate that never fires is indistinguishable from a gate that does not
work, and reporting the acceptance rate as a success would be exactly the mistake this project's
measurement layer keeps making. Two explanations, opposite meanings:

- **(a)** the prompt states the rules, the model obeys them, and the gate is redundant *on this input*
- **(b)** the checks are too weak to catch what the model would have written anyway

So the stage ships a control — [control.py](control.py). Same facts, same verifier, same corpus;
the system instruction keeps only the requirement to cite and drops the three content rules.

| arm | accepted | rate |
|---|---|---|
| guarded (shipped) | 230 / 231 | **99.6%** |
| **unguarded control** | 26 / 32 | **81.2%** |

**(a) is right.** Nineteen percent of unguarded sentences would not have survived, so the checks are
doing something the prompt does not. What they caught:

> *"This severe depletion **forced** a drastic biological adaptation, driving metabolic rates down
> while parental investment in offspring soared."*
>
> *"This profound scarcity **triggered** a demographic contraction…"*
>
> *"Concurrently, total available resources swelled by seventeen percent as geographic **wealth**
> slowly drifted toward the northeast."*

That first sentence is the risk register's *"the Historian writes beautiful nonsense"*
*(→ [12-risks.md](../../docs/12-risks.md))* in its exact predicted form. Nothing in the fact table
says depletion forced anything. It says resources fell and `metabolic_rate` fell, in that order.
The causal claim is entirely the narrator's, and it is the sort of sentence that would be quoted
back later as if the simulation had shown it.

## What I got wrong about my own design

**The numeric check never fired. Not once, in 263 sentences across both arms.**

It was designed as the load-bearing one — the module docstring called inventing a number "the
specific way this component fails". That was wrong. With a fact table in context, the model does not
invent statistics; it invents **connective tissue**. Every rejection in both arms was a lexicon
failure: three causal claims, three phenomena, zero bad numbers.

This is the same shape as the finding in
[12-risks.md § scored against three stages](../../docs/12-risks.md#scored-against-three-stages) — the
register predicted mechanism failures and got inference failures. Here the design predicted
arithmetic failures and got rhetorical ones. **The failure mode is overreach, not fabrication**, and
a grounding gate built only to check numbers would have passed every one of those sentences.

The numeric check stays. Its cost is nothing and its absence would be unprovable — but it is not
what makes this work, and `verify.py` now says so.

### And two false positives, both found by real data

A gate with false positives teaches the writer to avoid ordinary English, which is worse than the
failure it prevents. Two shipped in v0.1.0 of the lexicon and were fixed:

- **`produced`** deleted *"the agents produced 0 offspring"*. Bare `produced` is a count;
  `produced by` is a claim about mechanism. The causal list is now split into words that are causal
  alone and phrases that are causal only in combination.
- **`led to`** deleted *"births sett**led to** 38"* — a plain substring search inside a word. Phrases
  now match on word boundaries.

Neither would have been visible in a unit test written by the person who wrote the lexicon. Both
took one run over real prose.

## What it reads like

From world 0, the opening era — the whole file is in [narrative/world_00.md](narrative/world_00.md),
where every sentence carries a ledger row naming the aggregate rows behind it:

> **1. The First Thinning** · *Years 1–250*
>
> Available food declined across the map. Agents held less energy by the end of the era. Fewer
> young were born over time. Only 89 agents remained alive at the lowest point. The agents evolved
> to move less. They began to invest more energy into their offspring. The food supply shifted
> towards the south-west.

Three things in that passage are worth noting.

**It is a real S0 history.** The founding cohort overshoots and crashes — the same transient
`collapse` excludes as burn-in — and the prose describes it without being told it is a story.

**"The agents evolved to move less" is `metabolic_rate` falling**, named rather than numbered. The
gene labels are mirrored from `s0_reactive.py`, and a test reads the core's own docstring table to
stop the mirror drifting. Without them the sentence would be *"gene 6 fell from 0.048 to 0.001"*,
which is not a sentence about anything.

**"The food supply shifted towards the south-west" comes from a raster**, reduced in Python to a
circular centroid drift on the torus and a compass bearing. The model never saw a grid. This is what
buys the roadmap's *"the eastern settlements grew until…"* register without letting a language model
describe a 48×48 float field.

## What it does not read like

**There is no drama, because there is none in the world.** No war, no discovery, no city. A quiet
era gets two sentences and stops — the prompt says so explicitly, because padding a quiet age is the
one way to write something false without writing a false number. Several eras are genuinely dull,
and that is the honest rendering of a world containing food, movement, birth and death.

`collapse` came out **silent** on this corpus (z = −1.13 across three seeds), so no marker in any era
may be called significant, unusual or rare — the fifth check enforces it and the fact table carries
the verdict beside every mark *(→ [D-063](../../docs/DECISIONS.md#d-063))*.

## Containment, as tested

All four roadmap criteria are now assertions in `tests/test_historian.py`:

| criterion | test |
|---|---|
| traceable to a row | 5 checks, 12 tests; the model sees only the fact table |
| under `narrative/`, labelled generated | hashes every file in the run dir before and after; only `narrative/` appears |
| digest + aggregate tier only | builder runs with `checkpoints/` moved away; grep guard in CI |
| byte-identical Chronicle | `chronicle_digest` and `final_state_hash` unchanged — it is never attached |

The gate went 59 → 86 tests, none of which asserts anything about the text. Prose is the one
artifact here that is not a pure function of `(config, seed)`, which is also why `narrative/` is
committed under `experiments/` rather than left in the git-ignored corpus.

## The free tier, measured

Worth recording, because it shaped the run and will shape the next one.

**The Gemini free tier is 20 requests per day per model** — not per minute. Measured by exhausting
three: `gemini-3.7-flash`, `gemini-3.6-flash` and `gemini-3.5-flash` all report `limit: 20`. Quota
is enforced per Cloud **project**, not per key, so the client rotates over
`GEMINI_API_KEY_2` … `_8` and only helps when the keys come from separate projects.

This run therefore spans two models: **30 briefs on `gemini-3.7-flash`, 11 on `gemini-3.6-flash`**,
one model per file, and every file names what wrote it. The header reports the models actually used
rather than the one that was asked for — a single-model header would have been asserting something
the file could not support.

**The cache is keyed on the brief, not the model.** That was a bug first: twenty briefs already paid
for were about to be re-requested on a model switch. It is what makes a run resumable tomorrow, and
it is now a test.

## Verdict

The stage did what it was for. An unfalsifiable-narrative failure mode that the risk register named
three years of design ago showed up in the control arm on the first try, in almost the wording the
register predicted — and the gate deleted it.

**The prose is worth reading, and none of it is evidence.** Both halves are the point.

---

*Run [`d712b54d58fde26db2e9d1aa`](../a2-wall/spec.yaml) — a2-wall seed 0. Worlds 0–3, the first four
ids, chosen before any outcome was known *(→ [D-063](../../docs/DECISIONS.md#d-063))*; they rank
29th, 5th, 17th and 14th of 34 by final population, which is what an unselected sample looks like.*
