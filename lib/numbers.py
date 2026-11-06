"""Numbers in model-written text, checked against the numbers the model was given. A
report may show a recorded figure in another form (48,200 as 48.2K, 38.11 % as 38%),
never a new one: models may explain recorded totals but must never invent them
(Pulse PROCESS_DETERMINISM_MAPPING rule 4).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# "one" is left out: it is mostly a pronoun ("one thing didn't land").
NUMBER_WORDS = {
    word: value
    for value, word in enumerate(
        "two three four five six seven eight nine ten eleven twelve thirteen fourteen "
        "fifteen sixteen seventeen eighteen nineteen twenty".split(),
        2,
    )
}
MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|november|"
    "december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
)
# 48,200 / 3412 / 38.11 / 48.2K / 1.2k / 2M; a sign or % around it does not matter.
NUMBER = re.compile(
    r"(?<![\w.,])(?P<whole>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<decimals>\d+))?"
    r"(?:\s?(?P<scale>[kKmM])\b)?"
)
WORD = re.compile(r"\b(?:" + "|".join(NUMBER_WORDS) + r")\b", re.IGNORECASE)
# A day next to its month ("8 October", "October 8") is a date, not a figure.
DATE = re.compile(
    rf"\b(?:\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTHS})\b"
    rf"|(?:{MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?\b)",
    re.IGNORECASE,
)
# "3.2× your reach", "three times as many"; a count ("played 9,000 times") is not one.
RATIO = re.compile(
    r"\b(?:twice|double[sd]?|triple[sd]?|half|halved|quarter|thirds?\s+of)\b"
    r"|(?:\b(?:" + "|".join(NUMBER_WORDS) + r")|(?<![\w,.])\d+(?:\.\d+)?)\s*"
    r"(?:×|x\b|times\s+(?:as|more|less|fewer|bigger|higher|larger|greater|smaller|lower|"
    r"the|your|our|their|what|that|than|over)\b)",
    re.IGNORECASE,
)
SCALES = {"k": 1_000, "m": 1_000_000}


def numbers_in(text: str) -> list[tuple[str, float, float]]:
    """Each number in the text as (written, value, the step it is rounded to): 48.2K is
    ("48.2K", 48200, 100), 38 is ("38", 38, 1), "nine" is ("nine", 9, 1). Dates are
    skipped."""
    text = DATE.sub(" ", text)
    found = []
    for match in NUMBER.finditer(text):
        decimals = match["decimals"] or ""
        scale = SCALES.get((match["scale"] or "").lower(), 1)
        value = float(match["whole"].replace(",", "") + ("." + decimals if decimals else ""))
        found.append((match.group().strip(), value * scale, scale / 10 ** len(decimals)))
    for match in WORD.finditer(text):
        found.append((match.group(), float(NUMBER_WORDS[match.group().lower()]), 1.0))
    return found


def shows(value: float, written: float, step: float) -> bool:
    """Whether a number rounded to `step` (either way) shows `value`; signs do not
    count ("down 9%" shows -9.2)."""
    return abs(abs(value) - written) <= step / 2 + 1e-9


def unmatched(text: str, allowed: Iterable[float]) -> list[str]:
    """The numbers in the text that show none of the allowed values, as written."""
    values = [float(v) for v in allowed]
    return [
        written
        for written, number, step in numbers_in(text)
        if not any(shows(value, number, step) for value in values)
    ]


def ratios(text: str) -> list[str]:
    """Ratios and fractions ("three times", "twice", "a quarter of"), which recorded
    totals never give."""
    return [match.group() for match in RATIO.finditer(text)]
