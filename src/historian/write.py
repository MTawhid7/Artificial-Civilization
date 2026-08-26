"""Narrative objects → the files on disk.

Two things happen here that are part of the containment rather than presentation.

**The banner is in the file.** Every `.md` opens by naming the model, the prompt
version and the run. 09-visualization.md requires generated narrative to be
*visibly labelled* wherever it is displayed, and a file gets pasted into places the
viewer's label does not follow it — a chat, an issue, a slide. The label has to
travel with the bytes.

**The ledger is in the file too.** Clean prose reads better without inline citation
markers, so the citations go underneath: every sentence numbered, its fact ids, and
the tick range each of those ids points at. A reader who wants to check a claim can
do it from the markdown alone, without opening the JSON sidecar.

The rejection count is printed beside the acceptance count for the same reason it
is stored: a narrative that showed only what survived would report perfect
grounding by construction.
"""

from __future__ import annotations

from pathlib import Path

BANNER = (
    "> **Generated narrative — not evidence.**\n"
    "> Written by {model} from aggregate rows and detector output, prompt v{prompt}.\n"
    "> Every sentence is cited; the ledger under each era gives the rows.\n"
    "> Prose is an interface, never a finding *(→ docs/GLOSSARY.md)*.\n"
)


def _fact_source(fact: dict) -> str:
    return str(fact.get("source", "—"))


def era_section(narrative: dict, brief: dict) -> str:
    """One era: title, years, prose, ledger."""
    facts = {f["id"]: f for f in brief.get("facts", [])}
    era = brief["era"]
    y0, y1 = era["year_range"]
    t0, t1 = era["tick_range"]

    lines = [
        f"## {era['index'] + 1}. {narrative.get('title') or 'Untitled'}",
        "",
        f"*Years {y0:,.0f}–{y1:,.0f} · ticks {t0:,}–{t1:,}*",
        "",
    ]

    sentences = narrative.get("sentences", [])
    if sentences:
        lines += [" ".join(s["text"] for s in sentences), ""]
    else:
        lines += ["*Every sentence written for this era failed the grounding "
                  "checks and was removed.*", ""]

    if sentences:
        lines += ["<details><summary>ledger</summary>", ""]
        lines += ["| # | cites | source |", "|---|---|---|"]
        for i, s in enumerate(sentences, start=1):
            cites = ", ".join(f"`{c}`" for c in s["cites"])
            sources = " · ".join(
                _fact_source(facts[c]) for c in s["cites"] if c in facts
            )
            lines.append(f"| {i} | {cites} | {sources} |")
        lines += ["", "</details>", ""]

    rejected = narrative.get("rejected", [])
    if rejected:
        lines += [
            f"<details><summary>{len(rejected)} sentence(s) removed by the "
            "grounding checks</summary>",
            "",
        ]
        for r in rejected:
            lines.append(f"- {r['text']}  \n  *{r['reason']}*")
        lines += ["", "</details>", ""]

    return "\n".join(lines)


def models_used(narratives: list[dict], fallback: str) -> str:
    """The models that actually wrote this file, not the one that was asked for.

    Free-tier quota is per-model and capped per day, so a long run genuinely can
    span models — and a header naming one of them would be asserting something
    the file cannot support. Listing what was used is the same discipline the rest
    of the project applies to provenance: a digest records the code version that
    produced it, and prose records the model.
    """
    seen = {n.get("model") for n in narratives if n.get("model")}
    return ", ".join(sorted(seen)) if seen else fallback


def world_markdown(world: int, run_id: str, model: str, prompt_version: str,
                   pairs: list[tuple[dict, dict]]) -> str:
    """All eras for one world. `pairs` is `(narrative, brief)` in era order."""
    accepted = sum(len(n.get("sentences", [])) for n, _ in pairs)
    generated = sum(n.get("generated", 0) for n, _ in pairs)
    wrote = models_used([n for n, _ in pairs], model)

    head = [
        f"# World {world}",
        "",
        BANNER.format(model=wrote, prompt=prompt_version),
        "",
        f"Run `{run_id}` · {len(pairs)} eras · "
        f"{accepted} of {generated} sentences accepted",
        "",
        "---",
        "",
    ]
    return "\n".join(head) + "\n".join(era_section(n, b) for n, b in pairs)


def preface_markdown(narrative: dict, brief: dict, model: str,
                     prompt_version: str) -> str:
    facts = {f["id"]: f for f in brief.get("facts", [])}
    lines = [
        f"# {narrative.get('title') or 'A run'}",
        "",
        BANNER.format(model=model, prompt=prompt_version),
        "",
        f"Run `{brief['run_id']}`",
        "",
        "---",
        "",
    ]
    sentences = narrative.get("sentences", [])
    if sentences:
        lines += [" ".join(s["text"] for s in sentences), ""]
    else:
        lines += ["*Every sentence failed the grounding checks and was removed.*", ""]

    lines += ["", "## The worlds", ""]
    for world in brief.get("worlds", []):
        lines.append(f"- [World {world}](world_{world:02d}.md)")
    lines.append("")

    if sentences:
        lines += ["<details><summary>ledger</summary>", "",
                  "| # | cites | source |", "|---|---|---|"]
        for i, s in enumerate(sentences, start=1):
            cites = ", ".join(f"`{c}`" for c in s["cites"])
            sources = " · ".join(_fact_source(facts[c]) for c in s["cites"] if c in facts)
            lines.append(f"| {i} | {cites} | {sources} |")
        lines += ["", "</details>", ""]

    rejected = narrative.get("rejected", [])
    if rejected:
        lines += [f"<details><summary>{len(rejected)} sentence(s) removed</summary>", ""]
        for r in rejected:
            lines.append(f"- {r['text']}  \n  *{r['reason']}*")
        lines += ["", "</details>", ""]

    return "\n".join(lines)


def viewer_payload(world: int, run_id: str, model: str, prompt_version: str,
                   pairs: list[tuple[dict, dict]]) -> dict:
    """What the Atlas panel reads. Narrative joined to the era it describes.

    A narrative on its own knows its era index and not its years, and the panel
    needs both — so the join happens here, once, rather than in JavaScript against
    a digest whose frame boundaries would have to be re-derived. `sources` comes
    along so the page can show a sentence's provenance on hover: the citation has
    to survive into the interface, or the containment stops at the file.
    """
    eras = []
    for narrative, brief in pairs:
        facts = {f["id"]: f.get("source", "") for f in brief.get("facts", [])}
        cited = sorted({c for s in narrative.get("sentences", []) for c in s["cites"]})
        eras.append({
            "model": narrative.get("model", ""),
            "index": brief["era"]["index"],
            "of": brief["era"]["of"],
            "tick_range": brief["era"]["tick_range"],
            "year_range": brief["era"]["year_range"],
            "title": narrative.get("title", ""),
            "sentences": narrative.get("sentences", []),
            "sources": {c: facts.get(c, "") for c in cited},
            "rejected": narrative.get("rejected", []),
            "accepted": narrative.get("accepted", 0),
            "generated": narrative.get("generated", 0),
        })
    return {
        "world": int(world),
        "run_id": run_id,
        "model": models_used([n for n, _ in pairs], model),
        "prompt_version": prompt_version,
        "eras": eras,
    }


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text.endswith("\n") else text + "\n")
    return path
