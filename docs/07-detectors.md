# 07 — Detectors and Null Models

## Why this document exists

> **No new mechanism without a detector.**

Before building trade, write down the number that proves trade is happening and the null it
must beat. If you can't, you aren't ready to build trade.

This inverts the usual order — normally you build a thing and then wonder how to measure it,
which is how "emergence theater" happens: the world looks alive, the screenshots are great,
and nothing is known. Detectors written *first* also become the Atlas chapter markers for free
*(→ [09-visualization.md](09-visualization.md))*.

**The rule extends to depth.** Raising a primitive from L0 to L1 is a full freeze-protocol step
and requires its own detectors *(→ [02-primitives.md](02-primitives.md#the-freeze-protocol))*.
Richness that nothing measures is richness that cannot be justified.

---

## Detector contract

Every detector is a pure function over the Chronicle. No detector reads live state.

```python
def detect(chronicle, window) -> Firing | None:
    """
    Returns magnitude, confidence, tick range, and involved entity ids.
    Must be deterministic and side-effect free.
    """
```

Every detector ships with:

| Required | Why |
|---|---|
| **definition** | the exact computation, in terms of event types |
| **null model** | what "this happening by chance" looks like |
| **threshold** | the effect size above null that counts as a firing |
| **replication unit** | what one independent observation is — and it is almost never one agent |
| **unit test** | a synthetic log where it must fire, and one where it must not |

A detector without a null model is not a detector. It is a plot.

**A detector with only a null model is not enough either** *(→ [D-064](DECISIONS.md#d-064))*.
`directed_foraging` had a null. It beat that null in 39 runs, across six parameter levels and five
seeds, and was measuring the wrong thing. The null answers *is this chance?*; it does not answer
*am I measuring what I think I am measuring?*, and every claim this project has withdrawn failed on
the second question while passing the first.

The two additional obligations, both cheap and both learned the expensive way:

**Name the replication unit before computing anything.** A thousand agents in one world is N=1.
Stating the cluster in the detector's docstring forces the question early; discovering it late cost
`gradient_ascent` a z of 90.8 that was really 4.93 *(→ [D-058](DECISIONS.md#d-058))*.

**Any causal claim ships a control, not just a null.** A null asks what chance produces. A control
asks what the *world without the mechanism* produces, and only the second can distinguish selection
from drift *(→ [D-059](DECISIONS.md#d-059))*. Two arms are then compared on raw effect, never on z
*(→ [D-060](DECISIONS.md#d-060))*.

### Never condition on a variable the behavior influences

*(→ [D-056](DECISIONS.md#d-056))* Before writing a detector that splits behavior by agent state,
ask: **could the behavior I am measuring have produced the variable I am splitting on?**

Energy, health, wealth, population, and knowledge are all downstream of action. `directed_foraging`
was specified as "path straightness when energy < threshold" and came out backwards in 39 runs,
because straight movement *earns* energy — extraction empties a cell, so travelling straight keeps
finding fresh ground. The detector conditioned on the outcome and reported it as the cause.

**A null model does not save you here.** A permutation null controls for differences between
agents; this confound lives within an agent, across time, and permutation destroys the ordering
that carries it. Every permutation-based null shares that blind spot.

Condition on something upstream instead — a genome value, a world property, a fixed cohort — or
measure the decision directly rather than its consequences.

### Score one run at several windows before running a longer one

A detector that accepts a tick window turns "is this result length-limited?" into a **paired**
comparison — same worlds, same seeds, same landscapes, only the observation window differs — instead
of a comparison between two sets of worlds that differ in everything. With between-world spread
around ten to one here, the paired version is not merely cheaper, it is the only one with the power
to answer.

It settled the question it was built for at **zero simulation cost**: A1's advantage magnitude grows
1.5–1.8× between a quarter-length window and the full run, while its correlation with patchiness
stays between −0.87 and −0.93 with no trend. The *level* was length-dependent and the *slope* was
not *(→ `experiments/a1-run-length/`)*.

It also gives a free check on clustering. If z barely moves while the number of scored rows grows
fivefold, the statistic is clustered on the right unit; if z tracks the row count, it is
[D-054](DECISIONS.md#d-054) happening again.

### The four routes to a confident wrong number

All four were found in Phase A. Three of them survive a correct null model, which is why the
contract above asks for more than one.

| Route | Mechanism | What it did here |
|---|---|---|
| **Sample-size leak** | the statistic scales with n, and n correlates with the swept parameter | a dose-response curve at r = 0.97 that meant nothing *(→ [D-054](DECISIONS.md#d-054))* |
| **Endogenous conditioning** | the detector conditions on a variable the measured behavior *causes* | 39 runs, conclusion inverted *(→ [D-056](DECISIONS.md#d-056))* |
| **Pseudo-replication** | correlated within-cluster observations counted as independent | z 90.8 → 4.93 on clustering *(→ [D-058](DECISIONS.md#d-058))* |
| **Variance homogenization** | the intervention under test shrinks between-replicate spread, inflating its own z | control arm: 2.7× smaller effect, 10× larger z *(→ [D-060](DECISIONS.md#d-060))* |

The fourth generalizes furthest and is the least intuitive: **the more thoroughly a control removes
the mechanism, the more significant it can look.** Any manipulation that homogenizes replicates
inflates its own z, because z divides by the between-replicate spread that the manipulation just
collapsed.

A fifth route lives outside the lens entirely, in the Atlas: a sort order or a marker can
manufacture the appearance of structure with no statistic attached to catch it
*(→ [D-063](DECISIONS.md#d-063))*. The discipline is the same and the defenses are not automatic
there, because nothing computes a z for a rendering choice.

---

## The null model catalogue

| Null | Construction | Kills the claim that… |
|---|---|---|
| **Shuffled** | permute event subjects, preserve marginals | structure exists beyond base rates |
| **Memoryless** | agents with episodic memory disabled | reciprocity requires remembering |
| **Mute** | communication channel zeroed | coordination requires signalling |
| **Random-role** | roles assigned at random, matched distribution | specialization is real |
| **Spatial-scramble** | shuffle cell contents, preserve totals | geography matters |
| **Drift-only** | no agent actions, world dynamics alone | agents caused the change |
| **Frozen-policy** | learning disabled after tick T | adaptation is ongoing, not initial |
| **Random-search** | discovery by uniform sampling of the combination space | search is directed |
| **No-modulator** | modulators disabled, base parameters held | technology changed the world |
| **Instant-effect** | pending queue drained immediately | delay produced the outcome |
| **Random-delegation** | delegation edges rewired at random, degree preserved | hierarchy has structure |
| **Thin-tail** | discovery payoffs from a thin-tailed distribution | heavy tails sustain exploration |
| **Random-model** | models with matched parameter count, randomly structured | compression reflects understanding |
| **No-heredity** | children get freshly drawn genes; composition pinned at the founding distribution *(→ [D-059](DECISIONS.md#d-059))* | selection caused the change, rather than the world drifting |
| **Blind-choice** | *derived, not simulated*: an agent ignoring its options picks uniformly, so its expected chosen score **is** the mean of what was on offer | the choice used the information available |

Rule of thumb: the null should be the *most flattering* alternative explanation you can
construct. If the claim survives that, it survives.

---

## Detector suite

Mapped to the phenomena in [02-primitives.md](02-primitives.md). `⌛` marks detectors whose
primitive or depth level is not yet built — listed so the definition is settled in advance.
Depth requirements noted as `P1ᴸ²` where relevant.

### Population & space

| Detector | Definition | Null |
|---|---|---|
| `pop_stability` | population bounded, non-monotonic, over ≥20 seeds | drift-only |
| `migration_wave` | net directional flux of agents between regions above baseline | spatial-scramble |
| ~~`directed_foraging`~~ | ~~mean path straightness when energy < threshold~~ — **withdrawn**, conditions on an outcome of the behavior *(→ [D-056](DECISIONS.md#d-056))* | shuffled |
| `gradient_ascent` | `(chosen − mean) / (best − mean)` over the four perceived directions, from `PERCEIVE` events | **blind-choice** |
| `exploration_rate` | distinct P2 blocks a path touches, per agent-tick | **shuffled-step** |

### Scarcity & economy

| Detector | Definition | Null |
|---|---|---|
| `specialization` | drop in self-produced share of consumption | random-role |
| `trade_network` | flow-graph modularity + persistence of edges | shuffled |
| `inequality` | Gini of inventory value | shuffled |
| `effective_scarcity_gap` ⌛ | divergence between `effective_scarcity` and `physical_stock` — P1ᴸ² | drift-only |
| `extraction_spiral` ⌛ | rising marginal cost driving migration or abandonment of a deposit — P1ᴸ¹ | drift-only |
| `substitution_event` ⌛ | consumption shifting from resource A to B following a discovery — P1ᴸ² | no-modulator |
| `resource_boom` ⌛ | order-of-magnitude rise in a resource's extracted volume within a short window | no-modulator |

`effective_scarcity_gap` is the detector that proves P1ᴸ² is doing its job: physical quantity
unchanged, effective scarcity transformed.

### Cooperation & exchange

| Detector | Definition | Null |
|---|---|---|
| `cooperation_rate` | fraction of `TRANSFER` events with no immediate reciprocal | memoryless |
| `reciprocity` | correlation between give(A→B) and later give(B→A) | shuffled |
| `reputation_effect` | defection history predicts refusal to transact | memoryless |
| `hearsay_reputation` ⌛ | refusal predicted by *second-hand* beliefs only — requires `first_hand` flag, P2ᴸ¹ | memoryless |

`hearsay_reputation` separates reputation-by-experience from reputation-by-rumour. Without it,
the two are indistinguishable and the social half of the Chronicle Gap has nothing to grip.

### Communication

| Detector | Definition | Null |
|---|---|---|
| `signal_informativeness` | mutual information between signal and referent | mute |
| `compositionality` | topographic similarity of signal space vs meaning space | shuffled |
| `referential_validity` | **concept-vs-location test**: remap the world, does the signal follow the referent? | — (a designed control) |
| `dialect_divergence` | signal-distribution distance between populations over time | shuffled |
| `deception_rate` ⌛ | signals systematically diverging from sender's belief where it benefits the sender — P2ᴸ², S5 | shuffled |

### Information & epistemics ⌛

| Detector | Definition | Null |
|---|---|---|
| `epistemic_divergence` | distance between two populations' belief distributions over the same propositions | shuffled |
| `information_monopoly` | high-value proposition held by a small, stable set of agents | shuffled |
| `partial_knowledge` | propositions with some slots filled and others empty, persisting — P2ᴸ² | — |
| `stale_belief` | high-confidence beliefs whose truth changed ≥N ticks ago | — |

### Commitment & politics ⌛

| Detector | Definition | Null |
|---|---|---|
| `alliance` | pledge cluster whose members' coercion targets co-vary above chance | shuffled |
| `institution` | pledge-referencing-pledge cluster persisting beyond founder lifespans | — |
| `regime_type` | (concentration, reversibility) coordinates of the delegation graph | random-delegation |
| `revolution` | spike in `REVOKE` rate correlated with a meme crossing prevalence threshold | shuffled |
| `state_formation` | delegation cluster with monopoly on successful `COERCE` in a region | random-delegation |
| `conditional_pledge_depth` | nesting depth of active pledge expression trees — P4ᴸ² | shuffled |
| `principal_agent_drift` | delegate's accumulated authority exceeding what principals can afford to revoke — P6ᴸ² | random-delegation |

`principal_agent_drift` is how bureaucracy is measured rather than modelled: it fires when
revocation cost has grown past the principals' means.

### Conflict ⌛

| Detector | Definition | Null |
|---|---|---|
| `war` | sustained `COERCE` between two delegation clusters above baseline | shuffled |
| `peace_treaty` | pledge that measurably reduces subsequent coercion between clusters | shuffled |
| `deterrence` | coercion capacity correlates with *reduced* incoming coercion | shuffled |
| `espionage` | information acquired about non-adjacent regions above fog-limited baseline | drift-only |
| `coercion_repertoire` | distribution across the action taxonomy — is anything but `damage` used? P7ᴸ¹ | — |

`coercion_repertoire` is a **gate check**, not a phenomenon: if agents only ever use one action
from the taxonomy, the extra actions are dead richness *(→ [D-022](DECISIONS.md#d-022))*.

### Knowledge & technology ⌛

| Detector | Definition | Null |
|---|---|---|
| `discovery_rate` | first-time `RECIPE_DISCOVER` per capita per tick | random-search |
| `diffusion_rate` | time from discovery to N% knowledge prevalence | shuffled |
| `knowledge_loss` | recipes whose prevalence returns to zero | — |
| `rediscovery` | independent second discovery of a previously lost recipe | random-search |
| `tech_regression` | aggregate capability declining and later recovering — the dark-age signature | drift-only |
| `obsolescence` | recipe abandoned while still known, following an alternative's arrival — P8ᴸ² | no-modulator |
| `path_dependence` | variance in tech-discovery order across identical-config worlds | — |
| `law_recovery` | correlation of discovered Ĝ against true G across worlds | random-guess |
| **`modulator_cascade`** | a discovery whose modulators enable discoveries that enable further modulators, within a window — P8ᴸ² | no-modulator |

**`modulator_cascade` is the industrial-revolution detector.** We never implement an industrial
revolution; we detect the cascade signature and then ask what conditions produced it. This is
the clearest possible illustration of the governing principle.

### Contagion & belief ⌛

| Detector | Definition | Null |
|---|---|---|
| `outbreak` | infection prevalence crossing threshold with R > 1 | — |
| `cure_discovery` | recipe whose modulator targets a contagion parameter | random-search |
| `strain_escape` | a mutated variant spreading in a population resistant to its parent — P9ᴸ² | shuffled |
| `endemic_equilibrium` | contagion persisting at stable non-zero prevalence rather than burning out | — |
| `chronicle_gap` | `D(belief ‖ truth)` per proposition over time | — |
| `zombie_institution` | pledge/taboo still enforced ≥N ticks after its truth ceased | — |
| `myth_formation` | belief whose provenance chain exceeds K hops from any witness | shuffled |

`strain_escape` is what distinguishes contagion-as-diffusion from contagion-as-evolution. If it
never fires, P9ᴸ² is not earning its cost.

### Systemic & coupling ⌛

| Detector | Definition | Null |
|---|---|---|
| `commons_tragedy` | aggregate extraction exceeding regrowth while individual payoff stays positive | drift-only |
| `collapse` | population or tech level dropping >X% within Y ticks and not recovering | drift-only |
| `unintended_consequence` | global state change opposed by majority of contributing agents' local payoffs | — |
| `delayed_consequence` | effect at T+k traceable to actions at T via pending-queue provenance — P11ᴸ¹ | instant-effect |
| `tipping_point` | accumulator threshold crossing followed by a regime change in a detector that was previously stable — P11ᴸ² | instant-effect |
| `slow_then_sudden` | long low-variance period followed by rapid transition — P10ᴸ² | drift-only |

`tipping_point` requires the pending-effects provenance chain to be logged, or crossings cannot
be attributed to the actions that caused them.

---

### Psychology & valuation ⌛

Requires P12. The category where anthropomorphic reading is most dangerous — every detector
here measures **behavior or state**, never a narrative interpretation of it
*(→ [12-risks.md](12-risks.md))*.

| Detector | Definition | Null |
|---|---|---|
| `value_conflict` | dispersion of per-dimension scores across the available action set — the **drama scalar** | shuffled |
| `value_fitness_gap` | correlation between value-weighted outcome and realized offspring, over time — mechanism G | drift-only |
| `conviction_persistence` | value dimensions stable while their fitness correlation collapses | frozen-policy |
| `value_drift` | movement of an agent's `v` across its lifetime, beyond plasticity noise | frozen-policy |
| `transformation` | value drift exceeding threshold, attributable to an identifiable experience window | shuffled |
| `authority_drift` | value drift conditional on accumulated delegation authority — "power corrupts," measured | matched non-promoted agents |
| `worldview_cluster` | stable, transmissible, behaviorally-consequential clusters in belief×value space | **random value-vector clustering** |
| `worldview_novelty` | distance of a cluster's centroid from any human philosophical tradition's coordinates | — |
| `moral_disagreement` | two populations with high internal value coherence and low mutual coherence | shuffled |
| `relative_standing_weight` | behavior tracking *group-relative* rather than absolute outcome — envy's signature | shuffled |
| `sufficiency_violation` | accumulation continuing past the point of diminishing survival return — greed's signature | shuffled |
| `mobility_rate` | correlation between an agent's starting circumstance and its terminal competence | random-assignment |
| `capability_trap` | populations where the mobility correlation approaches 1 — the loop has locked | random-assignment |

`worldview_cluster` carries the strictest null in the entire suite, deliberately. The failure
mode here is seeing philosophies in noise the way people see faces in clouds, so a cluster must
beat random clustering of value vectors on **all three** of stability, transmissibility, and
behavioral consequence. Two out of three is not a philosophy.

### The altruism ablation battery ⌛

Not a detector but a **fork protocol** implementing mechanism H
*(→ [03-mechanisms.md](03-mechanisms.md#h-motivational-archaeology--separating-identical-behaviors))*.
Applied at a fork, never as a birth condition.

| Ablation | Fork intervention | Drop implicates |
|---|---|---|
| `abl_observed` | act rendered unwitnessed | reputation |
| `abl_reciprocal` | recipient's capacity to reciprocate removed | reciprocity |
| `abl_kin` | relatedness severed | kin selection |
| `abl_future` | expectation of further interaction removed | delayed self-interest |
| `abl_all` | all four simultaneously | **residual = internalized value** |

Reported as a **motive decomposition** — the share of altruistic acts attributable to each
channel — not as a binary verdict. A residual indistinguishable from zero is a legitimate and
publishable finding: this world produces no altruism that is not instrumental.

---

### Stagnation & open-endedness ⌛

The category that measures whether the project's central worry is happening. Per mechanism I,
**stagnation is the expected outcome** — these detectors quantify it rather than alarm on it.

| Detector | Definition | Null |
|---|---|---|
| **`model_compression`** | observations predicted by the population's collective models, per unit of model. **The primary non-anthropocentric intelligence measure** | random-model |
| `plateau_height` | asymptote of `model_compression` over a run | — |
| `time_to_plateau` | generations until `model_compression` slope falls below threshold and stays there | — |
| `exploration_rate` | fraction of actions with negative expected immediate return under the agent's own model | frozen-policy |
| `exploration_decay` | change in `exploration_rate` as environmental variance falls — does prosperity kill curiosity? | drift-only |
| `attention_shift` | reallocation of attention from low- to high-prediction-error domains | shuffled |
| `useless_discovery` | recipes discovered with no payoff at discovery time | random-search |
| `long_fuse` | a `useless_discovery` later combined into a high-payoff recipe ≥N generations afterward | random-search |
| `tail_realization` | share of total capability gain attributable to the top 1% of discoveries | thin-tail |
| `paradigm_shift` | replacement of a *structurally* different model that predicts a domain previously covered — S7 | `model_turnover` under parameter search only |
| `model_turnover` | rate at which models are replaced rather than refined | frozen-policy |
| `red_queen` | novelty rate sustained while material scarcity is low, tracking relative-standing competition | drift-only |
| `cognitive_regression` | brain cost declining across generations in a stable environment — evolving toward stupidity | drift-only |

`long_fuse` is the detector for the phenomenon most worth catching: an observation nobody valued,
preserved by accident, becoming the foundation of something transformative generations later. It
requires the Chronicle's provenance chain to reach back arbitrarily far, which is an argument
against ever compacting the log.

`cognitive_regression` is the alarm. If it fires across most seeds, the four engines of mechanism
I are not working and the honest response is to report that, not to add curiosity by hand.

**New null:** `thin-tail` — the same world with discovery payoffs drawn from a thin-tailed
distribution. It is the direct test of [D-033](DECISIONS.md#d-033).

---

### Substances, processes & artifacts ⌛

Requires P1ᴸ³ / P8ᴸ³. Measures mechanism K.

| Detector | Definition | Null |
|---|---|---|
| `substance_novelty` | rate at which substances not present at world init come into existence | random-search |
| `material_depth` | longest production chain from natural substance to terminal artifact | random-search |
| **`tool_bootstrapping`** | an artifact enabling a process that produces a superior version of that same artifact | no-modulator |
| `ladder_reachability` | fraction of discovered processes that opened at least one further reachable discovery | random-graph |
| `property_frontier` | expansion of the convex hull of achieved property vectors over time | drift-only |
| `trade_off_navigation` | artifacts specialized to different regions of the trade-off manifold rather than one optimum | random-role |
| `ecological_inheritance` | fraction of a cohort's realized environment attributable to prior generations' actions | drift-only |

`tool_bootstrapping` is the machine-makes-machine signature and the clearest evidence mechanism K
is working. `ladder_reachability` is the diagnostic when nothing bootstraps — a low value means the
generated process space is too sparse, not that agents are failing.

### Records & the archive ⌛

Requires P2ᴸ³. Measures mechanism L.

| Detector | Definition | Null |
|---|---|---|
| **`library_effect`** | does local record density predict subsequent discovery rate, controlling for population? | shuffled |
| `record_survival` | half-life of a record's content by medium and copy count | drift-only |
| `encoding_loss` | records physically intact whose notation recipe has zero prevalence | — |
| `retrieval_bottleneck` | discovery rate falling as corpus grows, absent indexing processes | shuffled |
| `compression_multiplier` | discovery-rate change following adoption of a record-compression process | no-modulator |
| **`error_fossilization`** | a false proposition maintained at high fidelity across ≥N generations of copying | shuffled |
| `fidelity_threshold` | the transmission fidelity at which cumulative knowledge switches from decaying to accumulating | — |

`error_fossilization` is the mechanism behind E2's rigidity arm: high-fidelity media preserve
mistakes as faithfully as truths. `fidelity_threshold` is a **phase transition**, which is the
shape of result the corpus is best at finding.

### Transmission bias ⌛

| Detector | Definition | Null |
|---|---|---|
| `bias_composition` | evolved values of the four copy-weight coefficients per lineage | — |
| `ritual_accumulation` | causally-irrelevant behaviors spreading alongside useful ones under prestige bias | shuffled |
| `conformity_lock` | correlation between `β_conformity` and `zombie_institution` duration | shuffled |

`conformity_lock` tests whether E2's answer depends more on transmission bias than on record decay
— which would relocate the Chronicle Gap's main driver from the medium to the copier.

### Generality ⌛

| Detector | Definition | Null |
|---|---|---|
| **`transplant_competence`** | performance of a lineage moved to a world it did not evolve in | native lineages |
| `overfit_gap` | native competence minus transplanted competence | — |

Borrowed from Melting Pot's design: evaluate on scenarios the population never trained against.
`overfit_gap` is a hard-to-fake intelligence measure — a lineage that is only competent at home has
memorized its world rather than modelled it, and no amount of local performance disguises that.

**New nulls:** `random-graph` — a process space with matched edge count but no ladder structure.
`native lineages` — the resident population of the destination world.

---

## Gate-check detectors

A distinct category worth naming. These do not measure phenomena — they measure **whether
depth is being used**, and they are what authorize the next depth level under
[D-022](DECISIONS.md#d-022).

| Gate check | Question it answers | Authorizes |
|---|---|---|
| `rights_differentiation` | do agents treat different rights slots differently? | P5 → L2 |
| `coercion_repertoire` | is more than one coercion action ever chosen? | P7 → L2 |
| `slot_utilization` | do partial propositions ever influence behavior? | P2 → L2 |
| `modulator_sensitivity` | does behavior change when a modulator fires? | P8 → L2 |
| `memory_horizon` | how far back does episodic memory actually influence action? | P3 → L2 |
| `value_dimensionality` | how many value dimensions actually vary with behavior? | P12 → L2 |
| `plasticity_utilization` | does within-life value drift ever change what an agent does? | P12 → L2 |

**If a gate check does not fire, do not raise the depth level.** The richness would be a tax on
compute and observation width with no behavioral consequence — and worse, it makes results
harder to interpret because unused dimensions still vary.

---

## Firing rules

A detector "fires" only when **all** hold:

1. effect size exceeds the threshold against its null
2. it holds across ≥ 3 seeds under identical config
3. it is not an artifact of a config change made in the same commit

Anything failing (2) is logged as a **candidate**, never reported as a result. Candidates are
useful — they're where hypotheses come from — but they are not findings.

### Never plot z alone across a sweep

*(→ [D-054](DECISIONS.md#d-054))* A z-score is an effect divided by a null width, and null width
shrinks as the sample grows. **Population is an outcome variable in this project**, so any swept
parameter that changes population changes every sample size, and therefore changes every z — for
reasons that have nothing to do with the behavior being measured.

This is not hypothetical. In `a1-patchiness`, z traced a clean monotonic dose-response against
patchiness at *r = 0.97*, exactly the shape the hypothesis predicted. It was an artifact: patchy
worlds supported fewer agents (442 → 79), which logged fewer windows (367k → 63k), which tightened
the null. The raw effect moved by about one between-seed standard deviation and never changed sign.
Reported as z alone, it would have been a confident and entirely wrong result.

**Rule: report the raw effect and z together, always, with `n` alongside.** If the raw effect is
flat, the finding is that it is flat, whatever z does. `tools/plot_sweep.py` enforces the pairing.

There is a second route to the same error, and it is worse *(→ [D-060](DECISIONS.md#d-060))*.
**Anything that homogenizes replicates inflates its own z.** In the heredity control, the arm with
the *smaller* effect scored the *larger* z — 0.100 at z = 46.8 against 0.267 at z = 4.7 — because
giving every world the same random gene distribution collapsed between-world variance 26-fold. The
more thoroughly a control removes the mechanism, the more significant it can look. **Two arms of an
experiment are never ranked by their z-scores.**

---

## Detector-driven development

```
1. pick the next phenomenon, primitive, or depth level on the roadmap
2. write its detector + null + unit tests      ← fires on synthetic positive,
3. confirm it does NOT fire on current builds     silent on synthetic negative
4. build the minimal primitive/depth that could produce it
5. run; check whether the detector fires
6. if it fires → check against null across seeds → record in the corpus
   if it doesn't → the mechanism is wrong, the gate is unmet, or the payoff
                   structure doesn't reward it. All three are findings.
                   Do NOT hand-code it.
```

Step 3 matters more than it looks: a detector that already fires on the current build is
measuring something other than what you think.
