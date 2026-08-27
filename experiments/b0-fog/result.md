# b0-fog — does a sense of one's own ignorance change anything?

**Verdict: `exploration_rate` does not fire. B0's second ship criterion is not met, and the
measurement is trustworthy rather than merely negative** — the same detector reads a ~20× larger
effect on the S0 arm, so the silence is a fact about the evolved policy and not about the
instrument.

Fog changes essentially nothing: agents with a known map cover 1.8% more ground than agents without
one, and their *shuffled surrogates* cover 1.8% more too. The entire difference is how far they
walk, not how they order it.

Run: 3 runs, 16 worlds × 30,000 ticks, commit `15c834e`, 1,763 s.
Spec: [spec.yaml](spec.yaml) · raw: [results.json](results.json) · paired: [fog.json](fog.json),
from [analyse.py](analyse.py). The no-fog arm is
[b0-neural](../b0-neural/result.md)'s S1 at `gather_efficiency` 2.5, already on disk — its resolved
config differs from this one in exactly one key, the presence of `primitives.p2`.

---

## The criterion

> **Ship:** `exploration_rate` above null
> *(→ [10-roadmap.md § B0](../../docs/10-roadmap.md#b0--neural-policy))*

Distinct P2 blocks a path touches per agent-tick, against a **shuffled-step** null: the agent's own
displacements, re-ordered, re-walked from the same start. Same step multiset, same path length,
same saturation — everything except the correspondence between where it has been and where it goes
next. The world is the replication unit.

| arm | seed | excess/tick | observed | shuffled | z | verdict |
|---|---|---|---|---|---|---|
| fog | 0 | 0.00067 | 0.1466 | 0.1462 | 1.52 | silent |
| fog | 1 | 0.00076 | 0.1535 | 0.1528 | 2.93 | silent |
| fog | 2 | 0.00008 | 0.1669 | 0.1671 | 0.26 | silent |
| no fog | 0 | 0.00085 | 0.1458 | 0.1447 | 1.60 | silent |
| no fog | 1 | −0.00090 | 0.1616 | 0.1613 | −0.74 | silent |
| no fog | 2 | 0.00033 | 0.1517 | 0.1516 | 0.97 | silent |

**0 of 3 seeds, and the firing rule needs 3.** The excess is ~0.4% of the observed rate. An S1
agent's path covers almost exactly what a random re-ordering of its own steps would cover.

## The control that makes the silence mean something

A silent detector is only informative if it can speak. S0 has a `heading_persistence` gene — a
hand-written reason to commit to a direction — so it is the natural positive control. Scored with
the identical statistic, the identical block size, and the identical landscapes:

| stage | seed | excess/tick | observed | shuffled | z | verdict |
|---|---|---|---|---|---|---|
| **S0** | 0 | **0.01533** | 0.0806 | 0.0795 | 2.13 | silent |
| **S0** | 1 | **0.01212** | 0.0815 | 0.0786 | 1.83 | silent |
| **S0** | 2 | **0.02177** | 0.0937 | 0.0830 | 3.28 | FIRED |
| S1 | 0 | 0.00085 | 0.1458 | 0.1447 | 1.60 | silent |
| S1 | 1 | −0.00090 | 0.1616 | 0.1613 | −0.74 | silent |
| S1 | 2 | 0.00033 | 0.1517 | 0.1516 | 0.97 | silent |

**S0's excess is 14–26× S1's**, and as a share of its own coverage the gap is wider still: 19% of
S0's blocks are excess over its shuffle, against 0.6% of S1's. The detector reads path *ordering*,
S0 has some, S1 has none worth measuring.

**S0 itself only fires in 1 of 3 seeds**, so by the project's own firing rule it is a candidate and
not a finding *(→ [07-detectors.md](../../docs/07-detectors.md))*. That is the honest statement of
this control: it establishes power and a large raw difference between the arms, not that S0
explores.

### The reversal worth noticing

S1 **covers more ground** than S0 — 0.146–0.167 blocks per tick against 0.081–0.094 — and covers
exactly as much as chance while doing it. S0 covers less and covers it deliberately.

That is consistent with [b0-neural](../b0-neural/result.md) rather than in tension with it. S0's
agents find resource and stay on it; wandering widely is what an agent does when it is not finding
anything. **Coverage is not competence**, and a detector that reported "more blocks visited" as
exploration would have called the worse forager the better explorer.

---

## Does fog change anything?

Raw effects, never z *(→ [D-060](../../docs/DECISIONS.md#d-060))*.

| | fog | no fog | delta |
|---|---|---|---|
| excess blocks/tick | 0.0005 | 0.0001 | +0.0004 |
| observed blocks/tick | 0.1557 | 0.1530 | +0.0027 |
| **shuffled** blocks/tick | 0.1553 | 0.1525 | **+0.0028** |
| mean population | 187.0 | 172.4 | +14.6 |

**The observed and shuffled deltas are the same number.** Whatever fog did to how far agents walk,
it did nothing to how they order their steps — which is the only channel through which a known map
could matter.

Survival is a non-result too: +14.6 agents per world, paired over 48 (seed, world) pairs at
t = +1.32, with fog ahead in **24 of 48** — exactly half. Same landscape, same founders, different
brains.

---

## Why this is the expected answer, having now seen it

Fog gives the policy four numbers describing where it has *not* been. Nothing in the world pays for
going there. Resource is already reported by the local patch, energy comes from gathering, and
[D-007](../../docs/DECISIONS.md#d-007) means the only fitness is offspring — so an agent that walks
toward the unknown spends metabolism for information it has no mechanism to cash in.

Exploration pays when the world holds something worth finding that the local patch does not already
show: a richer region beyond the view radius, a resource that moves, a seasonal shift. S0's world at
P1ᴸ⁰ + P10ᴸ⁰ with `rate: 0.0` has none of those. **The capacity was added without the incentive**,
and B0.1 already showed that lineage weights move slowly — ~79 generations was not enough to reach a
hand-written forager, let alone to discover a use for a channel with no payoff attached.

This is the depth-gate argument from [D-022](../../docs/DECISIONS.md#d-022) arriving from the other
direction. That rule forbids richness the *policy* cannot use; this is richness the *world* does not
reward. Both produce the same thing: a channel that costs compute and memory and teaches nothing.

## What would make this question answerable

1. **Turn on P10 drift.** `primitives.p10.rate` is 0.0 in every run this project has made. A
   capacity field that moves makes yesterday's knowledge stale and gives remembering somewhere a
   point. This is the cheapest change and the most likely to matter.
2. **Widen the gap between view and world.** At `view_radius` 2 on a 64 grid an agent sees 0.6% of
   its world, but the resource field is smooth at `patchiness` 0.6 — the local gradient is a decent
   proxy for the global one, so there is little that only exploration could reveal.
3. **Run longer.** B0.1's evidence is that S1 improves steadily and slowly; 30,000 ticks was not
   enough for foraging, and exploration is downstream of foraging.
4. **Not a bigger fog input.** More channels describing the unknown do not create a reason to go
   there.

**What this does not license.** Nothing here says fog is useless, or that agents cannot learn to
explore. It says that in a static world where the local patch already reports what matters, a known
map earns nothing — which is a statement about this world, and a testable prediction about the one
with drift turned on.
