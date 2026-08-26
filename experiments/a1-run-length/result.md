# a1-run-length — result

**Status: the concern is answered, and A1's conclusion survives.** No new simulation was run.
Reproduce with `uv run python experiments/a1-run-length/analyse.py`.

---

## What was asked

A2 measured between-world divergence still climbing at year 2,500, while every A1 result was scored
at 15,000 ticks. That raised a live question about a conclusion already committed:

> **Was A1's negative dose-response an artifact of observation length?**

A1 reported `corr(patchiness, advantage) = −0.926` — gradient-following gets *weaker* as resources
clump — and built an explanation on it about agents calibrating reliance on local information. If
that slope were still moving at 15,000 ticks, the explanation would be premature.

## How, and why not the obvious way

The obvious design is to re-run A1 at 30,000 ticks and compare. **That design was specified, costed,
and abandoned** — see [spec.yaml](spec.yaml). It would have confounded window length with everything
that differs between two sets of worlds, and between-world spread in this project is roughly ten to
one.

The better design was already available: `gradient_ascent` gained a `max_tick` parameter, so the 30
committed A1 runs can each be scored at four windows and compared **paired** — same worlds, same
seeds, same landscapes, only the observation window differs. 120 scorings, zero new compute.

## What happened

**The level rises. The order does not.**

| window | 0.0 | 0.2 | 0.4 | 0.6 | 0.8 | 1.0 | corr(patchiness, advantage) |
|---|---|---|---|---|---|---|---|
| 3,750 | 0.170 | 0.195 | 0.168 | 0.150 | 0.135 | 0.127 | **−0.876** |
| 7,500 | 0.214 | 0.251 | 0.222 | 0.190 | 0.161 | 0.147 | **−0.868** |
| 11,250 | 0.267 | 0.292 | 0.262 | 0.229 | 0.188 | 0.165 | **−0.929** |
| 15,000 | 0.304 | 0.333 | 0.296 | 0.267 | 0.217 | 0.189 | **−0.926** |

Advantage grows **1.5× to 1.8×** across the window range at every patchiness level — selection is
still improving gradient-following at 15,000 ticks and has not converged. The correlation with
patchiness does not move: it is between −0.87 and −0.93 across a **fourfold** range of observation
windows, with no trend.

**It is not one seed's doing.** Computed within each seed separately, the correlation is negative in
**20 of 20** seed–window combinations:

| window | seed 0 | seed 1 | seed 2 | seed 3 | seed 4 | mean |
|---|---|---|---|---|---|---|
| 3,750 | −0.707 | −0.705 | −0.642 | −0.139 | −0.705 | −0.579 |
| 7,500 | −0.579 | −0.679 | −0.593 | −0.393 | −0.830 | −0.615 |
| 11,250 | −0.511 | −0.665 | −0.690 | −0.707 | −0.798 | −0.674 |
| 15,000 | −0.460 | −0.674 | −0.720 | −0.804 | −0.738 | −0.679 |

Short windows are noisier per seed — seed 3 reads −0.139 at 3,750 ticks and −0.804 at 15,000 — which
is what a smaller sample should look like and not a trend in the effect.

**Rank order is identical at 3,750 and 15,000**, across a fourfold window range. There is one
transposition at 7,500, between patchiness 0.0 (0.214) and 0.4 (0.222) — two adjacent levels
separated by 0.008, which is well inside the noise. Reported because "stable except where it
wasn't" is the honest description.

**The evolutionary statistic behaves the same way.** Selection gain — last tenth of the scored window
against the first — grows with window, and its correlation with patchiness strengthens and then
settles: −0.631, −0.863, −0.958, −0.921.

## The answer

**The magnitude is length-dependent; the slope is not.**

A1's headline advantage of +0.268 is a **lower bound** — it was measured before selection finished,
and a longer run would report a larger number at every patchiness level. A1's *conclusion* — that
gradient-following weakens as resources clump — is converged by the earliest window measured and is
not an artifact of stopping at 15,000 ticks.

The gene-level explanation A1 gave is therefore safe to keep building on: exploration temperature
tracking patchiness at r = +0.937 while gradient sensitivity holds steady, which is the S0 shadow of
belief calibrated to evidence quality *(→ [a1-gradient-ascent](../a1-gradient-ascent/result.md))*.

## A free check on the clustering fix

Sample size grows **5.1×** across the window range while the effect size does not move:

| window | moves scored | mean z |
|---|---|---|
| 3,750 | 442,110 | 5.59 |
| 7,500 | 932,006 | 4.90 |
| 11,250 | 1,542,733 | 4.88 |
| 15,000 | 2,257,025 | 5.11 |

That is [D-058](../../docs/DECISIONS.md#d-058) working, measured rather than asserted. Before
clustering on world, this detector's z tracked the number of logged rows — the same defect that
manufactured a spurious dose-response at r = 0.97 under [D-054](../../docs/DECISIONS.md#d-054).
Five times the rows, no change in z, is what a correctly clustered statistic looks like.

## What this cost, and the thing worth remembering

Zero compute for the answer. The **abandoned** 30,000-tick design cost three failed headroom
prechecks and one equilibrium probe before the cost became clear — see [spec.yaml](spec.yaml).

> The check that answered the question was available from the start and was not the one first
> reached for. Adding a window parameter to an existing detector beat running a new experiment, on
> both cost and inferential strength, and the only reason the experiment came first is that
> re-running is the more obvious move.
