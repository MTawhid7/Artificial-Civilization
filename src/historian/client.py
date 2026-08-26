"""The LLM boundary. One interface, two implementations, and nothing else here.

The interface exists so that **the gate never touches the network**. Every test in
`tests/test_historian.py` runs against `ReplayClient`, so CI needs no API key, no
`google-genai` install, and no allowance for a model that answers differently on
Tuesday. What the tests assert is the containment — which is deterministic — and
never the text, which is not.

**Model: `gemini-3.7-flash`** *(→ [D-067](../../docs/DECISIONS.md#d-067))*.
[11-engineering.md](../../docs/11-engineering.md) specified Claude via the Anthropic
SDK; this is a deliberate departure with a decision record. It has a free tier, the
task is narration under a hard grounding gate rather than reasoning, and — the part
that makes it safe — **this is the one component where the model cannot affect a
result**, because its output is never evidence. If a weaker model writes worse
prose, the prose is worse. Nothing downstream moves.

The whole SDK surface is confined to `GeminiClient.complete`. This API has changed
shape before (`generate_content` → `interactions.create`), and when it changes
again exactly one function needs editing.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

MODEL = "gemini-3.7-flash"
API_KEY_VARS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")

# Free-tier request rates are not published — the docs point at AI Studio rather
# than a table. Six seconds between calls is ~10/minute, which is slow enough to
# be polite and fast enough that a 41-call run takes four minutes. The cache means
# a rate-limit failure costs only the eras not yet written.
MIN_INTERVAL_S = 6.0

# The free tier answers a burst with HTTP 429 and a "please retry in Ns" hint,
# and honouring the hint is the only reliable way through: the published rate is
# not in the docs, so a fixed interval is a guess and the server's number is not.
# Five retries covers a quota window; past that the run should stop and say so,
# because the cache means resuming costs nothing but the eras not yet written.
MAX_RETRIES = 5
RETRY_FALLBACK_S = 60.0

# How many numbered key slots are read. Free-tier quota is capped per day and
# enforced per Cloud project, so several keys from several projects is the only
# way to run a long narration on the free tier in one sitting — and rotating on a
# 429 is free, where sleeping through it costs a minute a time.
MAX_KEYS = 8

# Temperature 0 is not determinism — the same brief can still produce different
# prose, and nothing in this project pretends otherwise. It is a request for the
# most likely sentence rather than an interesting one, which is what a grounded
# historian should be writing.
TEMPERATURE = 0.0
THINKING_LEVEL = "low"


class Client(Protocol):
    """Anything that can turn a prompt into a JSON object matching a schema."""

    name: str

    def complete(self, system: str, prompt: str, schema: dict) -> tuple[dict, dict]:
        """Return `(payload, usage)`. `usage` may be empty."""
        ...


def load_dotenv(path: str | Path = ".env") -> None:
    """Read `KEY=value` lines from a git-ignored `.env`, without a dependency.

    Six lines against a package, for a file that holds one key. Existing
    environment variables win, so an explicit export always beats the file.
    """
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def api_keys() -> list[str]:
    """Every key configured, in the order they should be used.

    Accepts `GEMINI_API_KEY`, a comma-separated list in it, and numbered
    siblings `GEMINI_API_KEY_2` … `GEMINI_API_KEY_{}`. Duplicates are dropped so
    that setting both a list and a sibling cannot silently halve the rotation.

    **This multiplies quota only if the keys belong to different Google Cloud
    projects.** The free-tier limit is enforced per project per model, not per
    key, so five keys minted inside one project rotate through five names against
    one 20-request budget and buy nothing. Worth knowing before making five keys.
    """.format(MAX_KEYS)
    load_dotenv()
    found: list[str] = []
    for var in API_KEY_VARS:
        for name in (var, *(f"{var}_{i}" for i in range(1, MAX_KEYS + 1))):
            raw = os.environ.get(name, "")
            found.extend(k.strip() for k in raw.split(",") if k.strip())
    seen: set[str] = set()
    return [k for k in found if not (k in seen or seen.add(k))]


def api_key() -> str | None:
    keys = api_keys()
    return keys[0] if keys else None


class MissingKeyError(RuntimeError):
    pass


@dataclass(slots=True)
class GeminiClient:
    """The live client, rotating over however many keys are configured.

    Rotation is not a throughput trick. The free tier allows **20 requests per
    day per model**, measured here by exhausting three of them, and a single key
    therefore cannot narrate a run of any size in one sitting. On a 429 the client
    moves to the next key immediately; only when every key has refused does it
    fall back to sleeping on the server's retry hint.
    """

    model: str = MODEL
    min_interval_s: float = MIN_INTERVAL_S
    name: str = field(init=False)
    _clients: list = field(init=False, default_factory=list)
    _last_call: list = field(init=False, default_factory=list)
    _at: int = field(init=False, default=0)
    _dead: set = field(init=False, default_factory=set)

    def __post_init__(self) -> None:
        self.name = self.model
        keys = api_keys()
        if not keys:
            raise MissingKeyError(
                "no API key. Put one in a git-ignored .env at the repo root:\n"
                "    GEMINI_API_KEY=...\n"
                "Free tier is 20 requests per day per model, so a long run wants\n"
                "several keys FROM SEPARATE CLOUD PROJECTS (quota is per project,\n"
                "not per key):\n"
                "    GEMINI_API_KEY_2=...\n"
                "    GEMINI_API_KEY_3=...\n"
                "Get free-tier keys at https://aistudio.google.com/apikey"
            )
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - depends on an extra
            raise RuntimeError(
                "google-genai is not installed. It is a dependency group, because "
                "the test gate must never need it:\n"
                "    uv sync --all-extras --group historian"
            ) from exc
        self._clients = [genai.Client(api_key=k) for k in keys]
        self._last_call = [0.0] * len(self._clients)

    @property
    def n_keys(self) -> int:
        return len(self._clients)

    @property
    def n_live(self) -> int:
        return self.n_keys - len(self._dead)

    def _rotate(self) -> None:
        """Advance to the next key that has not been retired."""
        for _ in range(self.n_keys):
            self._at = (self._at + 1) % self.n_keys
            if self._at not in self._dead:
                return

    def complete(self, system: str, prompt: str, schema: dict) -> tuple[dict, dict]:
        refused = 0     # consecutive 429s since the last success
        slept = 0
        while True:
            i = self._at
            # Throttled per key, not globally: rotating exists precisely so the
            # next request does not have to wait on the last one's budget.
            wait = self.min_interval_s - (time.monotonic() - self._last_call[i])
            if wait > 0:
                time.sleep(wait)
            self._last_call[i] = time.monotonic()
            try:
                interaction = self._clients[i].interactions.create(
                    model=self.model,
                    input=prompt,
                    system_instruction=system,
                    generation_config={
                        "temperature": TEMPERATURE,
                        "thinking_level": THINKING_LEVEL,
                    },
                    response_format={
                        "type": "text",
                        "mime_type": "application/json",
                        "schema": schema,
                    },
                )
            except Exception as exc:
                pause = _retry_after(exc)
                # Order matters. A rate limit is temporary and a dead key is not,
                # and asking the second question first retires a key that was
                # merely out of budget for the day — losing it for the rest of
                # the run. Observed doing exactly that before this was reordered.
                #
                # A key whose project is denied, or whose credential is wrong,
                # fails identically forever. Retiring it keeps a rotation useful
                # when one of five keys is misconfigured, instead of letting the
                # run die the first time it comes round to that one. Seen for
                # real: "your project has been denied access".
                if pause is None and _is_dead_key(exc):
                    self._dead.add(i)
                    print(f"    key {i + 1}/{self.n_keys} retired: "
                          f"{str(exc)[:80]}", flush=True)
                    if self.n_live == 0:
                        raise
                    self._rotate()
                    continue
                if pause is None:
                    raise
                refused += 1
                if refused < self.n_live:
                    self._rotate()          # another key may still have budget
                    continue
                if slept >= MAX_RETRIES:
                    raise
                slept += 1
                print(f"    all {self.n_live} live key(s) rate limited on "
                      f"{self.model}; waiting {pause:.0f}s "
                      f"({slept}/{MAX_RETRIES})", flush=True)
                time.sleep(pause)
                refused = 0
                self._rotate()
                continue
            return json.loads(interaction.output_text), _usage(interaction)


def _usage(interaction: object) -> dict:
    """Token counts, defensively.

    Usage reporting is the least stable part of any of these SDKs and the least
    important: a missing count should cost the cost line in `result.md`, never the
    narrative that was already paid for.
    """
    for attr in ("usage", "usage_metadata"):
        meta = getattr(interaction, attr, None)
        if meta is None:
            continue
        out = {}
        for src, dst in (("total_input_tokens", "input_tokens"),
                         ("total_output_tokens", "output_tokens"),
                         ("total_thought_tokens", "thought_tokens"),
                         ("total_tokens", "total_tokens"),
                         # 1.x spellings, kept because a digest of costs that
                         # silently reads zero is worse than one that is absent.
                         ("input_tokens", "input_tokens"),
                         ("output_tokens", "output_tokens"),
                         ("prompt_token_count", "input_tokens"),
                         ("candidates_token_count", "output_tokens")):
            value = getattr(meta, src, None)
            if isinstance(value, int) and dst not in out:
                out[dst] = value
        if out:
            return out
    return {}


def _is_dead_key(exc: Exception) -> bool:
    """Is this key permanently unusable rather than temporarily out of budget?

    A 403 on the free tier is usually a project that was never enabled or has
    been denied access. It will not recover during a run, and treating it as a
    rate limit would spend five minutes of backoff discovering that.
    """
    text = str(exc)
    low = text.lower()
    # Anchored to how the status actually appears, not a bare substring: a "403"
    # can turn up inside a retry hint or a request id, and matching that would
    # retire a working key.
    if re.search(r"(error\s+code|status|code)\D{0,3}\b(401|403)\b", low):
        return True
    return ("permission_denied" in low or "unauthenticated" in low
            or "api key not valid" in low or "api_key_invalid" in low)


def _retry_after(exc: Exception) -> float | None:
    """Seconds to wait for a rate-limit error, or None if this is not one.

    Matched on the message rather than the exception class on purpose. This SDK
    has moved its error types along with everything else, and a retry that stops
    working after an upgrade would look exactly like the API being down.
    """
    text = str(exc)
    if "429" not in text and "too_many_requests" not in text.lower() \
            and "quota" not in text.lower():
        return None
    hit = re.search(r"retry in (\d+(?:\.\d+)?)s", text)
    return float(hit.group(1)) + 2.0 if hit else RETRY_FALLBACK_S


@dataclass(slots=True)
class ReplayClient:
    """Canned responses, in order. Every test in the gate runs on this.

    Also what makes a fixture recorded from a real call re-runnable forever: the
    committed narrative under `experiments/` came from the live model once, and
    nothing in CI ever needs to ask again.
    """

    responses: list[dict]
    name: str = "replay"
    calls: list[tuple[str, str]] = field(default_factory=list)
    _index: int = field(init=False, default=0)

    def complete(self, system: str, prompt: str, schema: dict) -> tuple[dict, dict]:
        self.calls.append((system, prompt))
        if self._index >= len(self.responses):
            raise AssertionError(
                f"ReplayClient ran out of responses after {self._index}; "
                "the code under test made more calls than the fixture covers"
            )
        payload = self.responses[self._index]
        self._index += 1
        return payload, {"input_tokens": 0, "output_tokens": 0}
