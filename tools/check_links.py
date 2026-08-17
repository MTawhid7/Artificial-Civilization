"""Verify every relative markdown link and anchor resolves, GitHub-slug rules."""
import re, pathlib, sys

def slugify(heading: str) -> str:
    s = heading.lstrip("#").strip().lower()
    s = re.sub(r'[^\w\s-]', '', s)      # drop punctuation, keep spaces
    return s.replace(" ", "-")           # each space -> one hyphen (not collapsed)

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
files = sorted(set(root.glob("docs/*.md")) | set(root.glob("*.md")) |
               set(root.glob("experiments/*/*.md")) | set(root.glob("schemas/*.md")))
bad, checked = [], 0
for md in files:
    for m in re.finditer(r'\[([^\]]+)\]\(([^)#]+)(#[^)]+)?\)', md.read_text()):
        target, anchor = m.group(2), m.group(3)
        if target.startswith(("http", "mailto")):
            continue
        checked += 1
        p = (md.parent / target).resolve()
        if not p.exists():
            bad.append(f"{md}: missing file -> {target}")
            continue
        if anchor and p.suffix == ".md":
            body = p.read_text()
            slugs = set(re.findall(r'<a id="([^"]+)"></a>', body))
            slugs |= {slugify(l) for l in body.splitlines() if l.startswith("#")}
            if anchor[1:].lower() not in slugs:
                bad.append(f"{md}: bad anchor {target}{anchor}")
print("\n".join(bad) if bad else
      f"OK — {checked} links across {len(files)} files, all resolve")
sys.exit(1 if bad else 0)
