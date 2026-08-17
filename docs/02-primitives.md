# 02 — World Primitives

## The governing principle

A list of historical phenomena — war, trade, revolution, plague — is an **output spec, not a
build spec**. If you implement "war" as a war system, you get a war system: something that
does exactly what you wrote and never surprises you.

The work is finding the small set of primitives those phenomena all fall out of. We believe
it is twelve — eleven describing the world outside the agent, and one describing the agent's
interior.

> **Never name a phenomenon in code.** There is no `war.py`, no `Alliance` class, no
> `revolution()`. Those words appear only in [07-detectors.md](07-detectors.md), where they
> name *measurements applied to logs*, never mechanisms.

**Corollary:** complexity goes into the primitives, never into the phenomena. We do not build
an "industrial revolution," a "collapse," or a "renaissance." We build primitives rich enough
to produce them, and then measure whether they did.

---

## Two axes: breadth and depth

The primitive set has a second dimension the original design ignored.

- **Breadth** — which primitives exist. Fixed at twelve: **P1–P11 world, P12 interior**.
- **Depth** — how rich each primitive is. Each has depth levels **L0 → L2**.

The real world is rarely binary or single-parameter. Scarcity, information, and technology
exist on continuous scales, interact, and produce different outcomes in different contexts.
Depth is how that enters without inventing new systems.

A version of the project is a point on both axes: *"C2 runs P1–P5 at L1, P8 at L0."*

---

## Three rules that let depth in without exploding the config

Depth appears to conflict with the freeze protocol — twelve primitives at fifteen parameters
each is a 165-dimensional space, and no sweep survives that. It doesn't, because of a
distinction the original design missed.

### Rule 1 — Generators: richness is structure, not parameters

Most depth is **structure that exists**, not **knobs a researcher tunes**. Extraction curves
exist; rights decompose; contagions mutate. None of those need to be swept.

So richness enters through **generators**: one or two hyper-parameters control a *distribution*
from which many heterogeneous entities are drawn.

```yaml
p1:
  resource_diversity: 0.7      # ← the only swept knob
  # generates 12 resource kinds, each with a sampled extraction curve,
  # regeneration profile, substitutability, and spatial clustering
```

**Sweepable surface stays small. Generated depth goes as deep as we like.** Two worlds with
the same `resource_diversity` and different seeds have genuinely different economies.

Consequence: generator outputs are part of world identity and must be reconstructible from
`(config, seed)` alone — never sampled lazily mid-run. *(→ [D-020](DECISIONS.md#d-020))*

### Rule 2 — Modulators: cross-primitive influence is one mechanism

Several depth requirements are secretly the same requirement:

- a previously useless material becomes valuable after a discovery *(P8 → P1)*
- a communication technology reduces effective fog *(P8 → P2)*
- a new weapon changes the economics of coercion *(P8 → P7)*
- writing lowers the decay rate of records *(P8 → beliefs)*
- an ideology changes how agents weight cooperation *(P9 → policy)*

Implemented separately these are twenty scattered special cases — phenomenon-coding by another
name. Implemented once:

```
Modulator {
  source:    (primitive, state_predicate)   e.g. (P8, knows_recipe:smelting)
  target:    (primitive, param_path)        e.g. (P1, resource[iron].extract_cost)
  fn:        multiply | add | replace | curve
  magnitude: float
  scope:     agent | region | world
}
```

Every primitive exposes named parameters. Recipes and contagions **bind modulators** to them.
"Technology transforms everything" becomes one code path.

**Critically: which modulators exist is generated per world from the seed.** Different worlds
have different technological consequences, which is what makes path dependence real rather
than decorative. *(→ [D-021](DECISIONS.md#d-021))*

### Rule 3 — Depth is gated by policy capacity, exactly like breadth

A seven-dimensional rights vector handed to an S4 agent yields an agent that uses two
dimensions and ignores five — while all seven cost compute and observation width.

**Build the structure to hold the full richness; populate only what the current intelligence
stage can distinguish; widen when a detector shows agents actually using the width.**

The existing gate rule *(D-015)* now applies to depth levels, not just primitives.
*(→ [D-022](DECISIONS.md#d-022))*

---

## The twelve, with depth levels

`L0` = A1-era, trivial. `L1` = the working default. `L2` = full richness.

---

### P1 — Scarcity

Resources are not `available` or `depleted`. Effective scarcity is a *derived* quantity that
can change while physical quantity does not.

| Level | Content |
|---|---|
| **L0** | one resource kind, logistic regrowth **plus a recolonization term**, patchiness parameter |
| **L1** | multiple kinds; per-kind regeneration class (finite / slow / fast / effectively unlimited); quality field; rising marginal extraction cost as good deposits deplete |
| **L2** | substitution matrix; extraction alters future regeneration; usefulness modulated by P8; undiscovered deposits found via P2 |

```
ResourceKind r  (generated):
  stock[H,W], quality[H,W]
  regen_class      finite | logistic | linear | unbounded-but-costly
  extract_cost(quality, cumulative_extracted, tech_modulators)   ← rising marginal
  substitutes[]    partial substitutability matrix
  usefulness       base value, modulated by P8
  discovered[H,W]  per-agent knowledge of deposits (P2)
```

Booms, depletion spirals, migration, trade routes, technological substitution, resource
conflict, and unexpected prosperity all come from this one structure.

**Key derived quantity:** `effective_scarcity = f(physical_stock, extract_cost, usefulness,
substitutes_available)`. Its divergence from `physical_stock` is a detector.

**Regrowth must not make zero absorbing** *(→ [D-051](DECISIONS.md#d-051))*. Pure logistic
`dR = rate·R·(1 − R/K)` gives a stripped cell zero growth forever. Measured in A0: 98% of cells
hit zero within 50 ticks and total resource never moved again — every world became a countdown
rather than a history. The form actually used is

```
dR = (1 − R/K) · (rate·R + seed_rain·K)
```

where `seed_rain` is recolonization from beyond the cell. At L1 a `finite` regeneration class
sets it to zero *deliberately*, and exhaustion becomes permanent — which is the point of having
regeneration classes at all.

---

### P2 — Fog / Information

Not "agents cannot see beyond radius X." **Two agents in the same world inhabit different
perceived worlds.**

| Level | Content |
|---|---|
| **L0** | per-agent view radius, binary known/unknown map |
| **L1** | beliefs carry `(value, confidence, age, provenance_hops, source)`; information decays; first-hand and second-hand are distinguishable |
| **L2** | partial propositions; contradictory beliefs held simultaneously; information as a tradeable/stealable/withholdable good; observation range modulated by P8 |

The **partial proposition** is the structure that gives you "knows that something exists
without knowing where":

```
Proposition { type, slots: {what: iron, where: NULL, quality: 0.6?} }
```

Slots fill independently. Knowing *where* without knowing *what it is* is the same structure
with different slots populated.

**On deception:** there is no `deceive()` action. Signals are cheap and unverified, so lying is
*available*. Whether it is selected for is a finding, not a feature. Requires S5.
*(→ [D-023](DECISIONS.md#d-023))*

---

### P3 — Identity

| Level | Content |
|---|---|
| **L0** | stable ids; agents distinguishable |
| **L1** | episodic memory of interactions with valence; decay; capacity limits |
| **L2** | distortion; reinforcement through repetition; group membership inference; reputation aggregated with source weighting |

The load-bearing detail: **first-hand experience and hearsay must be separately tracked.**
Without that distinction, reputation-by-rumour cannot emerge and the Chronicle Gap has no
grip on the social layer.

Trust, grudges, loyalty, and betrayal are then aggregates over episodic memory — never
dedicated systems.

---

### P4 — Pledge

| Level | Content |
|---|---|
| **L0** | flat promise with a stake; public; binary honored/broken |
| **L1** | variable stake, variable observability (private ↔ public), variable duration |
| **L2** | conditional terms as a small expression tree over observable predicates; nesting; third-party enforcement; outcomes neither party fully controls |

The expression tree is what produces *"I will help you if you help them"* generically:

```
Terms := Predicate | AND | OR | NOT | IF(Terms, Terms)
Predicate := observable state | another pledge's status | an event
```

Nested, conditional, mutually-referencing pledges produce increasingly complex political and
institutional structure with no government or diplomacy system anywhere in the code.

---

### P5 — Claim

Not ownership. The question is not *"who owns this?"* but *"who holds which rights over which
aspect, and how strongly are they enforced?"*

| Level | Content |
|---|---|
| **L0** | binary possession |
| **L1** | rights vector, **2 slots populated**: use, exclude |
| **L2** | full vector: access, use, extract, reside, transfer, exclude, temporary control, conditional; overlapping and conflicting claims over aspects of one object |

A river carries separable claims over water, fishing, transport, adjacent land, and extraction.
Conflict is when two claims assert `exclude` over the same aspect.

⚠️ Per Rule 3, populate two slots first. The remaining five are structure until a detector
shows agents distinguishing them.

---

### P6 — Delegation

The key move: agents delegate **decision authority**, not just actions — and delegated
authority can be re-delegated.

```
individual → representative → administrator → regional authority → larger authority
```

| Level | Content |
|---|---|
| **L0** | A defers to B; revocable at fixed cost |
| **L1** | scoped delegation (which decisions); transitive chains; communication lag along the chain |
| **L2** | **accumulated authority**: revocation cost grows with the authority a delegate has accumulated and with chain depth |

L2 is where organizations, bureaucracies, hierarchies, and states become possible — and where
a delegate can accumulate enough authority that the original principal can no longer easily
control them. Principal-agent drift is not modelled; it is a consequence of revocation cost
being a function of accumulated authority.

---

### P7 — Coercion

**Expand the action space, not the resolution function.** *(→ [D-024](DECISIONS.md#d-024))*

| Level | Content |
|---|---|
| **L0** | attack: spend energy, damage target |
| **L1** | full action taxonomy: steal, damage, displace, blockade, impose cost, capture, coerce behavior change |
| **L2** | preparation as an action; coordination through P4/P6; positional and supply advantages *as things agents act on* |

The action taxonomy is generative and we want all of it. The **resolution function stays a
simple, transparent function of two or three state variables.**

Terrain, supply, surprise, and coordination must matter *because agents can act on them* —
position yourself, cut a route, strike the unaware, coordinate via pledges — not because they
are weighted terms in a formula. An eleven-factor combat formula is a combat system wearing a
primitive's clothes: it gets tuned until battles "feel right," at which point the outcome is
authored rather than emergent.

---

### P8 — Recipe / Knowledge

The primitive with the greatest potential for genuine surprise. Not a database of predefined
technologies — **composable pieces agents discover, combine, modify, transmit, and
occasionally misunderstand.**

| Level | Content |
|---|---|
| **L0** | flat combination: two items → outcome from a latent table |
| **L1** | prerequisite graph; discovery difficulty; accidental discovery; independent rediscovery; resource requirements |
| **L2** | recipes bind **modulators** (Rule 2); obsolescence; recipes that unlock new regions of the search space; transmission with mutation |

**Progress must not be monotonic.** A civilization can discover something extraordinary, lose
it, rediscover it centuries later, improve on it, or find an alternative that makes the
original irrelevant. This is not a feature — it falls out of prerequisite chains plus knowledge
loss plus the possibility of disjoint paths to the same capability.

Because L2 recipes bind modulators, a single breakthrough can change the meaning of every other
primitive. That is the mechanism behind the industrial-revolution-shaped events we refuse to
implement directly.

---

### P9 — Contagion

Anything that propagates through a network. One implementation, many instances.

| Level | Content |
|---|---|
| **L0** | fixed transmission rate, fixed effect |
| **L1** | incubation, duration, resistance, distinct transmission networks per contagion |
| **L2** | mutation into strains; **partial resistance** (resistant to one variant, susceptible to a modified one); active suppression and protection; contagions binding modulators |

A contagion may be a disease, belief, religion, technique, fashion, rumour, political idea, or
behavioural norm. They differ by parameters, never by module.

**Partial resistance is the important one** — it is what makes ideas behave like evolving
organisms rather than a diffusion process, and it is what makes suppression a losing strategy
in some regimes and a winning one in others.

A cure is a recipe whose modulator targets a contagion parameter. Some diseases become
manageable rather than eliminated; that distinction is a modulator magnitude, not a design
decision.

---

### P10 — Drift

The world does not change at a constant rate.

| Level | Content |
|---|---|
| **L0** | constant slow drift |
| **L1** | a spectrum of processes: slow trends, cyclical, accelerating, and heavy-tailed shocks |
| **L2** | interruption and regime change; degradation coupled to extraction (P1) and aggregate action (P11) |

```
slow degradation ──────────────→ threshold ──→ sudden resource collapse
stable ──→ increasing variance ──→ extreme event ──→ transformed regime
```

Rare high-impact shocks — low probability, enormous consequence — are drawn from a heavy-tailed
distribution rather than scheduled. The world must contain both **historical continuity and
genuine discontinuity**: hundreds of years of incremental adaptation, then one event that
changes the trajectory.

---

### P11 — Coupling

Where most of the genuinely surprising behavior comes from.

| Level | Content |
|---|---|
| **L0** | individual extraction sums into a shared stock |
| **L1** | **delayed effects** — an action schedules a consequence at tick T+k |
| **L2** | **accumulators with thresholds** — many small actions cross a tipping point; effects at generational timescale |

```
action ──→ immediate effect
       └──→ delayed effect (T+k)
       └──→ accumulator ──→ threshold ──→ regime change
```

The essential property: **agents need not understand these relationships.** A farmer changing
one practice notices nothing; ten thousand farmers independently doing so transform an
ecosystem. One agent discovering an obscure recipe looks insignificant until another combines
it with something else decades later.

This is what produces nonlinear causality, feedback loops, tipping points, path dependence, and
unintended consequences — none of which are implemented.

**Architectural requirement:** L1 and L2 need a **pending-effects queue** — scheduled effects
and threshold accumulators — which must be captured in checkpoints or forking silently breaks.
*(→ [D-025](DECISIONS.md#d-025), [06-data-model.md](06-data-model.md))*

---

### L3 — the open-ended depth levels

Three primitives gain a fourth level, added in response to the critiques in
[13-related-work.md](13-related-work.md). L3 differs from L0–L2 in kind: **L0–L2 make a primitive
richer; L3 makes it unbounded.** These are the levels that let the world's structure grow rather
than only its state.

---

#### P1ᴸ³ — Substance

Resources stop being a fixed set of kinds and become **substances with generated property
vectors**. New substances can come into existence through agent action.

```
Substance s:
  props[D]      generated property vector (D ≈ 8):
                hardness · density · conductivity · reactivity ·
                stability · workability · energy_density · toxicity
  origin        natural | product_of(process, inputs)
  abundance     spatial distribution — NULL if synthetic
```

**Usefulness is computed from properties, never assigned.** A substance is good for a purpose
because its property vector suits it, so a material nobody valued can become critical the moment
a process needs its particular profile. This is P1ᴸ²'s "effective scarcity" taken to its
conclusion.

**The trade-off manifold is what prevents runaway.** Property vectors lie on a constraint surface
— improving hardness costs toughness, improving conductivity costs stability. There is no
substance that maximizes everything, which is both physically honest and the reason the design
space stays interesting rather than collapsing to one optimum. *(→ [D-042](DECISIONS.md#d-042))*

---

#### P8ᴸ³ — Process and artifact

Recipes become **processes over property vectors**, and their outputs become **artifacts that can
enable further processes**.

```
Process p:
  arity         number of input substances
  transform     props_out = f_p(props_in…)    ← generated per world
  requires      conditions · tool artifacts · energy
  yield         < 1  — conservation
  energy_cost

Artifact a:
  substance     what it is made of
  form          structure vector, from a recipe
  function      derived from (props, form) — computed, never authored
  durability    degrades with use
  enables[]     processes this artifact makes possible  ← modulator binding
```

The last field is the important one. **A tool is a modulator with a physical instantiation.** That
produces the recursion the design has been missing:

```text
   artifact enables process → process yields better substance →
   better substance makes better artifact → enables further processes → …
```

You need a furnace to make the metal that makes a better furnace. Nothing about that ladder is
authored — it falls out of processes being functions and artifacts binding modulators.

**Why this is unbounded:** if properties are continuous and `f_p` are functions rather than lookup
tables, the reachable substance space has no enumerable limit. Agents expand the world's state
space by acting in it. That is mechanism K
*(→ [03-mechanisms.md](03-mechanisms.md#k-endogenous-environment-growth))*.

##### Stepping stones — the constraint that decides whether any of this works

Avida's result on the EQU function is the relevant warning: a complex feature evolved **only when
simpler intermediate features were also rewarded.** Without intermediate rungs, it never appeared.

A randomly generated process space is almost certainly too sparse to bootstrap. With arity-2
combinations over N substances, the useful fraction is minute and nothing ever reaches the second
rung.

So the generator carries an explicit **ladder density** hyper-parameter: the fraction of
discoveries that open at least one further reachable discovery conferring some benefit.

> Ladder density is likely **the single most consequential parameter in the project** for whether
> technology happens at all. It is the first thing to sweep at E0, before anything else.

*(→ [D-043](DECISIONS.md#d-043))*

---

#### P2ᴸ³ — Record

Information becomes **externalized**: it exists outside any mind, survives its author, and is a
physical object subject to every other primitive.

```
Record r:
  medium        durability · capacity · copy_cost · access_cost   (generated)
  encoding      which signal system it is written in  ← itself a P8 recipe
  content[]     proposition refs · recipe refs · value refs
  fidelity      how accurately content was captured
  location      physical — occupies space, can be seized (P7), claimed (P5)
  copies        instances elsewhere
```

Four mechanics carry most of the weight:

**Reading requires the encoding.** Notation is a recipe that must itself be transmitted. Lose it
and every record written in it becomes inert — physically intact, informationally dead. Linear A,
for free, from machinery already in the design.

**Retrieval cost scales with corpus size.** Unless indexing processes are discovered, a large
archive is *worse* than a small curated one. Knowledge that exists but cannot be found is not
knowledge, and this is a genuine bottleneck rather than a decorative one.

**Compression is a process.** A recipe taking K records to one denser record with some loss is a
textbook. It is the multiplier on cumulative culture — the mechanism behind standing on shoulders
rather than re-deriving.

**Survival is redundancy.** N copies in M locations, maintained by pledge-clusters (P4) that
outlive their founders. Libraries are institutions, not buildings.

**Connection to the Chronicle Gap:** high-fidelity media preserve *errors* as faithfully as
truths. A wrong record copied accurately for five centuries behaves very differently from an oral
tradition drifting, and it is the mechanism behind E2's rigidity arm — the reason better
record-keeping might make a society *less* adaptive rather than more.
*(→ [03-mechanisms.md](03-mechanisms.md#l-the-archive--externalized-memory))*

**Gate:** S4 for P1ᴸ³/P8ᴸ³ (forward models needed to plan multi-step production), S6 for P2ᴸ³
(records are pointless without social learning to consume them).

---

### P12 — Valuation

**The first interior primitive.** P1–P11 describe the world outside the agent. P12 describes
what the agent *wants* — and it is a primitive rather than a policy detail because morality,
altruism, greed, philosophy, and personal transformation all derive from it and from nothing
else.

#### Why this does not violate D-007

The obvious objection: giving an agent a "fairness" value hard-codes a moral philosophy, and
[D-007](DECISIONS.md#d-007) says the only fitness is offspring. The resolution is that **the
fitness function and the agent's reward function are different objects.**

```text
        OUTER:  offspring          ← selection acts here, and only here
                   ↑
        evolved value vector       ← genome-primed, life-mutable, socially transmissible
                   ↑
        internal reward signal     ← what the policy actually learns against
                   ↑
        INNER:  behavior           ← what we observe
```

Evolution selects on offspring. What an agent *pursues* is an evolved proxy that correlated
with fitness in its ancestors' environment — exactly how human values work. Nobody consciously
maximizes descendants; we value sweetness, status, and reciprocity because those tracked fitness
once. D-007 holds: no fitness function anywhere mentions cooperation, morality, or complexity.
*(→ [D-026](DECISIONS.md#d-026))*

#### Structure

| Level | Content |
|---|---|
| **L0** | single scalar reward = energy. Effectively no valuation |
| **L1** | value vector `v[K]` (K ≈ 8–16), genome-primed; internal reward is a weighted function of observable outcomes |
| **L2** | values mutable within a lifetime via experience-driven plasticity; socially transmissible via P9; contradictory values held simultaneously |

```
ValueVector (generated dimensions, not authored ones):
  v[K]           weights over outcome channels
  plasticity[K]  how readily each shifts with experience  (genetic)
  salience[K]    context-dependent activation
```

**The dimensions are generated, not named.** We do not write `fairness`, `loyalty`, `purity`.
The generator samples K outcome-channels from what the world makes observable — own energy,
others' energy, kin outcomes, reciprocation history, group-relative standing, adherence to
pledges, deviation from observed norms. Whether the resulting cluster deserves a human name is
the Historian's problem, never the core's. *(→ [D-027](DECISIONS.md#d-027))*

#### What derives from it

| Behavior | Derives from |
|---|---|
| altruism | positive weight on others' outcome channels |
| greed | high own-accumulation weight persisting past sufficiency |
| envy | weight on *group-relative* standing rather than absolute |
| pride | weight on reputation channel (P3) |
| wrath | threat-channel weight × episodic memory of harm |
| sacrifice | others'/kin channel outweighing own-survival channel |
| loyalty | relationship-specific salience surviving negative episodes |
| moral transformation | L2 plasticity moving `v` across a lifetime |
| internal conflict | no action scoring well across all K dimensions at once |

**The seven deadly sins are not seven variables.** They are names humans give to regions of
value space. Same rule as war and revolution: interpretation lives in the detector layer.

#### The Value Gap

Because values are a proxy, they can come apart from what actually produces offspring — and
we hold ground truth on both sides. That divergence is the psychological twin of the Chronicle
Gap and is measurable per-agent and per-population
*(→ [03-mechanisms.md](03-mechanisms.md#g-the-value-gap--conviction-vs-fitness))*.

**Gate:** S3 for L1 (values need memory to attach to outcomes), S5 for L2 (transformation
requires modelling other agents to be socially transmissible). Requires P3ᴸ¹ and P9ᴸ¹.

---

## Derivation: phenomena from primitives

Everything below emerges from combinations of the twelve. None of these words appear in the
simulation core. Depth level noted where a phenomenon needs more than L0.

| Phenomenon | Derives from |
|---|---|
| alliances & coalitions | P4 + P3 + P7 *(threat is what makes allies worth having)* |
| rivalries & conflict | P1 + P3 + P7 |
| war & peace | P7 + P6 *(groups acting as one)* + P4 *(treaties)* |
| diplomacy & negotiation | P4ᴸ² + P2 *(you don't know their real strength)* + P7 |
| trade & economic competition | P5 + P1 + regional heterogeneity |
| game-theoretic decision-making | P3 + repeated interaction — not built, *appears* |
| political struggle | P6 + revocation cost |
| governance & state-building | P6ᴸ² + P4-referencing-P4 + P7 |
| bureaucracy & principal-agent drift | P6ᴸ² *(revocation cost ∝ accumulated authority)* |
| migration | P1 + P10 + P2 |
| cultural exchange | P9 + migration |
| technological innovation | P8 *(combinatorial search)* |
| new ideas & inventions | P8 + P9 |
| exploration & discovery | P2 — this is *the* primitive for it |
| resource competition/cooperation | P1 + P11 |
| resource booms & busts | P1ᴸ¹ *(rising extraction cost)* + P11ᴸ² |
| technological substitution | P1ᴸ² + P8ᴸ² *(modulators)* |
| disease outbreaks & cures | P9 *(the disease)* + P8 *(the cure)* |
| endemic vs. eradicated disease | P9ᴸ² *(partial resistance)* + modulator magnitude |
| scientific discovery | P8 + latent physics + P2 |
| environmental change & adaptation | P10 + P11 |
| ecological tipping points | P10ᴸ² + P11ᴸ² *(accumulators)* |
| dark ages & rediscovery | P8ᴸ² *(non-monotonic progress)* + knowledge loss |
| industrial-revolution-shaped events | P8ᴸ² modulators cascading into P1, P7, P2 |
| social movements & revolutions | P9 + mass P6-revocation |
| rise & fall of civilizations | all, through P11 |
| espionage & information sharing | P2ᴸ² + P3 + P5 over information |
| propaganda & deception | P2ᴸ² *(cheap unverified signals)* + S5 |
| individual vs. group competition | P4 + P7 + free-riding on P11 |
| unintended consequences | P11 — that is its definition |
| altruism & sacrifice | P12ᴸ¹ + P3 *(motive separated by ablation, not by declaration)* |
| greed & exploitation | P12ᴸ¹ + P1 scarcity + P7 |
| sin-shaped behavior *(pride, envy, wrath…)* | P12ᴸ¹ regions + P3 reputation — named in the detector layer only |
| moral transformation | P12ᴸ² plasticity + biographical experience |
| worldviews & philosophies | P12ᴸ² + P2 beliefs + P9 transmission — detected as clusters, never authored |
| inequality & social mobility | dynamic cognition + P1 + P5 *(the capability feedback loop)* |
| internal conflict & dilemma | P12ᴸ¹ — automatic once values are multidimensional |
| corruption by power | P12ᴸ² + P6ᴸ² *(value drift conditional on accumulated authority)* |

---

## Four derivations worth internalizing

### Contagion is one code path that gives six systems

A disease, a religion, a farming technique, a panic, a fashion, and a rumour are the same
object. **Implement it once.** Plague and the Reformation differ by parameters, not by module.
The single largest leverage point in the design.

### A cure is just a recipe

Combinatorial search (P8) for a recipe whose modulator happens to target a contagion parameter.
Identical code to inventing a better axe. Epidemiology and medicine come free the moment
technology exists.

### Revolution is a revocation cascade

An idea spreads by contagion (P9) until enough agents simultaneously revoke their delegations
(P6). We never write "revolution" — we *detect* it. What makes cascades tip is left to the
world to answer.

### War is an arithmetic comparison

War happens when expected cost of coercion falls below expected cost of negotiation. Peace
treaties are pledges that raise the first term. No diplomacy module — but agents must
*estimate both numbers*, which is a hard constraint on intelligence.

---

## Gating: primitives and depth are both gated by policy

Handing agents a coercion primitive while their policy is a weighted sum of six genes produces
**random violence, not war** — noise that superficially resembles the phenomenon, which is
worse than nothing because it looks like success.

| Primitive | Min stage for L0 | Min stage for L2 |
|---|---|---|
| P1 Scarcity, P10 Drift | S0 | S4 *(substitution needs forward modelling)* |
| P2 Fog | S1 | S5 *(deception needs opponent models)* |
| P3 Identity | S3 | S3 |
| P9 Contagion | S3 | S3 |
| P5 Claim, P8 Recipe | S4 | S5 |
| P4 Pledge, P6 Delegation, P7 Coercion | S5 | S5 |
| P11 Coupling | any *(it operates regardless)* | — *(understanding it needs S4+)* |
| P12 Valuation | S3 *(values need memory to attach to outcomes)* | S5 *(transmission needs opponent models)* |

**Do not add a primitive or a depth level before its gate.** It will "work" and produce
garbage. A config violating a gate must fail loudly at load, never run badly.

---

## The freeze protocol

Generators keep the swept surface small, but it still must be frozen deliberately.

1. Add exactly one primitive, or raise exactly one primitive by one depth level.
2. Run a viability sweep to find its habitable band *(→ [08-experiments.md](08-experiments.md#2-viability-sweep))*.
3. Lock the defaults into `configs/frozen/`. Record the freeze in [DECISIONS.md](DECISIONS.md).
4. Add its detectors and confirm they fire against a null.
5. Only then take the next step.

A frozen parameter is unfrozen only when it is the explicit variable of an experiment, and
re-freezes when that experiment ends.

**Generator hyper-parameters are swept; generated structure is never swept.** If you find
yourself wanting to tune an individual resource's extraction curve, the generator is wrong —
fix the distribution, not the instance.

**Expect degeneracy to be the default.** With everything switched on, most configurations
collapse to "one strategy eats the world by year 300" or "everyone dies by year 40." Finding
habitable regions will consume more time than analyzing them. That is the actual shape of the
work, and the strongest argument for generators over raw parameters: **twelve generator knobs
is a searchable space; a hundred and sixty-five is not.**
