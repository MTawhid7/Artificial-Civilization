"""The Atlas — what the wall renders, and what the page is allowed to depend on.

docs/09-visualization.md asks for deterministic playback: "frame N always renders
identically — a screenshot must be reproducible". These tests hold the renderer to
that, and hold the page to being genuinely self-contained rather than nearly so.

The RGB array is compared, never the PNG bytes. Encoded PNGs carry the
compressor's version in their headers, so byte-equality would fail on a library
bump and prove nothing about the picture.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from core.config import resolve
from digest import build as builder
from digest import schema as D
from forge.run import run
from tools import build_atlas, render_wall

from conftest import TINY


@pytest.fixture(scope="module")
def digests(tmp_path_factory) -> list:
    """Two runs, so the pooling path is exercised rather than assumed."""
    raw = {**TINY, "run": {**TINY["run"], "aggregate_every": 5, "checkpoint_every": 100}}
    cfg = resolve(raw, source="tests/test_atlas.py")
    root = tmp_path_factory.mktemp("corpus")
    out = []
    for seed in (11, 12):
        meta = run(cfg, seed, out_root=root, progress=False)
        run_dir = root / "runs" / meta["run_id"]
        path = run_dir / "digest.json"
        path.write_text(D.canonical_json(builder.build(run_dir, raster_worlds=1)))
        out.append(path)
    return out


def test_wall_render_is_deterministic(digests):
    a = render_wall.build_wall(render_wall.load(digests, "energy_gini"))
    b = render_wall.build_wall(render_wall.load(digests, "energy_gini"))
    assert np.array_equal(a, b)


def test_wall_pools_every_digest(digests):
    """A wall is the experiment, not one run. Two 4-world runs make 8 strips."""
    data = render_wall.load(digests, "energy_gini")
    assert data["population"].shape[0] == 2 * TINY["run"]["worlds"]
    wall = render_wall.build_wall(data)
    expected = data["population"].shape[0] * (render_wall.STRIP_HEIGHT + render_wall.GUTTER)
    assert wall.shape[0] == expected


def _bar_heights(wall: np.ndarray, n_worlds: int, height: int) -> list[int]:
    row_h = height + render_wall.GUTTER
    bg = np.asarray(render_wall.BACKGROUND)
    out = []
    for w in range(n_worlds):
        band = wall[w * row_h : w * row_h + height]
        painted = np.any(np.abs(band - bg) > 1e-9, axis=2)
        out.append(int(painted.sum(axis=0).max()))
    return out


def test_wall_scale_is_shared_not_per_world():
    """The claim is that these worlds diverged. Per-world normalization would
    rescale each strip to its own extremes and erase exactly that.

    Synthetic rather than sampled: the property is a ten-to-one population ratio
    rendering as a ten-to-one bar ratio, and a fixture whose worlds happen to be
    similar would let a per-world bug pass unnoticed.
    """
    n = 40
    data = {
        "population": np.stack([np.full(n, 100.0), np.full(n, 1000.0)]),
        "color": np.stack([np.full(n, 0.2), np.full(n, 0.4)]),
        "labels": ["a-00", "a-01"],
        "markers": [],
        "channel": "energy_gini",
        "meta": [{"capacity": 2000}],
    }
    height = 40
    wall = render_wall.build_wall(data, height=height, scale="max")
    quiet, loud = _bar_heights(wall, 2, height)
    assert loud == height
    assert quiet == pytest.approx(height / 10, abs=1)

    # And relative to the array ceiling, both shrink by the same factor.
    capped = render_wall.build_wall(data, height=height, scale="capacity")
    q2, l2 = _bar_heights(capped, 2, height)
    assert l2 == pytest.approx(height / 2, abs=1)
    assert q2 == pytest.approx(height / 20, abs=1)


def test_wall_default_order_is_world_order(digests):
    """D-063. Sorting by outcome makes noise look like a gradient, and the
    default must not do it."""
    data = render_wall.load(digests, "energy_gini")
    assert np.array_equal(render_wall._order(data["population"], "world"),
                          np.arange(data["population"].shape[0]))
    ranked = render_wall._order(data["population"], "final_pop")
    finals = data["population"][ranked, -1]
    assert np.all(np.diff(finals) <= 0)


def test_wall_refuses_a_version_it_does_not_speak(digests, tmp_path):
    """A digest outlives the code that wrote it. Guessing at an unknown version
    is how a renderer silently draws the wrong field."""
    d = json.loads(digests[0].read_text())
    d["digest_version"] = "99.0.0"
    stale = tmp_path / "digest.json"
    stale.write_text(json.dumps(d))
    with pytest.raises(SystemExit):
        render_wall.load([stale], "energy_gini")


def test_atlas_page_is_self_contained(digests):
    """No network, no build step, no sibling files.

    D-062: the page must render from `file://` and from a sandboxed host. Fonts
    are the one permitted external reference and degrade to the declared fallback
    stack when they do not load; anything that *fetches* would leave the page
    blank instead.
    """
    html = build_atlas.build(digests)
    assert build_atlas.PLACEHOLDER not in html
    for forbidden in ("fetch(", "XMLHttpRequest", "importScripts", "WebSocket"):
        assert forbidden not in html, forbidden

    external = {u.split("/")[2] for u in _urls(html)}
    assert external <= {"fonts.googleapis.com", "fonts.gstatic.com"}, external

    payload = json.loads(html.split(build_atlas.PLACEHOLDER.join([]) or "const DIGESTS = ")[1]
                         .split(";\n")[0].replace("<\\/", "</"))
    assert len(payload) == len(digests)
    assert "rasters" not in payload[0], "the wall does not read rasters; shipping them is dead weight"
    assert payload[0]["digest_version"] == D.DIGEST_VERSION


def _urls(html: str) -> list[str]:
    import re
    return re.findall(r"https?://[^\s\"')]+", html)


def test_viewer_actually_draws(digests, tmp_path):
    """Run the page's own script and look at the pixels it wrote.

    Everything up to the digest is checked in Python. From there the page is a
    deliverable no Python test can see, and the gap between a typo and a blank
    wall is exactly one untested language. This executes the script against a
    stub DOM and asserts on the resulting ImageData — the symptom a viewer would
    notice, not the implementation that produces it.

    Skipped rather than failed without node: the page is verified by its Python
    twin's tests either way, and a hard dependency on a second toolchain for a
    no-build page would defeat the point of D-062.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed; the viewer probe needs it")

    page = tmp_path / "probe.html"
    page.write_text(build_atlas.build(digests))
    probe = Path(__file__).parent / "js" / "render_probe.js"

    result = subprocess.run([node, str(probe), str(page)],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout, result.stdout
