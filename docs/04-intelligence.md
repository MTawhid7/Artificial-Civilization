# 04 — The Intelligence System

## The question this settles

*Do we predefine intelligence or do agents discover it?*

Neither. **You predefine the capacity; they discover the contents.** Getting that line in the
right place is most of the design.

---

## Three levels, three different answers

| Level | Example | Who supplies it |
|---|---|---|
| **Architecture** — what shape of mind is possible | 64 hidden units, an episodic buffer, a 5×5 view | **We do.** Unavoidable, and not cheating — a cortex is predefined too |
| **Parameters** — the weights in a particular mind | this agent's actual policy | **Discovered:** evolution across lifetimes, plasticity within one |
| **Content** — beliefs, strategies, knowledge | "north water kills"; "trade with strangers" | **Discovered**, and must be *transmissible* |

Predefining a strategy is cheating. Predefining the space a strategy can live in is building
the substrate. **Every failure mode here comes from level 3 leaking up into level 1** — someone
hand-codes `if attacked: retaliate` because retaliation isn't emerging fast enough, and the
project quietly dies while all the demos get better.

---

## The stage ladder

Each rung is gated against the primitive ladder *(→ [02-primitives.md](02-primitives.md#gating-primitives-and-depth-are-both-gated-by-policy))*.
Never build ahead of what the world can reward.

| Stage | Mechanism | Unlocks | Roadmap |
|---|---|---|---|
| **S0** | genome (~8 floats) → reactive rule; no within-life learning | foraging, migration, population dynamics, crude specialization | A1 |
| **S1** | a tiny MLP (~30–60 hidden) **per lineage**, with the genome as its input embedding; neuroevolution only | resource choice, exploration under fog | B0 |
| **S2** | genome encodes a **local plasticity rule**, not weights | within-life adaptation; *how to learn* becomes selectable | B1 |
| **S3** | recurrent state + episodic buffer with retrieval | reputation, reciprocity, trust — **gate for P3** | C0 |
| **S4** | learned forward model + short-horizon rollouts | investment, building, delayed payoff — **gate for P5, P8** | C2 |
| **S5** | opponent model: another agent's history → predicted action | negotiation, deception, deterrence, war — **gate for P4, P6, P7** | Phase F |
| **S6** | social learning: copy policies/knowledge from others | culture, cumulative technology, second inheritance channel | D0 |
| **S7** | **model criticism**: represent a model as an object, generate structural alternatives, hold them provisionally | paradigm change as distinct from optimization — **gate for mechanism J** | Phase F |

### Depth gates, not just breadth gates

Each stage also caps how *deep* a primitive may go
*(→ [D-022](DECISIONS.md#d-022))*. Full mapping in
[02-primitives.md](02-primitives.md#gating-primitives-and-depth-are-both-gated-by-policy).

| Stage | Depth it authorizes |
|---|---|
| S0–S1 | P1ᴸ⁰⁻ᴸ¹, P2ᴸ⁰, P10ᴸ⁰ |
| S3 | P2ᴸ¹ *(confidence, provenance)*, P3ᴸ¹⁻ᴸ², P9ᴸ¹⁻ᴸ² |
| S4 | P1ᴸ², P5ᴸ¹, P8ᴸ¹, P11ᴸ¹⁻ᴸ² |
| S5 | P2ᴸ² *(deception)*, P4ᴸ², P5ᴸ², P6ᴸ², P7ᴸ¹⁻ᴸ², P8ᴸ² |

The gate is enforced twice: the config loader hard-fails on violation, and a **gate-check
detector** *(→ [07-detectors.md](07-detectors.md#gate-check-detectors))* must fire before the
next depth level is authorized. Passing the first without the second means the richness is
legal but unused.

### S2 in detail — the interesting rung

Rather than the genome encoding weights, it encodes coefficients of a local update rule:

```
Δw = η · f(pre, post, reward, eligibility)
      ↑         ↑
      └─────────┴── these are genes, under selection
```

Now different lineages can evolve different learning rates, credit-assignment horizons, and
exploration tendencies. **This is the honest version of "agents discover their own
intelligence"** — and unlike the fantasy version, it runs.

---

## Architecture: one shared network, not ten thousand

Do **not** give each agent its own network and its own optimizer. It breaks determinism,
breaks batching, and multi-agent RL with thousands of non-stationary learners and constant
birth/death is a research project that would consume the civilization project.

```text
input (all numeric, fixed width)
  ├─ interoception : energy, age, health, inventory
  ├─ local view    : k×k × channels (food, terrain, agents, signals)
  ├─ memory read   : m retrieved episodic slots
  ├─ social        : reputation of visible agents
  └─ genome embed  : d floats — this agent's individuality
                    ↓
   ONE SHARED NETWORK (evolved weights) + per-agent plastic layer
                    ↓
   action head: discrete action · continuous params · signal vector
```

One shared network **per lineage**. Individual variation comes from the genome embedding and
the per-agent plastic layer. A tick becomes **one batched forward pass for all agents** — the
only reason batching worlds is feasible at all. See [D-004](DECISIONS.md#d-004).

> The S1 row above once read *"genome encodes weights of a tiny MLP"*, which is the natural
> reading and contradicts this section. B0 resolved it by measurement rather than by preference:
> per-agent weights are the same arithmetic — the same MACs happen — but they mean streaming
> `[W, N, n_in, H]` floats every tick, **470 MB per tick** at corpus scale on a machine with 8 GB.
> That number is what D-004 means. The genome is the *input embedding*, not the weights.

### Where the variants come from, since weights are not inherited per agent

Sharing a network is what makes S1 affordable and it removes the thing that made S0's selection
free: at S0 the policy is per-agent and inherited, so *the population is the population of
policies* and evolution needs no separate step at all.

**A lineage is a heritable clade** *(→ [D-071](DECISIONS.md#d-071))*. A child normally takes its
parent's lineage, and therefore its parent's network. With probability `speciation_rate` it instead
founds a new lineage in a free slot, carrying a perturbed copy. A lineage whose last member dies
frees its slot.

There is no generation clock, no fitness function and no scoring window, so phase 10 LEARN stays
the no-op it was at S0. Selection over weights is birth and death, which means
[D-007](DECISIONS.md#d-007) — *the only fitness is offspring* — holds literally at S1 rather than
by analogy. What changed is only which population is under selection: at S0 it is the agents, at S1
it is the lineages.

The two-loop table below still describes S2 onward. At S1 there is only the outer loop, and it is
the one that was already there.

### Training: two loops

| Loop | Mechanism | Timescale | Why |
|---|---|---|---|
| **Outer** | evolution over shared weights + genome | generations | gradient-free, trivially parallel, robust to non-stationarity, indifferent to agents dying mid-episode |
| **Inner** | local plasticity rule (S2) | within a lifetime | cheap, local, no backprop through time |

This is the Baldwin structure — **genome as prior, lifetime as adaptation**. Biologically
motivated and computationally cheap.

Gradient RL (PPO and friends) is not banned. It is an *experimental condition to add later*:
does sample-efficient learning change which civilizations emerge? That's a question, not a
default.

---

## Brains must cost energy

Without this the whole intelligence layer is inert.

Charge metabolic cost for cognition: hidden units, memory slots, planning horizon — all draw
energy per tick. Intelligence becomes an evolutionary **trade-off** that can be selected
*against*.

This unlocks the best experiment in the layer: **sweep environmental variability and find
where brains start paying for themselves.** In a perfectly stable world a large brain is a
metabolic tax on a problem that never changes, and populations should evolve toward
*stupidity*. In a volatile world the same brain is what keeps you alive. Somewhere between is
a threshold — finding it, and finding what moves it, is a real result using machinery we
already have.

**Corollary:** once S6 social learning exists, culture lets an agent acquire competence without
paying the cost of individual discovery. We can then measure which inheritance channel — genes
or culture — carries more of the adaptation, and how that ratio shifts with volatility.

---

## Cognition is a state variable, not a genome constant

An agent's capability should not be a number fixed at birth. Humans develop, specialize,
plateau, and decline, and *which* of those happens depends on circumstance as much as on
endowment.

Decompose it into a chain rather than a scalar:

```text
   potential ──→ learning capacity ──→ knowledge ──→ reasoning ──→ competence
   (genetic)      (developmental)      (acquired)    (applied)     (observed)
        ↑               ↑                  ↑             ↑
     genome        age · nutrition     exposure ·    problem
                   · stress · care     teaching ·    complexity
                                       P8 recipes
```

Only `potential` is genetic. Everything downstream is state that changes over a lifetime, driven
by nutrition (P1), teaching (S6), material security (P5), stress, and — critically — **the
complexity of problems the agent actually encounters.**

### The capability feedback loop

This is what makes it worth building, because it produces stratification without any
stratification mechanism:

```text
   capability → better decisions → resources → access to teaching → capability
                                                                        ↑
   ┌────────────────────────────────────────────────────────────────────┘
   │
   └─ and in reverse: scarcity → no teaching → worse decisions → deeper scarcity
```

Two agents with identical `potential` and different starting circumstances end up in different
places. **Inequality and social mobility become measurable outcomes rather than parameters** —
and the mobility rate is a detector, not a setting. A world where the loop is tight has low
mobility; where it is loose, high. Nobody configured either.

**Gate:** S3. Cognition-as-state requires memory of what was learned. `potential` remains under
selection at every stage, which keeps [D-016](DECISIONS.md#d-016) intact — a developed brain
costs more to run than an undeveloped one.

---

## Rationality is bounded by resources, not by named biases

Agents will reason badly. That is correct and necessary — but **do not implement a list of
biases.** `confirmation_bias = 0.3` is phenomenon-coding with a psychology textbook instead of
a history textbook, and it fails for the same reason: you get exactly the bias you wrote.

Bad reasoning should fall out of resource limits that already exist:

| Observed failure | Emerges from |
|---|---|
| confirmation bias | belief-weighted sampling of a limited memory |
| overconfidence | confidence estimated from a small sample without correcting for sample size |
| availability effects | recency-weighted episodic retrieval (P3ᴸ¹) |
| poor long-horizon reasoning | finite planning depth (S4), which costs energy |
| social conformity | cheap imitation (S6) outcompeting expensive individual inference |
| holding contradictory beliefs | no global consistency check — propositions are local (P2ᴸ²) |

That last one is worth stating explicitly: **nothing in the architecture enforces belief
consistency.** An agent can hold contradictory propositions indefinitely, exactly as people do,
because reconciling them would require a global sweep no agent can afford.

The payoff is that two highly capable agents can reach opposite conclusions from the same world
— different experiences, different samples, different priors — without either being assigned a
"bias" parameter.

---

## The observation budget

Depth makes the world richer to perceive, and perception is not free. A rights vector, partial
propositions, belief confidences, modulated parameters, and a coercion action repertoire all
widen the input tensor.

**Observation width draws from the same metabolic budget as cognition**
*(→ [D-016](DECISIONS.md#d-016))*. This is deliberate: it creates a real trade-off between
*perceiving more* and *thinking harder* about less, and it means depth cannot be added for free
even when a gate permits it.

```
cognition_cost = α·hidden_units + β·memory_slots + γ·planning_horizon + δ·observation_width
```

Two consequences worth anticipating:

- Agents may evolve to **ignore** available information — a finding, not a bug. If a rights slot
  is never attended to, `rights_differentiation` won't fire and P5 stays at L1.
- Populations may specialize epistemically: some lineages paying for wide observation and
  shallow thought, others the reverse. Whether that split emerges is worth a detector.

## Learning in a world whose rules change

Modulators *(→ [D-021](DECISIONS.md#d-021))* mean the world's parameters change under the agent.
After smelting is discovered, iron extraction cost is permanently different. A policy trained
against the old parameters is now trained against a world that no longer exists.

This is **nonstationarity by design**, and it cuts both ways:

| It is a feature because | It is a hazard because |
|---|---|
| adaptation to a transformed world is exactly what we want to study | evolution over shared weights assumes a roughly stable fitness landscape |
| it is what makes "technology changes everything" observable in behavior | a cascade can invalidate an entire population's competence at once |
| the genes/culture decomposition gets sharper when the world shifts | rapid modulator churn can prevent any policy from ever being good |

Three mitigations, in order of preference:

1. **Modulators are mostly local in scope.** `scope: agent | region | world` — world-scope
   modulators should be rare by construction in the generator.
2. **Plasticity absorbs the shift.** The S2 inner loop exists precisely for within-lifetime
   adaptation; a modulator firing is the canonical thing it should handle.
3. **Cascade rate is a viability criterion.** A config where modulator churn outpaces adaptation
   is degenerate and should be classified `EXPLOSIVE` by the viability sweep
   *(→ [08-experiments.md](08-experiments.md#2-viability-sweep))*, not studied.

**Open question:** whether the shared network needs an explicit input encoding the *currently
active modulator set*, so policies can condition on which world they are in rather than
re-adapting from scratch. That is arguably giving agents a free sense organ; it is also arguably
just "noticing that iron is now cheap." Unresolved — tracked in [DECISIONS.md](DECISIONS.md).

## Curiosity is attention, not a parameter

The tempting move is `creativity = 0.83` with periodic random idea generation. That is
phenomenon-coding: you get exactly the creativity you wrote, and learn nothing about when it
appears.

**The reduction that costs nothing:** the S2 plastic layer already updates proportional to
prediction error. Add finite attention, and well-modeled domains automatically stop consuming it
while unmodeled ones attract it.

```text
   domain well-modeled  → low prediction error → low update magnitude → attention drains away
   domain poorly-modeled → high prediction error → high update magnitude → attention flows in
```

That is boredom. It is a **consequence of a learning rule already in the design**, not a mechanism
added on top. And the rate at which attention shifts is a coefficient in the S2 plasticity
genome — so *how curious a lineage is* becomes evolvable without ever being specified.

The progression the design should be able to produce, with nothing scripting it:

```text
necessity → optimization → mastery → prediction error falls → attention drains →
attention flows to the unexplained → strange hypothesis → occasionally, discovery
```

**Critical constraint:** exploration rate must be **evolved, not reasoned**
*(→ [D-033](DECISIONS.md#d-033))*. Discovery payoffs are heavy-tailed, rare events are rare, and
any sample an agent can take underestimates the mean. A rational agent will always under-explore.
What sustains curiosity is selection at the lineage level, operating on a distribution no
individual can perceive.

## Selection must see lineages, not just generations

Bet-hedging — occasionally producing a variant that is worse on average and better in the tail —
is only visible to selection that scores **geometric mean fitness across generations** rather than
arithmetic mean within one.

Arithmetic-mean selection removes exploration wherever it lowers expected offspring. Geometric-mean
selection over long horizons can retain it, because a lineage that never explores is one
environmental shift from zero.

This is cheap to build correctly at the start and expensive to retrofit, so the outer loop should
score lineages over a multi-generation window from B1.
*(→ [D-035](DECISIONS.md#d-035))*

## Bad reasoning is not the same as useless reasoning

A distinction worth holding onto, because it determines whether wrong ideas are permitted to be
productive:

| | |
|---|---|
| **being wrong** | the model does not predict well |
| **being useless** | the model generates no observations that change any other model |

An incorrect theory that motivated a novel measurement has done work. A failed experiment that
eliminated an assumption has done work. Nothing in the architecture should penalize wrongness
directly — only prediction failure, and only where prediction is what the agent needed.

Practically this means the S7 model-comparison criterion is **predictive compression**
*(→ [D-036](DECISIONS.md#d-036))*, never a correctness oracle. There is no ground-truth channel
telling an agent its theory is false; there is only how much of the world it predicts, per unit of
model. That keeps wrong-but-generative ideas alive long enough to be generative.

## Who you copy is under selection

S6 says agents can copy each other. The cultural evolution literature says **the copying bias
matters more than the copying** — and the biases produce sharply different civilizations.

```
copy_weight(target) = β_prestige · status(target)
                    + β_success  · observed_payoff(target)
                    + β_conformity · population_frequency(behavior)
                    + β_kin      · relatedness(target)
```

The `β` coefficients are **genetic and under selection** — never chosen by us. Each produces a
characteristic pathology and a characteristic strength:

| Bias | Strength | Pathology |
|---|---|---|
| **prestige** | fast diffusion of whatever high-status agents do | copies causally-irrelevant behavior alongside useful behavior — ritual accumulates |
| **success** | tracks actual payoff | needs payoff to be observable, which fog often prevents |
| **conformist** | stabilizes accumulated culture against drift | **locks in maladaptive traditions** — the transmission-side engine of the Chronicle Gap |
| **kin** | cheap, reliable access | slow horizontal spread; culture stays in lineages |

Conformist bias is the notable one: it is what makes a zombie institution durable rather than
merely present, and it means E2's answer may depend more on `β_conformity` than on record decay
rate. *(→ [D-045](DECISIONS.md#d-045))*

## Noticing what does not change

A small cognitive primitive with outsized consequences, taken from the symbolic-regression
literature — AI Feynman's leverage came largely from exploiting **invariance, symmetry, and
separability** to decompose problems rather than searching blindly.

The corresponding agent capability is **invariance detection**: registering that some quantity
stays constant while others vary.

It is cheap — a running variance estimate over observed relations — and it is the foundational
scientific move. Conservation laws, symmetry principles, and dimensional reasoning all begin with
noticing that something does not change. Without it, mechanism B's law recovery is blind search
over expression space; with it, the search decomposes.

Sits between S4 and S7 as a precursor: it does not require representing a model as an object, but
it is what gives S7 something structural to work with.

## Two inheritance channels

Three, once niche construction is in the design
*(→ [03-mechanisms.md](03-mechanisms.md#ecological-inheritance--a-third-channel))*.

```text
   GENETIC          vertical, slow, high-fidelity, parent → child
        +
   CULTURAL         horizontal, fast, lossy, anyone → anyone
        +
   ECOLOGICAL       the transformed world itself — cleared land, depleted seams,
                    built artifacts, altered climate, surviving records
        ↓
   the adaptation actually observed
```

All three must be separately traceable in the Chronicle so their contributions can be decomposed.
*(→ [06-data-model.md](06-data-model.md))*

Ecological inheritance is the cheapest to measure — it is the difference between the world a
cohort was born into and the one its parents were — and it is likely to be the largest channel in
exactly the runs where technology took off, which is the case we most want to understand.

---

## The cheat vectors

Three rules. The first is the one that kills projects.

### 1. The only fitness is offspring

Never reward cooperation, trade, technology, or "civilizational complexity." **The moment the
fitness function mentions the phenomenon under study, the experiment is circular and the
result is worthless.** Cooperation must earn its way in by producing more surviving children,
or it does not count.

### 2. No agent ever touches ground truth

Only observations — always partial, always noisy. The sim knows; the agent infers. This is
what makes mechanism A possible at all *(→ [03-mechanisms.md](03-mechanisms.md))*.

### 3. Never hand-code a strategy as a fallback

When war isn't emerging, the temptation is a little `if threatened: fight` to "help it along."
That is the moment the project dies, and it dies quietly — everything still runs, the demos
look better, and none of the results mean anything.

---

## Open questions

- **Lineage granularity.** One shared network per species, per culture, or per region? Affects
  how much behavioural diversity is representable. Leaning per-lineage-with-splitting.
- **Plasticity family.** Which parameterization of `f` is expressive enough to be interesting
  but small enough to evolve? Needs an isolated benchmark before B1.
- **Opponent-model cost.** S5 is expensive per agent. Can it be amortized across a population
  (a shared model of "typical agent" + per-target correction)?
- **Does S4 need to be learned?** A hand-written planner over a learned model may be an
  acceptable architecture-level primitive. Unresolved — see [D-009](DECISIONS.md#d-009).
