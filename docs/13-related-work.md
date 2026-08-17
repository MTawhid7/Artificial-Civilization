# 13 — Related Work

## Why this document exists

Two reasons, and the second matters more.

1. **Know what is already solved.** Several things we designed independently are mature fields.
   Our contribution there is measurement discipline, not mechanism, and pretending otherwise
   wastes effort.
2. **Know what challenges our decisions.** Four established results argue that specific choices
   in these docs are wrong. Each is cross-referenced to the decision it threatens, so a cold
   restart meets the objection next to the commitment rather than after it.

> ⚠️ **Confidence note.** This survey is written from memory against a knowledge cutoff of
> roughly May 2026. Author names and findings are reliable; specific years are approximate.
> **Verify any citation before it appears in a paper.** Findings flagged *(low confidence)*
> should be checked before being relied on.

---

## 1. Artificial life and open-endedness

The literature that speaks most directly to mechanism I
*(→ [03-mechanisms.md](03-mechanisms.md#i-the-stagnation-problem--and-why-we-study-it-rather-than-solve-it))*.

### The canonical systems

| System | Author | What it showed |
|---|---|---|
| **Tierra** (~1991) | Tom Ray | self-replicating programs evolving parasites, hyper-parasites, immunity — genuine unanticipated novelty |
| **Avida** | Ofria, Lenski, Adami | evolution of complex features from simpler ones; used for real evolutionary biology results |
| **Polyworld** (~1994) | Larry Yaeger | evolved neural agents in an ecology; foraging, mating, and social strategies |
| **Geb** | Alastair Channon | designed explicitly to demonstrate ongoing evolutionary activity |

**All of them plateau.** Complexity rises, then flattens. This is the single most important fact
in this document.

### Measuring open-endedness

Bedau's **evolutionary activity statistics** are the established instrument: track how much
adaptive novelty is being generated and retained over time, and classify systems by whether that
quantity is bounded, bounded-but-persistent, or unbounded. His finding — that biology sits in a
class no artificial system has reached — has stood for roughly two decades.

**Implication for us:** we invented `model_compression` as the primary stagnation metric
*(→ [D-036](DECISIONS.md#d-036))*. We should measure **both** — compression as the intelligence
metric, activity statistics as the open-endedness metric, because the latter makes our results
comparable to forty years of prior systems. See [D-041](DECISIONS.md#d-041).

### Necessary conditions

Soros & Stanley (~2014) proposed conditions for open-ended evolution, of which two matter here:
a **minimal criterion** for continued existence rather than an optimization target, and the
system's ability to **keep creating novel opportunities**. Stanley, Lehman and Clune later framed
open-endedness as the field's unclaimed grand challenge.

### Novelty search — the result that most directly threatens D-007

Lehman & Stanley (2011), *"Abandoning objectives: evolution through the search for novelty
alone."* On deceptive problems, selecting purely for **behavioral novelty** outperforms selecting
for the objective. Objective-driven search walks into local optima and stays.

**Implication for us:** [D-007](DECISIONS.md#d-007) — "the only fitness is offspring" — is
maximally objective-driven. We predicted stagnation from D-007 plus D-016 by reasoning; this
literature reaches the same conclusion experimentally, from a different direction. See critique 3
below.

### POET — the result that most directly threatens our fixed generators

Wang, Lehman, Clune & Stanley (2019), **POET** (Paired Open-Ended Trailblazer), and Enhanced
POET. Sustained progress required **co-evolving environments alongside agents** — the system
generating new problems for itself, not merely new solutions. Agents transferred between
environments; environments were mutated and kept when they were neither trivial nor impossible.

**Implication for us:** our generators fix world structure at init. See critique 1 — this is the
most consequential objection in the document, and it drove the P1ᴸ³/P8ᴸ³ work
*(→ [03-mechanisms.md](03-mechanisms.md#k-endogenous-environment-growth))*.

---

## 2. Multi-agent RL and autocurricula

The literature behind engine 3 (Red Queen), and the best-supported of our four engines.

**OpenAI hide-and-seek** (Baker et al., 2019) is the reference demonstration: agents in a simple
physical environment discovered tool use, then counter-strategies, then counter-counter-strategies
across several distinct phases — with no novelty bonus anywhere. Competition between adapting
agents supplied the curriculum.

Leibo and colleagues at DeepMind formalized this as **autocurricula**, arguing explicitly that
social interaction is an inexhaustible source of new problems because the environment adapts. The
supporting testbeds are **sequential social dilemmas** (Leibo et al., ~2017), work on common-pool
resource appropriation, and the **Melting Pot** benchmark suite (~2021) for evaluating
generalization across social situations.

**Implication for us:** engine 3 is on solid ground. It also suggests Melting Pot's scenario
structure is worth studying as a model for our detector suite — they faced the same problem of
measuring social outcomes without hand-coding them.

---

## 3. Emergent communication and cultural evolution

### Iterated learning — the result that says mechanism C targets the wrong knob

Kirby, Smith and colleagues showed, in both simulation and human laboratory experiments, that
compositional structure emerges when a language must pass through a **transmission bottleneck**
each generation: learners see only a fraction of the data and must generalize. Compositionality is
what survives repeated learning under pressure to be learnable.

Brighton & Kirby's **topographic similarity** is the standard compositionality measure, which we
already adopted.

On the negative side, Kottur et al. (~2017) — *"natural language does not emerge naturally in
multi-agent dialog"* — found emergent protocols are compositional only under specific pressures
and otherwise degenerate into arbitrary codes.

**Implication for us:** mechanism C sweeps **channel capacity**. The evidence says the load-bearing
variable is the **transmission bottleneck**. Different knob. See critique 2.

### Cultural evolution

Boyd & Richerson's dual inheritance theory; Henrich's collective-brain work; Mesoudi's synthesis.

The robust finding: **population size and connectivity predict cumulative culture better than
individual intelligence does.** Larger, better-connected populations retain and accumulate more,
largely independent of how clever their members are.

Derex & Boyd added an important qualification: **fully-connected populations can lose diversity
and perform worse than partially-connected ones.** Intermediate connectivity is often optimal.
*(moderate confidence on the specific attribution; the effect is well-replicated)*

**Implication for us:** this independently supports our prior that diffusion rather than discovery
is the bottleneck *(→ [03-mechanisms.md](03-mechanisms.md#b-latent-physics-with-randomized-constants))*,
and it makes E10's population-size axis more important than we treated it. The connectivity
qualification also means our contact experiments (Phase F) should sweep connectivity rather than treat
it as binary.

---

## 4. Agent-based social simulation

Our direct ancestor.

**Sugarscape** — Epstein & Axtell, *Growing Artificial Societies* (1996). Agents, a resource
landscape, simple rules; emergent migration, inequality, trade, and epidemics. Epstein's
generative slogan — *"if you didn't grow it, you didn't explain it"* — is essentially our thesis.

Also foundational: **Schelling's segregation model** (mild individual preferences producing severe
aggregate segregation — the canonical unintended-consequence result, and P11's ancestor), and
**Axelrod's** iterated prisoner's dilemma tournament and culture-dissemination model.

### The field's hard-won lesson

ABM has a **validation problem**: results are frequently parameter-sensitive, hard to replicate,
and difficult to distinguish from artifacts of the modeler's choices. "Docking" — reproducing one
model's results in another implementation — is notoriously difficult.

**Implication for us:** our null models, viability sweeps, and pre-registration are a direct
response, and this literature suggests parameter sensitivity will be **worse than we have
budgeted for** *(→ [12-risks.md](12-risks.md))*.

---

## 5. The LLM-agent society line

What we are explicitly not doing, and why.

**Generative Agents** (Park et al., 2023) — the Smallville simulation, 25 LLM agents with memory,
reflection, and planning, producing plausible social behavior including a party organized through
word-of-mouth. **Project Sid** (Altera, 2024) ran 1000+ LLM agents in Minecraft and reported
emergent specialization, trade, and the spread of something religion-shaped. DeepMind's
**Concordia** is the research framework in this line.

The work is impressive and the research question is legitimate. It is simply not ours: agents
pre-trained on human history producing human-shaped institutions cannot separate emergence from
recall. This is exactly [D-003](DECISIONS.md#d-003), and Project Sid is the clearest illustration
of why the rule exists — the results are striking and uninterpretable *for our question*.

---

## 6. Adjacent literatures worth knowing

| Field | Key work | Relevance |
|---|---|---|
| **Niche construction** | Odling-Smee, Laland | organisms modify their own selective environment — the biologically legitimate form of environment co-evolution *(→ critique 1)* |
| **Mesa-optimization** | Hubinger et al. (~2019) | inner/outer misalignment — validates the Value Gap framing *(→ [D-026](DECISIONS.md#d-026))* |
| **Goal misgeneralization** | Langosco et al., Shah et al. (~2022) | learned proxies coming apart under distribution shift |
| **Symbolic regression** | Schmidt & Lipson (2009); Udrescu & Tegmark (AI Feynman) | the machinery for mechanism B's law recovery |
| **Evolved plasticity** | Hinton & Nowlan (1987, Baldwin effect); Najarro & Risi (~2020, Hebbian plasticity in random networks) | validates the S2 design *(→ [D-008](DECISIONS.md#d-008))* |
| **Brain cost** | Aiello & Wheeler (expensive tissue); Dunbar (social brain); cognitive buffer hypothesis | the empirical backing for [D-016](DECISIONS.md#d-016) and E7 |
| **Opinion dynamics** | Deffuant; Hegselmann–Krause | belief propagation models — but typically without a ground truth to diverge from, which is where the Chronicle Gap differs |
| **Automated science** | Sakana's AI Scientist (2024) | closest analogue to our Analyst loop; the criticism (plausible but shallow output) is the one our falsification gate targets |

---

## The four critiques

Cross-referenced to the decisions they threaten. Each is a live objection, not a settled matter.

### Critique 1 — Fixed environments may structurally cap the plateau

**Source:** POET; open-endedness literature generally.
**Threatens:** [D-020](DECISIONS.md#d-020) (generators fix world structure at init).

Sustained open-ended progress in POET required environments to co-evolve with agents. Our
generated structure — resource kinds, latent rules, the modulator graph — is sampled once and
never grows. That ceiling is a plausible location for our plateau.

**Partial defense:** P11 coupling and P8 modulators mean agents already transform their selective
environment, which is niche construction and is biologically real. What was missing is growth in
the *structure* rather than the *state*.

**Response adopted:** mechanism K — endogenous environment growth
*(→ [03-mechanisms.md](03-mechanisms.md#k-endogenous-environment-growth))*, via P1ᴸ³ substances
and P8ᴸ³ processes. Agents create genuinely new substances with computed properties, so the
world's state space grows through agent action rather than through an external generator with its
own objective. See [D-038](DECISIONS.md#d-038).

**Why not POET's approach directly:** POET mutates environments and keeps the ones that are
neither trivial nor impossible. That criterion is a designer's judgment about what makes an
environment interesting — reward shaping one level up, and it would break the non-circularity
D-007 protects. Niche construction achieves environment growth without anyone deciding what a good
environment is.

**Residual risk:** unbounded material creation is also unbounded degeneracy risk. Conservation
laws are the defense; whether they suffice is an open question.

### Critique 2 — Mechanism C targets channel capacity, not the transmission bottleneck

**Source:** iterated learning (Kirby et al.).
**Threatens:** [03-mechanisms.md § C](03-mechanisms.md#c-a-bandwidth-dial-on-communication).

Compositionality emerges from a **learnability** pressure — each generation of learners sees only
a fraction of the data and must generalize — not primarily from how many bits a message carries.
Our dial is on the wrong axis, or at least on only one of two.

**Response adopted:** mechanism C becomes two-dimensional — channel capacity **and** transmission
bottleneck (data per learner per generation). E3 sweeps both. See [D-039](DECISIONS.md#d-039).

This is cheap to fix now and expensive after B2 hardens.

### Critique 3 — D-007 is precisely the condition novelty search says fails

**Source:** Lehman & Stanley.
**Threatens:** [D-007](DECISIONS.md#d-007), and by extension the whole stagnation programme.

Objective-driven search gets stuck in deceptive landscapes. "The only fitness is offspring" is
maximally objective-driven.

**Why we cannot simply adopt novelty search:** selecting for novelty *is* reward shaping. It would
mean the system optimizes for what we consider interesting, and every result about what emerges
becomes circular.

**Response adopted:** the legitimate analogue is **minimal criterion coevolution** plus **spatial
population structure**. Survival as a threshold rather than a target is already how our fitness
works; what was missing is diversity maintenance. Geographic isolation, partial connectivity, and
migration are the mechanisms by which biology avoids the monoculture our design invites — and they
are population-structure choices, not reward shaping. See [D-040](DECISIONS.md#d-040).

Derex & Boyd's connectivity result (§3) says the same thing from the cultural side: partial
connectivity beats full connectivity.

### Critique 4 — We invented a metric where prior art exists

**Source:** Bedau's evolutionary activity statistics.
**Threatens:** [D-036](DECISIONS.md#d-036).

`model_compression` is defensible but incomparable to prior systems. Activity statistics are
established and would situate our plateau against Tierra, Avida, and Polyworld.

**Response adopted:** measure both. Compression as the intelligence metric, activity statistics as
the open-endedness metric. See [D-041](DECISIONS.md#d-041).

---

## Further opportunities mined from the literature

Beyond the four critiques, these are results that suggest capability we did not have. Each is now
a decision, a detector, or an experiment.

### Adopted

| Opportunity | Source | What it became |
|---|---|---|
| **Stepping stones** — complex features evolve only when simpler intermediates are also rewarded | Avida / the EQU result | ladder density as an explicit generator parameter *(→ [D-043](DECISIONS.md#d-043))*, and E22 gating every other E0 experiment |
| **Ecological inheritance** — offspring inherit a modified environment, not only genes and culture | niche construction theory | a third inheritance channel *(→ [D-044](DECISIONS.md#d-044))*, E8 extended to E28 |
| **Transmission bias** — *who* you copy matters more than that you copy | cultural evolution (prestige / success / conformist / kin bias) | evolved copy-weight coefficients *(→ [D-045](DECISIONS.md#d-045))*; conformist bias becomes a second Chronicle Gap engine |
| **Held-out evaluation** — test on co-players and scenarios never trained against | Melting Pot | transplantation experiments (E27), `transplant_competence`, `overfit_gap` |
| **Competing brain hypotheses** — social brain vs. cognitive buffer | comparative biology | E26, which tests two real biological hypotheses against each other on one substrate |
| **Fidelity threshold** — cumulative culture requires transmission fidelity above a critical value | Henrich | `fidelity_threshold` as a phase transition, second arm of E23 |
| **Invariance detection** — symmetry and separability decompose search | AI Feynman | a cognitive precursor between S4 and S7 *(→ [04-intelligence.md](04-intelligence.md#noticing-what-does-not-change))* |
| **Population size and language regularity** | sociolinguistics; iterated learning | population as a third axis on mechanism C alongside capacity and bottleneck |
| **Connectivity is non-monotonic** — partial beats full for cumulative culture | Derex & Boyd | Phase F contact experiments sweep connectivity rather than treating it as binary; also the cultural argument for [D-040](DECISIONS.md#d-040) |

### Noted, not yet adopted

| Opportunity | Source | Why deferred |
|---|---|---|
| **Parasitism as an open-endedness engine** — Tierra's novelty came largely from agents exploiting *other agents' code* | Tierra | the analogue is free-riding on accumulated culture and artifacts rather than producing them. A genuinely distinct fifth engine for mechanism I, but it needs P5 claims over knowledge before it can be expressed. Revisit at Phase F |
| **Affordance richness predicts phase count** — hide-and-seek's strategy phases came from exploiting environment affordances the designers had not anticipated | Baker et al. | suggests counting affordances as a leading indicator of plateau height. No clean definition of "affordance" in our substrate yet |
| **The Schelling pattern as a detector family** — the interesting quantity is the *gap* between individual preference and aggregate outcome | Schelling | generalizing `unintended_consequence` into a family — one instrument per phenomenon measuring intended-vs-realized divergence. Attractive, but it multiplies the detector suite and needs a clearer definition of "intended" |
| **Docking / reference scenarios** — reproducing results across implementations is ABM's hardest validation problem | ABM methodology | a published reference scenario suite others could replicate would be a real contribution, but it only makes sense once results exist |
| **Analyst blind test** — evaluate machine-generated hypotheses against human-generated ones on the same corpus | AI Scientist criticism | the natural parallel to E17 for tier 4. Deferred until the Analyst exists |

---

## Novel versus reinventing

Honest accounting. The right-hand column is what we would actually claim.

| Element | Status | Our contribution |
|---|---|---|
| **Chronicle Gap** | **Novel** *(strong)* | opinion-dynamics models study belief propagation but rarely against systematic ground truth; instrumenting belief-vs-truth over civilizational time with `SET_TRUTH` interventions has no clear precedent |
| **Fork-based matched counterfactuals as the default unit of evidence** | **Novel** *(strong, methodological)* | simulation counterfactuals exist; a systematic matched-pair corpus with typed interventions as standard methodology does not |
| **Value Gap** | **Novel** *(moderate)* | bridges ALife and alignment — mesa-optimization studied in trained systems, not evolved populations over civilizational horizons |
| **Modulators / tech transforming primitive parameters** | **Partly novel** | this is niche construction formalized as a uniform mechanism; the theory exists, the systematic implementation is unusual |
| **Detector-plus-null discipline** | **Not novel, but rare** | standard in experimental science, uncommon in ALife; a real contribution given the validation crisis |
| **Autocurricula / Red Queen** | **Reinventing** | well-established since 2019 |
| **Emergent communication, compositionality metrics** | **Reinventing** | mature field; we should adopt their measures wholesale |
| **Open-endedness engines** | **Reinventing** | heavily studied; our framing as *measured plateau* is the only new part |
| **Population size drives cumulative culture** | **Reinventing** | our "diffusion is the bottleneck" prior is the field's consensus |
| **Compositional materials from properties** | **Partly novel** *(low confidence)* | chemistry-like generative crafting exists in games; as an open-endedness mechanism in an ALife substrate it seems underexplored |

The pattern: **our mechanisms are mostly known; our methodology and our two gap-instruments are
what would be new.** That is a reasonable position — the field's stated weakness is exactly
methodology.

---

## Reading list

If you read four things, in this order:

1. **Lehman & Stanley (2011)** — novelty search. The result that most threatens D-007.
2. **Wang, Lehman, Clune & Stanley (2019)** — POET. The result that drove mechanism K.
3. **Baker et al. (2019)** — hide-and-seek. The clearest demonstration of the Red Queen engine.
4. **Epstein & Axtell (1996)** — *Growing Artificial Societies*. The ancestor of this project.

Then: Bedau on evolutionary activity, Kirby on iterated learning, Henrich on collective brains.

---

## Maintaining this document

- When a critique is resolved by a design change, record the decision and link it from the
  critique. Do not delete the critique — the objection remains valid context for why the design
  looks the way it does.
- When something here is confirmed or corrected against the actual literature, upgrade the
  confidence note on that item.
- New work that threatens a decision belongs in the critiques section, not the survey.
