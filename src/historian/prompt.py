"""Versioned prompts, and the fact table rendered for a model to read.

`PROMPT_VERSION` is recorded in every narrative
*(→ [docs/11-engineering.md § LLM usage](../../docs/11-engineering.md#llm-usage):
"a narrative records the prompt version that produced it")*. Prose written under
v0.1.0 stays attributable when v0.2.0 changes the rules, which matters because
prose is the one artifact here that cannot be regenerated from a seed.

The system instruction states the rules `verify.py` enforces. The model is told
the contract rather than punished by it — a rejected sentence costs a repair round
and a repair round costs tokens, so the cheapest verifier is a prompt the model can
actually satisfy. But the prompt is not the guarantee and must never be treated as
one: everything here is advisory, and the file next door is what decides.
"""

from __future__ import annotations

PROMPT_VERSION = "0.1.0"

# The response shape. Sentence-level cites rather than paragraph-level: a
# paragraph of five sentences citing three facts leaves four sentences
# unaccounted for, and "traceable" then means "mostly traceable".
RESPONSE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "A short title for this era. No numbers.",
        },
        "sentences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "One sentence."},
                    "cites": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Fact ids this sentence rests on, e.g. ['f01'].",
                    },
                },
                "required": ["text", "cites"],
            },
        },
    },
    "required": ["title", "sentences"],
}


SYSTEM = """\
You are a historian of a synthetic world. You are writing from a table of measured
facts, and the table is the entire world: you have no other source, and there is
nothing you know about this world that is not in it.

Write plain, concrete historical prose. Short sentences. No hedging, no summary
paragraph, no preamble, no bullet points.

Five rules. Every one of them is checked by a program after you answer, and a
sentence that breaks any of them is deleted:

1. CITE. Every sentence carries the ids of the facts it rests on. A sentence with
   no cite is deleted.
2. ONLY REAL IDS. Cite ids that appear in the table. An invented id is the worst
   failure available to you, because it makes an unsupported sentence look
   supported.
3. ONLY REAL NUMBERS. Every number you write must appear in a fact you cited, at
   the precision you write it. If a fact says 601.3 you may write 601 or 601.3,
   never 600. If you are not certain of a number, write no number: "the population
   roughly halved" is always allowed and never wrong.
4. NO INVENTED WORLD. This world contains food, movement, birth, death, and
   inherited traits. It does not contain cities, kings, tribes, wars, trade,
   religion, technology, farming, weather, or disease. Do not use those words.
   There are no place names. Do not invent any.
5. NO CAUSATION. You may say what happened and in what order. You may not say why.
   "After the resource fell, the population fell" is allowed. "Because", "caused",
   "led to", "due to", "therefore", "drove" are not. If a detector's verdict is
   SILENT, you may describe what it marked but not call it significant, unusual,
   or rare.

WHAT TO WRITE

The fact table is a list of measurements. History is not. Do not walk the table:
most of what is in it does not deserve a sentence, and a passage that reports
every row is a spreadsheet with verbs.

- Use at most FOUR numbers in the whole passage, and choose which four.
- Never make a measurement the subject of a sentence. "Births rose from 2 to 12"
  is a row from a table. "More were born in these years than in any before them"
  is history.
- Write about the agents: how many there were, whether they were feeding well,
  whether a few of them held most of what there was, where on the map they were.
- The traits are named, and the name is what they do. A rise in `crowd_avoidance`
  means the agents were spreading out. A fall in `gradient_sensitivity` means they
  were following the food less closely. A fall in `metabolic_rate` means they were
  moving less. Write the behaviour, not the number.
- If little happened, say so in two sentences and stop. A quiet age is a true fact
  about this world, and padding one is the only way to write something false
  without writing a false number.

The drama here is demographic. There are no heroes, no places with names, and
nothing was decided by anyone. That is enough.
"""


def render_facts(brief: dict) -> str:
    """The fact table as compact text. This is all the model ever sees."""
    lines = []
    for f in brief.get("facts", []):
        parts = [f"{f['id']}  {f['kind']}"]
        for key in ("series", "trait", "gene_index", "detector", "layer", "measure",
                    "extreme", "bearing", "world"):
            if key in f:
                parts.append(f"{key}={f[key]}")
        if f.get("kind") == "marker":
            verdict = str(f.get("detector_verdict", "silent")).upper()
            parts.append(f"[detector verdict: {verdict}, z={f.get('detector_effect_size')}]")
        values = "  ".join(f"{k}={_num(v)}" for k, v in f.get("values", {}).items())
        lines.append("  ".join(parts) + "   " + values)
    return "\n".join(lines)


def _num(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def era_prompt(brief: dict) -> str:
    era = brief["era"]
    y0, y1 = era["year_range"]
    t0, t1 = era["tick_range"]
    return f"""\
World {brief['world']}, era {era['index'] + 1} of {era['of']}.
Simulated years {y0:,.0f} to {y1:,.0f} (ticks {t0:,} to {t1:,}).

FACTS
{render_facts(brief)}

Write 4 to 7 sentences of history covering this era, and a short title.
Cite the fact ids for every sentence.
"""


def preface_prompt(brief: dict) -> str:
    return f"""\
An introduction to a whole run: {len(brief['worlds'])} of its worlds are written up
individually, but this is about the run as a whole.

Every world in this run started from an identical configuration and an identical
seed. Nothing was varied between them. Whatever differences the facts below show
were produced by the worlds themselves.

FACTS
{render_facts(brief)}

Write 4 to 6 sentences introducing this run, and a short title. State what was held
identical and what differed. Cite the fact ids for every sentence.
"""


def repair_prompt(brief: dict, note: str, kept: int) -> str:
    """The single repair round.

    Sends back the reasons rather than a retry instruction. Most rejections are one
    word or one number, and a model told *which* word can fix it; a model told
    "that was wrong" re-rolls the whole passage and usually loses the good
    sentences with the bad.
    """
    return f"""\
{kept} of your sentences were accepted and are kept. These were deleted:

{note}

FACTS (unchanged — this is still the entire world)
{render_facts(brief)}

Write replacements for the deleted sentences only. Fix the stated problem: drop the
banned word, drop the causal claim, or drop the number you could not source. Keep
the same title. Do not rewrite the sentences that were accepted.
"""
