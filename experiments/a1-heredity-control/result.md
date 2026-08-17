# a1-heredity-control — result

**Status: the evolutionary claim survives.** 10 runs (2 arms × 5 seeds), 16 worlds each, 15,000
ticks, 16 minutes. Spec: [spec.yaml](spec.yaml).

---

## The question

[a1-gradient-ascent](../a1-gradient-ascent/result.md) reports that agents ascend resource gradients
better late in a run than early, and reads that as selection. A competing explanation has nothing
to do with selection: **the landscape at tick 15,000 is not the landscape at tick 0.** Agents have
stripped the easy patches and population has grown from 120 toward carrying capacity, so the
gradients an agent faces late may simply be different from the ones it faced early.

`population.inherit: false` gives every child freshly drawn random genes instead of its parent's.
Genetic composition stays pinned at the founding distribution forever, so nothing can accumulate,
while world, physics, population dynamics, depletion, and the detector are untouched.

    inherit: true   →  selection + environment
    inherit: false  →  environment alone

## What happened

| arm | mean pop | advantage | took best | early | late | **selection gain** | worlds improved |
|---|---|---|---|---|---|---|---|
| **heredity** | 344 | 0.267 | 0.447 | 0.126 | 0.340 | **+0.214** | 13.2 / 16 |
| **no heredity** | 101 | 0.100 | 0.286 | 0.093 | 0.103 | **+0.010** | 9.2 / 16 |

**The environment accounts for 5% of the gain.** Selection accounts for the rest: +0.204 of the
+0.214, *t* ≈ 7.8 across seeds, and every one of the five heredity seeds (0.152–0.297) exceeds
every one of the five control seeds (0.006–0.016) with no overlap at all.

Two supporting details. Without heredity, `worlds_improved` is 9.2 of 16 — indistinguishable from
the 8 of 16 you would get by tossing a coin, which is what "nothing is accumulating" should look
like. And the no-heredity population stabilizes at 101 rather than 344: agents that cannot inherit
anything are markedly worse at staying alive, which is the same result seen from the other side.

## The trap this control walked into

Read by z alone, the control says the opposite of the truth.

| arm | raw advantage | z vs null | between-world SD |
|---|---|---|---|
| heredity | **0.267** | 4.7 | 0.0562 |
| no heredity | **0.100** | **46.8** | 0.0022 |

The no-heredity arm has an effect **2.7× smaller** and a z **10× larger**. Nothing is wrong with
either number. Every world in the control has the same randomly-drawn gene distribution, so the
worlds barely differ — between-world SD collapses by 26× — and z, which divides by that spread,
explodes.

This is [D-054](../../docs/DECISIONS.md#d-054) arriving from a direction it was not written for.
The original case was sample size; this one is variance homogenization, and it is arguably nastier
because the intervention that shrinks the variance is the very thing under test. Reporting
"no-heredity scores z = 46.8, heredity only 4.7" would have been arithmetically correct and exactly
backwards.

> **z is a claim about distinguishability from chance, never about size.** Two arms of one
> experiment cannot be ranked by their z-scores.

## Standing

The evolutionary claim in [a1-gradient-ascent](../a1-gradient-ascent/result.md) is sound:
gradient-ascent improves over a run because the population adapts, not because the world drifts
underneath it.

`population.inherit` stays in the config as a permanent control rather than a one-off. Any future
claim of the form "selection produced X" can be checked the same way, in one extra run, and should
be.
