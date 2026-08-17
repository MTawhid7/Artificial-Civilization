"""`directed_foraging` — do agents commit to a direction when they are hungry?

**Definition.** Mean path straightness over windows of consecutive moves, compared
between hungry and sated windows. Straightness is net displacement divided by path
length: 1.0 is a perfectly straight run, 0.0 is a walk that ends where it started.
The statistic is the difference, `straightness(hungry) - straightness(sated)`.

**Null: shuffled.** Permute the hunger labels *within each agent*, then recompute.
This preserves every agent's movement pattern, its overall straightness, and how
much of its life it spent hungry — and destroys only the correspondence between
being hungry and moving straight. It is the most flattering alternative available:
if agents are simply straight movers, or simply hungry a lot, the null reproduces
the statistic exactly.

**Why this is the first real result.** Nothing in `s0_reactive.py` implements
"forage directionally when hungry". The genome makes it *reachable* — a high
`gradient_sensitivity` with low `exploration_temp` produces it — and it is equally
free to evolve the opposite. If this fires, selection found the behavior, because
the only thing selection was ever told to prefer is offspring.

Computable from the sampled tier: 1-in-K agents are logged for their whole lives
(see `chronicle.schema.sample_mask`), so their trajectories are complete.
"""

from __future__ import annotations

import numpy as np

from chronicle import schema as S
from lens.base import ChronicleReader, Firing, wrapped_delta

WINDOW = 8              # consecutive moves per straightness estimate
HUNGER_PERCENTILE = 33  # "hungry" is the lowest third of observed energy
MIN_WINDOWS = 200
THRESHOLD = 3.0         # z against the null
N_PERMUTATIONS = 200


def compute(
    reader: ChronicleReader,
    grid: int | None = None,
    rng: np.random.Generator | None = None,
) -> Firing:
    rng = rng or np.random.default_rng(0)
    if grid is None:
        import yaml

        grid = int(yaml.safe_load((reader.run_dir / "config.yaml").read_text())["world"]["grid"])

    rows = reader.sql(
        f"""
        select world_id, subject, tick, a as x, b as y, c as energy
        from {{events}} where event_type = {S.MOVE}
        order by world_id, subject, tick
        """
    ).fetchnumpy()

    if rows["tick"].size == 0:
        return _empty("no MOVE events in the sampled tier")

    world = rows["world_id"].astype(np.int64)
    subject = rows["subject"].astype(np.int64)
    tick = rows["tick"].astype(np.int64)
    x = rows["x"].astype(np.int64)
    y = rows["y"].astype(np.int64)
    energy = rows["energy"].astype(np.float64)

    hunger_cut = float(np.percentile(energy, HUNGER_PERCENTILE))

    # Windows are built only from strictly consecutive ticks belonging to one
    # agent. A gap means the trajectory is broken and straightness across it would
    # be meaningless, so those windows are dropped rather than approximated.
    same_agent = (subject[1:] == subject[:-1]) & (world[1:] == world[:-1])
    consecutive = same_agent & (tick[1:] == tick[:-1] + 1)

    dx = wrapped_delta(x[:-1], x[1:], grid)
    dy = wrapped_delta(y[:-1], y[1:], grid)

    starts = _window_starts(consecutive, WINDOW)
    if starts.size < MIN_WINDOWS:
        return _empty(f"only {starts.size} complete windows; need {MIN_WINDOWS}")

    offsets = np.arange(WINDOW)
    idx = starts[:, None] + offsets[None, :]
    net_x = dx[idx].sum(axis=1)
    net_y = dy[idx].sum(axis=1)
    straightness = np.hypot(net_x, net_y) / WINDOW

    # A window is "hungry" if the agent was below the cut at its start.
    hungry = energy[starts] < hunger_cut
    agent_of_window = subject[starts]

    if hungry.sum() < 30 or (~hungry).sum() < 30:
        return _empty("too few windows on one side of the hunger cut")

    observed = float(straightness[hungry].mean() - straightness[~hungry].mean())

    # --- null: permute hunger labels within each agent -------------------------
    # Vectorized: a lexsort on (agent, random key) permutes every agent's labels
    # independently in one pass. The obvious Python loop over agents is O(agents x
    # permutations) and takes minutes on a full run, which in practice means the
    # null quietly stops being run.
    order = np.argsort(agent_of_window, kind="stable")
    grouped_agent = agent_of_window[order]
    grouped_labels = hungry[order]
    grouped_straight = straightness[order]

    null = np.empty(N_PERMUTATIONS, dtype=np.float64)
    for i in range(N_PERMUTATIONS):
        keys = rng.random(grouped_labels.size)
        within = np.lexsort((keys, grouped_agent))
        shuffled = grouped_labels[within]
        if shuffled.all() or not shuffled.any():
            null[i] = 0.0
            continue
        null[i] = grouped_straight[shuffled].mean() - grouped_straight[~shuffled].mean()

    null_mean, null_std = float(null.mean()), float(null.std())
    z = (observed - null_mean) / max(null_std, 1e-12)

    return Firing(
        detector="directed_foraging",
        magnitude=observed,
        null_mean=null_mean,
        null_std=null_std,
        effect_size=z,
        threshold=THRESHOLD,
        fired=bool(z > THRESHOLD),
        tick_range=(int(tick.min()), int(tick.max())),
        n_observations=int(starts.size),
        detail={
            "straightness_hungry": float(straightness[hungry].mean()),
            "straightness_sated": float(straightness[~hungry].mean()),
            "hunger_cut_energy": hunger_cut,
            "n_hungry_windows": int(hungry.sum()),
            "window_length": WINDOW,
        },
    )


def _window_starts(consecutive: np.ndarray, length: int) -> np.ndarray:
    """Indices where `length` consecutive steps are all available.

    Windows are non-overlapping so that each step contributes to exactly one
    estimate; overlapping windows would correlate the observations and inflate
    the effective sample size, which makes the null look tighter than it is.
    """
    runs = np.flatnonzero(consecutive)
    if runs.size == 0:
        return np.empty(0, dtype=np.int64)
    breaks = np.flatnonzero(np.diff(runs) != 1) + 1
    starts: list[np.ndarray] = []
    for segment in np.split(runs, breaks):
        n = segment.size // length
        if n:
            starts.append(segment[: n * length : length])
    return np.concatenate(starts) if starts else np.empty(0, dtype=np.int64)


def _empty(reason: str) -> Firing:
    return Firing(
        detector="directed_foraging",
        magnitude=0.0, null_mean=0.0, null_std=0.0, effect_size=0.0,
        threshold=THRESHOLD, fired=False, tick_range=(0, 0), n_observations=0,
        detail={"skipped": reason},
    )
