# a1-hunger-coupling — result

**Status: prediction falsified, and the real cause found.** 9 runs (3 settings × 3 seeds), 16
worlds each, 15,000 ticks, 9 minutes. Spec: [spec.yaml](spec.yaml).

---

## The prediction

[a1-patchiness](../a1-patchiness/result.md) found `directed_foraging` robustly **negative** —
hungry agents less path-straight than sated ones, in 30 runs of 30. The proposed explanation was
that the policy caused it: `choose_action` weighted the resource gradient `sated_gradient_factor`
times lower for sated agents, so hungry agents steered by a noisy gradient (wiggly) while sated
agents coasted on heading persistence (straight).

If that were the whole story, raising the factor to 1.0 — hunger no longer changes gradient
weighting at all — should collapse the effect toward zero.

## What happened

| `sated_gradient_factor` | mean pop | n windows | straightness hungry | sated | raw effect | z |
|---|---|---|---|---|---|---|
| 0.25 *(default)* | 326 | 254,349 | 0.448 | 0.560 | **−0.112** | −44.3 |
| 0.50 | 337 | 262,805 | 0.401 | 0.535 | **−0.135** | −62.6 |
| 1.00 *(no coupling)* | 345 | 266,565 | 0.355 | 0.505 | **−0.150** | −72.6 |

Negative in 9 runs of 9. Sample size is nearly constant here (254k–267k), so unlike
[a1-patchiness](../a1-patchiness/result.md) the raw effect and z tell the same story — which is
itself a useful check on [D-054](../../docs/DECISIONS.md#d-054).

**The effect got 34% *stronger* as the hypothesized cause was removed.** The prediction is not
merely unsupported; it points the wrong way.

---

## The actual mechanism: the causation runs backwards

Straightness does not follow from being sated. **Being sated follows from moving straight.**

Measured on one run, 243,725 windows, correlating window straightness against energy:

| | correlation with straightness |
|---|---|
| energy *before* the window | +0.102 |
| energy *after* the window | +0.147 |
| **energy *change* across the window** | **+0.224** |

Straightness predicts how much energy an agent *gains* more than twice as strongly as it reflects
how much it already had. Movement is upstream of energy, not downstream.

The mechanism is structural, and it is in `p01_scarcity.extract`: harvesting takes a cell's entire
stock, first-wins. A cell you just visited is empty. So an agent moving in a straight line keeps
entering fresh cells and eats well, while an agent that turns and doubles back revisits ground it
has already stripped and starves. Straight movers become the sated ones. That is not a behavior
anyone wrote; it falls out of extraction being local and exhaustive.

Raising `sated_gradient_factor` makes *everyone* follow the noisy gradient more, so everyone gets
wigglier — hungry 0.448 → 0.355, sated 0.560 → 0.505. But it also sharpens the sorting: with more
wiggle in the population, the gap between those who happened to travel straight and those who did
not grows. Hence a larger effect, not a smaller one.

## Why the detector was wrong

`directed_foraging` conditions on energy — an outcome of the very behavior it measures — and reads
the resulting correlation as though hunger caused the movement. The shuffled null does not save it:
permuting hunger labels *within* an agent controls for differences between agents, but the
confound is within-agent and temporal, and permutation destroys exactly the temporal ordering that
carries it.

> **A detector must not condition on a state variable that the measured behavior influences.**
> Energy, population, health, and wealth are all downstream of action. Conditioning on them and
> reading the correlation causally inverts the arrow.

This generalizes well beyond A1 and is now [D-056](../../docs/DECISIONS.md#d-056).

## What replaces it

`directed_foraging` should measure movement **up the resource gradient** — whether the direction
chosen points toward more resource than the alternatives — which is a property of the decision
itself and is not downstream of energy. Path straightness cannot be repaired by a better null,
because the problem is the conditioning variable, not the comparison.

The three-way split the redesign has to respect:

| what it measures | how | contaminated by energy? |
|---|---|---|
| persistence | path straightness | yes — straightness earns energy |
| directedness | move direction vs local gradient | no |
| success | energy gained per tick | it *is* the outcome |

## Standing

`sated_gradient_factor` stays a config parameter ([D-055](../../docs/DECISIONS.md#d-055)) and stays
at its default of 0.25. Nothing here justifies changing it: it is not the cause of the effect, and
the value that makes the artifact smallest is not thereby the right value.

Two negative results in a row, both from the pipeline catching its own errors, in under an hour of
compute. This is the stage working as intended.
