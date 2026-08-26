"""Inline digests into the Atlas template to make one self-contained page.

D-062: the A2 viewer is a single HTML file with no build step. Inlining is not a
stylistic choice — the page has to work from `file://` and from a sandboxed host,
and neither will fetch a sibling `digest.json`. A page that cannot fetch its data
also cannot fetch a decoder, which is why the digest is base64 JSON (D-061) rather
than a format needing a library.

Output is git-ignored. It is fully regenerable from the digests, which are fully
regenerable from the runs, which are pure functions of `(config, seed)`.

Usage:
    python tools/build_atlas.py corpus/runs/*/digest.json -o atlas/wall.html
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "atlas" / "wall.template.html"
PLACEHOLDER = "__DIGESTS__"
NARRATIVE_PLACEHOLDER = "__NARRATIVES__"


def _narratives(digest_path: Path) -> list[dict]:
    """Any Historian output sitting beside the digest, or nothing.

    Narrative is optional and the page renders without it: a digest built before
    A3, or a run nobody narrated, produces a wall with no Chronicle panel rather
    than a broken one. Only the viewer payloads are read — `world_NN.json` —
    which already carry the sentences joined to the eras they describe and the
    source string behind every citation.
    """
    out = []
    for path in sorted((digest_path.parent / "narrative").glob("world_*.json")):
        payload = json.loads(path.read_text())
        if payload.get("eras"):
            out.append(payload)
    return out


def build(digest_paths: list[Path], template: Path = TEMPLATE) -> str:
    digests, narratives = [], []
    for path in digest_paths:
        d = json.loads(path.read_text())
        # Rasters are for the C3 map view and are ~40% of the file. The wall does
        # not read them, and shipping them would triple the page for nothing.
        d.pop("rasters", None)
        digests.append(d)
        narratives.extend(_narratives(path))

    if not digests:
        raise SystemExit("no digests given")

    html = template.read_text()
    for name in (PLACEHOLDER, NARRATIVE_PLACEHOLDER):
        if name not in html:
            raise SystemExit(f"{template} has no {name} placeholder")

    return (html
            .replace(PLACEHOLDER, _inline(digests))
            .replace(NARRATIVE_PLACEHOLDER, _inline(narratives)))


def _inline(payload: object) -> str:
    # `</script>` inside a string literal would close the block early. Digest data
    # cannot contain it; generated prose can, so escaping stopped being defensive
    # the moment narrative started being inlined.
    return json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("digests", nargs="+")
    p.add_argument("-o", "--out", default="atlas/wall.html")
    args = p.parse_args()

    paths = [Path(x) for x in args.digests]
    html = build(paths)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)

    mb = len(html.encode()) / 2**20
    narrated = sum(len(_narratives(p)) for p in paths)
    print(f"  {len(paths)} digest(s), {narrated} narrated world(s) -> {out}  "
          f"({mb:.2f} MB, self-contained)")
    if mb > 16:
        print("  WARNING: over 16 MB — too large to publish as a hosted page")


if __name__ == "__main__":
    main()
