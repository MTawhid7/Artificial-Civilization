"""The unguarded control: what does the grounding gate actually catch?

The main pass accepted 238 of 238 sentences. Taken alone that number says nothing
useful, and reporting it as a success would be the exact mistake this project keeps
making in its measurement layer: a gate that never fires is indistinguishable from
a gate that does not work.

There are two explanations and they have opposite meanings.

    (a) the prompt states the rules, so the model obeys them and the gate is
        redundant on this input
    (b) the checks are too weak to catch what the model would have written anyway

The control separates them. Same facts, same model, same verifier — but the system
instruction keeps only the requirement to cite, and drops the three content rules:
no invented numbers, no phenomena, no causation. If the gate then starts rejecting,
(a) is right and 100% is the prompt working. If it still accepts everything, (b)
is right and the checks need to be harder.

This costs a handful of API calls against a per-model daily quota, so it runs over
a few briefs rather than all 41. It is a control, not a second corpus.

    uv run python experiments/a3-historian/control.py --briefs 6
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[2] / "src")]

from historian import facts, prompt, verify              # noqa: E402
from historian.client import GeminiClient                # noqa: E402

RUN = "corpus/runs/d712b54d58fde26db2e9d1aa"

# Rule 1 only. The citation requirement has to stay: without ids there is nothing
# to check a number against, and the control would be measuring whether the model
# emits a JSON field rather than whether it invents facts.
UNGUARDED = """\
You are a historian of a synthetic world, writing from a table of measured facts.

Write vivid, engaging historical prose. Give the era a title.

Every sentence must carry the ids of the facts it draws on, in its `cites` field.
"""


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--briefs", type=int, default=6)
    p.add_argument("--model", default="gemini-3.5-flash-lite")
    p.add_argument("--run", default=RUN)
    p.add_argument("-o", "--out", default="experiments/a3-historian/control.json")
    args = p.parse_args()

    data = facts.load(args.run)
    client = GeminiClient(model=args.model)

    # Spread across worlds and eras rather than taking the first N, so the control
    # is not accidentally a measurement of one world's quiet opening.
    picks = [(int(w), e) for e in (0, 4, 9) for w in data.world_ids[:2]][:args.briefs]

    rows, kept, made = [], 0, 0
    tally: dict[str, int] = {}

    for world, era in picks:
        brief = facts.era_brief(data, world, era)
        payload, _ = client.complete(UNGUARDED, prompt.era_prompt(brief),
                                     prompt.RESPONSE_SCHEMA)
        ok, bad = verify.verify(payload.get("sentences", []), brief)
        kept += len(ok)
        made += len(payload.get("sentences", []))
        for r in bad:
            for reason in r.reasons:
                # The reason string carries the offending token; the class of
                # failure is what the table needs.
                tally[reason.split(":")[0]] = tally.get(reason.split(":")[0], 0) + 1
        rows.append({
            "world": world, "era": era, "title": payload.get("title", ""),
            "accepted": len(ok), "generated": len(payload.get("sentences", [])),
            "rejected": [r.to_dict() for r in bad],
        })
        print(f"  world {world} era {era + 1:>2}  {len(ok)}/{len(payload.get('sentences', []))} "
              f"kept   {'; '.join(sorted({r.reasons[0].split(':')[0] for r in bad})) or '—'}",
              flush=True)

    out = {
        "arm": "unguarded",
        "model": args.model,
        "prompt_version": prompt.PROMPT_VERSION,
        "run_id": data.meta.get("run_id"),
        "briefs": len(rows),
        "accepted": kept,
        "generated": made,
        "acceptance_rate": round(kept / max(made, 1), 3),
        "rejections_by_class": tally,
        "detail": rows,
    }
    Path(args.out).write_text(json.dumps(out, indent=2) + "\n")
    print(f"\n  unguarded: {kept}/{made} accepted ({kept / max(made, 1) * 100:.1f}%)")
    for name, n in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"    {name:<34} {n}")
    print(f"  wrote {args.out}")


if __name__ == "__main__":
    main()
