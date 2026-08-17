# 03 — Signature Mechanisms

The twelve primitives *(→ [02-primitives.md](02-primitives.md))* are the substrate. These twelve
mechanisms are the *specific design choices* that make this a research project rather than a
sandbox. Each turns a soft question into a number.

If you have limited time, mechanism A is the distinctive bet of the whole project.

---

## A. The Chronicle Gap — belief vs. truth, measured

The simulator knows exactly what happened. **The civilization only knows what it recorded.**
Records decay, get copied with error, get compressed, get reinterpreted.

```text
   ground truth ──────────────────────────────→  (kept by sim, never visible to agents)
        │
        │ witnessed by N agents (partial, noisy)
        ↓
   individual memory ──dies with the agent──┐
        │                                   │
        │ retold                            │ lost
        ↓                                   ↓
   oral record ──── copy error ──── drift ─────→ myth
        │
        │ (writing invented → durable medium, lower decay)
        ↓
   institution / law / taboo
```

### What to implement

- Ground-truth event stream (already the Chronicle) that agents **never read**.
- A separate **belief store**: propositions with confidence, `provenance_hops`, `source_id`,
  `first_hand`, medium, and a decay rate that depends on the medium (oral < written < archived).
- **Slot-based propositions** (P2ᴸ²) so partial knowledge is representable — knowing that
  something exists without knowing where, or where without knowing what.
- Copy-on-transmit with error. A retelling is a lossy write, not a pointer.
- The medium's decay rate is a **modulator target**: discovering writing binds a modulator that
  lowers it *(→ [D-021](DECISIONS.md#d-021))*. Literacy is not a special case; it is one entry in
  the modulator table.

`first_hand` is the flag that makes the social half of this work. Without separating direct
experience from hearsay, reputation-by-rumour is indistinguishable from
reputation-by-experience, and `hearsay_reputation` cannot fire.

### What to measure

Divergence `D(belief_t ‖ truth_t)` over time, per proposition and aggregate. Myth formation
becomes a plotted quantity rather than a story we tell about a screenshot.

### The experiment that makes it concrete

Plant a real cause: the north river is poisoned in year 40 and drinking there kills. Agents
form a rule. Then (a) let every agent who witnessed it die, and (b) **silently un-poison the
river in year 120.**

- Does the taboo persist after its cause is gone? For how many generations?
- What predicts persistence — record fidelity, population size, institutional density?
- Do high-fidelity societies adapt *faster* (they can check) or become *more rigid* (the
  record is authoritative)? Genuinely not obvious, which is exactly why it is worth running.

We are not aware of anyone instrumenting belief-versus-truth cleanly in a simulated society.
This is the most distinctive thing in the project. See [D-006](DECISIONS.md#d-006).

---

## B. Latent physics with randomized constants

The world runs on a hidden law. Agents observe noisy instances and perform symbolic
regression. The critical twist: **the constant is re-randomized per world.**

```text
world 001 → true G = 0.83 → discovers  F ∝ m₁m₂/r²,  Ĝ = 0.79
world 002 → true G = 2.41 → discovers  F ∝ m₁m₂/r²,  Ĝ = 2.55
world 003 → true G = 1.07 → never discovers anything
                            ↓
        plot Ĝ against G across ~60 worlds → r² is the answer
```

This converts "did science emerge?" from a vibe into a correlation coefficient, and makes
memorization structurally impossible — there is no fixed answer to memorize.

Then separate the two rates that actually matter:

- **discovery rate** — how often a truth is first found
- **diffusion rate** — how fast it spreads, and how often it is *re-lost*

Working hypothesis: most civilizations will be bottlenecked on diffusion, not discovery. If
true, that is likely the most interesting unplanned finding of the project.

---

## C. A bandwidth dial on communication

Do not ask "does language emerge?" — that is a yes/no anecdote. Make channel capacity a
continuous knob (bits per message) and **sweep it.**

```text
compositionality
      │                    ╭────────────
      │                   ╱
      │                  ╱  ← where is the threshold?
      │        ─────────╯      what moves it?
      └──────────────────────────────── channel capacity (bits)
```

Measure topographic similarity, vocabulary size, ambiguity, information density. Let dialects
drift with geography; measure the tick at which two populations become mutually
unintelligible, and whether that predicts conflict.

**The validity test that matters:** rebuild the map so the resource that signal `7` referred
to is now in the opposite direction. Does `7` follow the *concept* or the *location*? That
single test separates a real referential signal from a cute correlation.

---

## D. Commitment primitives instead of institutions

Never hard-code "government." Agents get exactly four political primitives — P4 Pledge,
P5 Claim, P6 Delegation, P7 Coercion — and everything else must be built out of them.

A collective entity bootstraps through **a pledge that references another pledge**: a "state"
is a pledge-cluster that agents can address, not a data structure we provide.

Classification happens **post hoc**, from the delegation graph:

```text
     reversible
         ↑
   council│ democracy-ish
  ─────────┼─────────→ concentration
   faction │ autocracy
         ↓
     entrenched
```

Regimes become *measured coordinates*, not authored categories. This is the trick that makes
governance real emergence rather than a menu selection.

---

## E. Technology by composition, not by tree

Items carry latent attribute vectors. A recipe is a combination plus a process. Effects come
from latent rules, never a hand-written tech tree.

The resulting space is combinatorially vast and mostly barren, with reachable islands — so
different civilizations genuinely find different technologies. This makes **path dependence
measurable**: how much of tech ordering is forced by the structure of the space, and how much
is contingent on who wandered where first?

At L2, progress stops being monotonic. A civilization can discover something extraordinary,
lose it, rediscover it centuries later, improve on it, or find an alternative that makes the
original irrelevant. None of that is implemented — it falls out of prerequisite chains, plus
knowledge loss, plus disjoint paths to the same capability.

---

## F. The cascade — how revolutions happen without a revolution

The sixth mechanism, and the one that makes P8ᴸ² worth its cost.

Because recipes bind **modulators** *(→ [D-021](DECISIONS.md#d-021))*, a discovery can change
the parameters of other primitives. Sometimes those changes open regions of the search space
that were previously unreachable, whose discoveries bind further modulators.

```text
   discovery ──→ modulator ──→ a resource becomes cheap to extract
                                        ↓
                          new combinations become affordable
                                        ↓
                    discovery ──→ modulator ──→ coercion economics shift
                                        ↓                    ↓
                          further discovery            fog reduced
                                        ↓                    ↓
                                   ... cascade, or fizzle
```

We never implement an industrial revolution, a renaissance, or a dark age. We implement
modulator binding, then **detect the cascade signature** with `modulator_cascade`
*(→ [07-detectors.md](07-detectors.md))* — after which the interesting question becomes
empirical: what produces a cascade rather than a fizzle?

Candidate answers the corpus could actually settle: population size, diffusion rate, the density
of the generated modulator graph, whether knowledge loss outpaces discovery, whether
institutions are stable enough to sustain unproductive search.

**This is the clearest illustration of the governing principle in the project.** The most
dramatic phenomenon in human history is not a feature. It is a pattern we look for.

⚠️ It is also the most likely source of degeneracy. Multiplicative modulator stacking compounds
explosively, and a cascade that never stops is as uninformative as one that never starts — see
the composition-rule open question in [DECISIONS.md](DECISIONS.md).

---

## G. The Value Gap — conviction vs. fitness

The psychological twin of mechanism A, and it works for the same reason: we hold ground truth
on both sides of a divergence the agents cannot see.

Values are an **evolved proxy** for fitness *(→ [02-primitives.md](02-primitives.md#p12--valuation))*.
Proxies drift. An agent whose values were shaped by an ancestral environment now lives in a
different one, and what it pursues can come apart from what actually produces offspring.

| | internal model | external reality | the gap is called |
|---|---|---|---|
| **A. Chronicle Gap** | what the civilization believes happened | what happened | myth |
| **G. Value Gap** | what agents pursue | what produces offspring | conviction |

```text
   ancestral environment ──→ selection ──→ value vector
                                               │
                          environment changes  │  values persist
                                               ↓
                              pursued outcome ≠ fitness-producing outcome
                                               ↓
                        martyrdom · asceticism · maladaptive tradition · principle
```

**What to measure:** per-agent and per-population correlation between value-weighted outcome
and realized offspring, tracked over time. A population where that correlation collapses while
values stay stable is a population holding convictions that no longer pay.

**Why this matters beyond the project.** This is structurally identical to inner/outer
misalignment: selection optimizes one objective, produces agents that optimize a learned proxy,
and the two come apart under distribution shift. Agents here are mesa-optimizers by
construction. That makes the corpus a laboratory for studying proxy drift in evolved
populations — a connection worth stating plainly, because it is real rather than decorative.

---

## H. Motivational archaeology — separating identical behaviors

Two agents transfer resources to a stranger. One expects reputation, one expects reciprocity,
one has internalized the act as valuable. **The behavior is identical. The internals are not.**

Declared motives are unavailable (no English in the core), and reading them off the value
vector is circular. But motives have distinct **counterfactual signatures**, and forking lets us
ablate them one at a time:

| Fork ablates | If altruism drops, the motive was |
|---|---|
| observability — nobody witnesses the act | reputation |
| recipient's capacity to reciprocate | reciprocity |
| relatedness to the recipient | kin selection |
| any expectation of future interaction | delayed self-interest |
| **all of the above at once** | **internalized value — the residual** |

Genuine altruism is defined **operationally**: what survives every instrumental ablation.

This is only possible with matched counterfactuals on a deterministic substrate, which is
exactly what invariant I3 provides. It answers a question philosophy has argued over for
centuries in a form that can actually come back negative — if nothing survives the ablations,
the honest finding is that this world produces no altruism that isn't instrumental.

⚠️ The ablations must be applied at a fork, never as a config difference from birth. An agent
raised in an unobservable world develops different values; an agent that suddenly *acts*
unobserved does not. Confusing the two answers a different question.

---

## I. The stagnation problem — and why we study it rather than solve it

### Stagnation is the design's prediction, not a risk to it

[D-007](DECISIONS.md#d-007) makes fitness offspring. [D-016](DECISIONS.md#d-016) makes cognition
cost energy. At carrying capacity with a working strategy, exploration is a metabolic tax on a
solved problem — so **selection actively removes curiosity at equilibrium.**

E7 already states this: in a stable world, populations should evolve *toward stupidity*. A
prosperous, peaceful, stable civilization that stops thinking is not a bug in the model. It is
what the model predicts.

### Open-ended evolution is an unsolved problem

Tierra, Avida, Polyworld, Geb — four decades of artificial life, and every system plateaus.
Complexity rises, then flattens. Nobody has demonstrated unbounded open-ended growth, and a
civilization simulation claiming to have solved it would be overclaiming.

**We will plateau too.** The design goal is therefore not open-endedness.

### The reframe: plateau height and time-to-plateau are dependent variables

Make stagnation the *object of study* rather than the failure to avoid.

```text
   complexity
       │        ╭─────────────── plateau height  ← measure this
       │       ╱
       │      ╱
       │     ╱   ← time-to-plateau  ← and this
       └────────────────────────────── generations
```

Then sweep everything against them. *"Under condition X, populations stagnate at complexity C
after T generations"* is a real finding. So is *"under condition Y they had not plateaued within
the horizon we ran."* This converts an unsolvable engineering target into a research programme
that produces results either way — and it is exactly the comparative-corpus thesis the project is
already built on. *(→ [D-032](DECISIONS.md#d-032))*

### Four engines that could push the plateau out

None hardcodes curiosity. Each is a sweepable condition, and whether it works is empirical.

**1. Heavy-tailed discovery payoffs — the load-bearing knob.**
If exploration payoffs are thin-tailed, agents correctly estimate low returns and exploration
dies. Heavy-tailed — most discoveries worthless, rare ones transformative — produces a gap:
individual expected value stays low while lineage expected value is high, **and no agent can
tell**, because rare events are rare and any local sample underestimates the mean.

> Consequence: **exploration rate must be evolved, not reasoned.** A rational agent will always
> under-explore a heavy-tailed distribution it cannot sample. Selection at the lineage level
> sustains what individual inference cannot justify.

*(→ [D-033](DECISIONS.md#d-033))*

**2. Curiosity as attention allocation — free, no new parameter.**
If the S2 plastic layer updates proportional to prediction error and attention is finite, then
well-modeled domains stop consuming attention and it flows to unmodeled ones. **That is boredom,
and it is a consequence of a learning rule already in the design, not a mechanism added to it.**

How fast attention shifts is a coefficient in the S2 plasticity genome — so *how curious a
lineage is* becomes evolvable without ever being specified.
*(→ [04-intelligence.md](04-intelligence.md#curiosity-is-attention-not-a-parameter), [D-034](DECISIONS.md#d-034))*

**3. Red Queen dynamics — why peace need not end progress.**
The environment that never saturates is other agents. Material abundance has a carrying capacity;
**relative standing does not.** P12 already generates group-relative outcome channels, so status
competition is an endogenous novelty engine that survives prosperity.

Honest caveat: a society with material abundance, a stable environment, *and* no relative-standing
competition probably **should** stagnate. If the corpus shows that, it is a finding about the
world, not a defect to patch.

**4. Lineage-level selection over long horizons.**
Bet-hedging is only visible if the outer loop scores lineages on geometric mean fitness across
generations rather than arithmetic mean within one. Cheap to get right at the start, expensive to
retrofit. *(→ [D-035](DECISIONS.md#d-035))*

### Measuring intelligence without defining it

To detect stagnation at all, something must be measured — but it need not be anthropocentric.

> **Predictive compression:** how much of the world the population's collective models predict,
> per unit of model.

It rises when agents find better theories and does not care whether those theories look like
science to a human reader. It is the least human-shaped measure of intelligence available, and it
is the primary stagnation detector. *(→ [D-036](DECISIONS.md#d-036))*

---

## J. Model criticism — questioning a framework that works

The Einstein case needs a capability S0–S6 does not have. Newtonian gravity was not broken;
relativity did not come from a practical failure. Questioning a *working* framework requires
representing the framework **as an object**:

```text
   S0–S6:  world ──→ model ──→ action
   S7:     world ──→ model ──→ action
                       ↑
                  model-of-model:  "I am modelling X as Y"
                       ↓
              generate Y′ ──→ hold provisionally ──→ compare
```

Three capacities: represent that a model *is* a model, generate a structural alternative rather
than a parameter tweak, and hold a competing model provisionally without acting on it.

**The dangerous question is the comparison criterion.** If both models fit, what makes one
preferred? Answering "elegance" or "simplicity as we perceive it" hardcodes an epistemology.

The non-arbitrary answer is again **predictive compression** — more observations predicted, fewer
parameters, wider domain. Relativity beats Newton on exactly this, and the criterion presupposes
nothing about what a good theory looks like to us.

This is the last rung, it is expensive, and it is the honest architectural requirement for
paradigm change as distinct from optimization. *(→ [D-037](DECISIONS.md#d-037))*

⚠️ Structural search is far more expensive than parameter search and almost always worse in the
short run. S7 will be selected *against* in any world where the current paradigm is adequate —
which is the stagnation problem again, one level up. Engines 1 and 4 are what could sustain it.

---

## K. Endogenous environment growth

**The response to critique 1** *(→ [13-related-work.md](13-related-work.md#critique-1--fixed-environments-may-structurally-cap-the-plateau))*.

POET found that sustained open-ended progress required environments to co-evolve with agents. Our
generators sample world structure once and never grow it — a plausible location for our plateau.

### Why not POET's approach directly

POET mutates environments and keeps those that are neither trivial nor impossible. That criterion
is **a designer's judgment about what makes an environment interesting** — reward shaping one
level up, and it would break the non-circularity D-007 exists to protect.

### Niche construction instead

Agents modify their own selective environment. This is established theory (Odling-Smee, Laland),
it needs no external arbiter of interestingness, and three channels already exist or are cheap:

```text
   STATE growth   (have)   P11 coupling — agents change global stocks
   PARAM growth   (have)   P8 modulators — discoveries change primitive parameters
   STRUCTURE growth (new)  P1ᴸ³ + P8ᴸ³ — agents create substances that did not exist
   SPACE growth   (new)    procedurally generated frontier keyed to (seed, coordinates)
```

The third is the real unlock. If properties are continuous and processes are functions, the
substance space has no enumerable limit, so **agents expand the world's state space by acting in
it.** That is environment co-evolution driven from inside, which is what POET achieved from
outside.

The fourth is cheaper and worth having anyway: an unbounded map whose regions are generated
deterministically on first exploration means the frontier never closes. Migration always has
somewhere to go, and P2's fog always has something behind it.

### Ecological inheritance — a third channel

Niche construction theory contributes something our design was missing. Offspring inherit not only
genes and culture but **a modified environment**:

```text
   GENETIC     vertical, slow, high-fidelity
   CULTURAL    horizontal, fast, lossy
   ECOLOGICAL  the transformed world itself — cleared land, depleted seams,
               built artifacts, altered climate
```

E8's two-way decomposition becomes three-way. This is cheap to measure — ecological inheritance is
already in the Chronicle as the difference between the world a cohort was born into and the one
its parents were — and it is likely to be substantial in exactly the runs where technology took
off. *(→ [D-044](DECISIONS.md#d-044))*

### What limits it

Conservation laws: yields below one, energy costs, and a property **trade-off manifold** so no
substance dominates on every axis. Without those, unbounded material creation is unbounded
`RUNAWAY`. Whether they suffice is genuinely open.

---

## L. The archive — externalized memory

P2ᴸ³ deserves separate treatment because it is the mechanism the cultural evolution literature
identifies as the actual driver of cumulative capability — and because it changes the Chronicle
Gap.

### The transition that matters

```text
   memory ────────dies with the agent
      ↓
   oral tradition ──drifts, decays, but survives its speakers
      ↓
   RECORD ─────────outlives everyone, and is a physical object
      ↓
   indexed archive ─findable, therefore usable
      ↓
   compressed record ─a textbook: K discoveries in one transmissible unit
```

Each step is a discovery, not a stage we schedule. Each is a recipe binding modulators that change
transmission parameters.

### Four failure modes we get for free

| Failure | Mechanism |
|---|---|
| **Encoding loss** | the notation recipe dies; records survive but become inert |
| **Retrieval collapse** | corpus outgrows the indexing available; knowledge exists, unfindable |
| **Catastrophic loss** | records are physical — fire (P10), seizure (P7), neglect (no maintaining pledge) |
| **Error fossilization** | high-fidelity copying preserves mistakes as faithfully as truths |

The last is the one that changes an existing result. E2 asks whether high-fidelity record-keeping
makes a society adaptive or rigid. **Error fossilization is the mechanism by which the answer
could be "rigid"** — a wrong record copied accurately for five centuries is far more durable than a
drifting oral tradition, because each copy is faithful and none of them checks.

### The fidelity threshold

Henrich's argument, which our sweeps can test directly: cumulative culture requires transmission
fidelity above a threshold, below which knowledge decays faster than it accumulates. That is a
**phase transition** — exactly the shape of result the corpus is built to find.

---

## Cross-references

| Mechanism | Depends on | Measured by | Shown by |
|---|---|---|---|
| A. Chronicle Gap | P2ᴸ¹⁺, P3, P9 | `chronicle_gap`, `zombie_institution`, `myth_formation` | Atlas split-screen *(→ [09-visualization.md](09-visualization.md))* |
| B. Latent physics | P2, P8 | `law_recovery` — Ĝ vs G correlation | Atlas chronicle panel |
| C. Bandwidth dial | P2, P3 | `compositionality`, `referential_validity` | dialect map overlay |
| D. Commitment | P4–P7 | `regime_type`, `principal_agent_drift` | territory / border view |
| E. Composition tech | P8 | `path_dependence`, `tech_regression`, `rediscovery` | tech strip on fingerprint |
| F. The cascade | P8ᴸ² + modulators | `modulator_cascade` | cascade animation on the timeline |
| G. The Value Gap | P12ᴸ¹⁺ | `value_fitness_gap`, `conviction_persistence` | value drift beside the fitness curve |
| H. Motivational archaeology | P12 + I3 forking | ablation battery — see above | motive breakdown on a followed life |
| I. The stagnation problem | P8 tails, S2 attention, P12 standing | `plateau_height`, `model_compression`, `exploration_rate` | complexity curve with the plateau marked |
| J. Model criticism | S7 | `paradigm_shift`, `model_turnover` | competing models held side by side |
| K. Endogenous environment growth | P1ᴸ³, P8ᴸ³, P11 | `substance_novelty`, `tool_bootstrapping`, `ecological_inheritance` | substance space expanding over time |
| L. The archive | P2ᴸ³, P4, S6 | `library_effect`, `encoding_loss`, `error_fossilization` | archive growth beside discovery rate |

All twelve are measured by detectors in [07-detectors.md](07-detectors.md) and none are named
anywhere in `src/core/`.
