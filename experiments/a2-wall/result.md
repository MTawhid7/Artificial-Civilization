# a2-wall — result

**Status: the wall exists, and it shows what it was built to show.** 102 worlds from an identical
configuration, 30,000 ticks each (~2,500 simulated years), 43.6 minutes.
Spec: [spec.yaml](spec.yaml). Picture: [wall.png](wall.png).

![the fingerprint wall](wall.png)

---

## What was asked

Nothing about a parameter. This is not a sweep and there is no dose-response curve in it. The
question is the project's founding premise, which had been asserted in every document and never
shown:

> **Do identical starting conditions actually produce different histories?**

If they do not — if a hundred worlds under one config converge on one trajectory — then the corpus
is not a corpus, it is one run measured a hundred times, and every effect size the project has
reported is built on a replication unit that does not replicate.

## What happened

**They diverge, and the divergence compounds.**

| window | mean pop | between-world SD | within-world SD | ratio |
|---|---|---|---|---|
| years 0–625 | 249 | 87.0 | 52.8 | **1.65** |
| years 625–1,250 | 404 | 282.5 | 54.3 | **5.20** |
| years 1,250–1,875 | 486 | 357.7 | 42.3 | **8.45** |
| years 1,875–2,500 | 563 | 396.4 | 42.3 | **9.38** |

By the end of the run, worlds differ from each other **nine times more than each fluctuates over
time**. Final populations span 192 to 1,928 — a **tenfold spread** from one config. Mean pairwise
trajectory correlation is 0.572: family resemblance, not repetition.

The ratio is the number that matters, not the spread. A large spread with a large within-world
variance would just be noisy worlds; a large spread with a *small* within-world variance means
each world has settled somewhere and the somewheres differ. The second is what a replication unit
has to look like, and it is what the last three rows show.

**Nothing was tuned to produce this.** Patchiness 0.6 was chosen from A1's measured divergence,
before this run existed; the only later change was raising the population ceiling, which was
forced by the pinning described below and moves against the effect rather than for it.

## The detectors

| detector | verdict | observed | null | z |
|---|---|---|---|---|
| `pop_stability` | **FIRING**, 3/3 seeds | 0.128 | 0.049 ± 0.004 | **+17.5** |
| `collapse` | silent, 0/3 seeds | 1.157 | 1.29 ± 0.12 | **−1.16** |
| `gradient_ascent` | **skipped** — not measurable here | — | — | — |

### `collapse` is silent, and the sign is the informative part

The detector counts drawdown episodes — population falling more than 35% below its running peak —
against a null that shuffles the run's own steps, preserving its volatility and destroying only
the order. Observed rate is **below** the null in all three seeds (z = −2.14, −0.70, −0.57).

That is what regulation looks like. A mean-reverting population climbs back before a drawdown gets
deep, so it produces *fewer* deep drawdowns than a random walk built from the same steps.
`pop_stability` firing at z = +17.5 on the same runs is the independent corroboration: two
detectors, different statistics, same conclusion about the same worlds.

This was predicted in the detector's docstring before the run, which is the only reason it counts
for anything. A negative result whose direction was guessed afterwards is a story.

**The threshold was not moved.** A >35% drawdown is common — measured across the 480
world-instances of the A1 sweep, ~90% of worlds show one — so a detector counting them without a
null would have fired on essentially every run in the corpus and meant nothing. The null is doing
all of the work here.

### `gradient_ascent` was skipped, not silent

This run is logged at `log_tier: aggregated`, which writes no `PERCEIVE` events, so the detector
has nothing to read. The sweep first reported that as **silent** — indistinguishable in the output
table from *measured and did not fire*. It now reports `skipped` with the reason.

The distinction is not cosmetic. A results table that renders "not measurable on this data" as
"did not fire" is how a detector comes to be believed tested when it never ran, and the belief is
invisible afterwards because the row looks normal.

## The array regulated the experiment, twice

**First attempt, capacity 1,200: 4 of 102 worlds pinned at the ceiling.** The capacity was
projected from A1's measured mean of ~344 at this patchiness, with what looked like 3× headroom.
It was wrong because A1's populations were measured at 15,000 ticks and were **still climbing** —
over 30,000 ticks the mean reaches 525 and the largest worlds run past 1,200.

A pinned world matters more in a picture than in a table. It renders as a flat, full-height bar,
and several of them side by side read as *these worlds converged on the same outcome* — a claim
about the world produced entirely by the array. Re-run at capacity 2,000.

**Second attempt, capacity 2,000: no world pinned.** Highest world-mean is 1,423 of 2,000 (71%).
Three worlds still touch the ceiling at their *peaks*, for 1.4%, 1.9% and 3.2% of their frames
respectively — 0.06% of all frames in the wall. Their peaks are clipped; their trajectories are
not. Stated rather than hidden, because a clipped peak biases `collapse` downward: a drawdown is
measured from a peak, and a peak the array truncated is a peak that was never reached.

### A hypothesis the data cannot settle

`collapse`'s mean z moved from **−4.29 at capacity 1,200 to −1.14 at capacity 2,000**. The obvious
reading is that the ceiling was manufacturing part of the suppression — a pinned world sits flat
at its peak and cannot draw down from it — which would make this a third instance of the array
regulating a *measurement* rather than the world, alongside
[D-054](../../docs/DECISIONS.md#d-054) and [D-060](../../docs/DECISIONS.md#d-060).

**It is not established.** Three seeds per arm, Welch t = −1.71 on ~2.3 df against a critical 4.30,
and the two ranges overlap (−7.08…−0.98 against −2.14…−0.57). Recorded as a hypothesis with a
cheap test attached — sweep capacity as an axis — not as a finding. The reading is plausible and
the seed noise is larger than the effect.

## What the picture does and does not claim

The strip draws **every** drawdown it is given. The caption states that they are not above the
volatility-matched null, and the digest carries the detector's verdict beside the markers so a
renderer cannot show one without the other.

This is the visualization-layer version of the rule that produced D-054 and D-060: a red mark on a
timeline reads as significance whether or not any was measured. The verdict travels with the
marks for the same reason z travels with a raw effect.

Two other choices in the same spirit:

- **World order, never outcome order** *(→ [D-063](../../docs/DECISIONS.md#d-063))*. Sorting a
  hundred strips by final population produces a smooth gradient, and a gradient reads as a
  finding — but the identical picture appears if the outcomes are pure noise. `--sort` exists and
  is not the default.
- **One scale for every world.** Per-world normalization would rescale each strip to its own
  extremes and erase exactly the divergence the wall exists to show. Enforced in the digest at
  quantization time and again at render time, because decoding and re-normalizing would quietly
  undo it.

**No extinctions.** At patchiness 0.6 all 102 worlds survive 2,500 years, so the wall has no
breaks and no ✕ marks — the design mock in
[09-visualization.md](../../docs/09-visualization.md) promises drama this S0 world does not yet
contain. Marginal worlds exist at patchiness 1.0, where 3 of 80 A1 instances died. Not run here:
the wall's job was divergence under viable conditions, and picking conditions for their body count
would be choosing the picture before the measurement.

## The digest

| | |
|---|---|
| size | **0.91 MB** per run of 34 worlds × 2,000 frames — budget is 5 MB |
| purity | building twice from one run directory gives an identical hash |
| inputs | `aggregate.parquet` + checkpoints; **no per-agent events at all** |
| page | 2.11 MB self-contained HTML, no network, no build step |

The run was logged at `log_tier: aggregated` — 25 MB of Chronicle instead of ~900 MB — and the
digest is complete anyway. That is [D-047](../../docs/DECISIONS.md#d-047)'s tiering claim used
rather than restated.

**The schema has two consumers on purpose.** A contract answerable only to its own producer is
untested, so the Python renderer and the browser page were written against the same spec and their
decoders checked against each other on real data before either was trusted. They agree to the last
decimal. The cross-check also caught the marker width: one pixel is invisible once 2,000 columns
are scaled to the width a canvas is displayed at.

Unimplemented fields — `territory`, `belief_layer`, `tech_level` and the rest — are listed in the
digest's own `reserved` array rather than filled with zeros. An Atlas reading zeros cannot tell
*nothing happened* from *nothing was measured*.

## Reproducing

```bash
uv run python -m forge.sweep experiments/a2-wall/spec.yaml          # ~44 min
for r in <the three run ids in results.json>; do
  uv run python -m digest.build corpus/runs/$r
done
uv run python tools/render_wall.py corpus/runs/*/digest.json -o experiments/a2-wall/wall.png
uv run python tools/build_atlas.py corpus/runs/*/digest.json        # -> atlas/wall.html
```

## What this changes

Nothing about the design, and one thing about confidence: **the replication unit replicates.**
Every effect size A1 reported clusters on worlds, and this is the first direct measurement that
worlds are worth clustering on. Had the ratio come out near 1.0, the honest response would have
been to revisit every result in the corpus.

The open thread from A1 is untouched and still the most interesting one — agents calibrating
reliance on local information to that information's reliability
*(→ [a1-gradient-ascent](../a1-gradient-ascent/result.md))*. Measuring it needs the sampled tier,
which this stage deliberately did not write.
