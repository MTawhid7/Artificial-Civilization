# 08 — Experiments

## The unit of work

Not a run. A **sweep**: N worlds, one variable changed, an effect size at the end.

If a proposed experiment cannot be written as *"sweep X over range R, measure detector D,
report effect size against null Z"*, it is not ready to run.

---

## Protocol

Every experiment follows the same five steps. Skipping step 1 is how six months of parameter
tweaking happens.

### 1. Pre-register

Before running anything, write `experiments/<name>/spec.yaml`:

```yaml
question:    "Does record fidelity make societies adaptive or rigid?"
variable:    beliefs.decay_rate
range:       [0.001, 0.01, 0.05, 0.1, 0.3]
held_frozen: [all other primitive params @ configs/frozen/v7.yaml]
detector:    zombie_institution
null:        shuffled
seeds:       200
prediction:  "rigidity increases monotonically with fidelity"
kill_criterion: "no monotonic trend at p<0.01 → hypothesis dead, do not re-spec"
```

The `prediction` and `kill_criterion` fields are the point. Writing down in advance what would
falsify the idea is what stops post-hoc storytelling.

### 2. Viability sweep

**Run this first, every time.** Most parameter settings produce dead or exploding worlds.

```
coarse grid over the variable range × 10 seeds
→ classify each cell: EXTINCT | EXPLOSIVE | FROZEN | RUNAWAY | VIABLE
→ the experiment runs only inside the VIABLE band
```

If the viable band is empty, the experiment is malformed — fix the config, not the analysis.
If the viable band is a single point, the variable isn't really free.

**`RUNAWAY` is a depth-era addition.** Once modulators exist, a new degeneracy appears: a
cascade that never stops. Capability compounds without bound, one civilization dominates by
year 400, and the run is as uninformative as extinction. Classify and exclude it like any other
degenerate regime *(→ [04-intelligence.md](04-intelligence.md#learning-in-a-world-whose-rules-change))*.

**Generators change what a viability sweep means.** Since generated structure varies with seed,
a config is viable only if *most of its generated worlds* are viable. Classify at the config
level by the fraction of seeds landing in `VIABLE` — a config where half the seeds run away is
not a viable config with unlucky seeds, it is a bad config.

### 3. Sweep

Full N-seed run across the viable band. Forge handles scheduling, batching, and the corpus
index. Every run is reproducible from `(config, seed)`.

### 4. Analyze

Lens produces metrics; analysis is SQL over the corpus index. Report:

- effect size with confidence interval, **not** p-values alone
- the null comparison explicitly
- number of seeds, and how many were excluded (and why — pre-registered exclusions only)
- correction for multiple comparisons when several detectors were checked

### 5. Record

Result lands in `experiments/<name>/result.md` — including negative results. A refuted
hypothesis is a finding and costs the same to produce.

---

## Fork-based causal inference

This is the affordance simulation has that observational social science never will, and most
projects squander it.

```text
                    ┌──── re-run, plague hits ────→ history A₁
   run to tick T ───┤
                    └──── re-run, plague averted ─→ history A₂

   repeat over 32–64 seeds → matched counterfactual pairs → causal estimate
```

Not "civilizations with plagues tend to…" — an **intervention**, N=32–64, with everything else
held byte-identical up to the fork point.

Mechanics *(→ [06-data-model.md](06-data-model.md#interventions-typed))*:

1. Run to tick T; a checkpoint exists at or before T.
2. Apply a **typed** intervention. Never arbitrary code — untyped interventions aren't
   reproducible.
3. Re-run both branches to completion with the same downstream RNG stream.
4. Compare detector outputs pairwise, not in aggregate.

**Pairwise comparison matters.** Matched pairs remove between-seed variance, which is usually
larger than the effect you're chasing. Comparing group means throws that away.

---

## Marquee experiments

Written as the results they would become. Each is a sweep with a number at the end.

### E1 — Replaying the tape
~200 worlds (about seven batches), identical initial conditions, different seeds. Cluster trajectories. Which
outcomes are **attractors** (nearly everyone reaches them) and which are **contingent** (coin
flips that lock in)? Gould's thought experiment, actually executed.
*Detectors:* all. *Output:* trajectory clustering + attractor basin map.

### E2 — The taboo that outlived its reason
Chronicle Gap *(→ [03-mechanisms.md](03-mechanisms.md#a-the-chronicle-gap--belief-vs-truth-measured))*.
Plant a cause, kill the witnesses, silently remove the cause via `SET_TRUTH`. How long do
institutions survive their justification, and what sustains them?
*Detector:* `zombie_institution`. *Variable:* `beliefs.decay_rate` × population size.

### E3 — Dose-response for language
Sweep channel capacity; locate the compositionality threshold; test whether it moves with
population size, mobility, and task complexity.
*Detectors:* `compositionality`, `referential_validity`. *Null:* mute.

### E4 — Discovery is easy, keeping is hard
Separate discovery from diffusion from re-loss. Which one actually gates technological level?
*Detectors:* `discovery_rate`, `diffusion_rate`, `knowledge_loss`.
*Prior:* diffusion-bound, not discovery-bound.

### E5 — Memory advantage
One population gets lower record decay. Does it dominate, or ossify? Directly tests whether E2's
mechanism has a fitness sign.
*Fork-based:* matched pairs at tick T.

### E6 — Collapse boundary
Remove a critical resource at year N across 64 matched forks. Map the adaptation/collapse
boundary and find what predicts which side a civilization lands on.
*Detector:* `collapse`. *Intervention:* `RESOURCE_SHOCK`.

### E7 — When are brains worth their cost
Sweep environmental variability against cognition cost. Find where selection flips from
favouring smaller brains to larger ones.
*(→ [04-intelligence.md](04-intelligence.md#brains-must-cost-energy))*

### E8 — Genes vs. culture
Once S6 exists, decompose observed adaptation into vertical (genetic) and horizontal
(cultural) channels. How does the ratio shift with volatility?

### E9 — Law recovery
Randomized latent constant per world; correlate discovered Ĝ against true G across ~60 worlds (two batches).
*Detector:* `law_recovery`. This is the cleanest possible test that science emerged.

### E10 — What makes a cascade
The marquee experiment of the depth work. Sweep generated modulator-graph density against
population size and diffusion rate; measure whether `modulator_cascade` fires, fizzles, or runs
away. **We never implement an industrial revolution — we find the conditions that produce one.**
*Detector:* `modulator_cascade`. *Null:* no-modulator. *Blocks on:* E0.

### E11 — Substitution or collapse
Deplete a critical resource whose substitutes exist but are undiscovered. Does the civilization
find a substitute, migrate, or collapse — and what predicts which?
*Detectors:* `substitution_event`, `collapse`, `migration_wave`. *Intervention:* `RESOURCE_SHOCK`.
Pairs with E6: E6 removes a resource with no substitute, E11 with a reachable one.

### E12 — Are tipping points predictable from the inside?
Sweep accumulator threshold visibility. Given only what agents can observe, is a crossing
detectable before it happens — and do agents that could detect it act differently?
*Detectors:* `tipping_point`, `slow_then_sudden`, `commons_tragedy`. *Null:* instant-effect.

This one is the sharpest test of P11ᴸ²: the whole point is that agents need not understand the
couplings they are embedded in. Measuring how much they *could* have understood is the
interesting half.

### E13 — Dark ages
Under what conditions does `tech_regression` occur, and what predicts recovery time? Sweep
knowledge-loss rate against population size and diffusion rate.
*Detectors:* `tech_regression`, `rediscovery`, `knowledge_loss`. Direct extension of E4.

### E14 — Is there such a thing as genuine altruism?
The altruism ablation battery
*(→ [07-detectors.md](07-detectors.md#the-altruism-ablation-battery-))* run as matched forks at
scale. Decompose altruistic acts into reputation, reciprocity, kin, delayed self-interest, and
residual. Then sweep: which conditions grow the residual?
*Prediction:* the residual is small but non-zero, and grows with the stability of the social
environment. *Kill criterion:* residual indistinguishable from zero across all conditions —
which is itself a clean, publishable negative.

### E15 — Do worldviews cluster, or are we seeing faces in clouds?
Cluster belief×value space across a large corpus; test every cluster against random
value-vector clustering on stability, transmissibility, and behavioral consequence. Only then
ask whether any cluster's coordinates resemble a human philosophical tradition.
*Detector:* `worldview_cluster`, `worldview_novelty`. **Order matters:** establish that clusters
are real before asking what they resemble, or the answer is guaranteed and worthless.

### E16 — Does power corrupt?
Fork at the moment an agent accumulates delegated authority. In one branch it is promoted, in
the matched branch it is not. Compare value drift over the remaining lifetime.
*Detector:* `authority_drift`. *Null:* matched non-promoted agents.

The cleanest possible form of a claim usually made with anecdotes — same agent, same world,
same seed, one difference. If value drift is equal in both branches, power selects rather than
corrupts, and that is the finding.

### E17 — The blind test
The falsifiable version of "emergent human stories." Generate agent life-summaries from the
Chronicle via the Historian; mix with real biographical summaries matched for length and
specificity; have human raters sort them.
*Endpoint:* rater accuracy. Chance-level accuracy is the strongest possible result for the
project's most ambitious goal — and unlike "the stories feel human," it can come back negative.

⚠️ The Historian's writing quality confounds this badly. Both arms must be rendered through the
**same** prose pipeline, or the test measures prose rather than lives.

### E18 — What moves the plateau
**The marquee experiment of the stagnation work, and arguably of the project.** Sweep each of the
four engines from mechanism I — payoff tail thickness, attention-shift rate, relative-standing
weight, selection window length — against `plateau_height` and `time_to_plateau`.
*Detectors:* `model_compression`, `plateau_height`, `time_to_plateau`, `cognitive_regression`.

Note what makes this unusual: **every outcome is a result.** If nothing moves the plateau, that is
a finding about the difficulty of open-endedness, obtained on a substrate where the negative can
actually be trusted. Most of the field cannot report that cleanly.

### E19 — Does prosperity kill curiosity?
Fork at the point a population reaches stable abundance. One branch keeps material pressure; the
matched branch does not. Measure `exploration_decay` and `cognitive_regression` over the following
thousand generations.
*Prediction:* exploration collapses under abundance **unless** relative-standing competition is
active. *Kill criterion:* no difference between branches — meaning material pressure was never
what sustained exploration.

Directly tests the "peaceful equilibrium ends progress" worry, as an intervention rather than an
argument.

### E20 — Do heavy tails sustain exploration?
Sweep discovery-payoff tail thickness from thin to heavy, holding mean payoff constant. Find where
evolved `exploration_rate` stops collapsing.
*Detectors:* `exploration_rate`, `tail_realization`, `long_fuse`. *Null:* thin-tail.
The most direct test of [D-033](DECISIONS.md#d-033), and holding the mean constant is what makes
it clean.

### E21 — Paradigm change vs. optimization
Once S7 exists: does structural model search ever beat parameter refinement, and under what
conditions? Sweep environmental novelty rate against S7 cost.
*Detectors:* `paradigm_shift`, `model_turnover`. *Null:* `model_turnover` under parameter search
only.
*Prior:* S7 is selected against wherever the current paradigm is adequate, so it survives only
under engines 1 and 4 — which makes this a joint test of all of them.

### E22 — Ladder density, or why nothing bootstraps
**Run this before anything else at E0.** Sweep the generator's ladder-density parameter and
measure whether a technology chain of depth > 2 ever forms.
*Detectors:* `ladder_reachability`, `material_depth`, `tool_bootstrapping`. *Null:* random-graph.

Avida's EQU result is the warning: a complex feature evolved only when simpler intermediates were
also rewarded. A randomly generated process space is almost certainly too sparse to bootstrap, and
**if this parameter is wrong, every downstream technology experiment measures nothing.** Likely the
single most consequential sweep in the project.

### E23 — Does the archive drive discovery?
Fork at the introduction of a durable record medium. Measure subsequent discovery rate against the
matched no-record branch, controlling for population.
*Detectors:* `library_effect`, `compression_multiplier`, `retrieval_bottleneck`.
*Second arm:* sweep transmission fidelity to locate the accumulation threshold Henrich's argument
predicts — `fidelity_threshold` as a phase transition.

### E24 — Does better record-keeping make societies rigid?
The sharpened version of E5, now with a mechanism. Sweep medium fidelity and copy cost; measure
`zombie_institution` duration **and** `error_fossilization` together.
*Prediction:* high fidelity raises both adaptive capacity and error persistence, and which
dominates depends on whether records are ever checked against observation.
*Kill criterion:* no relationship between fidelity and error persistence — meaning fossilization
is not the rigidity mechanism and E2's answer lies elsewhere.

### E25 — Does the frontier prevent the plateau?
Fork a world at equilibrium: one branch keeps a bounded map, the matched branch gets an unbounded
procedurally-generated frontier. Measure `plateau_height` and `time_to_plateau`.
*Detectors:* `plateau_height`, `exploration_rate`, `substance_novelty`.

Tests engine-adjacent claim K directly: is spatial open-endedness sufficient, or does structural
open-endedness (new substances) do the real work? Run both arms separately to separate them.

### E26 — Social brain or ecological brain?
**Two competing hypotheses from biology, tested against each other on the same substrate.** The
social brain hypothesis says cognition tracks group size; the cognitive buffer hypothesis says it
tracks environmental variability. Sweep both axes independently and see which predicts evolved
cognition cost.
*Detectors:* `cognitive_regression`, brain-cost trajectory, `model_compression`.

This is the experiment most likely to interest researchers outside artificial life — it is a real
open question in comparative biology, and our substrate can vary both axes independently in a way
field data never can.

### E27 — Is this intelligence, or memorization of one world?
Evolve lineages in world A; transplant to world B with different generated structure; measure
competence against B's natives.
*Detectors:* `transplant_competence`, `overfit_gap`. *Null:* native lineages.
Borrowed from Melting Pot's evaluation design. A high `overfit_gap` means we have been measuring
adaptation to a particular world and calling it intelligence.

### E28 — Which inheritance channel carries the weight?
E8 extended to three channels — genetic, cultural, ecological. Decompose observed adaptation and
sweep volatility.
*Prediction:* ecological inheritance dominates precisely in the runs where technology took off,
which would make it the most under-measured channel in the literature.

---

## The Analyst loop

The closed loop, and the project's tier-4 goal.

```text
   corpus ──→ Analyst ──→ hypothesis ──→ experiment spec ──→ Forge
                 ↑                                            │
                 └──────────── result, incl. refutations ──────┘
```

**The Analyst may not assert.** It reads Lens metrics across the corpus and must emit a
*runnable experiment spec* in the same format as §1 — variable, range, detector, null,
prediction, kill criterion. Forge executes it as matched counterfactual forks. Hypotheses that
survive are promoted; the rest are logged as refuted, with the refutation kept.

Constraints:

- The Analyst reads **metrics**, never raw Chronicles, and never live state.
- Historian narrative is **never** input to the Analyst. Prose about a world is not evidence
  about a world.
- Every Analyst-proposed experiment carries the corpus snapshot it was generated from, so
  hypotheses generated from the same data that tests them are detectable and discarded.

That last constraint is the difference between an AI scientist and an AI that produces
confident-sounding overfitting.

---

## Statistical hygiene

- Pre-register or it's exploratory. Exploratory findings are hypotheses, not results.
- Report effect sizes and intervals; a p-value alone is not a finding.
- Correct for multiple comparisons across detectors — we run dozens per sweep.
- Seeds are the unit of replication. N=1,000 agents in one world is **N=1**.
- Never re-run a sweep with a different seed count because the first result was disappointing.
