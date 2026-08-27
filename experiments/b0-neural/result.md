# b0-neural — can selection rediscover what S0 was handed?

**Verdict: the survival criterion is not met, and the capability question underneath it gets a
clear yes.** An evolved network does not beat the hand-written reactive rule on survival — it loses
at every dose, in every seed, in 128 of 144 paired worlds. But it starts effectively blind and ends
up ascending resource gradients in **105 of 105 worlds that survived to be measured**, which is the
thing S1 was built to find out.

Run: 18 runs, 16 worlds × 30,000 ticks each, commit `197c679`, 5,173 s wall.
Spec: [spec.yaml](spec.yaml) · raw: [results.json](results.json) · paired analysis:
[survival.json](survival.json), produced by [analyse.py](analyse.py).

---

## The criterion, and how it failed

> **Ship:** evolved policies beat the reactive genome on survival
> *(→ [10-roadmap.md § B0](../../docs/10-roadmap.md#b0--neural-policy))*

Post-burn-in mean population per world, paired by `(seed, world)` — the same landscape with the
same founding cohort in both arms *(→ [D-072](../../docs/DECISIONS.md#d-072))*. Raw effect, not z
*(→ [D-060](../../docs/DECISIONS.md#d-060))*.

| gather | pairs | S0 mean | S1 mean | paired Δ | t | S1/S0 | S1 won | seeds ahead |
|---|---|---|---|---|---|---|---|---|
| 1.5 | 48 | 104.1 | 39.1 | −65.0 | −9.2 | 0.376 | 3/48 | 0/3 |
| 2.0 | 48 | 169.5 | 102.6 | −66.9 | −6.5 | 0.605 | 6/48 | 0/3 |
| 2.5 | 48 | 246.9 | 172.4 | −74.5 | −5.0 | 0.698 | 11/48 | 0/3 |

Not close, not marginal, and not a seed effect. **The criterion fails.**

The **absolute** deficit is flat across doses (−65, −67, −75) while the **ratio** climbs steadily
(0.38 → 0.61 → 0.70). S1 pays what looks like a fixed toll, so the richer the world, the smaller
that toll is as a share of what there was to get.

### Extinction is the mechanism, not a lower steady state

| | gather 1.5 | 2.0 | 2.5 |
|---|---|---|---|
| S0 worlds extinct | 1/48 | 0/48 | 0/48 |
| **S1 worlds extinct** | **28/48** | **9/48** | **2/48** |
| S1 median final population | 0 | 130 | 174 |

S1's surviving worlds are not far behind S0's; S1's problem is that in a lean world most of them
die. That reframes the deficit as a **founding-phase** failure rather than a steady-state one — the
network has to become competent before the founding cohort's energy runs out, and at gather 1.5 it
usually does not make it.

---

## What actually happened: selection found the gradient

`gradient_ascent` measures the chosen direction against the four that were visible, so it reads the
*decision* and conditions on nothing downstream of it *(→ [D-056](../../docs/DECISIONS.md#d-056))*.
Raw magnitudes, averaged over three seeds:

| stage | gather | magnitude | took best | early | late | Δ | worlds improved |
|---|---|---|---|---|---|---|---|
| S0 | 1.5 | 0.363 | 0.467 | 0.216 | 0.495 | +0.279 | 40/47 |
| S0 | 2.0 | 0.394 | 0.497 | 0.189 | 0.521 | +0.332 | 45/48 |
| S0 | 2.5 | 0.425 | 0.534 | 0.169 | 0.553 | +0.384 | 42/48 |
| **S1** | **1.5** | 0.074 | 0.306 | **0.066** | **0.223** | **+0.157** | **20/20** |
| **S1** | **2.0** | 0.117 | 0.291 | **0.047** | **0.199** | **+0.152** | **39/39** |
| **S1** | **2.5** | 0.126 | 0.288 | **0.033** | **0.192** | **+0.159** | **46/46** |

**Read the `early` column first.** S0's founding cohort already scores 0.17–0.22 because the rule
ascends gradients from tick zero — that is exactly why `gradient_ascent`'s docstring warns that
firing at S0 is not evidence of evolution. S1's founding cohort scores **0.033–0.066**: a random
network is very nearly blind, which is what a fair starting point looks like.

By the last tenth of the run S1 is at 0.19–0.22 — roughly where S0's *unselected founders* began,
reached from nothing, and reached in **every single world that survived long enough to be scored**.
The improvement is also remarkably stable across doses (+0.152 to +0.159) even as the ratio and the
extinction rate move a lot, which suggests the learning rate is a property of the mechanism rather
than of the world.

So: **selection rediscovered gradient-following from scratch, and did not rediscover enough of it
in 79 generations to beat a competent hand-written rule.** Those are two different results and only
the first was in doubt.

### The caveat that has to travel with that number

**`advantage_delta` is measured only on worlds that survived**, and at gather 1.5 that is 20 of 48.
A world whose policy failed went extinct and contributed no late-window rows, so "20/20 improved"
is a statement about survivors and is **survivorship-biased by construction**. It is not evidence
that every world improved; it is evidence that every *surviving* world did, and survival is
plausibly caused by the very improvement being measured.

The **gather 2.5 arm is the one to trust**: 46 of 48 worlds scored, 96% coverage, so there is
almost no room for selection on the outcome. It shows the same +0.159. The lean arms are consistent
with it rather than independent support for it.

---

## Regulation, and one number not to over-read

| stage | gather | pop_stability | its null | collapse | its null |
|---|---|---|---|---|---|
| S0 | 1.5–2.5 | 0.343–0.354 | 0.095 | 7.6–10.8 | 7.0–7.6 |
| S1 | 1.5 | 0.121 | 0.077 | 3.75 | 4.51 |
| S1 | 2.0 | 0.263 | 0.089 | 3.40 | 5.72 |
| S1 | 2.5 | 0.295 | 0.094 | 1.67 | 5.57 |

S1's regulation coefficient climbs toward S0's as the world gets richer (0.12 → 0.26 → 0.30 against
0.34), and `pop_stability` only fires for S1 at gather 2.5.

**`collapse`'s strongly negative z at S1 should not be read as regulation here.** Its docstring says
a negative z is the signature of a mean-reverting population suppressing drawdowns — but S1 also has
the extinctions, and a series that goes to zero and stays there has few drawdown *episodes* by
construction, because an episode needs a recovery to a new peak to close. The detector is behaving
correctly on a series it was not designed for. This is a candidate artifact, not a finding, and
disentangling it needs a run where S1 does not go extinct.

---

## One world, looked at

`uv run python tools/scope.py corpus/runs/e72ac134ca3ae15fe8d48049 --world 4`, against its S0 twin
`f17826b6639607c2b8e3406c` — the same landscape and the same founders, by construction.

Two things are visible that no series in this experiment carries, and **both are N=1 observations
from one world, not findings** *(→ [D-063](../../docs/DECISIONS.md#d-063))*:

- **S0's harvest field is rectilinear** — a dense cross-hatch of horizontal and vertical stripes.
  That is the sector rule made visible: scores are computed N/E/S/W and heading persistence keeps
  agents ploughing along grid axes. **S1's is smooth and diagonal.**
- **S1's population organizes.** It starts as uniform scatter and by year ~1,750 has formed a
  coherent band tracking the bright resource ridges. S0's stays dispersed for the whole run.

The second is the qualitative face of `advantage_delta`, and it is exactly the observation the scope
was built before B0 to make possible: a population that aggregates on resource and one that is
merely lucky are the same row in `aggregate.parquet`.

---

## Cost

| | |
|---|---|
| S0 tick, 16×1200 | 7.99 ms |
| S1 tick, same | 11.40 ms (**1.43×**) |
| Chronicle per S1 run | 59 MB at `sampled`, rate 32 |
| Whole sweep | 5,173 s including six full-length prechecks |

The 1.43× here is below the 1.57× measured at 32×1000 on a 96 grid, as expected — this
configuration has a smaller grid, so the phases that scale with grid² are cheaper and the policy is
a smaller share of the tick.

---

## What would change the answer, in the order worth trying

1. **Run length.** 30,000 ticks is ~79 generations. S1's `advantage_delta` is still a *rate*, not a
   plateau — nothing in this data says it has stopped improving. The cheapest real test is 100,000
   ticks at gather 2.5, which is ~38 min per run.
2. **Survive the founding phase.** The deficit is extinction, and extinction happens early while
   the network is still blind. A larger `initial` population, or a higher `start_energy`, buys
   generations without touching the policy. This is the intervention most likely to move the
   criterion.
3. **Lineage count.** Eight per world; the two that survive at gather 1.5 are doing all the work.
   Sixteen costs 0.2 ms *(→ [00-feasibility](../../docs/00-feasibility.md#s1-measured-again-after-b0))*.
4. **Not `weight_mutation_scale`.** Tuning the mutation size until S1 wins would be fitting the
   knob to the outcome, and the outcome is the thing being measured.

**What this does not license.** S1 is worse than S0 at foraging in S0's world, and S0's rule was
written for exactly this world. Nothing here says a network is a worse policy class — it says an
evolved one has not caught a hand-designed one yet, on this landscape, in this many generations.
The comparison that would settle that is a world S0's rule was *not* designed for, which is B0.2's
fog and, properly, E27's transplant.

---

## Notes for whoever reads this next

**The precheck sample pointed the wrong way, and that is the argument for the axis.** Before the
sweep, a 4-world one-seed precheck suggested the S0 lead *grew* with abundance (≈4× at gather 4.0,
≈2× at 2.5 and 2.0). The full 48-pair paired measurement says the opposite: the S1/S0 ratio
*improves* with abundance, 0.376 → 0.698. A worst-world mean over four worlds is a noisy statistic
and it inverted a monotone relationship. Had `gather_efficiency` been fixed at one value on the
strength of that reading, this experiment would have reported a direction it does not have.

**`gather_efficiency` had to move at all because of a ceiling.** At the inherited 4.0, the headroom
precheck put S0 at 1,479 of 2,000 with its peak pinned at exactly 2,000 while S1 sat at 19%. A
censored control and an uncensored treatment bias the comparison *toward* this experiment's own
hypothesis — a worse failure than an ordinary [D-065](../../docs/DECISIONS.md#d-065) miss, and one
the precheck caught before a single scored run existed.
