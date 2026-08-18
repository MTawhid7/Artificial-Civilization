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


def build(digest_paths: list[Path], template: Path = TEMPLATE) -> str:
    digests = []
    for path in digest_paths:
        d = json.loads(path.read_text())
        # Rasters are for the C3 map view and are ~40% of the file. The wall does
        # not read them, and shipping them would triple the page for nothing.
        d.pop("rasters", None)
        digests.append(d)

    if not digests:
        raise SystemExit("no digests given")

    html = template.read_text()
    if PLACEHOLDER not in html:
        raise SystemExit(f"{template} has no {PLACEHOLDER} placeholder")

    payload = json.dumps(digests, separators=(",", ":"))
    # `</script>` inside a string literal would close the block early. It cannot
    # occur in this data, and escaping it costs nothing against the day it can.
    payload = payload.replace("</", "<\\/")
    return html.replace(PLACEHOLDER, payload)


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
    print(f"  {len(paths)} digest(s) -> {out}  ({mb:.2f} MB, self-contained)")
    if mb > 16:
        print("  WARNING: over 16 MB — too large to publish as a hosted page")


if __name__ == "__main__":
    main()
