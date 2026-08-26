# 12 — Risks and Failure Modes

Named in advance, because every one of these is a *plausible-looking* path that quietly
destroys the project's value while everything continues to run and the demos keep improving.

---

## Scored against three stages

This document was written before any code existed. Phase A has now run, and a risk register that
misses the real failure mode is worse than none — it produces confidence in the wrong direction, so
it gets graded rather than quietly amended.

**The register spent 27 rows on the simulation misbehaving and six lines on the inference
misbehaving. The actual score is close to the inverse.** The simulation core has needed exactly one
correction in three stages *(→ [D-051](DECISIONS.md#d-051))*. Of the thirteen decisions that
implementation forced, seven were corrections to how we measure, and **all three withdrawn claims
were inference failures, not mechanism failures**.

| Predicted | Verdict | What happened |
|---|---|---|
| Degenerate worlds | **hit** | zero was an absorbing state; every world died *(→ [D-051](DECISIONS.md#d-051))* |
| Determinism rot | **half** | happened, but the prescribed defense was wrong — the fix was to *narrow the guarantee* to per-platform, not to chase cross-ISA identity *(→ [D-057](DECISIONS.md#d-057))* |
| Seeds as fake N | **half** | the doc states it plainly and we wrote the code anyway: 3.2M correlated moves as independent observations *(→ [D-058](DECISIONS.md#d-058))* |
| Emergence theater — *defense: "null models from A1"* | **falsified** | `directed_foraging` had a null, beat it in 39 runs, and was wrong. A null model is necessary and demonstrably **not sufficient** *(→ [D-056](DECISIONS.md#d-056))* |
| — absent — | **missed** | z tracking sample size, producing a spurious r = 0.97 dose-response *(→ [D-054](DECISIONS.md#d-054))* |
| — absent — | **missed** | variance homogenization: the control's z inflated *because* the intervention worked *(→ [D-060](DECISIONS.md#d-060))* |
| — absent — | **missed** | a sampling scheme that made trajectories unreconstructable *(→ [D-052](DECISIONS.md#d-052))* |
| — absent — | **missed** | presentation as inference: sort order manufacturing a gradient *(→ [D-063](DECISIONS.md#d-063))* |

The rows below have been extended accordingly. **Where this conclusion is weakest:** three stages,
one simple core — S0 is a reactive policy over eight floats. B0 and B1 add neural policies and
evolved learning rules and may swing the balance back toward mechanism bugs. Re-score at B1.

---

## The failure table

| Failure | Looks like | Early warning sign | Defense |
|---|---|---|---|
| **Emergence theater** | it looks alive, means nothing | you're showing screenshots instead of effect sizes | null models from A1 *(→ [07-detectors.md](07-detectors.md))* |
| **Fiddle-forever** | six months of parameter tweaking, zero results | no `experiments/*/result.md` in a month | pre-register the observable before building the mechanism |
| **Complexity collapse** | a later stage silently breaks an earlier one | old detectors stop firing and nobody notices | every stage's exit criteria become permanent CI tests |
| **LLM contamination** | agents "invent" human institutions | results are suspiciously familiar | numeric core; LLMs only at the boundary |
| **Degenerate worlds** | everything dies, or grows forever | most configs you try are unusable | automated viability sweep before every experiment |
| **Unfalsifiable narrative** | the Historian writes beautiful nonsense | conclusions cite prose, not metrics | Historian output is never evidence; only Lens metrics are |
| **Determinism rot** | forks stop reproducing parents | the cross-machine hash test starts "flaking" | CI gate; treat a flaky determinism test as a P0 bug |
| **Gate-jumping** | a primitive added before its intelligence stage | "war" happens but looks like random violence | config loader hard-fails on gate violations |
| **Premature scale** | optimizing before the science works | rewriting the tick loop in B0 | performance targets are per-milestone, not aspirational |
| **The helpful hand-code** | `if threatened: fight` "just to bootstrap it" | a PR that makes behavior better and results worse | code review rule: no strategy literals in `src/core/policy/` |
| **Resolution-formula drift** | a primitive's resolution function grows terms until it is a hand-tuned system | you are calibrating a formula so outcomes "feel right" | expand the action space, never the resolution function *(→ [D-024](DECISIONS.md#d-024))* |
| **Dead richness** | depth built past what agents can use | a rights vector where five slots never vary | depth gated by policy capacity *(→ [D-022](DECISIONS.md#d-022))* |
| **Silent fork divergence** | forks stop matching parents once delayed effects exist | the no-op fork test fails, or worse, isn't run | pending queue and accumulators must be in checkpoints *(→ [D-025](DECISIONS.md#d-025))* |
| **Generator tuning** | hand-adjusting an individual generated entity | "this one resource needs a different curve" | if you want to tune an instance, the distribution is wrong — fix the generator |
| **Anthropomorphic reading** | value clusters "are" philosophies; transfers "are" sacrifices | conclusions cite a narrative rather than a detector | behavioral detectors with nulls; strictest null in the suite on `worldview_cluster` *(→ [D-027](DECISIONS.md#d-027))* |
| **Named-psychology creep** | `confirmation_bias`, `morality`, seven sin variables | a psychology textbook is open beside the editor | biases emerge from resource limits; value dimensions are generated *(→ [D-029](DECISIONS.md#d-029))* |
| **Unfalsifiable ultimate goal** | "the stories feel human" | success is asserted, never measured | E17 blind test with rater accuracy as endpoint *(→ [D-031](DECISIONS.md#d-031))* |
| **Ablation-as-birth-condition** | motive decomposition run as a config difference, not a fork | agents raised unobserved, not acting unobserved | ablations apply at forks only *(→ [D-030](DECISIONS.md#d-030))* |
| **Hand-added curiosity** | a novelty bonus or `creativity` term added because exploration died | "just to bootstrap discovery" | curiosity is attention under prediction error; exploration rate is evolved *(→ [D-033](DECISIONS.md#d-033), [D-034](DECISIONS.md#d-034))* |
| **Detector anthropocentrism** | alien cognition invisible to the whole suite | every intelligence we find looks reassuringly familiar | weight the suite toward general measures — compression, prediction, novelty rate *(→ [D-036](DECISIONS.md#d-036))* |
| **Open-endedness overclaim** | reporting sustained growth that is really a long transient | a complexity curve that has not been run to its asymptote | plateau is the measured variable; run past the apparent knee before claiming anything |
| **Sample-size leak** ⚠ | a clean dose-response curve that is really a population curve | z rises with the swept parameter and so does n | plot raw effect beside z, annotate n *(→ [D-054](DECISIONS.md#d-054))* |
| **Endogenous conditioning** ⚠ | a detector beats its null for months and is backwards | the split variable is downstream of the measured action | condition on genome, world, or cohort — never on outcome *(→ [D-056](DECISIONS.md#d-056))* |
| **Pseudo-replication** ⚠ | implausibly large z on a plausible effect | n is agent-ticks rather than worlds | the replication unit is declared in the detector *(→ [D-058](DECISIONS.md#d-058))* |
| **Variance homogenization** ⚠ | the control arm looks *more* significant than the treatment | the better the control, the larger its z | compare arms on raw effect, never on z *(→ [D-060](DECISIONS.md#d-060))* |
| **Presentation as inference** ⚠ | a picture implies a result nobody measured | a sort order, a marker, or a per-panel scale is doing the arguing | shared scales; verdicts travel with markers; never sort by outcome *(→ [D-063](DECISIONS.md#d-063))* |
| **Ceiling as regulator** ⚠ | a population "stabilizes" against the array, not the world | mean population approaches `population.capacity` | headroom precheck refuses the sweep *(→ [D-065](DECISIONS.md#d-065))* |
| **Length-limited negative** ⚠ | an effect declared absent that had not finished appearing | the effect is still growing at the end of the run | run past the knee before reporting a null result |

⚠ = **observed in Phase A**, not hypothetical. The five inference rows were absent from the
original register; each cost at least one run to find, and one cost thirty-nine.

---

## The seven that will actually happen

Ranked by probability, with what to do when they do.

### 1. Degenerate worlds — near certain

Most parameter settings produce dead or exploding worlds. **Finding habitable regions will
consume more time than analyzing them.** This is not a design flaw; it is the actual shape of
the work, and it is the strongest argument for twelve primitives over twenty-five systems —
twelve generator knobs is a searchable space.

*Response:* build the viability sweep as a first-class tool in A1, not C0. You will run it
before every single experiment for the life of the project.

### 2. The helpful hand-code — near certain, and the most dangerous

War isn't emerging. The temptation is a small `if threatened: fight` to "help it along." This
is the moment the project dies, and it dies quietly: everything still runs, demos improve, and
no result means anything afterward.

*Response:* treat it as a hard code-review rule, and understand the diagnosis. A phenomenon
that won't emerge means one of three things — the primitive is wrong, the intelligence gate is
unmet, or the payoff structure doesn't reward it. All three are findings. Hand-coding converts
a finding into a bug you can't see.

### 3. Fiddle-forever — likely

The mechanisms are more fun to build than the measurements. Six months in, there are eleven
primitives, a beautiful Atlas, and no `result.md`.

*Response:* the detector-driven workflow in
[07-detectors.md](07-detectors.md#detector-driven-development), plus a standing rule — if a
month passes with no committed experiment result, stop adding mechanisms.

### 4. Determinism rot — likely

Determinism decays silently. A library update, an unsorted operation, a parallel reduction,
and forking is quietly broken while everything still appears to work.

*Response:* the CI gate in [11-engineering.md](11-engineering.md#ci-gate), and never tolerating
a "flaky" determinism test. There is no such thing as a flaky determinism test — there is only
a determinism bug you haven't localized.

### 5. Anthropomorphic reading — near certain once P12 exists

Every prior layer had a natural defense: you cannot really fool yourself about a trade network.
The psychology layer has none. An agent transferring resources *reads* as sacrifice. A value
shift *reads* as redemption. A cluster in value space *reads* as Stoicism. And the Historian
will write beautiful, moving prose confirming every one of those readings.

This is the Rorschach failure mode, and it is worse than emergence theater because the output is
genuinely affecting rather than merely impressive.

*Response:* three rules, held tightly.

1. **Every psychological claim needs a behavioral detector and a null.** "The agent became
   compassionate" is not a finding; `value_drift` exceeding threshold with an identifiable
   experience window is.
2. **`worldview_cluster` carries the strictest null in the suite** — it must beat random
   value-vector clustering on stability, transmissibility, *and* behavioral consequence. Two out
   of three is not a philosophy.
3. **Establish that clusters are real before asking what they resemble.** E15 fixes this order
   deliberately: reversing it guarantees a match, because any cluster resembles some tradition if
   you are looking for one.

And the standing rule, which matters most here: **prose that moves you is evidence of nothing.**

### 6. Hand-added curiosity — near certain, and the same shape as the helpful hand-code

Exploration will die. Selection removes it at equilibrium — that is the *prediction*
*(→ [D-032](DECISIONS.md#d-032))*, not a malfunction. The temptation will be a small novelty
bonus or a `creativity` term to get discovery moving again.

It is the helpful hand-code wearing a new hat, and it fails identically: the demos improve, the
discovery curve looks healthy, and nothing about when curiosity survives is knowable afterward.

*Response:* the diagnosis when exploration collapses is one of four things, all of them findings —
payoff tails too thin, attention-shift rate not under selection, no relative-standing competition,
or a selection window too short to see bet-hedging. Sweep them (E18, E19, E20). Do not add a term.

### 7. Scope inflation via the phenomenon list — likely

The list of historical phenomena is seductive and infinitely extensible. Every conversation
generates three more things the world "should" have.

*Response:* the derivation table in [02-primitives.md](02-primitives.md). A proposed addition
must either derive from the existing eleven — in which case build nothing — or justify a
twelfth primitive against the freeze protocol. "It would be cool" is not a justification.

---

## Scientific risks

Distinct from engineering risks: these threaten the *validity* of results rather than the
ability to produce them.

| Risk | Mitigation |
|---|---|
| **Overfitting the corpus** | Analyst records the corpus snapshot each hypothesis came from; hypotheses tested on their generating data are discarded *(→ [08-experiments.md](08-experiments.md#the-analyst-loop))* |
| **Multiple comparisons** | dozens of detectors per sweep; correction is mandatory, not optional |
| **Seeds as fake N** | 1,000 agents in one world is N=1. Seeds are the unit of replication |
| **Post-hoc storytelling** | pre-registered predictions with kill criteria |
| **Anthropomorphic reading** | detectors are defined over event patterns, never over what the behavior "looks like" |
| **Ground-truth leakage** | the `beliefs`/`truth` split is enforced at the type level; a leak silently invalidates mechanism A |

That last one deserves attention out of proportion to its size. If any code path lets an agent
read `truth` instead of `beliefs`, the Chronicle Gap results are meaningless and there is no
symptom — the simulation runs fine and the numbers look plausible. It should be structurally
impossible, not merely avoided.

---

## What would make us abandon the project

Worth naming, so that persisting becomes a choice rather than a default:

- Determinism proves unachievable at the scale we need, killing fork-based causal inference —
  the project's core scientific affordance.
- The viable parameter band is so narrow that results are artifacts of tuning rather than
  properties of the model.
- Detectors consistently fail to beat nulls through C2, indicating the primitives cannot
  generate structure regardless of parameters.

Note that **universal stagnation is not on this list.** If every configuration plateaus early and
nothing moves it, that is the central finding of the stagnation programme rather than a reason to
stop *(→ [D-032](DECISIONS.md#d-032))*. It would be a real, cleanly-obtained negative result about
a question the field has been circling for forty years.

None of these are likely. All are detectable early, which is the point of front-loading A1's
unglamorous ship criteria *(→ [10-roadmap.md](10-roadmap.md#a0--skeleton))*.
