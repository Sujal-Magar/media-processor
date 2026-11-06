#!/usr/bin/env python3
"""draft-insights, step 3: turn the model's answer into output/draft-insights/<month>-<hash>/
insights.md, insights.json and metadata.json. Free; draft.py runs it.

Each insight answers one trigger the anomaly rules raised: an observation, one or two
hypotheses worded as possibilities (each with what would confirm or refute it), a
proposed asset request for next month and a client card draft. Every insight is
`Proposed` and the file a draft for the strategist; nothing is sent. A sentence keeps the
data its references point to; one citing nothing that was sent is dropped. Every number
must show one the data holds: one that does not, and a quantity the request may not ask
for, make the draft incomplete. `checks` also lists numbers from data the sentence does
not cite, ratios the comparisons do not give, causes stated as fact, hypotheses not
worded as possibilities, internal terms and jargon on the client card, and references
written into the text. Prints only counts, paths and these notes, never the draft.

    python3 processors/draft-insights/finalize.py work/draft-insights/<job> [--keep-work]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `lib`

from lib.numbers import numbers_in, ratios, shows, unmatched
from lib.wording import CAUSAL, DATA_GAP, INTERNAL, JARGON
from lib.workspace import (
    archive_previous,
    fail,
    is_job_dir,
    now_iso,
    print_json,
    result_metadata,
    write_json,
    write_text,
)

# C18a's rules as mocked here (DFD_05 §5.5), with how the material names them.
RULES = {
    "engagement_gt_200pct_mean": "engagement rate above 2 × the 90-day average",
    "hook_dropoff_gt_45pct": "more than 45% stopped watching in the first 3 seconds",
    "pace_behind_quota": "2 or more posts behind the monthly quota",
}
POST_RULES = ("engagement_gt_200pct_mean", "hook_dropoff_gt_45pct")
# What an asset request asks for (DFD_04 checklist category, without documents) and in
# which language the footage is wanted.
CATEGORIES = ("photo", "video", "story")
LANGUAGES = ("en", "ne", "any")
MAX_INSIGHTS = 3  # a month; the screens show one card at a time
MAX_HYPOTHESES = 2
MAX_QUANTITY = 3
MAX_BUTTON_WORDS = 5
MAX_REFS = 5
MAX_NOTES = 10
# A reference as a model may write it: T1, G3, P12, BL, [P3], "P3 and P4".
REF_PATTERN = re.compile(r"\b(?:[TGP]\d+|BL)\b")
# Words that make a claim a possibility rather than a fact.
HEDGE = re.compile(
    r"\b(?:may|might|could|possibly|perhaps|one explanation|it is possible|a possible)\b",
    re.IGNORECASE,
)
# How insights are made, which the client never needs to read, and the engagement
# measure the Pulse screens put in people terms instead.
CLIENT_TERMS = re.compile(
    r"\b(?:trigger(?:ed|s)?|baselines?|anomal\w*|rules?|thresholds?|quotas?|slots?|"
    r"hypothes\w*|engagement rate|retention|drop-?off|pillars?|catch(?:ing)? up|\d+-day)\b",
    re.IGNORECASE,
)
# What a test can be measured on, as the material names the measures.
MEASURE_WORDS = re.compile(
    r"\b(?:engag\w*|liked|likes?|comment\w*|shar(?:e|ed|es)|sav(?:e|ed|es)|reach\w*|"
    r"people|watch\w*|seen|saw|plays?|played|views?)\b",
    re.IGNORECASE,
)
# An engagement rate is a share of the people reached: a client line about one that
# says "more often" or "more than" without a share or a ratio claims a count it is not.
COUNT_LEAD = re.compile(r"\b(?:more often|more than|most|less often|fewer than)\b", re.IGNORECASE)
AS_SHARE = re.compile(r"\bshare of\b|\bof the people\b|×|\btimes (?:your|the|as)\b", re.IGNORECASE)
NUMBER_WORD = re.compile(r"\d|\b(?:one|two|three)\b", re.IGNORECASE)
# Two requests whose briefs share at least this much of their longer words ask for one
# thing.
# A card action that shares this much of its longer words with the finding repeats it.
REPEAT_SHARE = 0.5
# The measure a trigger's tests are measured on, for their bar.
BAR_MEASURES = {"engagement_gt_200pct_mean": "true_engagement_rate", "hook_dropoff_gt_45pct": "retention_3s_pct"}
LANGUAGE_WORDS = {"ne": re.compile(r"\bnepali\b", re.IGNORECASE), "en": re.compile(r"\benglish\b", re.IGNORECASE)}
PLATFORM_WORDS = re.compile(r"\b(?:instagram|tiktok|linkedin|youtube)\b", re.IGNORECASE)
# What to do belongs in the request, not in a hypothesis (F-053).
ADVICE = re.compile(
    r"\b(?:worth (?:testing|trying|a try)|consider\w*|reconsider\w*|should|recommend\w*|try|investigat\w*)\b", re.IGNORECASE
)
PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def fmt_number(value: float) -> str:
    return f"{value:g}"


def text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_refs(values: list[Any] | None) -> list[str]:
    """The references in what the model wrote, in order; brackets, commas or "and"
    between them do not matter."""
    return [match.group() for value in values or [] for match in REF_PATTERN.finditer(str(value))]


def evidence(refs: list[Any] | None, known: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """What the references point to, in order, without repeats or unknown references;
    at most MAX_REFS."""
    kept = [
        {"ref": ref, **{key: value for key, value in known[ref].items() if key != "numbers"}}
        for ref in dict.fromkeys(parse_refs(refs))
        if ref in known
    ]
    return kept[:MAX_REFS]


def sentence(
    item: dict[str, Any] | None,
    known: dict[str, dict[str, Any]],
    where: str,
    dropped: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """A sentence with data behind it, or None (recorded in `dropped` when it had text)."""
    line = text((item or {}).get("text"))
    if not line:
        return None
    found = evidence((item or {}).get("refs"), known)
    if not found:
        dropped.append({"where": where, "refs": (item or {}).get("refs") or []})
        return None
    return {"text": line, "evidence": found}


def language_of(action: dict[str, Any]) -> str:
    """The request's language: the one its title or brief names when it names exactly one
    ("Nepali TikTok videos" is ne whatever the field says, F-059), else the field."""
    said = f"{action.get('title') or ''} {action.get('brief') or ''}"
    named = {code for code, pattern in LANGUAGE_WORDS.items() if pattern.search(said)}
    if len(named) == 1:
        return named.pop()
    return action.get("language") if action.get("language") in LANGUAGES else "any"


def clean_insight(
    item: dict[str, Any],
    trigger: str,
    plan: dict[str, Any],
    dropped: list[dict[str, Any]],
) -> dict[str, Any]:
    known, info = plan["refs"], plan["triggers"][trigger]
    about_post = info["rule"] in POST_RULES
    hypotheses = []
    for number, raw in enumerate(item.get("hypotheses") or [], 1):
        if not about_post:
            # The numbers cannot say why fewer posts went out (F-042): kept out by code.
            dropped.append({"where": f"{trigger} hypothesis {number}", "refs": raw.get("refs") or [],
                            "reason": "the data cannot say why posting fell behind"})  # fmt: skip
            continue
        kept = sentence(raw, known, f"{trigger} hypothesis {number}", dropped)
        if kept and not any(trigger in item.get("triggers", []) for item in kept["evidence"]):
            # A post cannot explain its own result (F-052).
            dropped.append({"where": f"{trigger} hypothesis {number}", "refs": raw.get("refs") or [],
                            "reason": "it cites no comparison for this trigger"})  # fmt: skip
            continue
        if kept and len(hypotheses) < MAX_HYPOTHESES:
            kept.update(confirm_if=text(raw.get("confirm_if")), refute_if=text(raw.get("refute_if")))
            hypotheses.append(kept)
    action = item.get("action") or {}
    card = item.get("client_card") or {}
    tests = action.get("tests") if about_post else 0
    return {
        "trigger": trigger,
        "trigger_rule_id": info["rule"],
        "content_item_id": info.get("content_item_id"),
        # D5 strategic_insights.status; acceptance moves it on, never this processor.
        "status": "Proposed",
        "observation": sentence(item.get("observation"), known, f"{trigger} observation", dropped),
        # For the pace rule: why the data cannot say why posting fell behind.
        "why_unknown": None if about_post else text(item.get("reason")) or None,
        "hypotheses": hypotheses,
        # The fields an asset request needs (DFD_04 I03, DFD_05 F19), as a proposal.
        "action": {
            "title": text(action.get("title")),
            # The hypothesis the request tests (1 or 2); 0 for the pace rule.
            "tests": tests if isinstance(tests, int) and not isinstance(tests, bool) else None,
            "category": action.get("category") if action.get("category") in CATEGORIES else None,
            # The pace rule's request is sized from the gap by prepare (F-049).
            "quantity": info.get("quantity") or action.get("quantity"),
            "language": language_of(action),
            "due_month": plan["month"]["next"],
            "brief": text(action.get("brief")),
            "evidence": evidence(action.get("refs"), known),
        },
        "client_card": {
            # Written by prepare from the trigger's numbers, never by the model (F-048).
            "finding": {"text": info["card"], "evidence": evidence([trigger], known)},
            "action": text(card.get("action")),
            "button": text(card.get("button")),
        },
    }


def clean_answer(
    answer: dict[str, Any], plan: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """(insights, triggers answered with "not enough evidence", dropped): at most one
    answer per sent trigger, in the triggers' order."""
    dropped: list[dict[str, Any]] = []
    first: dict[str, dict[str, Any]] = {}
    for number, item in enumerate(answer.get("insights") or [], 1):
        refs = [ref for ref in parse_refs([item.get("trigger")]) if ref in plan["triggers"]]
        if not refs:
            dropped.append({"where": f"insight {number}", "trigger": item.get("trigger")})
        elif refs[0] in first:
            dropped.append({"where": f"insight {number}", "trigger": refs[0], "reason": "a second answer"})
        else:
            first[refs[0]] = item
    insights, not_enough = [], []
    for trigger in plan["triggers"]:
        item = first.get(trigger)
        if item is None:
            continue
        if not item.get("enough_evidence"):
            not_enough.append({"trigger": trigger, "reason": text(item.get("reason"))})
            continue
        insight = clean_insight(item, trigger, plan, dropped)
        compared = any(trigger in ref.get("triggers", []) for ref in plan["refs"].values())
        if insight["trigger_rule_id"] in POST_RULES and not insight["hypotheses"] and not compared:
            not_enough.append({"trigger": trigger, "reason": "No comparison bears on it, so only the post "
                               "itself could explain its result (decided by the scripts)."})  # fmt: skip
        else:
            insights.append(insight)
    return insights, not_enough, dropped


def insight_texts(
    insight: dict[str, Any], plan: dict[str, Any]
) -> list[tuple[str, str, list[dict[str, Any]], str, list[float]]]:
    """Every piece of text in an insight: (where, text, evidence, kind, numbers it may
    use besides what it cites). Kind is "strategist", "hypothesis" or "client". What
    would confirm or refute a hypothesis may also use its trigger's and the baseline's
    numbers: a test is measured against the result that was flagged."""
    trigger, action, card = insight["trigger"], insight["action"], insight["client_card"]
    quantity = [float(action["quantity"])] if isinstance(action["quantity"], int) else []
    measured = [*quantity, *plan["refs"][trigger]["numbers"], *plan["refs"]["BL"]["numbers"]]
    texts = []
    if insight["observation"]:
        texts.append((f"{trigger}'s observation", insight["observation"]["text"],
                      insight["observation"]["evidence"], "strategist", []))  # fmt: skip
    for number, hypothesis in enumerate(insight["hypotheses"], 1):
        where = f"{trigger}'s hypothesis {number}"
        texts.append((where, hypothesis["text"], hypothesis["evidence"], "hypothesis", []))
        for key, name in (("confirm_if", "what would confirm it"), ("refute_if", "what would refute it")):
            if hypothesis[key]:
                texts.append((f"{where}, {name}", hypothesis[key], hypothesis["evidence"], "strategist", measured))
    for key in ("title", "brief"):
        if action[key]:
            texts.append((f"{trigger}'s request {key}", action[key], action["evidence"], "strategist", quantity))
    if card["finding"]:
        texts.append((f"{trigger}'s client card finding", card["finding"]["text"],
                      card["finding"]["evidence"], "client", []))  # fmt: skip
    for key in ("action", "button"):
        if card[key]:
            # They follow the card's finding, so they may use its (the trigger's) numbers (F-054).
            own = [*quantity, *plan["refs"][trigger]["numbers"]]
            texts.append((f"{trigger}'s client card {key}", card[key], action["evidence"], "client", own))
    return texts


def all_texts(insights: list[dict[str, Any]], plan: dict[str, Any]) -> list[tuple[str, str, list[dict[str, Any]], str, list[float]]]:
    return [entry for insight in insights for entry in insight_texts(insight, plan)]


def cited_numbers(found: list[dict[str, Any]], known: dict[str, dict[str, Any]], plan: dict[str, Any]) -> list[float]:
    return [*plan["general_numbers"], *(v for item in found for v in known[item["ref"]].get("numbers", []))]


def number_checks(texts: list[tuple], plan: dict[str, Any]) -> list[str]:
    """Numbers that show nothing the data holds (nor the request's quantity)."""
    return [
        f'"{written}" in {where} matches no number in the data; check it or remove it.'
        for where, line, _, _, extra in texts
        for written in dict.fromkeys(unmatched(line, [*plan["allowed_numbers"], *extra]))
    ]


def cited_number_checks(texts: list[tuple], plan: dict[str, Any]) -> list[str]:
    """Numbers in the data that are not in what their sentence cites: the sentence may
    give a number to the wrong post or comparison."""
    checks = []
    for where, line, found, _, extra in texts:
        invented = set(unmatched(line, [*plan["allowed_numbers"], *extra]))  # number_checks lists these
        for written in dict.fromkeys(unmatched(line, [*cited_numbers(found, plan["refs"], plan), *extra])):
            if written not in invented:
                cited = ", ".join(item["ref"] for item in found) or "nothing"
                checks.append(
                    f'"{written}" in {where} is in the data, but not in what it cites '
                    f"({cited}); check which number it means."
                )
    return checks


def ratio_checks(texts: list[tuple], plan: dict[str, Any]) -> list[str]:
    """Ratios other than one a cited trigger or comparison gives ("2.2×" is fine when
    the comparison it cites has 2.2; "twice" never is)."""
    checks = []
    for where, line, found, _, _ in texts:
        cited = cited_numbers(found, plan["refs"], plan)
        for phrase in dict.fromkeys(ratios(line)):
            values = numbers_in(phrase)
            if values and all(any(shows(v, n, step) for v in cited) for _, n, step in values):
                continue
            checks.append(
                f'{where.capitalize()} has a ratio ("{phrase}") that what it cites does not '
                "give; use the comparison's own figure or none."
            )
    return checks


def wording_checks(texts: list[tuple]) -> list[str]:
    """Causes stated as fact, hypotheses not worded as possibilities, and terms a client
    should not read."""
    checks = []
    for where, line, _, kind, _ in texts:
        if kind == "hypothesis":
            if not HEDGE.search(line):
                checks.append(
                    f"{where.capitalize()} is not worded as a possibility (may, might, could); "
                    "a hypothesis is never stated as fact."
                )
            if found := ADVICE.search(line):
                checks.append(
                    f'{where.capitalize()} gives advice ("{found.group()}") instead of a possible '
                    "reason; what to do belongs in the request."
                )
        elif (found := CAUSAL.search(line)) and not DATA_GAP.search(line):
            checks.append(
                f'{where.capitalize()} states a cause ("{found.group()}"); only a hypothesis '
                "may suggest why, as a possibility."
            )
        if kind == "client":
            for pattern, name in ((INTERNAL, "internal term"), (CLIENT_TERMS, "internal term"), (JARGON, "jargon word")):
                if found := pattern.search(line):
                    checks.append(
                        f'{where.capitalize()} uses the {name} "{found.group()}"; say it as '
                        "the client would."
                    )
                    break
    return checks


def share_checks(texts: list[tuple]) -> list[str]:
    """A client line about an engagement rate that says it in count words ("more
    often") without a share or a ratio: another post with more likes contradicts it."""
    checks = []
    for where, line, found, kind, _ in texts:
        about_rate = any(
            item.get("rule") == "engagement_gt_200pct_mean" or item.get("measure") == "true_engagement_rate"
            for item in found
        )  # fmt: skip
        if kind == "client" and about_rate and (word := COUNT_LEAD.search(line)) and not AS_SHARE.search(line):
            checks.append(
                f'{where.capitalize()} gives an engagement rate as a count ("{word.group()}"); '
                "say it as a share of the people who saw it, or give its ratio."
            )
    return checks


def same_request_checks(insights: list[dict[str, Any]], pillars: list[str]) -> list[str]:
    """Two requests in one month for the same category and the same kind of post (the
    first pillar the title or brief names: "educational", "promo"). Word overlap could
    not tell them apart: different requests scored up to 0.27, duplicates from 0.28
    (F-055)."""
    def kind(insight: dict[str, Any]) -> str | None:
        said = f"{insight['action']['title']} {insight['action']['brief']}".lower()
        found = [(said.find(pillar), pillar) for pillar in pillars if pillar in said]
        return min(found)[1] if found else None

    def apart(insight: dict[str, Any]) -> tuple:
        """What can set a request apart: its language, the platforms it names, and the
        kinds of comparison behind the hypothesis it tests."""
        action = insight["action"]
        said = f"{action['title']} {action['brief']}".lower()
        tested = insight["hypotheses"][action["tests"] - 1] if action["tests"] in range(1, len(insight["hypotheses"]) + 1) else None
        kinds = frozenset(item.get("kind") for item in (tested or {}).get("evidence", []) if item.get("kind"))
        return action["language"], frozenset(PLATFORM_WORDS.findall(said)), kinds

    # The quota request asks for what works best, so it may well match another; the
    # month's total ask says what that adds up to (F-057).
    tests = [insight for insight in insights if insight["trigger_rule_id"] in POST_RULES]
    checks = []
    for n, first in enumerate(tests):
        for second in tests[n + 1:]:
            same = first["action"]["category"] == second["action"]["category"]
            if same and kind(first) is not None and kind(first) == kind(second) and apart(first) == apart(second):
                checks.append(
                    f"{first['trigger']}'s and {second['trigger']}'s requests both ask for "
                    f"{kind(first)} {first['action']['category']}s, and nothing sets them apart "
                    "(language, platform, what they test); merge them or say what each adds."
                )
    return checks


def total_ask(insights: list[dict[str, Any]], plan: dict[str, Any]) -> str | None:
    """What the month's requests add up to: "Requests for November 2026: 7 videos (T1 2,
    T2 2, T3 3)."."""
    by_category: dict[str, list[str]] = {}
    for insight in insights:
        action = insight["action"]
        if isinstance(action["quantity"], int) and action["category"]:
            by_category.setdefault(action["category"], []).append(f"{insight['trigger']} {action['quantity']}")
    if not by_category:
        return None
    totals = {category: sum(int(item.split()[1]) for item in items) for category, items in by_category.items()}
    parts = [
        f"{totals[category]} {category}{'' if totals[category] == 1 else 's'} ({', '.join(items)})"
        for category, items in by_category.items()
    ]
    return f"Requests for {plan['month']['next_name']}: {'; '.join(parts)}."


def repeat_checks(insights: list[dict[str, Any]], plan: dict[str, Any]) -> list[str]:
    """A card action that says the finding again, which the card shows just before it: it
    shares most of its words, or gives the trigger's numbers (other than the request's
    quantity), which the finding already carries in other words (F-054)."""
    def words(line: str) -> set[str]:
        return set(re.findall(r"[a-z]{4,}", line.lower()))

    checks = []
    for insight in insights:
        card, quantity = insight["client_card"], insight["action"]["quantity"]
        finding, action = words((card["finding"] or {}).get("text", "")), words(card["action"])
        own = [value for value in plan["refs"][insight["trigger"]]["numbers"] if value not in plan["general_numbers"]]
        # "Send us two more" asks for the quantity; "two" also rounds to a 2.2× ratio.
        restated = [written for written, value, step in numbers_in(card["action"])
                    if not (isinstance(quantity, int) and shows(quantity, value, step))
                    and any(shows(number, value, step) for number in own)]  # fmt: skip
        if restated or (finding and action and len(finding & action) / len(action) >= REPEAT_SHARE):
            checks.append(
                f"{insight['trigger']}'s client card action repeats its finding"
                + (f" ({', '.join(restated)})" if restated else "")
                + "; the card shows the finding just before it, so ask for the request instead."
            )
    return checks


def reference_checks(texts: list[tuple]) -> list[str]:
    """References (P2, G1) written into the text, which no reader can follow."""
    return [
        f'{where.capitalize()} shows the reference "{found.group()}"; name what it is instead.'
        for where, line, _, _, _ in texts
        if (found := REF_PATTERN.search(line))
    ]


def insight_checks(insight: dict[str, Any], plan: dict[str, Any]) -> tuple[list[str], list[str]]:
    """(missing parts, checks) of one insight's structure."""
    trigger, action, card = insight["trigger"], insight["action"], insight["client_card"]
    missing, checks = [], []
    if not insight["observation"]:
        missing.append(f"{trigger}: no observation with data behind it")
    about_post = insight["trigger_rule_id"] in POST_RULES
    if about_post and not insight["hypotheses"]:
        missing.append(f"{trigger}: no hypothesis with data behind it")
    for number, hypothesis in enumerate(insight["hypotheses"], 1):
        lacking = [name for key, name in (("confirm_if", "what would confirm it"),
                                          ("refute_if", "what would refute it")) if not hypothesis[key]]  # fmt: skip
        if lacking:
            checks.append(f"{trigger}'s hypothesis {number} does not say {' or '.join(lacking)}.")
        unmeasured = [name for key, name in (("confirm_if", "what would confirm it"),
                                             ("refute_if", "what would refute it"))
                      if hypothesis[key] and not MEASURE_WORDS.search(hypothesis[key])]  # fmt: skip
        if unmeasured:
            checks.append(
                f"{trigger}'s hypothesis {number}: {' and '.join(unmeasured)} names no measure "
                "(liked or shared, people reached, still watching); say what will be measured."
            )
    if about_post and insight["hypotheses"] and action["tests"] not in range(1, len(insight["hypotheses"]) + 1):
        checks.append(f"{trigger}'s request does not say which hypothesis it tests.")
    baseline, measure = plan["triggers"][trigger].get("bar"), BAR_MEASURES.get(insight["trigger_rule_id"])
    for number, hypothesis in enumerate(insight["hypotheses"], 1):
        # The bar is the 90-day average, or the average of a group the hypothesis cites on
        # the trigger's measure where that is higher: those posts already beat the average,
        # so an ordinary new one would confirm nothing (F-058).
        groups = [item["mean"] for item in hypothesis["evidence"]
                  if item.get("measure") == measure and item.get("mean") is not None]  # fmt: skip
        bar = max([baseline, *groups]) if baseline is not None else None
        shares = [float(value) for value in PERCENT.findall(hypothesis["confirm_if"])]
        if bar is not None and shares and max(shares) < bar:
            checks.append(
                f"{trigger}'s hypothesis {number} would be confirmed below its bar, the 90-day or group average "
                f"({fmt_number(max(shares))}% against {fmt_number(bar)}%); almost any post would pass."
            )
    lean = plan.get("format_lean")
    wrong = {"video": "photo", "photo": "video"}.get((lean or {}).get("category"))
    if wrong and action["category"] == wrong:
        checks.append(
            f"{trigger}'s request asks for a {wrong}, but the numbers favour the other format "
            f"({lean['text']})."
        )
    if not action["title"] or not action["brief"]:
        missing.append(f"{trigger}: the request has no title or no brief")
    if action["category"] is None:
        missing.append(f"{trigger}: the request has no category ({', '.join(CATEGORIES)})")
    if action["quantity"] not in plan["quantities"]:
        missing.append(
            f"{trigger}: the request asks for {action['quantity']!r}; it may ask for "
            f"{', '.join(map(str, plan['quantities']))}"
        )
    if not action["evidence"]:
        checks.append(f"{trigger}'s request cites no data; check what it rests on.")
    if not card["finding"] or not card["action"] or not card["button"]:
        missing.append(f"{trigger}: the client card lacks a finding, an action or a button")
    if card["button"] and len(card["button"].split()) > MAX_BUTTON_WORDS:
        checks.append(
            f"{trigger}'s client card button has {len(card['button'].split())} words; the card "
            f"fits {MAX_BUTTON_WORDS}."
        )
    if card["button"] and not NUMBER_WORD.search(card["button"]):
        checks.append(f'{trigger}\'s client card button ("{card["button"]}") does not say how many.')
    return missing, checks


def to_markdown(plan: dict[str, Any], document: dict[str, Any]) -> str:
    month = plan["month"]
    lines = [
        f"# Insights for {month['name']} (draft)",
        "",
        f"- Input: insights/{plan['source']['name']} (the anomaly rules' triggers) and the "
        "month's numbers in "
        + ", ".join(f"reports/{name}" for name in plan["inputs"]["window_reports"])
        + " (the posts in the baseline window)",
        f"- Requests proposed for: {month['next_name']}"
        + (f" ({document['total_ask']})" if document.get("total_ask") else ""),
        f"- Model: {document['provider']['model']}",
        f"- Review status: {document['review_status']}; every insight is Proposed (for the "
        "strategist to review; nothing reaches the client)",
        f"- Created: {document['created_at']}",
        "",
        "> Drafted by a model. The hypotheses are possibilities to test, not findings. Every "
        "number comes from the rules and comparisons worked out before the model ran; check "
        "each against the dashboard before showing anything to the client.",
    ]
    if document["missing"] or document["checks"]:
        lines.extend(["", "## Needs attention", ""])
        lines.extend(f"- {item}" for item in document["missing"] + document["checks"])
    if document["review_notes"]:
        lines.extend(["", "## Notes from the model", ""])
        lines.extend(f"- {note}" for note in document["review_notes"])
    if document["held_back"]:
        lines.extend(["", "## Held back (not sent)", ""])
        lines.extend(f"- {item['label']}: {item['reason']}" for item in document["held_back"])
    if document["not_enough_evidence"]:
        lines.extend(["", "## Not enough evidence", ""])
        for item in document["not_enough_evidence"]:
            lines.append(f"- {item['trigger']} ({plan['refs'][item['trigger']]['label']}): {item['reason'] or '_no reason given_'}")

    cited: dict[str, None] = {}
    for insight in document["insights"]:
        action, card = insight["action"], insight["client_card"]
        trigger = insight["trigger"]
        lines.extend(["", f"## {trigger}: {RULES[insight['trigger_rule_id']]}", "",
                      plan["refs"][trigger]["label"].split(": ", 1)[-1], "", "**Observation.** "
                      + (insight["observation"]["text"] if insight["observation"] else "_None._")])  # fmt: skip
        if insight["trigger_rule_id"] not in POST_RULES:
            lines.extend(["", "**Why posting fell behind:** the numbers cannot say. "
                          + (insight["why_unknown"] or "")])  # fmt: skip
        if insight["hypotheses"]:
            lines.extend(["", "**Hypotheses (to test, not facts)**", ""])
        for number, hypothesis in enumerate(insight["hypotheses"], 1):
            refs = ", ".join(e["ref"] for e in hypothesis["evidence"])
            lines.append(f"{number}. {hypothesis['text']} *({refs})*")
            lines.append(f"   - Confirmed if: {hypothesis['confirm_if'] or '_not given_'}")
            lines.append(f"   - Refuted if: {hypothesis['refute_if'] or '_not given_'}")
        tested = f"hypothesis {action['tests']}" if action["tests"] else "-"
        lines.extend(["", "**Proposed request (status Proposed)**", "",
                      "| Title | Tests | Category | Quantity | Language | Due | Brief |",
                      "| --- | --- | --- | --- | --- | --- | --- |",
                      f"| {action['title']} | {tested} | {action['category'] or '_none_'} | {action['quantity']} | "
                      f"{action['language']} | {action['due_month']} | {action['brief']} |"])  # fmt: skip
        lines.extend(["", "**Client card (draft; the first sentence is written from the numbers)**", "",
                      f"> {card['finding']['text'] if card['finding'] else '_no finding_'} {card['action']}",
                      f"> [{card['button'] or 'no button'}]"])  # fmt: skip
        for _, _, found, _, _ in insight_texts(insight, plan):
            cited.update(dict.fromkeys(e["ref"] for e in found))
    if not document["insights"]:
        lines.extend(["", "_No insight was drafted._"])
    lines.extend(["", "## References", ""])
    lines.extend(f"- {ref}: {plan['refs'][ref]['label']}" for ref in cited)
    if not cited:
        lines.append("_None._")
    return "\n".join(lines) + "\n"


def finalize(job_dir: Path, keep_work: bool = False) -> dict[str, Any]:
    plan = json.loads((job_dir / "plan.json").read_text(encoding="utf-8"))
    answer_file = job_dir / "results" / "answer.json"
    if not answer_file.is_file():
        fail("no answer found; nothing to save (the work folder was kept)")
    result = json.loads(answer_file.read_text(encoding="utf-8"))
    answer, options = result["answer"], plan["options"]
    usage = result.get("usage") or {}

    insights, not_enough, dropped = clean_answer(answer, plan)
    notes = [note for note in (text(n) for n in answer.get("review_notes") or []) if note]
    answered = {i["trigger"] for i in insights} | {i["trigger"] for i in not_enough}
    missing = [f"{ref}: no answer" for ref in plan["triggers"] if ref not in answered]
    structure = []
    for insight in insights:
        lacking, checks = insight_checks(insight, plan)
        missing += lacking
        structure += checks
    texts = all_texts(insights, plan)
    numbers = number_checks(texts, plan)
    checks = (
        numbers
        + cited_number_checks(texts, plan)
        + ratio_checks(texts, plan)
        + wording_checks(texts)
        + share_checks(texts)
        + same_request_checks(insights, plan.get("pillars", []))
        + repeat_checks(insights, plan)
        + reference_checks(texts)
        + structure
    )

    output_dir = Path(plan["output_dir"])
    files = ["insights.md", "insights.json", "metadata.json"]
    archived = archive_previous(output_dir, "insights.json", files, plan.get("replaces"))
    # A number the data does not hold may be invented: the draft is not usable as it is.
    complete = not missing and not numbers
    document = {
        "version": 1,
        "processor": plan["processor"],
        "complete": complete,
        # Proposals for the strategist to review (Pulse D5 status Proposed); never sent.
        "review_status": "draft",
        "source": plan["source"],
        "month_period": plan["month"]["period"],
        "requests_for": plan["month"]["next"],
        # What each input was; prepare compares them to notice a newer one.
        "inputs": plan["inputs"],
        "organisation": plan.get("organisation"),
        "options": options,
        "provider": {"name": "openai", "model": options["model"]},
        "usage": {
            "requests": 1,
            "input_tokens": int(usage.get("input_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or 0),
        },
        "estimated_input_tokens": plan["estimated_input_tokens"],
        "missing": missing,
        "checks": checks,
        "review_notes": notes[:MAX_NOTES],
        "dropped": dropped,
        "held_back": plan["held_back"],
        "not_enough_evidence": not_enough,
        # What the month's requests add up to, for the strategist to weigh.
        "total_ask": total_ask(insights, plan),
        "insights": insights,
        "created_at": now_iso(),
    }
    status = "complete" if complete else "incomplete"
    write_json(output_dir / "insights.json", document)
    write_text(output_dir / "insights.md", to_markdown(plan, document))
    # The context and refs hold the month's data, which the input files already have.
    kept = {k: v for k, v in plan.items()
            if k not in ("context", "refs", "allowed_numbers", "general_numbers")}  # fmt: skip
    write_json(output_dir / "metadata.json", result_metadata(kept, status))
    if not keep_work:
        shutil.rmtree(job_dir)

    return {
        "status": status,
        "output_dir": str(output_dir),
        "files": files,
        "previous_result": str(archived) if archived else None,
        "month": plan["month"]["period"],
        "insights": [
            {"trigger": i["trigger"], "rule": i["trigger_rule_id"], "hypotheses": len(i["hypotheses"]),
             "request": f"{i['action']['quantity']} {i['action']['category']}",
             "tests": i["action"]["tests"]}
            for i in insights
        ],  # fmt: skip
        "not_enough_evidence": [i["trigger"] for i in not_enough],
        "total_ask": document["total_ask"],
        "held_back": len(plan["held_back"]),
        "dropped": len(dropped),
        "missing": missing,
        "checks": checks,
        "review_notes": document["review_notes"],
        "usage": document["usage"],
        "warnings": plan["warnings"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("job_dir", type=Path)
    parser.add_argument("--keep-work", action="store_true", help="keep the job folder")
    args = parser.parse_args()
    job_dir = args.job_dir.expanduser().resolve()
    if not is_job_dir(job_dir) or not (job_dir / "plan.json").is_file():
        fail(f"{args.job_dir} is not a prepared job folder inside work/")
    print_json(finalize(job_dir, args.keep_work))


if __name__ == "__main__":
    main()
