"""Run directory → `narrative/`. The Historian's entry point.

    python -m historian.build corpus/runs/<run_id> --worlds 4 --eras 10

**The Historian is never attached to a run.** It is a separate command over a
finished run directory, which is how the fourth ship criterion — *a run with the
Historian attached produces a byte-identical Chronicle to one without* — is met by
construction rather than by care. There is no code path from here into a
simulation, and `tests/test_historian.py` hashes every file in the run directory
before and after to keep it that way.

Everything is written under `narrative/`. Never `metrics/`, which is Lens output;
the directory split is the first line between prose and evidence.

**A completed era is never re-billed.** The cache key is the brief hash plus the
prompt version plus the model, so re-running is free, rebuilding a digest that did
not change the numbers is free, and only an era whose facts actually moved costs
anything *(→ docs/11-engineering.md § LLM usage)*.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from digest import schema as D
from historian import NARRATIVE_VERSION, facts, prompt, verify, write
from historian import client as client_module
from historian.client import Client, GeminiClient, MissingKeyError, ReplayClient


def cache_key(brief: dict) -> str:
    """Keyed on what was asked, deliberately **not** on who answered.

    The obvious key includes the model, and it is wrong. Free-tier quota is
    per-model and capped per day, so a long run legitimately continues on a
    different model tomorrow — and a model-keyed cache would answer that by
    re-requesting every era it already had, which is the one thing the cache
    exists to prevent. The narrative records the model that wrote it, so nothing
    is lost by leaving it out of the key.

    The prompt version *is* in the key: a changed prompt is a changed question,
    and the old answer is to a question no longer being asked.
    """
    return D.digest_hash({
        "brief": facts.brief_hash(brief),
        "prompt_version": prompt.PROMPT_VERSION,
    })


def narrate(brief: dict, client: Client, *, cache_dir: Path | None = None,
            repair: bool = True, refresh: bool = False) -> dict:
    """One brief → one verified narrative. Cached, verified, and repaired once.

    The repair round is worth its tokens only because it is told *why*: most
    rejections are a single banned word or a single unsourced number, and a model
    handed the reason fixes that sentence. A model told merely "that was wrong"
    rewrites the passage and loses the good sentences with the bad — which is why
    the accepted sentences are kept across the round rather than regenerated.
    """
    cached = cache_dir / f"{cache_key(brief)}.json" if cache_dir else None
    if cached is not None and cached.exists() and not refresh:
        return json.loads(cached.read_text())

    is_era = brief.get("kind") == "era"
    ask = prompt.era_prompt(brief) if is_era else prompt.preface_prompt(brief)

    payload, usage = client.complete(prompt.SYSTEM, ask, prompt.RESPONSE_SCHEMA)
    title = str(payload.get("title", "")).strip()
    accepted, rejected = verify.verify(payload.get("sentences", []), brief)
    generated = len(payload.get("sentences", []))

    if repair and rejected:
        note = prompt.repair_prompt(brief, verify.repair_note(rejected), len(accepted))
        retry, retry_usage = client.complete(prompt.SYSTEM, note, prompt.RESPONSE_SCHEMA)
        fixed, still_bad = verify.verify(
            retry.get("sentences", []), brief, stage="repair"
        )
        accepted += fixed
        generated += len(retry.get("sentences", []))
        # The first-round rejections stay in the record even when the repair
        # succeeded. What the model had to be stopped from writing is part of what
        # this stage measured.
        rejected = rejected + still_bad
        for k, v in retry_usage.items():
            usage[k] = usage.get(k, 0) + v

    # A title is a label rather than a claim, so it is not cited — but it may not
    # name a phenomenon either, and it is the line a reader sees first.
    if verify.title_reasons(title):
        title = _fallback_title(brief)

    out = {
        "narrative_version": NARRATIVE_VERSION,
        "run_id": brief.get("run_id"),
        "kind": brief.get("kind"),
        "title": title,
        "sentences": [{"text": s.text, "cites": s.cites} for s in accepted],
        "rejected": [r.to_dict() for r in rejected],
        "model": client.name,
        "prompt_version": prompt.PROMPT_VERSION,
        "brief_hash": facts.brief_hash(brief),
        "generated": generated,
        "accepted": len(accepted),
        "usage": usage,
    }
    if is_era:
        out["world"] = brief["world"]
        out["era_index"] = brief["era"]["index"]
    else:
        out["worlds"] = brief.get("worlds", [])

    if cached is not None:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    return out


def _fallback_title(brief: dict) -> str:
    if brief.get("kind") != "era":
        return "A run"
    y0, y1 = brief["era"]["year_range"]
    return f"Years {y0:,.0f}–{y1:,.0f}"


def build(run_dir: str | Path, client: Client, *, worlds: list[int] | None = None,
          n_eras: int = facts.DEFAULT_ERAS, n_worlds: int = facts.DEFAULT_WORLDS,
          out_dir: Path | None = None, progress: bool = True,
          refresh: bool = False) -> dict:
    """Narrate a run. Writes `narrative/` and returns a summary."""
    run_dir = Path(run_dir)
    data = facts.load(run_dir)

    # Default is the first N world ids, deliberately not the most interesting
    # ones. Narrating the extremes is D-063 — a presentation choice that
    # manufactures a finding — and `--worlds` exists so an override is a
    # documented act rather than a default nobody notices.
    chosen = worlds or [int(w) for w in data.world_ids[:n_worlds]]

    out_dir = Path(out_dir) if out_dir else run_dir / "narrative"
    cache_dir = out_dir / "cache"

    preface = facts.preface_brief(data, chosen, n_eras)
    if progress:
        print(f"  preface  ({len(preface['facts'])} facts)", flush=True)
    preface_n = narrate(preface, client, cache_dir=cache_dir, refresh=refresh)
    write.write_text(
        out_dir / "preface.md",
        write.preface_markdown(preface_n, preface, client.name, prompt.PROMPT_VERSION),
    )
    write.write_text(out_dir / "preface.json",
                     json.dumps(preface_n, indent=2, sort_keys=True))

    n_bounds = len(facts.era_bounds(data.n_frames, n_eras))
    accepted = generated = 0
    usage: dict[str, int] = {}

    for world in chosen:
        pairs = []
        for era in range(n_bounds):
            brief = facts.era_brief(data, world, era, n_eras)
            narrative = narrate(brief, client, cache_dir=cache_dir,
                                refresh=refresh)
            pairs.append((narrative, brief))
            accepted += narrative["accepted"]
            generated += narrative["generated"]
            for k, v in narrative.get("usage", {}).items():
                usage[k] = usage.get(k, 0) + v
            if progress:
                print(f"  world {world:>3}  era {era + 1:>2}/{n_bounds}  "
                      f"{narrative['accepted']}/{narrative['generated']} kept",
                      flush=True)

        write.write_text(
            out_dir / f"world_{world:02d}.md",
            write.world_markdown(world, preface["run_id"], client.name,
                                 prompt.PROMPT_VERSION, pairs),
        )
        write.write_text(
            out_dir / f"world_{world:02d}.json",
            json.dumps(
                write.viewer_payload(world, preface["run_id"], client.name,
                                     prompt.PROMPT_VERSION, pairs),
                indent=2, sort_keys=True,
            ),
        )

    accepted += preface_n["accepted"]
    generated += preface_n["generated"]
    for k, v in preface_n.get("usage", {}).items():
        usage[k] = usage.get(k, 0) + v

    return {
        "run_id": preface["run_id"],
        "out_dir": str(out_dir),
        "worlds": chosen,
        "eras": n_bounds,
        "accepted": accepted,
        "generated": generated,
        "acceptance_rate": round(accepted / max(generated, 1), 3),
        "usage": usage,
        "model": client.name,
        "prompt_version": prompt.PROMPT_VERSION,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dir")
    p.add_argument("--worlds", type=int, default=facts.DEFAULT_WORLDS,
                   help="how many worlds to narrate (default: the first 4)")
    p.add_argument("--world-ids", type=int, nargs="+", default=None,
                   help="narrate these world ids instead. Choosing them by outcome "
                        "is a presentation choice (D-063); say so in result.md")
    p.add_argument("--eras", type=int, default=facts.DEFAULT_ERAS)
    p.add_argument("--model", default=None,
                   help=f"default: {client_module.MODEL}. Free-tier quota is "
                        "per-model, so a model swap is also the way past a "
                        "daily cap — and it invalidates the cache, because the "
                        "narrative records which model wrote it")
    p.add_argument("--refresh", action="store_true",
                   help="re-ask for eras that are already cached. Costs quota; "
                        "the only reason is a deliberate re-narration")
    p.add_argument("-o", "--out", default=None,
                   help="default: <run_dir>/narrative")
    args = p.parse_args()

    try:
        client = GeminiClient(model=args.model or client_module.MODEL)
    except MissingKeyError as exc:
        print(f"\n  {exc}\n", file=sys.stderr)
        raise SystemExit(2)

    summary = build(
        args.run_dir, client,
        worlds=args.world_ids, n_eras=args.eras, n_worlds=args.worlds,
        out_dir=Path(args.out) if args.out else None, refresh=args.refresh,
    )

    tokens = summary["usage"]
    cost = (tokens.get("input_tokens", 0) * 0.75
            + tokens.get("output_tokens", 0) * 3.75) / 1e6
    print(
        f"\n  {len(summary['worlds'])} worlds x {summary['eras']} eras "
        f"-> {summary['out_dir']}\n"
        f"  {summary['accepted']}/{summary['generated']} sentences accepted "
        f"({summary['acceptance_rate'] * 100:.1f}%)\n"
        f"  {tokens.get('input_tokens', 0):,} in / "
        f"{tokens.get('output_tokens', 0):,} out  "
        f"(free tier; ${cost:.2f} at the paid rate)"
    )


if __name__ == "__main__":
    main()
