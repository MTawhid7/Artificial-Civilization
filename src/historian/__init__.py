"""The Historian — an LLM reading a finished run and writing narrative history.

The one component in this project whose output is **never evidence**
*(→ docs/GLOSSARY.md, docs/12-risks.md)*. That is not a disclaimer, it is the
design brief: A3's ship criteria are about containment rather than measurement,
because the risk here is not a wrong number but a beautiful one that was never in
the data.

Four containment properties, each enforced by code rather than convention:

**The model never sees the world.** It sees a numbered table of facts computed in
Python by `facts.py`, and nothing else — no Chronicle, no digest, no grid, no
per-agent event. It cannot describe what it was not given.

**Every sentence names the facts it rests on**, and `verify.py` rejects the rest:
uncited sentences, citations to ids that do not exist, numbers not derivable from
the cited facts, phenomenon vocabulary the S0 world cannot contain, and causal
claims of any kind. Rejections ship in the output.

**Nothing is written outside `narrative/`.** Never `metrics/`, which is Lens
output. The Historian is a separate CLI over a finished run directory, never
attached to a running simulation, so a run with it is byte-identical to a run
without it — by construction, and by test.

**Nothing here imports `src/core/`.** The arrow runs one way. A narrative that
could reach the simulation would be a feedback path from prose into evidence.

    python -m historian.build corpus/runs/<run_id>

Contract: schemas/narrative.md.
"""

from __future__ import annotations

NARRATIVE_VERSION = "0.1.0"
