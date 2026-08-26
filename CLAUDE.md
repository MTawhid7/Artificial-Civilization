# Artificial Civilization — working notes

A **comparative history laboratory**: a machine that produces thousands of divergent histories from
controlled initial conditions, plus the tooling to ask causal questions of them. Agents are numeric,
not LLMs. Twelve primitives generate everything; no phenomenon is implemented directly.

**Start here:** [docs/14-handoff.md](docs/14-handoff.md) — current state and what to build next.
`docs/` is canonical; when docs and code disagree, the docs are wrong *and get fixed immediately*.

---

## Rules that break things silently if violated

These are not style preferences. Each one has a decision record and, usually, a run that was thrown
away discovering it.

1. **Draw RNG at a shape fixed by config, then mask.** Never draw per living agent — stream position
   must not depend on how many agents are alive, or a fork diverges from its parent with no symptom.
   *(D-053)*
2. **Never renumber an event enum.** Recorded Chronicles store integers. Append only. *(chronicle/schema.py)*
3. **No phenomenon names in `src/core/`.** No `war`, `trade`, `revolution`. Those words name
   measurements and live only in `src/lens/`. CI greps for this. *(D-002)*
4. **`src/core/` imports nothing from the analysis layer** — no duckdb, matplotlib, lens, digest.
   The arrow runs one way: core writes, everything else reads. CI greps for this.
5. **Sampling consumes no randomness.** The log tier must not change the simulation.
   *(chronicle/schema.py `sample_mask`)*
6. **Append to `DETECTORS` in `forge/sweep.py`, never insert.** Detector RNG is seeded by position;
   inserting silently changes every null below it.
7. **Determinism is per-platform, not cross-ISA.** `np.exp` differs in the last ulp between NEON and
   AVX. When the cross-machine test goes red on a new platform, add that platform's golden. Do not
   re-litigate. *(D-057)*

## The traps this project actually falls into

The risk register predicted mechanism failures and missed almost every inference failure. The core
has needed one correction in three stages; the measurement layer has produced seven and all three
withdrawn claims. Before writing a detector, read
[docs/07-detectors.md § Detector contract](docs/07-detectors.md#detector-contract).

- **A null model is necessary and not sufficient.** `directed_foraging` had one, beat it in 39 runs,
  and was wrong. A null asks *is this chance?*; it never asks *am I measuring the right thing?* *(D-056)*
- **Declare the replication unit.** A thousand agents in one world is N=1. *(D-058)*
- **Never rank two arms by z.** A control that works shrinks between-replicate variance and inflates
  its own z. Compare raw effects. *(D-060)*
- **Never plot z alone across a sweep.** It tracks sample size, which tracks population. *(D-054)*
- **Never condition on a variable the measured behavior causes.** *(D-056)*
- **A presentation choice can manufacture a finding** — sort order, per-panel scales, unqualified
  markers. Verdicts travel with markers. *(D-063)*
- **Check the ceiling.** `population.capacity` has been mis-set in every experiment that has run.
  The precheck now refuses; do not `--skip-precheck` to make a red gate go away. *(D-065)*

## Commands

```bash
uv sync --all-extras                                     # exact versions from uv.lock
uv run pytest                                            # the gate — green before anything else
uv run python tools/check_links.py .                     # docs are cross-referenced ~450 times

uv run python -m bench.bench_tick --scales all           # tick cost
uv run python -m bench.bench_policy                      # S1 forward-pass cost

uv run python -m forge.run configs/frozen/a0_smoke.yaml --seed 0
uv run python -m forge.sweep experiments/<name>/spec.yaml   # runs the headroom precheck first

uv run python -m digest.build corpus/runs/<run_id>
uv run python tools/render_wall.py corpus/runs/*/digest.json -o wall.png
uv run python tools/build_atlas.py corpus/runs/*/digest.json    # -> atlas/wall.html
```

## Conventions

- An experiment is `experiments/<name>/{spec.yaml, result.md}` and **`result.md` is committed
  whether or not the hypothesis survived.** Negative results are the point.
- New design decision → append to `docs/DECISIONS.md` with an explicit `<a id="d-nnn">` anchor
  (GitHub slugs include the whole heading, so `#d-067` alone scrolls nowhere and CI fails).
- New detector → one file in `src/lens/`, plus two tests: a synthetic log where it must fire and one
  where it must stay silent.
- `corpus/` is git-ignored and fully regenerable from `(config, seed)`. Currently ~2.8 GB; safe to delete.
- Runs record a `-dirty` code version from an uncommitted tree. Commit before a run that matters.
