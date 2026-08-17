# Decision Record

Every settled design decision, its rationale, and what was rejected. **This is the most
valuable file for restarting cold** — it prevents re-litigating questions that are already
answered, and records *why* an obvious-looking alternative was not taken.

Format: `D-nnn` · status · decision · why · rejected alternatives.
Status is `settled`, `open`, or `superseded by D-nnn`.

---

<a id="d-001"></a>
### D-001 · settled · The product is a corpus of worlds, not a world

Optimize for worlds-per-dollar, not fidelity. The unit of scientific work is a sweep — N
worlds, one variable changed, an effect size at the end.

**Why:** a single trajectory has no counterfactual, so nothing can be attributed to anything.
Every other invariant (determinism, event sourcing, array state, forkability) is downstream of
this one choice.

**Rejected:** one high-fidelity world with rich per-agent detail and a live inspection UI —
the default shape of this genre, and the reason the genre produces demos instead of findings.

*(→ [01-vision.md](01-vision.md))*

---

<a id="d-002"></a>
### D-002 · settled · Primitives, not phenomena

Implement twelve primitives — eleven world, one interior. Never implement "war," "trade," or "government." No phenomenon
name appears anywhere in `src/core/`.

**Why:** a list of historical phenomena is an output spec. Implementing "war" as a war system
yields a system that does exactly what was written and never surprises anyone. The eleven
primitives derive all 30 target phenomena.

**Rejected:** a module per phenomenon (readable, fast to demo, produces zero emergence); a
hybrid where "hard" phenomena get modules (the hybrid always expands).

*(→ [02-primitives.md](02-primitives.md))*

---

<a id="d-003"></a>
### D-003 · settled · No English inside the core; LLMs only at the boundary

The simulation speaks numbers. LLMs appear only as Historian (narrative from logs) and Analyst
(hypotheses from metrics).

**Why:** if agents are LLMs and they invent democracy, that is recall, not emergence — the
model read about democracy. Results become uninterpretable.

**Rejected:** LLM agent policies. Permitted later *only* as an explicitly labelled
experimental condition A/B'd against a numeric baseline, never as the default substrate.

*(→ [01-vision.md](01-vision.md), [04-intelligence.md](04-intelligence.md))*

---

<a id="d-004"></a>
### D-004 · settled · One shared network per lineage, not one per agent

All agents in a lineage share a network. Individuality comes from a per-agent genome embedding
plus a per-agent plastic layer.

**Why:** a tick becomes one batched forward pass. This is the only reason 1,000 agents × 32
worlds is feasible. Per-agent networks break batching and determinism.

**Rejected:** per-agent networks with per-agent optimizers — multi-agent RL with 10,000
non-stationary learners and constant birth/death is a research project that would consume the
civilization project.

*(→ [04-intelligence.md](04-intelligence.md#architecture-one-shared-network-not-ten-thousand))*

---

<a id="d-005"></a>
### D-005 · settled · Structure-of-arrays from commit #1; worlds are a batch axis

Agents are columns, not objects — even in A1, where a list of objects would be easier.

**Why:** once state is arrays, adding a worlds axis is one extra dimension, which means GPU,
which means the marquee experiments run overnight instead of never. Retrofitting SoA later
means rewriting every mechanism.

**Rejected:** object-oriented agents with a "we'll vectorize later" plan. Later never arrives
cheaply.

*(→ [05-architecture.md](05-architecture.md#i4--array-state))*

---

<a id="d-006"></a>
### D-006 · settled · The Chronicle Gap is the project's distinctive bet

Maintain ground truth and agent belief as separate stores. Instrument their divergence.

**Why:** we have ground truth sitting right there, which no empirical historian ever does.
Nobody appears to instrument belief-versus-truth cleanly in a simulated society. It is the
most likely source of a genuinely novel result, and it makes the best visualization.

**Rejected:** agents reading world state directly (simpler, and forecloses the entire result).

*(→ [03-mechanisms.md](03-mechanisms.md#a-the-chronicle-gap--belief-vs-truth-measured))*

---

<a id="d-007"></a>
### D-007 · settled · The only fitness is offspring

Never reward cooperation, trade, technology, or complexity.

**Why:** the moment the fitness function mentions the phenomenon under study, the experiment is
circular and the result is worthless. Cooperation must earn its way in by producing more
surviving children.

**Rejected:** shaped rewards to "speed up" emergence. They do speed it up — into a result that
means nothing.

*(→ [04-intelligence.md](04-intelligence.md#the-cheat-vectors))*

---

<a id="d-008"></a>
### D-008 · settled · Evolution outer loop + local plasticity inner loop; not PPO

Evolution shapes shared weights across generations; a genome-encoded local plasticity rule
adapts within a lifetime.

**Why:** gradient-free, trivially parallel, robust to non-stationarity, and indifferent to
agents dying mid-episode. It is also the Baldwin structure — genome as prior, lifetime as
adaptation.

**Rejected:** PPO/A2C per agent (breaks batching and determinism, episode boundaries are
ill-defined when the episode is a life). Gradient RL is retained as a *later experimental
condition*, not a default.

*(→ [04-intelligence.md](04-intelligence.md#training-two-loops))*

---

<a id="d-009"></a>
### D-009 · **open** · Is the S4 planner learned or hand-written?

A hand-written planner over a *learned* forward model may be acceptable as an
architecture-level primitive (level 1), or it may be strategy leakage (level 3).

**Considerations:** hand-written planning is cheap and interpretable, but "how to plan" is
arguably part of intelligence and therefore should be discovered. Leaning toward hand-written
short-horizon rollout with an evolved horizon parameter — the horizon being genetic keeps the
trade-off under selection.

**Blocking:** C2. Must be resolved before the forward model ships.

---

<a id="d-010"></a>
### D-010 · settled · Level-of-detail decisions must be deterministic

Promotion/demotion of regions between full simulation and aggregate integration is a pure
function of world state — never of available compute, wall clock, or machine load.

**Why:** LOD is the most likely way invariant I1 gets broken, and a compute-dependent LOD makes
runs irreproducible across machines with no visible symptom.

**Rejected:** adaptive LOD driven by a frame/time budget.

*(→ [05-architecture.md](05-architecture.md#scale-strategy))*

---

<a id="d-011"></a>
### D-011 · settled · Detector before mechanism

No mechanism is built until its detector, null model, threshold, and unit tests exist.

**Why:** it is the only defense against emergence theater, it forces the observable to be
defined before the thing that produces it, and the detectors become the Atlas chapter markers
for free.

**Rejected:** build-then-measure — the natural order, and how "it looks alive" substitutes for
knowing anything.

*(→ [07-detectors.md](07-detectors.md))*

---

<a id="d-012"></a>
### D-012 · settled · The freeze protocol

Add one primitive → viability sweep → lock defaults in `configs/frozen/` → add detectors →
next primitive. Unfreeze only when a parameter is an experiment's explicit variable.

**Why:** twelve primitives × ~5 parameters is a ~60-dimensional space that cannot be swept.
Freezing makes it searchable.

**Rejected:** global tuning across all parameters (intractable); leaving parameters free
"for flexibility" (guarantees results are artifacts of tuning).

*(→ [02-primitives.md](02-primitives.md#the-freeze-protocol))*

---

<a id="d-013"></a>
### D-013 · settled · The Atlas reads a digest, never live state

Sim writes Chronicle → digest builder produces ~5 MB of ~2,000 downsampled frames → Atlas
reads only that.

**Why:** nothing rendered may ever slow a run; 10 GB of events cannot reach a browser; and the
Atlas can be built against synthetic digests before the simulator exists, which pins the
schema early.

**Rejected:** live streaming from a running sim (couples the two, slows runs, and makes the
viewer useless for the corpus, which is the actual product).

*(→ [09-visualization.md](09-visualization.md))*

---

<a id="d-014"></a>
### D-014 · settled · Interventions are typed, never arbitrary code

Forks apply one of a fixed set of typed interventions (`RESOURCE_SHOCK`, `SET_TRUTH`, …).

**Why:** untyped interventions are not reproducible, which destroys the counterfactual
guarantee that makes forking scientifically useful. Typing also lets God mode in the Atlas
reuse the exact same path.

**Rejected:** a callback that mutates world state at the fork point.

*(→ [06-data-model.md](06-data-model.md#interventions-typed))*

---

<a id="d-015"></a>
### D-015 · settled · Primitives are gated by intelligence stages

A config enabling a primitive past its stage gate fails loudly at load.

**Why:** giving coercion to an agent with a six-gene reactive policy produces random violence
that superficially resembles war — worse than nothing, because it looks like success.

**Rejected:** enabling everything and letting evolution sort it out. It does not sort it out;
it produces noise that passes a casual glance.

*(→ [02-primitives.md](02-primitives.md#gating-primitives-and-depth-are-both-gated-by-policy))*

---

<a id="d-016"></a>
### D-016 · settled · Cognition costs energy

Hidden units, memory slots, and planning horizon all draw metabolic energy per tick.

**Why:** without a cost, intelligence is free and cannot be selected against, which makes the
whole intelligence layer inert. With it, intelligence is an evolutionary trade-off — and the
variability threshold where brains start paying for themselves becomes a real experiment.

*(→ [04-intelligence.md](04-intelligence.md#brains-must-cost-energy))*

---

<a id="d-017"></a>
### D-017 · settled · Parquet + DuckDB, no database server

Chronicle as Parquet shards on disk; analysis as SQL over files.

**Why:** full-corpus queries for free with zero infrastructure, and the corpus stays portable
and inspectable. A server is operational overhead with no benefit at this scale.

**Rejected:** Postgres/TimescaleDB (server ops); raw NumPy dumps (unqueryable); SQLite
(poor columnar scan performance over a large corpus).

---

<a id="d-018"></a>
### D-018 · **superseded by [D-046](DECISIONS.md#d-046)** · Python/NumPy first, JAX second

Core in NumPy SoA, with the state layout designed so a JAX backend could drop in without touching
mechanism code.

**Superseded because:** the target hardware is an 8 GB fanless M1 Air. There is no GPU backend and
there will not be one *(→ [00-feasibility.md](00-feasibility.md))*. **What survives:** the SoA
layout, which is now justified by CPU world-batching rather than by a future GPU.

**Rejected:** Rust core from day one (premature; optimizes the wrong axis; slows the phase
where design churn is highest).

*(→ [11-engineering.md](11-engineering.md#stack))*

---

<a id="d-019"></a>
### D-019 · settled · `CONCEPT.md` superseded by `docs/`

The original concept document has been absorbed into `docs/` and deleted. `docs/README.md` is
the entry point; [01-vision.md](01-vision.md) carries the thesis and
[03-mechanisms.md](03-mechanisms.md) carries the signature mechanisms.

**Why:** two overlapping sources of truth diverge, and the concept doc predated the primitives,
intelligence, and visualization designs.

---

<a id="d-020"></a>
### D-020 · settled · Depth enters through generators, not config surface

Richness is *structure that exists*, not *knobs a researcher tunes*. One or two hyper-parameters
control a distribution from which many heterogeneous entities are drawn — twelve resource kinds
with sampled extraction curves, not twelve hand-configured resources.

**Why:** twelve primitives at full depth is ~180 raw parameters, which no sweep survives. With
generators the swept surface stays at roughly one knob per primitive while generated depth goes
arbitrarily deep. Two worlds sharing a generator setting and differing in seed have genuinely
different economies — which is exactly what the corpus needs.

**Constraint:** generator output is part of world identity and must be reconstructible from
`(config, seed)` alone. Never sample lazily mid-run — it breaks I1.

**Rejected:** exposing full depth as raw config (unsweepable, and guarantees results are
artifacts of tuning); keeping primitives shallow to stay sweepable (loses the phenomena we want).

*(→ [02-primitives.md](02-primitives.md#rule-1--generators-richness-is-structure-not-parameters))*

---

<a id="d-021"></a>
### D-021 · settled · Cross-primitive influence is one modulator table

A discovery making a material valuable (P8→P1), a technology reducing fog (P8→P2), a weapon
changing coercion economics (P8→P7), writing lowering record decay (P8→beliefs), and an ideology
shifting behavior (P9→policy) are all the same mechanism. Every primitive exposes named
parameters; recipes and contagions bind `Modulator{source, target, fn, magnitude, scope}`.

**Why:** implemented separately these are ~20 scattered special cases — phenomenon-coding by
another name, and the exact drift D-002 exists to prevent. One table makes "technology
transforms everything" a single code path.

**Key property:** *which* modulators exist is generated per world from the seed. Different
worlds have different technological consequences, which is what makes path dependence real
rather than decorative.

**Rejected:** hard-coded effect hooks per technology (unmaintainable, and authored); a global
"tech level" scalar modulating everything uniformly (destroys divergence between worlds).

*(→ [02-primitives.md](02-primitives.md#rule-2--modulators-cross-primitive-influence-is-one-mechanism))*

---

<a id="d-022"></a>
### D-022 · settled · Depth is gated by policy capacity, exactly like breadth

D-015 gated *which primitives* exist by intelligence stage. It now also gates *how deep* each
one goes. Build the structure to hold full richness; populate only what the current stage can
distinguish; widen when a detector shows agents using the width.

**Why:** a seven-slot rights vector given to an S4 agent produces an agent that uses two slots
and ignores five — while all seven cost compute and observation width. Unused richness is not
neutral; it is a tax that also makes results harder to interpret.

**Canonical case:** P5 ships with two populated rights (use, exclude) and five structural.

*(→ [02-primitives.md](02-primitives.md#rule-3--depth-is-gated-by-policy-capacity-exactly-like-breadth))*

---

<a id="d-023"></a>
### D-023 · settled · No `deceive()` action — deception must be available, not provided

Signals are cheap and unverified. Lying is therefore *possible*; whether it is selected for is
a finding.

**Why:** a deception action is a strategy at level 3 leaking into architecture at level 1
*(→ [04-intelligence.md](04-intelligence.md))*. The interesting question is under what
conditions deception pays, and providing it as a primitive answers that question by fiat.

**Requires:** S5. Below that, agents cannot model what a receiver will believe.

---

<a id="d-024"></a>
### D-024 · settled · Coercion expands its action space, not its resolution function

Full action taxonomy (steal, damage, displace, blockade, impose cost, capture, coerce behavior).
Resolution stays a simple, transparent function of two or three state variables.

**Why:** an eleven-factor combat formula gets tuned until battles "feel right," at which point
outcomes are authored rather than emergent — a hard-coded historical system wearing a
primitive's clothes. Terrain, supply, and surprise should matter because agents can *act* on
them, not because they are weighted terms we calibrated.

**Rejected:** a rich combat resolution model incorporating morale, supply, preparation, and
terrain as formula terms.

*(→ [02-primitives.md](02-primitives.md#p7--coercion))*

---

<a id="d-025"></a>
### D-025 · settled · Multi-timescale causality is one pending-effects queue

Delayed effects, accumulators, threshold crossings, and generational consequences are served by
a single scheduled-effects structure: an effect registered for tick T+k, plus accumulators that
fire on threshold.

**Why:** P10ᴸ² and P11ᴸ¹⁻ᴸ² both require it, and the tick loop otherwise assumes everything
resolves within the current tick. One mechanism, two primitives.

**Constraint:** the queue and all accumulator states must be captured in checkpoints. An
omitted queue makes forks diverge from their parents with no visible symptom — the most
dangerous class of determinism bug.

*(→ [02-primitives.md](02-primitives.md#p11--coupling), [06-data-model.md](06-data-model.md))*

---

<a id="d-026"></a>
### D-026 · settled · Values are an evolved proxy reward; fitness is still offspring

The fitness function and the agent's reward function are **different objects**. Evolution selects
on offspring (D-007, unchanged). What an agent *pursues* is a genome-primed value vector that
correlated with fitness ancestrally. The policy learns against the value-derived reward; selection
never sees it.

**Why:** without this, P12 directly violates D-007 and every result about morality is circular.
With it, morality, altruism, greed, and philosophy become studiable while the fitness function
still mentions nothing but offspring. It is also how human values demonstrably work — nobody
consciously maximizes descendants.

**Consequence:** values can come apart from fitness, and we hold ground truth on both sides. That
divergence is mechanism G *(→ [03-mechanisms.md](03-mechanisms.md#g-the-value-gap--conviction-vs-fitness))*,
and it is structurally the inner/outer alignment problem — agents are mesa-optimizers by
construction.

**Rejected:** a scalar `morality` variable (collapses a multidimensional thing and hard-codes an
ethics); values as terminal goals selection acts on directly (circular); no values at all
(forecloses the entire layer).

*(→ [02-primitives.md](02-primitives.md#p12--valuation))*

---

<a id="d-027"></a>
### D-027 · settled · Value dimensions are generated, never named

The generator samples K outcome-channels from what the world makes observable — own energy,
others' outcomes, kin outcomes, reciprocation history, group-relative standing, pledge
adherence, norm deviation. We never write `fairness`, `loyalty`, `purity`, or the seven deadly
sins as fields.

**Why:** same rule as war and revolution. Naming a value dimension authors a moral psychology;
the interpretation belongs in the detector and Historian layers. It also means different worlds
can have different value dimensions, which is required for `worldview_novelty` to mean anything.

**Rejected:** Moral Foundations Theory or any other named-dimension scheme as the schema. Useful
as an *interpretive lens* over generated dimensions; fatal as the generator.

---

<a id="d-028"></a>
### D-028 · settled · Cognition is a state variable that develops over a lifetime

Decompose into `potential → learning capacity → knowledge → reasoning → competence`. Only
`potential` is genetic; the rest is state shaped by nutrition, teaching, security, stress, and
problem complexity.

**Why:** it produces the capability feedback loop, which makes inequality and social mobility
*measurable outcomes* rather than parameters. Mobility rate becomes a detector, not a setting.

**Gate:** S3. Keeps D-016 intact — a developed brain costs more to run.

*(→ [04-intelligence.md](04-intelligence.md#cognition-is-a-state-variable-not-a-genome-constant))*

---

<a id="d-029"></a>
### D-029 · settled · No named cognitive biases

Bad reasoning emerges from resource limits — bounded memory, small samples, finite planning
depth, cheap imitation, no global consistency check. There is no `confirmation_bias` parameter.

**Why:** a list of named biases is phenomenon-coding with a psychology textbook instead of a
history textbook, and fails identically — you get exactly the bias you wrote, and learn nothing
about when it appears.

**Notable consequence:** nothing enforces belief consistency, so agents can hold contradictory
propositions indefinitely. That is a feature, and it is free.

---

<a id="d-030"></a>
### D-030 · settled · Motives are separated by ablation, never by declaration

Identical altruistic behaviors are decomposed into reputation / reciprocity / kin / delayed
self-interest / residual by running matched forks that ablate each instrumental channel.
"Genuine" altruism is defined operationally as the residual.

**Why:** declared motives are unavailable (no English in the core) and reading motive off the
value vector is circular. Counterfactual signatures are the only non-circular evidence, and
forking is what makes them available.

**Critical detail:** ablations are applied **at a fork**, never as a birth condition. An agent
*raised* unobserved develops different values; an agent that suddenly *acts* unobserved does not.
Confusing the two answers a different question.

*(→ [03-mechanisms.md](03-mechanisms.md#h-motivational-archaeology--separating-identical-behaviors))*

---

<a id="d-031"></a>
### D-031 · settled · "Emergent human stories" is replaced by a blind test

The project's most ambitious goal is restated as E17: human raters sort Historian-rendered agent
life-summaries from real biographical summaries, both through the same prose pipeline. Endpoint
is rater accuracy.

**Why:** "stories that feel surprisingly human" cannot come back negative, and an unfalsifiable
goal at the top of the project licenses unfalsifiable claims below it. Chance-level rater
accuracy is a real result; "it felt human to me" is not.

**Confound to control:** the Historian's prose quality. Both arms must render through the same
pipeline or the test measures writing rather than lives.

---

<a id="d-032"></a>
### D-032 · settled · Stagnation is the object of study, not the failure to avoid

`plateau_height` and `time_to_plateau` are measured dependent variables. We do not set
open-endedness as a goal.

**Why:** stagnation is what this design *predicts* — D-007 plus D-016 means exploration is a
metabolic tax on a solved problem, so selection removes curiosity at equilibrium. And open-ended
evolution is unsolved: Tierra, Avida, Polyworld, Geb, four decades of artificial life, all
plateau. Setting an unachievable and unfalsifiable target at the top of the project would license
unfalsifiable claims below it.

**What this buys:** every outcome becomes a result. "Populations stagnate at complexity C after T
generations under condition X" is a finding; so is "condition Y had not plateaued within our
horizon." It is the comparative-corpus thesis applied to the project's own central worry.

**Rejected:** treating stagnation as a bug to patch (invites hand-added curiosity, which is
D-011's failure mode wearing a new hat); claiming open-endedness as an objective.

*(→ [03-mechanisms.md](03-mechanisms.md#i-the-stagnation-problem--and-why-we-study-it-rather-than-solve-it))*

---

<a id="d-033"></a>
### D-033 · settled · Discovery payoffs are heavy-tailed, and exploration rate is evolved not reasoned

Most discoveries are worthless; rare ones are transformative. Exploration rate is a genetic
coefficient under lineage selection, never a quantity an agent computes.

**Why:** with thin tails, agents correctly estimate low returns and exploration dies — correctly,
which is worse than a bug. With heavy tails, individual expected value stays low while lineage
expected value is high, **and no agent can perceive the difference**, because rare events are rare
and any obtainable sample underestimates the mean.

The consequence is the important part: **a rational agent will always under-explore a heavy-tailed
distribution it cannot sample.** Curiosity therefore cannot be sustained by inference. It must be
sustained by selection operating on a distribution individuals cannot see — which is, as far as
anyone can tell, how it works in humans.

**Rejected:** an intrinsic-novelty reward term (reward shaping, violates D-007 in spirit); a
`curiosity` parameter (phenomenon-coding).

---

<a id="d-034"></a>
### D-034 · settled · Curiosity is attention allocation, not a parameter

Given S2 plasticity proportional to prediction error plus finite attention, well-modeled domains
stop consuming attention and it flows to unmodeled ones. Boredom is a consequence of the learning
rule, not an addition to it.

**Why:** it costs nothing — the machinery exists at S2 — and the attention-shift rate is a
coefficient in the plasticity genome, so *how curious a lineage is* becomes evolvable without ever
being specified.

**Rejected:** `creativity = 0.83` with periodic idea generation.

*(→ [04-intelligence.md](04-intelligence.md#curiosity-is-attention-not-a-parameter))*

---

<a id="d-035"></a>
### D-035 · settled · Selection scores lineages over a multi-generation window

The outer evolutionary loop uses geometric mean fitness across generations, not arithmetic mean
within one.

**Why:** bet-hedging is invisible to arithmetic-mean selection, which removes exploration wherever
it lowers expected offspring. Geometric-mean selection over long horizons can retain it, because a
lineage that never explores is one environmental shift away from zero.

**Cost:** cheap from B1, expensive to retrofit — the scoring window shapes the entire outer loop.

---

<a id="d-036"></a>
### D-036 · settled · Intelligence is measured as predictive compression

`model_compression` — observations predicted by the population's collective models, per unit of
model — is the primary intelligence metric and the primary stagnation detector.

**Why:** something must be measured to detect stagnation at all, but it need not be
anthropocentric. Compression rises when agents find better theories and is indifferent to whether
those theories look like science to a human reader. It is the least human-shaped measure
available.

It is also the S7 model-comparison criterion, which matters: choosing "elegance" or "simplicity as
we perceive it" would hardcode an epistemology. Relativity beats Newton on compression without
anyone having to specify what a good theory looks like.

**Known limit:** our detectors are human-designed, so genuinely alien cognitive strategies may be
invisible to the entire suite. Partial mitigation is to weight the suite toward general measures
(compression, prediction, novelty rate, model turnover) over specific ones ("does this look like
doing science"). *(→ [12-risks.md](12-risks.md))*

---

<a id="d-037"></a>
### D-037 · settled · S7 model criticism is a distinct architectural rung

Representing a model *as an object*, generating structural alternatives, and holding a competing
model provisionally is a capability S0–S6 does not have and cannot approximate.

**Why:** paradigm change is not optimization. Newtonian gravity was not broken; relativity did not
come from practical failure. Questioning a framework that *works* requires the framework to be
representable, which is a representational capacity rather than a parameter.

**Expected outcome:** S7 is selected *against* wherever the current paradigm is adequate —
structural search is far more expensive than parameter search and usually worse in the short run.
That is the stagnation problem one level up, and engines 1 and 4 of mechanism I are what could
sustain it. E21 is the joint test.

*(→ [03-mechanisms.md](03-mechanisms.md#j-model-criticism--questioning-a-framework-that-works))*

---

<a id="d-038"></a>
### D-038 · settled · Environment co-evolution via niche construction, not environment generation

Agents grow the world's structure by creating substances (P1ᴸ³) and processes (P8ᴸ³) that did not
exist at init, plus an unbounded procedurally-generated spatial frontier.

**Why:** POET showed sustained open-ended progress needs environments to co-evolve. But POET
mutates environments and keeps those neither trivial nor impossible — **a designer's judgment about
what makes an environment interesting**, which is reward shaping one level up and would break the
non-circularity D-007 protects.

Niche construction (Odling-Smee, Laland) achieves environment growth with no external arbiter. If
substance properties are continuous and processes are functions rather than lookup tables, the
reachable space has no enumerable limit and agents expand it by acting.

**Rejected:** POET-style environment mutation with a novelty or difficulty criterion; a
hand-authored tech tree with more branches (same problem, less honest).

*(→ [03-mechanisms.md](03-mechanisms.md#k-endogenous-environment-growth), [13-related-work.md](13-related-work.md#critique-1--fixed-environments-may-structurally-cap-the-plateau))*

---

<a id="d-039"></a>
### D-039 · settled · Mechanism C gains a transmission-bottleneck axis

Communication sweeps two variables: channel capacity **and** data-per-learner-per-generation.

**Why:** iterated learning shows compositionality emerges from a *learnability* pressure —
learners see a fraction of the data and must generalize — not primarily from channel width. Our
original single axis was, on the evidence, the less important one. Cheap to fix now, expensive
after B2 hardens.

*(→ [13-related-work.md](13-related-work.md#critique-2--mechanism-c-targets-channel-capacity-not-the-transmission-bottleneck))*

---

<a id="d-040"></a>
### D-040 · settled · Diversity comes from spatial structure, never from novelty selection

Partial connectivity, geographic isolation, and migration maintain population diversity. We do not
select for novelty.

**Why:** novelty search outperforms objective-driven search on deceptive problems, and D-007 is
maximally objective-driven — so the critique lands. But selecting for novelty *is* reward shaping:
the system would optimize for what we find interesting and every emergence result becomes circular.

Spatial structure is how biology avoids the monoculture our design invites, it is a
population-structure choice rather than a reward, and Derex & Boyd's result — partial connectivity
beating full connectivity for cumulative culture — says it pays on the cultural side too.

**Rejected:** novelty search, quality-diversity archives (MAP-Elites), any explicit diversity
bonus.

*(→ [13-related-work.md](13-related-work.md#critique-3--d-007-is-precisely-the-condition-novelty-search-says-fails))*

---

<a id="d-041"></a>
### D-041 · settled · Measure both compression and evolutionary activity statistics

`model_compression` is the intelligence metric; Bedau's evolutionary activity statistics are the
open-endedness metric.

**Why:** compression is defensible but incomparable to prior work. Activity statistics are
established and situate our plateau against Tierra, Avida, and Polyworld — which is what makes a
negative result publishable rather than merely private.

---

<a id="d-042"></a>
### D-042 · settled · Substance properties lie on a trade-off manifold

No substance maximizes every property. Improving hardness costs toughness; improving conductivity
costs stability.

**Why:** without it, unbounded material creation is unbounded `RUNAWAY` — agents find the
dominating substance and the design space collapses to one optimum. With it, different purposes
want different regions of the manifold, which keeps specialization and trade meaningful at every
technology level. It is also physically honest.

**Companion constraints:** process yields below one, and energy costs that scale with property
improvement.

---

<a id="d-043"></a>
### D-043 · settled · Ladder density is an explicit generator parameter

The process-space generator carries a hyper-parameter controlling the fraction of discoveries that
open at least one further reachable, beneficial discovery.

**Why:** Avida's EQU result — a complex feature evolved *only* when simpler intermediates were also
rewarded, never without them. A randomly generated process space over N substances is almost
certainly too sparse to bootstrap, and if it is, every downstream technology experiment measures
nothing while appearing to run correctly.

**Consequence:** E22 runs before every other E0 experiment. This is plausibly the most
consequential single parameter in the project.

---

<a id="d-044"></a>
### D-044 · settled · Ecological inheritance is a third channel

Adaptation decomposes into genetic, cultural, and **ecological** inheritance — the transformed
world offspring are born into.

**Why:** niche construction theory contributes it, it is nearly free to measure (the difference
between the world a cohort was born into and the one its parents were), and it is likely the
largest channel exactly in the runs where technology took off — the case we most want to explain.

*(→ [04-intelligence.md](04-intelligence.md#two-inheritance-channels))*

---

<a id="d-045"></a>
### D-045 · settled · Transmission bias is genetic, not chosen

Who an agent copies — prestige, success, conformity, kin — is a vector of evolved coefficients.

**Why:** the cultural evolution literature finds the bias matters more than the copying, and each
bias produces a characteristic pathology: prestige bias copies causally-irrelevant behavior
(ritual accumulates), conformist bias locks in maladaptive traditions.

**The consequence that matters:** conformist bias is a *second* engine of the Chronicle Gap,
operating on the copier rather than the medium. E2's answer may depend more on `β_conformity` than
on record decay rate, which would relocate the mechanism entirely.

**Rejected:** a single `imitation_rate`; hand-chosen biases per population.

---

<a id="d-046"></a>
### D-046 · settled · NumPy on CPU only; no GPU backend

The core runs on NumPy through Accelerate. No JAX/Metal, no PyTorch MPS.

**Why:** the target machine is an 8 GB fanless M1 Air. `jax-metal` is immature, MPS gives little
for this workload shape, and the scale that motivated a GPU backend (1,000 worlds × 10k agents) is
unreachable regardless. Supersedes the JAX half of [D-018](DECISIONS.md#d-018); the SoA layout
stays, so a backend can still be added if the project ever moves to different hardware.

**Cost accepted:** corpus size drops to 32–64 worlds per batch and 500–2,000 agents per world.

*(→ [00-feasibility.md](00-feasibility.md))*

---

<a id="d-047"></a>
### D-047 · settled · Tiered logging is mandatory, not an optimization

Chronicle events are always-logged, sampled, aggregated, or snapshotted. Target ≤ 50 MB per
world-run.

**Why:** a naive log at 1,000 agents over 100k ticks is ~2 GB **per world**. On 8 GB of unified
memory the Chronicle hits the ceiling long before the simulation does — it is the binding
constraint on the whole project.

**Consequence for detectors:** every detector must be computable from sampled and aggregated data.
A detector needing every movement event needs redesigning, and that constraint should be applied
when the detector is written, not discovered later.

---

<a id="d-048"></a>
### D-048 · settled · A live viewer is permitted as a development tool

A throwaway viewer may read sampled live state at low frequency on runs flagged non-scientific.
It is never in the measurement path and its output is never evidence.

**Why:** [D-013](DECISIONS.md#d-013) — the Atlas reads digests, never live state — is correct for
the science and removes something genuinely enjoyable from a hobby project. This narrows the rule
rather than breaking it: the science still runs on digests.

**Guard:** runs with the viewer attached are marked in `meta.json` and excluded from the corpus
index.

---

<a id="d-049"></a>
### D-049 · settled · Level of detail is cut

No promotion/demotion between full simulation and aggregate integration.

**Why:** LOD only pays above ~10k agents, which this hardware cannot reach. It was also the most
likely way invariant I1 breaks *(→ [D-010](DECISIONS.md#d-010))*. Removing it deletes a whole class
of determinism bug for free.

**Status of D-010:** retained as a rule in case LOD ever returns; currently moot.

---

<a id="d-050"></a>
### D-050 · settled · The roadmap is ordered by payoff, not only by dependency

Stages that produce something worth showing are pulled as early as their dependencies allow — the
Historian at month one rather than month seven, the fingerprint wall in week three.

**Why:** this is a hobby project with no external deadline. The dominant failure mode is
abandonment, not incorrectness, and a roadmap that defers all satisfaction to month twelve
maximizes that risk. Ordering by payoff costs nothing scientifically: the gating rule
*(→ [D-011](DECISIONS.md#d-011))* is unchanged, and every stage still ships a detector and a null.

*(→ [10-roadmap.md](10-roadmap.md))*

---

<a id="d-051"></a>
### D-051 · settled · Regeneration needs a recolonization term; zero must not be absorbing

P1's regrowth is `dR = (1 - R/K) * (rate * R + seed_rain * K)`, not the pure logistic
`dR = rate * R * (1 - R/K)`.

**Why:** pure logistic makes zero an absorbing state — a cell stripped bare has zero growth and
stays empty forever. Measured in A0 at the default settings: 98% of cells hit zero within 50 ticks,
total resource then never moved again, and every world died. No parameter choice fixed it; they
only changed the date. That is not a harsh world, it is a broken one, and it would have made the
entire simulation a countdown rather than a history.

`seed_rain` represents recolonization from beyond the cell — a seed bank, a neighbouring patch, a
migrating population. It vanishes at capacity, so abundance stays bounded and worth competing for.
Adding it moved a 12-point viability scan from uniformly EXTINCT to uniformly VIABLE.

**Consequence at L1:** regeneration classes become meaningful rather than cosmetic. A `finite`
resource sets `seed_rain` to zero *on purpose*, and then exhaustion really is permanent — which is
the entire point of having regeneration classes.

**Rejected:** tuning extraction rates instead. The absorbing state is structural; no rate avoids it.

*(→ [02-primitives.md](02-primitives.md#p1--scarcity))*

---

<a id="d-052"></a>
### D-052 · settled · The Chronicle samples agents, not agent-ticks

The sampled tier keys its 1-in-K decision on `agent_id` alone. A sampled agent is logged for its
entire life; an unsampled one is never logged.

**Why:** keying on `(tick, agent_id)` scatters the samples. Measured in A0: 4.83 positions per
agent spread across a 191-tick lifespan — isolated snapshots with no two consecutive. Path
straightness, and every other trajectory-based detector, is uncomputable from that. Keying on the
agent follows a cohort from birth to death **at identical row cost**. A cohort you can follow beats
a scatter you cannot.

**Cost accepted:** the cohort is fixed rather than refreshed, so rare events among unsampled agents
are missed. Population-level rates must therefore never come from the sampled tier — they come from
the aggregated tier, which is where they already belonged.

**Constraint retained:** sampling still consumes no randomness. It is a hash, not a draw, so
changing `log_tier` cannot change what happens *(→ [D-047](DECISIONS.md#d-047))*.

*(→ [06-data-model.md](06-data-model.md#chronicle-the-event-log)) · verified by `test_log_tier_invariance`*

---

<a id="d-053"></a>
### D-053 · settled · Fixed-shape RNG draws are sized by config constants, not by capacity

Every random draw is at a shape fixed by `(config, seed)` — never by the living population. Where
that shape would be wastefully large, a config constant bounds it: mutation noise is drawn at
`[worlds, birth_cap, genes]` rather than `[worlds, agent_capacity, genes]`.

**Why:** the discipline exists because a draw sized by population makes stream position depend on
how many agents happen to be alive, so a fork diverges from its parent the moment the populations
differ by one — silently, with no symptom. But drawing at full capacity cost 2.3 ms per tick to
generate 256,000 numbers for roughly sixty births, a sixth of the whole tick budget. `birth_cap`
keeps the rule and drops the waste, and doubles as a cap on explosive growth.

*(→ [11-engineering.md](11-engineering.md#determinism-rules)) · verified by `test_noop_fork`*

---

<a id="d-054"></a>
### D-054 · settled · Raw effect and z are reported together; z is never plotted alone

Every sweep result reports the raw effect size, the z against the null, and the sample size `n`.
`tools/plot_sweep.py` renders raw and z side by side and refuses to do otherwise.

**Why:** z is an effect divided by a null width, and null width shrinks with sample size.
Population is an *outcome variable* here, so any swept parameter that moves population moves every
sample size and therefore every z-score — independently of behavior.

Measured in `a1-patchiness`: z rose monotonically with patchiness at *r = 0.97*, precisely the
predicted dose-response. It was entirely an artifact of population falling from 442 to 79, which
cut logged windows from 367k to 63k and tightened the null accordingly. The raw effect was flat
within one between-seed standard deviation and never changed sign. Reported as z alone, this would
have been a confident, publishable-looking, wrong result.

**Consequence:** "the effect grew" is a claim about the raw statistic. z answers only "is it
distinguishable from chance *at this sample size*", which is a different question and is not the
one a dose-response curve is asking.

*(→ [07-detectors.md](07-detectors.md#never-plot-z-alone-across-a-sweep))*

---

<a id="d-055"></a>
### D-055 · settled · Behavioral coupling constants in a policy are config, not literals

Any constant in a policy that conditions one behavior on another — the degree to which hunger
sharpens gradient-following, for instance — is a named config parameter, never a numeric literal.

**Why:** a detector must never be measuring a number hidden in the policy. `directed_foraging`
came out robustly negative in A1, and the leading explanation was a `0.25` sitting in
`choose_action` that made sated agents weigh the resource gradient less, so hungry agents steered
by a noisy gradient while sated agents coasted straight. With the constant buried, that hypothesis
could only be argued. As a parameter it can be swept to zero effect and *tested*.

**The general form:** at S0 the policy necessarily has structure, and every piece of that structure
is a claim about behavior that we made rather than evolved. Those claims must be visible and
falsifiable. Where a structural constant proves load-bearing, the next stage should evolve it
rather than set it.

*(→ [04-intelligence.md](04-intelligence.md), `experiments/a1-hunger-coupling/`)*

---

<a id="d-056"></a>
### D-056 · settled · A detector must not condition on a variable its behavior influences

No detector conditions the behavior it measures on a state variable that behavior affects. Energy,
health, wealth, population, and knowledge are all *downstream of action*; splitting behavior by any
of them and reading the difference causally inverts the arrow.

**Why:** `directed_foraging` was specified as "path straightness when energy < threshold" and came
out robustly backwards — hungry agents *less* straight — in 39 runs across two experiments. The
cause was not the policy, which was tested and eliminated. It was that **straight movement causes
satiation**: extraction empties a cell, so an agent travelling straight keeps entering fresh ground
while one that doubles back re-crosses what it stripped. Straightness correlates with energy
*gained* (+0.224) at over twice the strength of energy *held* (+0.102). The detector conditioned on
the outcome and reported it as the cause.

**A null model does not fix this.** The shuffled null permuted hunger labels within each agent,
which controls for differences between agents — but the confound is within-agent and temporal, and
permutation destroys exactly the ordering that carries it. Any null built by permutation has this
blind spot.

**The test to apply when writing a detector:** could the behavior I am measuring have *produced*
the variable I am splitting on? If yes, either condition on something upstream (a genome value, a
world property, a fixed cohort) or measure the decision directly rather than its consequences.

*(→ [07-detectors.md](07-detectors.md#detector-contract), `experiments/a1-hunger-coupling/`)*

---

<a id="d-057"></a>
### D-057 · settled · Determinism is guaranteed within a platform, not across instruction sets

Invariant I1 means: a run is a pure function of `(config, seed)` **on a given platform**. Golden
hashes are recorded per platform (`darwin-arm64`, `linux-x86_64`), and `test_cross_machine` asserts
each platform against its own.

**Why:** CI failed on the first push, exactly where
[11-engineering.md](11-engineering.md#ci-gate) predicted. Per-stage hashes then located it
precisely: **`world_init` already differs, before a single tick runs.** The cause is `np.exp` in the
resource-field generator — SIMD transcendental implementations differ in the last ulp between NEON
and AVX, and numpy dispatches to whichever the machine has.

Bit-identical float across instruction sets requires eliminating every transcendental from the
core. That is achievable today, where only `exp` is used, but it would forbid `tanh`, `sigmoid`,
and `exp` in the S1 neural policy — the cost lands on the whole future of the project, to buy a
property nothing currently needs.

**Nothing this project does crosses machines.** Forking, checkpointing, replay, and every
comparison within a corpus happen on one machine. Cross-ISA identity would be reassuring; it is not
load-bearing.

**What the gate still does, and it is most of the value:** each platform is checked against its own
recorded hashes at three stages, so the day a code change silently alters results *on the machine
you actually use*, CI says so. The per-stage split also means the next divergence gets located
rather than guessed at.

**Corollary retained:** the matmul in the policy was removed anyway
*(`obs @ masks.T` → fixed-order slice sums, 12% slower)*. BLAS chooses its summation order per
platform, so it was a second, independent source of the same problem — one that would have
surfaced later, on top of this one, and been much harder to isolate.

**Open:** whether to buy cross-ISA determinism by replacing the Gaussian blob with a
compact-support polynomial bump and the softmax with an exp-free sampler. Cheap now, constraining
later. Revisit if the corpus ever needs to be produced on more than one machine.

*(→ [11-engineering.md](11-engineering.md#determinism-rules))*

---

<a id="d-058"></a>
### D-058 · settled · The Chronicle logs the decision context, so nulls can be derived rather than simulated

Where a detector needs to judge a choice, the core logs **what the agent perceived when it chose** —
not a verdict about the choice. `PERCEIVE` carries the score of the direction taken, the mean of the
four on offer, and the best of the four.

**Why those three:** they make the null *exact*. An agent ignoring the gradient picks uniformly, so
its expected chosen score **is** the mean of the four — therefore `chosen − mean` has expectation
exactly zero, conditional on the landscape, for any landscape, with nothing to simulate and no
distributional assumption. Dividing by `best − mean` puts perfect gradient-following at 1.0 and
makes the statistic comparable across worlds of different richness.

**Why this matters beyond one detector.** [D-056](DECISIONS.md#d-056) killed `directed_foraging`
with a confound its permutation null could not see, and *every* permutation null shares that blind
spot: permutation preserves whatever it does not disturb. A null whose centre is derived has no
structure left to preserve. Prefer a designed control over a shuffle wherever the arithmetic allows
one — `referential_validity` is the same pattern.

**The line this does not cross.** Logging perception is not logging a measurement. The Chronicle
records what the agent saw; whether that adds up to foraging is the lens's question, and the lens
still has to combine perception with choice and compare against the null. A `FORAGED_WELL` event
would be the circular version, and is exactly what the no-phenomenon-names rule forbids.

**Cost accepted:** one extra sampled-tier row per logged agent-tick, roughly a third more Chronicle
volume at the sampled tier. Cheap against a detector whose null cannot be argued with.

*(→ [07-detectors.md](07-detectors.md#the-null-model-catalogue), `schemas/events.md`)*

---

## Open questions

Tracked here so they are not mistaken for oversights. Each blocks a specific version.

| ID | Question | Blocks |
|---|---|---|
| [D-009](#d-009--open--is-the-s4-planner-learned-or-hand-written) | S4 planner: learned or hand-written? | C2 |
| — | Lineage granularity: per species, per culture, or per region? | D0 |
| — | Which plasticity-rule family is expressive enough to be interesting but small enough to evolve? | B1 |
| — | Can opponent modeling (S5) be amortized across a population rather than per-target? | Phase F |
| — | `known_mask` at `bool[N,H,W]` will dominate memory. Chunk, share per-lineage, or store sparsely? | B0 |
| — | Does the Chronicle Gap need per-agent beliefs, or are per-record beliefs sufficient? | C0 |
| — | Should modulators be composable (two recipes stacking on one parameter), and if so with what combination rule? Multiplicative is the obvious default but may compound explosively | E0 |
| — | Can generated modulator sets be constrained so most worlds are viable, without hand-authoring the tech consequence graph? | E0 |
| — | What is the right accumulator granularity for P11ᴸ² — per-cell, per-region, or per-resource-kind? Finer is more realistic and much more expensive | C2 |
| — | Does non-monotonic technology (P8ᴸ²) need explicit obsolescence, or does it fall out of prerequisite chains plus knowledge loss alone? | E0 |
| — | Should the shared network take the active modulator set as an explicit input, so policies condition on which world they are in rather than re-adapting? Arguably a free sense organ; arguably just noticing iron got cheap | E0 |
| — | How many value dimensions (K)? Too few collapses moral diversity; too many is dead richness and unsweepable. Needs `value_dimensionality` data before committing | D0 |
| — | Are relationship *types* (parent, rival, teacher) emergent clusters in interaction-history space, or a small typed enum? Emergent is more honest and much more expensive | D0 |
| — | Can `value_conflict` be computed cheaply enough to run every tick, or only on a sampled subset? It is the drama scalar and also a full pass over the action set | D0 |
| — | Does P12ᴸ² value transmission need its own contagion instance, or is it a P9 effect channel? Probably P9 — but the effect channel is a value *vector*, not a scalar | D0 |
| — | How is `model_compression` computed when agents' models are distributed policy weights rather than explicit symbolic structures? Needs a concrete estimator before it can be the primary metric | E0 |
| — | What is the right multi-generation window for lineage scoring (D-035)? Too short reverts to arithmetic mean; too long makes selection too weak to act | B1 |
| — | Can S7 structural search be made cheap enough to ever be selected for, or does it require explicit protection (a subsidised minority of structural searchers)? Protection would be reward shaping | Phase F |
| — | Is `long_fuse` detectable without retaining the full provenance chain forever? If not, the Chronicle can never be compacted | E0 |
| — | Do the four engines of mechanism I interact additively or multiplicatively? E18 sweeps them individually; the interaction may be where the answer lives | Phase F |
| — | Do conservation laws (D-042) actually bound substance creation, or can agents find unbounded property-improvement loops through multi-step processes? Needs adversarial search before E0 | E0 |
| — | Can ladder density be generated without implicitly authoring a tech tree? A generator that guarantees reachable ladders may be hand-designing the ladder | E0 |
| — | Does the unbounded spatial frontier break batching? Procedural regions keyed to coordinates conflict with fixed-size world arrays | Phase F |
| — | Can the belief store (P2ᴸ¹) fit the memory budget at 1,000 agents, or does it need per-region rather than per-agent beliefs? The N×M blowup is the likeliest place Phase D stalls | Phase D |
| — | Is 32 worlds enough seeds for the effect sizes we care about, or do sweeps need to run sequentially overnight to reach 100+? Depends on effect magnitudes we cannot yet estimate | Phase A |
| — | How are records represented in the digest so the Atlas can show archive growth without shipping the corpus? | Phase F |
| — | Is invariance detection an S-rung of its own, or a component of S4's forward model? It is cheap enough that a separate rung may be over-engineering | E2 |
| — | For transplantation (E27), how different can two worlds be before the comparison is meaningless rather than informative? Needs a world-distance metric | Phase F |
