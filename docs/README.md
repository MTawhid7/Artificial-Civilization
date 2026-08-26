# Artificial Civilization — Documentation

**Status:** **Phase A is complete — A0, A1, A2 and A3 all shipped.** The deterministic core runs,
the determinism gate holds, agents demonstrably evolve, there is a picture of it, and the worlds now
have written histories. Next up is [10-roadmap.md § B0](10-roadmap.md#b0--neural-policy),
preceded by the two-hour tier 1 of [§ A4](10-roadmap.md#a4--the-viewer-optional-tiered) — a
viewer built as a B0 debugging instrument rather than as a treat *(→ [D-070](DECISIONS.md#d-070))*.

| Stage | Result |
|---|---|
| A0 — skeleton | [`experiments/a0-baseline/`](../experiments/a0-baseline/result.md) — 11 ms/tick, 4.68 ms per world-year, forking exact |
| A1 — first evolution | [`experiments/a1-gradient-ascent/`](../experiments/a1-gradient-ascent/result.md) — patchier worlds select for **more random movement** |
| A1 — control | [`experiments/a1-heredity-control/`](../experiments/a1-heredity-control/result.md) — 95% of the gain is selection, not drift |
| A1 — negative | [`a1-patchiness`](../experiments/a1-patchiness/result.md), [`a1-hunger-coupling`](../experiments/a1-hunger-coupling/result.md) — a detector that beat its null in 39 runs and was still wrong |
| A2 — first picture | [`experiments/a2-wall/`](../experiments/a2-wall/result.md) — 102 worlds, one config, **9.4× more spread between worlds than within them** |
| A2 — re-analysis | [`a1-run-length`](../experiments/a1-run-length/result.md) — A1's dose-response is not length-limited; the level is, the slope is not |
| A3 — first story | [`experiments/a3-historian/`](../experiments/a3-historian/result.md) — an LLM writes the history, and a verifier deletes what it could not source |

**Nineteen decisions were added *by* implementation rather than before it** —
[D-051](DECISIONS.md#d-051) through [D-069](DECISIONS.md#d-069) — every one because a measurement
contradicted something these documents assumed.

**Seven of them are corrections to how we measure, not to what we built**, and all three withdrawn
claims were inference failures rather than mechanism failures. The simulation core has needed
exactly one correction in three stages. [12-risks.md](12-risks.md#scored-against-three-stages)
now carries the scorecard: the register spent 27 rows on the simulation misbehaving and six lines
on the statistics misbehaving, and the actual score is close to the inverse. Its stated defense
against emergence theater — "null models from A1" — was **falsified**: `directed_foraging` had a
null, beat it in 39 runs, and was still wrong.

Expect more of that. These documents are canonical, not infallible, and the gap between them and
the code is where the findings have come from so far.

**Scope:** hobby project on an 8 GB M1 Air. Read
[00-feasibility.md](00-feasibility.md) first — it constrains everything else, and several
ambitions in these docs are explicitly out of reach on this hardware.

This folder is the single source of truth for the project. It supersedes the original
`CONCEPT.md`, which has been absorbed here and deleted *(→ [D-019](DECISIONS.md#d-019))*.

---

## Reading order

If you are picking this project up cold — new chat, new contributor, future you — read in this
order. The first five are the non-negotiable context; the rest can be read on demand.

| # | Doc | What it settles |
|---|---|---|
| — | [14-handoff.md](14-handoff.md) | **Read first in a new session.** Where the project actually is, what to build next, and the traps that waste a day |
| 0 | [00-feasibility.md](00-feasibility.md) | The machine, the real budget, what is cut, what is still reachable |
| 1 | [01-vision.md](01-vision.md) | What this project is, what it refuses to be, what success means |
| 2 | [02-primitives.md](02-primitives.md) | The 12 primitives — eleven world, one interior — and how 30 phenomena derive from them |
| 3 | [03-mechanisms.md](03-mechanisms.md) | The twelve signature design choices, including the project's distinctive bets |
| 4 | [04-intelligence.md](04-intelligence.md) | How agents think, learn, develop, and reason badly |
| 5 | [05-architecture.md](05-architecture.md) | Components, invariants, the tick loop |
| 6 | [06-data-model.md](06-data-model.md) | State layout, Chronicle schema, digest schema, config |
| 7 | [07-detectors.md](07-detectors.md) | How we know a phenomenon actually happened |
| 8 | [08-experiments.md](08-experiments.md) | Experiment protocol and the marquee experiments |
| 9 | [09-visualization.md](09-visualization.md) | The Atlas — how this is shown to people |
| 10 | [10-roadmap.md](10-roadmap.md) | Phases A–F, stage-by-stage, ordered by payoff |
| 11 | [11-engineering.md](11-engineering.md) | Stack, repo layout, determinism rules, perf budget, testing |
| 12 | [12-risks.md](12-risks.md) | Failure modes and their early warning signs |
| 13 | [13-related-work.md](13-related-work.md) | What the field has found, four critiques of our decisions, what is actually novel |
| — | [DECISIONS.md](DECISIONS.md) | Every design decision, its rationale, and what was rejected |
| — | [GLOSSARY.md](GLOSSARY.md) | Terms, and the distinctions that cause confusion later |

**Shortest useful path for a new session:** [14-handoff.md](14-handoff.md) →
[00-feasibility.md](00-feasibility.md) → [10-roadmap.md](10-roadmap.md). The handoff is state and
goes stale on purpose; everything else here is design. `CLAUDE.md` at the repo root carries the
same essentials in the form a coding session needs them.

Add [13-related-work.md](13-related-work.md) if the question is *why* a decision looks the way it
does — it holds the four standing objections to our design. Add
[12-risks.md](12-risks.md#scored-against-three-stages) if the question is what actually goes wrong
here, which is not what this project originally guessed.

---

## The one-paragraph version

Artificial Civilization is a **comparative history laboratory**. It is not a world you watch;
it is a machine that produces thousands of divergent histories from controlled initial
conditions, plus the tooling to ask causal questions of them. Agents are numeric, not LLMs.
They want one thing — energy above zero, and offspring — and every social structure from trade
to government must earn its place by being a better way of not dying — including the values
agents come to hold, which are evolved proxies for fitness rather than goals we assigned. Twelve
primitives generate everything; no phenomenon is ever implemented directly. Complexity goes *into* the
primitives, never sideways into the phenomena they produce — so there is no industrial
revolution, no collapse, no plague, only primitives rich enough to make those happen and
detectors that notice when they do. The simulation is the instrument, the histories are the
data, and the science is comparative.

---

## The seven rules

Everything in these documents is downstream of seven commitments. If a proposed change violates
one of them, the change is wrong, not the rule.

1. **No new mechanism without a detector.** Before building trade, define the number that
   proves trade is happening and the null baseline it must beat.
   *(→ [07-detectors.md](07-detectors.md), [D-011](DECISIONS.md#d-011))*

2. **The only fitness is offspring.** Never reward cooperation, technology, or complexity. A
   fitness function that mentions the phenomenon under study makes every result circular. Agents
   pursue evolved *values*; selection sees only offspring *(→ [D-026](DECISIONS.md#d-026))*.
   *(→ [04-intelligence.md](04-intelligence.md#the-cheat-vectors), [D-007](DECISIONS.md#d-007))*

3. **No English inside the core.** The simulation speaks numbers. LLMs live at the boundary
   reading logs — never as agent policy, except as an explicitly labelled experimental
   condition. *(→ [D-003](DECISIONS.md#d-003))*

4. **Never name a phenomenon in code.** There is no `war.py`. War is what the detector finds
   when coercion between two delegation clusters sustains above baseline.
   *(→ [02-primitives.md](02-primitives.md), [D-002](DECISIONS.md#d-002))*

5. **The corpus is the product, not the world.** One beautiful run is an anecdote. The unit of
   work is a sweep with an effect size at the end.
   *(→ [01-vision.md](01-vision.md), [D-001](DECISIONS.md#d-001))*

6. **Complexity goes into primitives, never into phenomena.** Depth enters through generators
   and modulators, is gated by what agents can actually use, and every level of it ships its own
   detectors. *(→ [02-primitives.md](02-primitives.md#three-rules-that-let-depth-in-without-exploding-the-config), [D-020](DECISIONS.md#d-020)–[D-022](DECISIONS.md#d-022))*

7. **Stagnation is measured, never patched.** Exploration dying at equilibrium is what this design
   predicts. When it happens, sweep the four engines — do not add a curiosity term.
   *(→ [03-mechanisms.md](03-mechanisms.md#i-the-stagnation-problem--and-why-we-study-it-rather-than-solve-it), [D-032](DECISIONS.md#d-032))*

---

## Where to start building

[10-roadmap.md § A0](10-roadmap.md#a0--skeleton) — skeleton, determinism tests, and the
benchmark that replaces the estimated numbers in [00-feasibility.md](00-feasibility.md) with real
ones.

Then **A1**, which produces one boring dose-response curve and thereby proves the entire pipeline
before any interesting mechanism is built on top of it. It is the highest-value week in the plan.

If you have three months total: **A0 → A1 → A2 → A3 → B0 → B2**. That ends at the first emergent
word, which is a complete and genuinely interesting project on its own.

---

## Maintaining these docs

- **New design decision?** Append to [DECISIONS.md](DECISIONS.md) with rationale and rejected
  alternatives, then update the affected doc. The decision log is what makes a cold restart
  cheap — it stops settled questions from being re-litigated.
- **New primitive?** [02-primitives.md](02-primitives.md) + detectors in
  [07-detectors.md](07-detectors.md) + a roadmap gate in [10-roadmap.md](10-roadmap.md). All
  three, or it is not real.
- **Changed a schema?** [06-data-model.md](06-data-model.md) is canonical and versioned. Bump
  the version; never silently redefine a field's meaning.
- **Docs and code disagree?** The docs are wrong until proven otherwise — but fix them
  immediately. Stale design docs are worse than none.
- **Stage shipped?** Update [14-handoff.md](14-handoff.md) — status table, the numbers block, and
  what is next. It is the one file that is allowed to be about *now*, and the one a cold session
  reads first.

## Conventions in these documents

- `P1`–`P11` — world primitives; `P12` — the interior primitive *(→ [02-primitives.md](02-primitives.md))*
- `L0`–`L3` — primitive depth levels; written `P8ᴸ²`. **L3 makes a primitive unbounded** *(→ [02-primitives.md](02-primitives.md#l3--the-open-ended-depth-levels))*
- `S0`–`S7` — intelligence stages *(→ [04-intelligence.md](04-intelligence.md))*
- `A0`–`F` — roadmap phases and stages *(→ [10-roadmap.md](10-roadmap.md))*; older docs may still say `A1`–`Phase F`
- `D-nnn` — decision records *(→ [DECISIONS.md](DECISIONS.md))*
- `E1`–`E28` — marquee experiments *(→ [08-experiments.md](08-experiments.md))*
- `⌛` — a detector whose primitive or depth level is not yet built
- **Open question** marks something deliberately unsettled. These are invitations, not
  oversights — all are tracked at the bottom of [DECISIONS.md](DECISIONS.md).
