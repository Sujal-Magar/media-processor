#!/usr/bin/env python3
"""draft-report, step 3: turn the model's answer into output/draft-report/<month>-<hash>/
report.md, report.json and metadata.json. Free; draft.py runs it.

Every sentence keeps the data its references point to (a total, a platform, a post, an
item of the strategist's plan); a reference to something that was not sent is dropped,
and so is a sentence left with none. Next month's items are kept only as rewordings of
the strategist's plan, so without a plan there are none. Every number in the text must
show one the month's data holds (48,200 as 48.2K, 38.11% as 38%) or a total's
difference from last month: one that does not is listed in `checks`, and the draft is
saved as incomplete, as is a draft that lacks a part. `checks` also lists ratios, causal
wording, jargon, superlatives without earlier months and sentences resting on partial
data. A number that is in the month's data but not in what its sentence cites, a
ranking among posts while some have incomplete numbers, and internal terms are listed
too. An item holding several sentences is split, each keeping the item's references.
Prints only counts, paths and these notes, never the draft.

    python3 processors/draft-report/finalize.py work/draft-report/<job> [--keep-work]
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

from lib.numbers import ratios, unmatched
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

# Metric: how the material names it. The PRD's dashboard list (reach, engagement, video
# views, follower growth, link clicks, enquiries where tracked); video views are D2's
# views_count, which counts plays, not people.
METRICS = {
    "reach": "people reached",
    "video_views": "video plays (times the videos were played, not people)",
    "engagement_rate": "engagement rate, (likes + comments + shares + saves) / people "
    "reached x 100",
    "new_followers": "new followers",
    "link_clicks": "link clicks",
    "enquiries": "enquiries",
}
# The report's metric row (Pulse screen 7), with the label each number goes under.
TILES = {
    "reach": "people reached",
    "video_views": "video plays",
    "enquiries": "enquiries",
    "new_followers": "new followers",
}
PLATFORMS = ("instagram", "tiktok", "linkedin", "youtube")  # D1 content_variants.platform
# C17a's Top 3 highlights; the top post of the month is the highest-reach one.
SLOTS = {
    "highest_reach": "Highest reach",
    "highest_engagement": "Highest engagement",
    "best_retention": "Best retention",
}
PARAGRAPHS = {
    "what_happened": "What happened",
    "what_worked": "What worked",
    "what_did_not_land": "What didn't land",
}
MAX_REFS = 5
MAX_NOTES = 10
MAX_HEADLINE_WORDS = 20
MIN_PARAGRAPH_SENTENCES, MAX_PARAGRAPH_SENTENCES = 2, 4
MAX_TOP_POST_SENTENCES = 2
# A reference as a model may write it: M:reach, PL:tiktok, P3, N2, [P3], "P3 and P4".
REF_PATTERN = re.compile(r"\b(?:M|PL):[a-z_]+|\b[PN]\d+\b")
# A sentence ends at . ! or ? before a capital or digit (48.2K and 9.35% stay whole).
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")
# Words that claim a cause: the data shows what happened, not why.
CAUSAL = re.compile(
    r"\b(?:because|due to|thanks to|led to|leads to|caused?|causing|drove|driven|"
    r"driving|resulted in|results in|that's why)\b",
    re.IGNORECASE,
)
# Words that say data is missing: "because" next to them explains a gap, not a result.
DATA_GAP = re.compile(
    r"\b(?:incomplete|missing|not recorded|not shown|held back|not tracked|not counted|"
    r"left out|leaves? out|leaving out|with complete (?:data|numbers))\b",
    re.IGNORECASE,
)
# Words that say a number went down.
FELL = re.compile(r"\b(?:down|fell|fewer|lower|dropped|drop|less|dip(?:ped)?|slower|quieter)\b", re.IGNORECASE)
# How the report is made, which the client never needs to read.
INTERNAL = re.compile(
    r"\b(?:report engine|engine|snapshots?|data quality|highlight slots?)\b", re.IGNORECASE
)
# Jargon the Pulse docs keep off client surfaces (PROJECT_SCOPE pre-flight scan and
# plain-English rule).
JARGON = re.compile(
    r"\b(?:impressions?|CTR|CPC|KPIs?|conversions?|funnel|video completions?)\b",
    re.IGNORECASE,
)
# Comparisons beyond last month, which only earlier months can support ("the strongest
# post" ranks this month's posts and is not one).
SUPERLATIVE = re.compile(
    r"\b(?:ever|so far|since we started|all-time|on record|record (?:month|high|low)|"
    r"(?:best|strongest|weakest|worst|biggest|busiest|quietest)\s+(?:\w+\s+){0,2}month)\b",
    re.IGNORECASE,
)
# Which way a ranking of posts goes.
# "more than any", also with words between: "reached more people than any other post".
MOST = re.compile(
    r"\b(?:most|highest|top|topped|tops|biggest|largest|widest|greatest|best|led|leads|"
    r"leading|ahead of|outperform\w*|came (?:out )?(?:first|top)|number one|"
    r"more(?:\s+\w+){0,3}\s+than any)\b",
    re.IGNORECASE,
)
FEWEST = re.compile(
    r"\b(?:fewest|lowest|least|smallest|narrowest|weakest|bottom|trailed|trails|"
    r"came last|behind (?:every|all|the others)|(?:fewer|less)(?:\s+\w+){0,3}\s+than any)\b",
    re.IGNORECASE,
)
# Words that rank posts against each other, either way.
RANKING = re.compile(f"{MOST.pattern}|{FEWEST.pattern}", re.IGNORECASE)
# What a ranking is about, by the snapshot field it rests on. The engagement wording
# ("the share of people reached who liked, commented on, shared or saved") names reach,
# likes, comments, shares and saves without being about them, so it is taken out of the
# line before the counts are looked for.
ENGAGEMENT = re.compile(
    r"\bengag\w*(?:\s+rate)?|\bliked,?\s+commented(?:\s+on)?,?\s+shared,?\s+(?:or|and)\s+saved",
    re.IGNORECASE,
)
# "The share of people reached (who ...)" is a share, not a count of people reached; what
# it is a share of (liking, or watching to the end) is named after it.
SHARE = re.compile(
    r"\bshare of (?:the )?(?:people|viewers)(?:\s+(?:reached|who saw it))?", re.IGNORECASE
)
RETENTION = {
    "retention_complete_pct": re.compile(r"\bto the end\b", re.IGNORECASE),
    "retention_10s_pct": re.compile(r"\b(?:10|ten) s(?:econds?)?\b", re.IGNORECASE),
    "retention_3s_pct": re.compile(r"\b(?:3|three) s(?:econds?)?\b", re.IGNORECASE),
}
COUNTS = {
    "reach_count": re.compile(r"\breach|\bpeople saw|\bseen by|\bsaw it\b", re.IGNORECASE),
    "views_count": re.compile(r"\bplay(?:s|ed)?\b|\bviews?\b", re.IGNORECASE),
    "likes_count": re.compile(r"\blike[sd]?\b", re.IGNORECASE),
    "comments_count": re.compile(r"\bcomment", re.IGNORECASE),
    "shares_count": re.compile(r"\bshare[sd]?\b", re.IGNORECASE),
    "saves_count": re.compile(r"\bsave[sd]?\b", re.IGNORECASE),
}


def text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_refs(values: list[Any] | None) -> list[str]:
    """The references in what the model wrote, in order; brackets, commas or "and"
    between them do not matter."""
    return [match.group() for value in values or [] for match in REF_PATTERN.finditer(str(value))]


def evidence(
    refs: list[Any] | None, known: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """What the references point to, in order, without repeats or unknown references;
    at most MAX_REFS."""
    kept = [
        {"ref": ref, **{key: value for key, value in known[ref].items() if key != "numbers"}}
        for ref in dict.fromkeys(parse_refs(refs))
        if ref in known
    ]
    return kept[:MAX_REFS]


def clean_sentences(
    items: list[dict[str, Any]] | None,
    known: dict[str, dict[str, Any]],
    section: str,
    dropped: list[dict[str, Any]],
    split: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Sentences with data behind them; one without is added to `dropped` with its
    references as written. With `split`, an item holding several sentences becomes one
    entry per sentence, each with the item's references, and is recorded in `split`."""
    kept = []
    for number, item in enumerate(items or [], 1):
        line = text(item.get("text"))
        if not line:
            continue
        found = evidence(item.get("refs"), known)
        if not found:
            dropped.append({"section": section, "number": number, "refs": item.get("refs") or []})
            continue
        parts = SENTENCE_END.split(line) if split is not None else [line]
        if len(parts) > 1:
            split.append({"section": section, "number": number, "sentences": len(parts)})
        kept.extend({"text": part, "evidence": found, "item": number} for part in parts)
    return kept


def clean_keyed(
    items: list[dict[str, Any]] | None,
    key: str,
    wanted: list[str],
    known: dict[str, dict[str, Any]],
    section: str,
    dropped: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """The first line with data behind it for each wanted highlight slot or tile, in
    the wanted order."""
    first: dict[str, dict[str, Any]] = {}
    for number, item in enumerate(items or [], 1):
        name, line = item.get(key), text(item.get("text"))
        if name not in wanted or name in first or not line:
            continue
        found = evidence(item.get("refs"), known)
        if not found:
            dropped.append({"section": section, "number": number, key: name,
                            "refs": item.get("refs") or []})  # fmt: skip
            continue
        first[name] = {"text": line, "evidence": found}
    return {name: first[name] for name in wanted if name in first}


def clean_next_month(
    items: list[dict[str, Any]] | None,
    known: dict[str, dict[str, Any]],
    dropped: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """The client's wording of each item of the strategist's plan, in the plan's order,
    one per item. An item that names no plan item is dropped: the model does not plan
    the month, so without a plan nothing is kept."""
    plan = [ref for ref, item in known.items() if item["source"] == "plan"]
    first: dict[str, dict[str, Any]] = {}
    for number, item in enumerate(items or [], 1):
        line = text(item.get("text"))
        refs = parse_refs([item.get("plan_item")])
        ref = refs[0] if refs else None
        if not line:
            continue
        if ref not in plan:
            dropped.append({"section": "next_month", "number": number,
                            "plan_item": item.get("plan_item")})  # fmt: skip
            continue
        first.setdefault(ref, {"plan_item": ref, "text": line, "plan_text": known[ref]["text"]})
    return [first[ref] for ref in plan if ref in first]


def sentence_texts(
    sentences: list[dict[str, Any]], grouped: bool
) -> list[tuple[str, str, list[dict[str, Any]]]]:
    """Each sentence as (which, text, evidence); with `grouped`, the sentences split from
    one item as one text, since what one says about the data the next may qualify."""
    texts, start = [], 0
    while start < len(sentences):
        end = start + 1
        while grouped and end < len(sentences) and sentences[end].get("item") == sentences[start].get("item"):
            end += 1
        which = f"sentence {start + 1}" if end == start + 1 else f"sentences {start + 1} to {end}"
        line = " ".join(s["text"] for s in sentences[start:end])
        texts.append((which, line, sentences[start]["evidence"]))
        start = end
    return texts


def client_texts(
    document: dict[str, Any], grouped: bool = False
) -> list[tuple[str, str, list[dict[str, Any]]]]:
    """Every piece of text the client would read: (where it is, text, its evidence)."""
    texts = []
    if document["headline"]:
        texts.append(("the headline", document["headline"]["text"], document["headline"]["evidence"]))
    for key, name in PARAGRAPHS.items():
        for which, line, found in sentence_texts(document["summary"][key], grouped):
            texts.append((f"{name}, {which}", line, found))
    for which, line, found in sentence_texts(document["top_post"]["sentences"], grouped):
        texts.append((f"the top post, {which}", line, found))
    for slot, item in document["highlights"].items():
        texts.append((f"the {SLOTS[slot].lower()} highlight", item["text"], item["evidence"]))
    for metric, item in document["tiles"].items():
        texts.append((f"the {TILES[metric]} tile", item["text"], item["evidence"]))
    for item in document["next_month"]:
        texts.append((f"next month's item {item['plan_item']}", item["text"], []))
    return texts


def number_checks(
    texts: list[tuple[str, str, list[dict[str, Any]]]], allowed: list[float]
) -> list[str]:
    """Numbers that show nothing the month's data holds."""
    return [
        f'"{written}" in {where} matches no number in the month\'s data; check it '
        "against the dashboard or remove it."
        for where, line, _ in texts
        for written in dict.fromkeys(unmatched(line, allowed))
    ]


def cited_number_checks(
    texts: list[tuple[str, str, list[dict[str, Any]]]],
    known: dict[str, dict[str, Any]],
    general: list[float],
    allowed: list[float],
) -> list[str]:
    """Numbers in the month's data that are not in what their sentence cites: the
    sentence may give a number to the wrong post or metric."""
    checks = []
    for where, line, found in texts:
        if not found:
            continue
        cited = [*general, *(v for item in found for v in known[item["ref"]].get("numbers", []))]
        invented = set(unmatched(line, allowed))  # number_checks lists these
        for written in dict.fromkeys(unmatched(line, cited)):
            if written not in invented:
                checks.append(
                    f'"{written}" in {where} is in the month\'s data, but not in what it '
                    f"cites ({refs_text(found)}); check which number it means."
                )
    return checks


def ratio_checks(texts: list[tuple[str, str, list[dict[str, Any]]]]) -> list[str]:
    """Ratios and fractions, which the data never gives ("twice a week" in a plan is
    fine, so they are left to the reviewer)."""
    checks = []
    for where, line, _ in texts:
        for found in dict.fromkeys(ratios(line)):
            checks.append(
                f'{where.capitalize()} has a ratio or fraction ("{found}") that the data '
                "does not give; check it or remove it."
            )
    return checks


def wording_checks(
    texts: list[tuple[str, str, list[dict[str, Any]]]], has_history: bool
) -> list[str]:
    """Causal wording, jargon, and comparisons beyond last month without earlier months."""
    checks = []
    for where, line, _ in texts:
        if (found := CAUSAL.search(line)) and not DATA_GAP.search(line):
            checks.append(
                f'{where.capitalize()} claims a cause ("{found.group()}"); the numbers show '
                "what happened, not why. Reword it as an observation."
            )
        if found := INTERNAL.search(line):
            checks.append(
                f'{where.capitalize()} uses the internal term "{found.group()}"; say it as '
                "the client would."
            )
        if found := JARGON.search(line):
            checks.append(
                f'{where.capitalize()} uses the jargon word "{found.group()}"; say it in '
                "plain English."
            )
        if not has_history and (found := SUPERLATIVE.search(line)):
            checks.append(
                f'{where.capitalize()} compares beyond last month ("{found.group()}"), but '
                "no earlier months were given; check it or remove it."
            )
    return checks


def partial_checks(texts: list[tuple[str, str, list[dict[str, Any]]]]) -> list[str]:
    """Sentences resting on a post whose snapshot is Partial or Stale, unless they say
    its data is incomplete or that it is left out."""
    checks = []
    for where, line, found in texts:
        if DATA_GAP.search(line):
            continue
        for item in found:
            flag = item.get("data_quality_flag")
            if item["source"] == "post" and flag in ("Partial", "Stale"):
                checks.append(
                    f"{where.capitalize()} rests on {item['ref']}, whose data is {flag}; "
                    "make sure it calls those numbers incomplete."
                )
    return checks


def ranking_checks(
    texts: list[tuple[str, str, list[dict[str, Any]]]], known: dict[str, dict[str, Any]]
) -> list[str]:
    """A sentence about posts that ranks them while some posts' numbers are incomplete,
    without saying those posts are left out."""
    incomplete = [ref for ref, item in known.items()
                  if item["source"] == "post" and item.get("data_quality_flag") in ("Partial", "Stale")]  # fmt: skip
    if not incomplete:
        return []
    checks = []
    for where, line, found in texts:
        about_posts = any(item["source"] == "post" for item in found)
        if about_posts and (word := RANKING.search(line)) and not DATA_GAP.search(line):
            them = "it" if len(incomplete) == 1 else "them"
            checks.append(
                f'{where.capitalize()} ranks posts ("{word.group()}") while the numbers of '
                f"{', '.join(incomplete)} are incomplete; say the ranking leaves {them} out."
            )
    return checks


def measures_in(line: str) -> list[str]:
    """Every snapshot field a ranking in this line may be about: the engagement rate when
    its wording is there, watching, and the counts named outside that wording."""
    found = ["true_engagement_rate"] if ENGAGEMENT.search(line) else []
    found += [key for key, pattern in RETENTION.items() if pattern.search(line)]
    rest = SHARE.sub(" ", ENGAGEMENT.sub(" ", line))
    return found + [key for key, pattern in COUNTS.items() if pattern.search(rest)]


def order_checks(
    texts: list[tuple[str, str, list[dict[str, Any]]]], leaders: dict[str, dict[str, Any]]
) -> list[str]:
    """A ranking of posts that the leaders among posts with complete data do not back:
    the posts it cites are not the leader, or it cites the leader with other posts, so
    the text may put another one first (the leader's name is in the check)."""
    checks = []
    for where, line, found in texts:
        posts = {item["ref"] for item in found
                 if item["source"] == "post" and item.get("data_quality_flag") == "Full"}  # fmt: skip
        direction = "most" if MOST.search(line) else "fewest" if FEWEST.search(line) else None
        if not posts or not direction:
            continue
        place = "first" if direction == "most" else "last"
        shared = []  # measures whose leader is cited along with other posts
        for key in measures_in(line):
            lead = leaders.get(key)
            if not lead:
                continue
            first = lead[direction]
            label = lead["label"].split(" (")[0]
            if not posts & set(first):
                checks.append(
                    f"{where.capitalize()} puts {', '.join(sorted(posts))} {place} on {label}, "
                    f"but {', '.join(first)} {'is' if len(first) == 1 else 'are'} {place} among "
                    "posts with complete data; check it."
                )
            elif posts - set(first):
                shared.append(f"{', '.join(first)} on {label}")
        if shared:
            checks.append(
                f"{where.capitalize()} ranks posts and cites {', '.join(sorted(posts))}; "
                f"among posts with complete data the {place} is {'; '.join(shared)}: make sure "
                f"that is the post it puts {place}."
            )
    return checks


def reference_checks(texts: list[tuple[str, str, list[dict[str, Any]]]]) -> list[str]:
    """References (P2, M:reach) written into the text, which the client cannot read."""
    return [
        f'{where.capitalize()} shows the reference "{found.group()}" to the client; name '
        "what it is instead."
        for where, line, _ in texts
        if (found := REF_PATTERN.search(line))
    ]


def headline_checks(document: dict[str, Any], tiles: dict[str, dict[str, Any]]) -> list[str]:
    """A headline that does not say that the people reached fell, in a month they did."""
    delta = (tiles.get("reach") or {}).get("delta_pct")
    headline = (document["headline"] or {}).get("text", "")
    if headline and delta is not None and delta < 0 and not FELL.search(headline):
        return [f"The headline does not say that fewer people were reached ({delta:g}% on last month)."]
    return []


def split_checks(split: list[dict[str, Any]]) -> list[str]:
    names = {**PARAGRAPHS, "top_post": "The top post text"}
    return [
        f"{names[item['section']]}, item {item['number']}, held {item['sentences']} "
        "sentences; each keeps all of the item's references, so check which data each "
        "one rests on."
        for item in split
    ]


def highlight_checks(document: dict[str, Any], highlights: dict[str, str | None]) -> list[str]:
    """A highlight or the top post that does not cite the post the report engine chose."""
    checks = []
    for slot, item in document["highlights"].items():
        if highlights.get(slot) not in {e["ref"] for e in item["evidence"]}:
            checks.append(
                f"The {SLOTS[slot].lower()} highlight does not cite {highlights.get(slot)}, "
                "the post the report engine chose for it."
            )
    top = highlights.get("highest_reach")
    cited = {e["ref"] for s in document["top_post"]["sentences"] for e in s["evidence"]}
    if top and document["top_post"]["sentences"] and top not in cited:
        checks.append(f"The top post text does not cite {top}, the highest-reach post.")
    return checks


def length_checks(document: dict[str, Any]) -> list[str]:
    checks = []
    if document["headline"]:
        words = len(document["headline"]["text"].split())
        if words > MAX_HEADLINE_WORDS:
            checks.append(
                f"The headline has {words} words; the report card fits about "
                f"{MAX_HEADLINE_WORDS}."
            )
    for key, name in PARAGRAPHS.items():
        count = len(document["summary"][key])
        if count and not MIN_PARAGRAPH_SENTENCES <= count <= MAX_PARAGRAPH_SENTENCES:
            checks.append(
                f"{name} has {count} sentence{'' if count == 1 else 's'}; the report asks "
                f"for {MIN_PARAGRAPH_SENTENCES} to {MAX_PARAGRAPH_SENTENCES}."
            )
    if len(document["top_post"]["sentences"]) > MAX_TOP_POST_SENTENCES:
        checks.append(
            f"The top post text has {len(document['top_post']['sentences'])} sentences; "
            f"the spotlight fits {MAX_TOP_POST_SENTENCES}."
        )
    return checks


def missing_parts(document: dict[str, Any], plan: dict[str, Any]) -> list[str]:
    """What the report needs and the draft lacks; empty when complete."""
    missing = []
    if not document["headline"]:
        missing.append("no headline with data behind it")
    for key, name in PARAGRAPHS.items():
        if not document["summary"][key]:
            missing.append(f'no "{name}" paragraph with data behind it')
    if plan["highlights"].get("highest_reach") and not document["top_post"]["sentences"]:
        missing.append("no top post text with data behind it")
    for slot, ref in plan["highlights"].items():
        if ref and slot not in document["highlights"]:
            missing.append(f"no line for the {SLOTS[slot].lower()} highlight")
    for metric in plan["tiles"]:
        if metric not in document["tiles"]:
            missing.append(f"no line under the {TILES[metric]} tile")
    have = {item["plan_item"] for item in document["next_month"]}
    for ref, item in plan["refs"].items():
        if item["source"] == "plan" and ref not in have:
            missing.append(f"no client wording for the strategist's plan item {ref}")
    return missing


def compact(metric: str, value: float | None) -> str:
    """A tile's number as the report shows it: 48.2K, 3,412, 7.14%."""
    if value is None:
        return "not tracked"
    if metric == "engagement_rate":
        return f"{value:g}%"
    if value >= 10_000:
        return f"{value / 1000:.1f}K"
    return f"{value:,.0f}"


def change_text(total: dict[str, Any]) -> str:
    if total.get("delta_pct") is None:
        return "not shown" if total.get("previous") is not None else "no earlier number"
    delta = total["delta_pct"]
    return f"{'▲' if delta > 0 else '▼' if delta < 0 else '='} {abs(delta):.0f}%"


def refs_text(found: list[dict[str, Any]]) -> str:
    return ", ".join(item["ref"] for item in found)


def to_markdown(plan: dict[str, Any], document: dict[str, Any]) -> str:
    month = plan["month"]
    organisation = document["organisation"]
    lines = [
        f"# {month['name']} at a glance (draft)",
        "",
        f"- Organisation: {organisation['name'] if organisation else 'not given (organisation.json)'}",
        f"- Month: {month['name']}, compared with {month['previous_name']}",
        f"- Input: {plan['source']['name']}",
        f"- Model: {document['provider']['model']}",
        f"- Review status: {document['review_status']} (for the strategist to review, edit "
        "and sign off; nothing is sent)",
        f"- Created: {document['created_at']}",
        "",
        "> Drafted by a model from the month's recorded numbers. People are never named. "
        "Every sentence lists the data it rests on; check each number and claim against "
        "the dashboard before approving.",
    ]
    if document["missing"] or document["checks"]:
        lines.extend(["", "## Needs attention", ""])
        lines.extend(f"- {item}" for item in document["missing"] + document["checks"])
    if document["review_notes"]:
        lines.extend(["", "## Notes from the model", ""])
        lines.extend(f"- {note}" for note in document["review_notes"])

    lines.extend(["", "## Report card", ""])
    headline = document["headline"]
    lines.append(f"{headline['text']} *({refs_text(headline['evidence'])})*" if headline else "_None._")

    lines.extend(["", f"## {month['name']} at a glance"])
    for key, name in PARAGRAPHS.items():
        sentences = document["summary"][key]
        lines.extend(["", f"**{name}.** " + (" ".join(s["text"] for s in sentences) or "_None._")])
        if sentences:
            cited = dict.fromkeys(e["ref"] for s in sentences for e in s["evidence"])
            lines.append(f"*Rests on: {', '.join(cited)}*")

    lines.extend(["", "## The numbers", "",
                  f"| Tile | Number | Change on {month['previous_name']} | Line under it |",
                  "| --- | --- | --- | --- |"])  # fmt: skip
    for metric, total in plan["tiles"].items():
        line = document["tiles"].get(metric, {}).get("text", "_none_")
        lines.append(
            f"| {TILES[metric]} | {compact(metric, total.get('current'))} | "
            f"{change_text(total)} | {line} |"
        )
    if not plan["tiles"]:
        lines.append("| _no tile is tracked_ | | | |")

    lines.extend(["", "## Top post of the month", ""])
    top = plan["highlights"].get("highest_reach")
    if top:
        lines.append(f"{top}: {plan['refs'][top]['label']}")
        for sentence in document["top_post"]["sentences"]:
            lines.extend(["", f"{sentence['text']} *({refs_text(sentence['evidence'])})*"])
    else:
        lines.append("_No highest-reach post was given._")

    lines.extend(["", "## Highlights", ""])
    for slot, ref in plan["highlights"].items():
        if ref:
            line = document["highlights"].get(slot, {}).get("text", "_none_")
            lines.append(f"- **{SLOTS[slot]}** ({ref}): {line}")

    lines.extend(["", f"## What we're doing in {month['next_name'].split()[0]}", ""])
    for number, item in enumerate(document["next_month"], 1):
        lines.append(f"{number:02d}. {item['text']} *(strategist's item {item['plan_item']})*")
    if not document["next_month"]:
        lines.append(
            "_The strategist writes this list; the input has no plan for "
            f"{month['next_name']} yet._"
        )

    cited = dict.fromkeys(e["ref"] for _, _, found in client_texts(document) for e in found)
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
    answer, refs, options = result["answer"], plan["refs"], plan["options"]
    usage = result.get("usage") or {}

    dropped: list[dict[str, Any]] = []
    split: list[dict[str, Any]] = []
    headline = clean_sentences([answer.get("headline") or {}], refs, "headline", dropped)
    summary = {
        key: clean_sentences(answer.get(key), refs, key, dropped, split) for key in PARAGRAPHS
    }
    top_post = clean_sentences(answer.get("top_post"), refs, "top_post", dropped, split)
    slots = [slot for slot, ref in plan["highlights"].items() if ref]
    highlights = clean_keyed(answer.get("highlights"), "slot", slots, refs, "highlights", dropped)
    tiles = clean_keyed(answer.get("tiles"), "metric", list(plan["tiles"]), refs, "tiles", dropped)
    next_month = clean_next_month(answer.get("next_month"), refs, dropped)
    notes = [note for note in (text(n) for n in answer.get("review_notes") or []) if note]

    output_dir = Path(plan["output_dir"])
    files = ["report.md", "report.json", "metadata.json"]
    archived = archive_previous(output_dir, "report.json", files, plan.get("replaces"))
    document = {
        "version": 1,
        "processor": plan["processor"],
        "complete": False,
        # Candidate text for the strategist to review, edit and sign off (Pulse F09/F11);
        # never sent to the client as it is.
        "review_status": "draft",
        "source": plan["source"],
        "month_period": plan["month"]["period"],
        "previous_month": plan["month"]["previous"],
        # When each earlier result was made; prepare compares them to notice a newer one.
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
        "missing": [],
        "checks": [],
        "review_notes": notes[:MAX_NOTES],
        "dropped": dropped,
        # Items the model wrote as several sentences, each now its own entry.
        "split": split,
        "headline": headline[0] if headline else None,
        "summary": summary,
        "top_post": {"ref": plan["highlights"].get("highest_reach"), "sentences": top_post},
        "highlights": highlights,
        "tiles": tiles,
        "next_month": next_month,
        "created_at": now_iso(),
    }
    texts = client_texts(document)
    numbers = number_checks(texts, plan["allowed_numbers"])
    document["missing"] = missing_parts(document, plan)
    document["checks"] = (
        numbers
        + cited_number_checks(texts, refs, plan["general_numbers"], plan["allowed_numbers"])
        + ratio_checks(texts)
        + wording_checks(texts, plan["has_earlier_months"])
        + reference_checks(texts)
        + partial_checks(client_texts(document, grouped=True))
        + ranking_checks(client_texts(document, grouped=True), refs)
        + order_checks(texts, plan["leaders"])
        + headline_checks(document, plan["tiles"])
        + highlight_checks(document, plan["highlights"])
        + length_checks(document)
        + split_checks(split)
    )
    # A number the data does not hold may be invented: the draft is not usable as it is.
    document["complete"] = not document["missing"] and not numbers
    status = "complete" if document["complete"] else "incomplete"
    write_json(output_dir / "report.json", document)
    write_text(output_dir / "report.md", to_markdown(plan, document))
    # The context and refs hold the month's data, which the input file already has.
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
        "sentences": {
            "headline": 1 if headline else 0,
            **{key: len(summary[key]) for key in PARAGRAPHS},
            "top_post": len(top_post),
        },
        "highlights": list(highlights),
        "tiles": list(tiles),
        "next_month": len(next_month),
        "dropped": len(dropped),
        "missing": document["missing"],
        "checks": document["checks"],
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
