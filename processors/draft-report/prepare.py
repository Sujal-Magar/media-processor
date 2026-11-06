#!/usr/bin/env python3
"""draft-report, step 1: read one month's report input and gather it into the material
draft.py sends: the totals with their change from last month, each platform, each post
with its month-end snapshot, the report engine's Top 3 highlights, the strategist's plan
for next month (when written), earlier months, the brand voice and, for posts made from
a video in input/, the topic tags and the opening hook earlier processors saved. Nothing
here costs money. Writes work/draft-report/<job>/plan.json and prints a JSON summary,
never the material.

The input stands in for what Pulse's analytics (C15) and report compilation (C17a)
give; its shape is fixtures/report-input.example.json.

    python3 processors/draft-report/prepare.py input/reports/2026-10.json [--force]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `lib`

from draft import INSTRUCTIONS, SCHEMA
from finalize import TILES

from lib.material import input_record, read_result
from lib.numbers import numbers_in
from lib.openai_api import estimate_text_tokens, report_model, setting
from lib.organisation import load_organisation, organisation_section
from lib.report_input import (
    COUNTS,
    METRICS,
    MONTH,
    RATES,
    SLOTS,
    fmt,
    is_video,
    language_name,
    month_name,
    month_of,
    plural,
    post_label,
    post_refs,
    read_month,
    signed,
    snapshot_text,
)
from lib.workspace import (
    INPUT,
    OUTPUT,
    fail,
    new_job_dir,
    now_iso,
    output_dir_for,
    previous_created_at,
    print_json,
    safe_name,
    sha256,
    write_json,
)

PROCESSOR = "draft-report"
# What a post can lead the month on, as the material names it.
LEADS = {
    "reach_count": "people reached",
    "views_count": "plays (videos only)",
    "likes_count": "likes",
    "comments_count": "comments",
    "shares_count": "shares",
    "saves_count": "saves",
    "true_engagement_rate": "engagement rate (the share of the people reached who liked, "
    "commented on, shared or saved)",
    "retention_3s_pct": "still watching after 3 s",
    "retention_10s_pct": "still watching after 10 s",
    "retention_complete_pct": "watched to the end",
}


# --- Earlier results for the posts' videos -------------------------------------------


def gather_materials(
    month: dict[str, Any], input_dir: Path = INPUT
) -> tuple[dict[str, dict[str, Any]], dict[str, Any], list[str]]:
    """Per post made from a video in input/: its topic tags and the hook it used. Returns
    them by content_item_id, what each result was (to notice a newer one), and warnings.
    Each file is hashed once."""
    refs = post_refs(month)
    digests: dict[str, str | None] = {}
    materials, records, warnings = {}, {}, []
    for post in month["posts"]:
        name = post["source_file"]
        if not name:
            continue
        ref = refs[post["content_item_id"]]
        path = input_dir / name
        if name not in digests:
            digests[name] = sha256(path) if path.is_file() else None
        if digests[name] is None:
            warnings.append(f"{ref}'s source_file {name} is not in input/; its topic tags and hook are left out.")
            continue
        topics = read_result(output_dir_for("tag-topics", path, digests[name]) / "topics.json")
        copy = read_result(output_dir_for("generate-copy", path, digests[name]) / "copy.json")
        hook = None
        if post["hook_used"]:
            hooks = (copy or {}).get("hooks") or []
            if post["hook_used"] <= len(hooks):
                chosen = hooks[post["hook_used"] - 1]
                hook = {"text": str(chosen.get("text") or ""), "style": chosen.get("style")}
            else:
                warnings.append(
                    f"{ref} used hook {post['hook_used']} of {name}, but its copy has "
                    f"{len(hooks)} hooks" + ("" if copy else " (no /generate-copy result)")
                    + "; the hook is left out."
                )
        if topics is None:
            warnings.append(f"No topic tags for {name} ({ref}); /tag-topics adds them.")
        materials[post["content_item_id"]] = {"topics": topics, "hook": hook}
        records[post["content_item_id"]] = {
            "source_file": name,
            "topics": input_record(topics),
            "copy": input_record(copy) if post["hook_used"] else None,
        }
    return materials, records, warnings


# --- Warnings about the data ---------------------------------------------------------


def expected_delta(total: dict[str, Any]) -> float | None:
    current, previous = total.get("current"), total.get("previous")
    if current is None or not previous:
        return None
    return (current - previous) / previous * 100


def data_warnings(month: dict[str, Any]) -> list[str]:
    """What the strategist should know before paying: incomplete snapshots, numbers that
    do not add up, and parts the draft leaves out."""
    refs = post_refs(month)
    warnings = []
    for post in month["posts"]:
        ref, snapshot = refs[post["content_item_id"]], post["snapshot"]
        if snapshot["data_quality_flag"] != "Full":
            warnings.append(
                f"{ref} ({post['platform']}, {post['published_at']}) has "
                f"{snapshot['data_quality_flag']} data; the draft must call its numbers "
                "incomplete."
            )
        if post["published_at"][:7] != month["month_period"]:
            warnings.append(f"{ref} was published on {post['published_at']}, outside {month['month_period']}.")
        parts = [snapshot[key] for key in ("likes_count", "comments_count", "shares_count", "saves_count")]
        reach, rate = snapshot["reach_count"], snapshot["true_engagement_rate"]
        if rate is not None and reach is not None and None not in parts:
            expected = sum(parts) / reach * 100 if reach else 0.0
            if abs(expected - rate) > 0.01:
                warnings.append(
                    f"{ref}'s true_engagement_rate is {rate}, but its counts give "
                    f"{expected:.2f} ((likes + comments + shares + saves) / reach x 100)."
                )
    totals = [(f"totals.{key}", total) for key, total in month["totals"].items()]
    totals += [
        (f"platforms.{name}.{key}", total)
        for name, entry in month["platforms"].items()
        for key, total in entry.items()
        if key != "posts"
    ]
    for where, total in totals:
        expected = expected_delta(total) if total else None
        if expected is not None and total["delta_pct"] is not None and abs(expected - total["delta_pct"]) > 0.01:
            warnings.append(f"{where}.delta_pct is {total['delta_pct']}, but its numbers give {expected:.2f}.")
    untracked = [METRICS[key].split(" (")[0].split(",")[0] for key in METRICS
                 if (month["totals"].get(key) or {}).get("current") is None]  # fmt: skip
    if untracked:
        warnings.append(f"Not tracked, so not written about: {', '.join(untracked)}.")
    for slot, chosen in month["highlights"].items():
        if chosen is None:
            warnings.append(f"No post was given for the {SLOTS[slot].lower()} highlight.")
    if not month["next_month_plan"]:
        warnings.append(
            "No next-month plan from the strategist: the draft leaves \"What we're doing "
            "next month\" empty for the strategist to write."
        )
    if not month["earlier_months"]:
        warnings.append(
            "No earlier months: the draft compares with last month only and calls nothing "
            "the best or worst so far."
        )
    return warnings


def other_reports(source: Path, output_dir: Path) -> list[str]:
    """Reports drafted for the same month from another version of the input."""
    folders = sorted(
        folder
        for folder in (OUTPUT / PROCESSOR).glob(f"{safe_name(source)}-*")
        if folder != output_dir and (folder / "report.json").is_file()
    )
    return [
        f"A report for this month was drafted from another version of {source.name}: "
        f"{folder.relative_to(OUTPUT.parent)}."
        for folder in folders
    ]


# --- The material sent ---------------------------------------------------------------


def difference(total: dict[str, Any]) -> float | None:
    """This month's number minus last month's, when the change is shown."""
    if total["delta_pct"] is None or total["current"] is None or total["previous"] is None:
        return None
    return round(total["current"] - total["previous"], 2)


def total_text(key: str, total: dict[str, Any], previous_name: str) -> str:
    unit = "%" if key == "engagement_rate" else ""
    parts = [f"{fmt(total['current'])}{unit}"]
    if total["previous"] is None:
        parts.append(f"no number for {previous_name}")
    else:
        parts.append(f"{previous_name}: {fmt(total['previous'])}{unit}")
        if total["delta_pct"] is None:
            parts.append("change not shown (held back: incomplete data)")
        else:
            parts.append(f"change {signed(total['delta_pct'])}%")
            gap = difference(total)
            parts.append(f"difference {signed(gap)}" + (f" point{'' if abs(gap) == 1 else 's'}" if unit else ""))
    if total["footnote"]:
        parts.append(f"note: {total['footnote']}")
    return "; ".join(parts)


def counts_text(month: dict[str, Any]) -> str:
    posts = month["posts"]
    platforms = Counter(post["platform"] for post in posts)
    pillars = Counter(post["content_pillar"] for post in posts if post["content_pillar"])
    languages = Counter(language_name(post["language"]) for post in posts if post["language"])
    line = f"Posts this month: {len(posts)} (" + ", ".join(f"{p} {n}" for p, n in platforms.items()) + ")"
    if pillars:
        line += "; by pillar: " + ", ".join(f"{p} {n}" for p, n in pillars.items())
    if languages:
        line += "; by language: " + ", ".join(f"{p} {n}" for p, n in languages.items())
    return line


def leaders(month: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Per measure, the posts with complete data that have the most and the fewest
    (ties kept), so no ranking is left to the model. A measure fewer than two such
    posts have is left out: there is nothing to rank."""
    ids = post_refs(month)
    found = {}
    for key, label in LEADS.items():
        values = {
            ids[post["content_item_id"]]: post["snapshot"][key]
            for post in month["posts"]
            if post["snapshot"]["data_quality_flag"] == "Full"
            and post["snapshot"][key] is not None
            and (key != "views_count" or is_video(post))
        }
        if len(values) < 2:
            continue
        top, bottom = max(values.values()), min(values.values())
        found[key] = {
            "label": label,
            "most": [ref for ref, value in values.items() if value == top],
            "fewest": [ref for ref, value in values.items() if value == bottom],
            "values": values,
        }
    return found


def leaders_section(month: dict[str, Any], incomplete: list[str]) -> str:
    unit = {key: "%" for key in LEADS if key.endswith(("_rate", "_pct"))}
    lines = ["LEADERS AMONG POSTS WITH COMPLETE DATA (worked out from the snapshots: every "
             "ranking of posts, such as the most shares or the fewest people reached, must "
             "agree with this; never rank posts any other way)"]  # fmt: skip
    if incomplete:
        lines[0] += f"; left out because their data is incomplete: {', '.join(incomplete)}"
    found = leaders(month)
    for key, lead in found.items():
        show = lambda refs: ", ".join(f"{ref} ({fmt(lead['values'][ref])}{unit.get(key, '')})" for ref in refs)  # noqa: E731
        lines.append(f"- {lead['label']}: most {show(lead['most'])}; fewest {show(lead['fewest'])}")
    if not found:
        lines.append("- fewer than two posts have complete data: rank no posts")
    return "\n".join(lines)


def build_context(
    month: dict[str, Any],
    materials: dict[str, dict[str, Any]],
    organisation: dict[str, Any] | None,
) -> tuple[str, dict[str, dict[str, Any]], list[float], list[float]]:
    """The material sent; the references finalize maps sentences to, each with its own
    numbers; every number the draft may show (each in the material, so the model can
    only reword them); and the numbers that belong to no reference (years, post counts,
    the brand's text), which any sentence may use."""
    period, previous = month["month_period"], month["previous_month"]
    names = {"name": month_name(period), "previous": month_name(previous),
             "next": month_name(month_of(period, 1))}  # fmt: skip
    refs: dict[str, dict[str, Any]] = {}
    general: list[float] = [int(p[:4]) for p in (period, previous, month_of(period, 1))]

    def keep(ref: str | None, *values: Any) -> None:
        """Numbers of a reference (or of none), and those in text given as a string."""
        found = []
        for value in values:
            if isinstance(value, str):
                found.extend(number for _, number, _ in numbers_in(value))
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                found.append(float(value))
        (refs[ref].setdefault("numbers", []) if ref else general).extend(found)

    header = [
        "REPORT",
        f"Month: {names['name']} ({period}), compared with {names['previous']} ({previous}); "
        f"next month: {names['next']}",
        counts_text(month),
    ]
    posts = month["posts"]
    keep(None, len(posts), *Counter(p["platform"] for p in posts).values(),
         *Counter(p["content_pillar"] for p in posts if p["content_pillar"]).values(),
         *Counter(p["language"] for p in posts if p["language"]).values())  # fmt: skip

    totals = ["TOTALS FOR THE MONTH (from recorded snapshots; write nothing about a metric "
              "that is not tracked)"]  # fmt: skip
    for key, label in METRICS.items():
        total = month["totals"].get(key)
        if not total or total["current"] is None:
            totals.append(f"- {label}: not tracked")
            continue
        line = total_text(key, total, names["previous"])
        totals.append(f"[M:{key}] {label}: {line}")
        refs[f"M:{key}"] = {"source": "metric", "metric": key, "label": f"{label.split(' (')[0]}: {line}"}
        keep(f"M:{key}", total["current"], total["previous"], total["delta_pct"],
             difference(total), total["footnote"])  # fmt: skip
    sections = ["\n".join(header), "\n".join(totals)]

    if month["platforms"]:
        lines = ["BY PLATFORM"]
        for name, entry in month["platforms"].items():
            ref = f"PL:{name}"
            refs[ref] = {"source": "platform", "platform": name}
            parts = [plural(entry["posts"], "post")] if entry["posts"] is not None else []
            keep(ref, entry["posts"])
            for key, total in entry.items():
                if key != "posts" and total and total["current"] is not None:
                    parts.append(f"{METRICS[key].split(' (')[0]} {total_text(key, total, names['previous'])}")
                    keep(ref, total["current"], total["previous"], total["delta_pct"],
                         difference(total), total["footnote"])  # fmt: skip
            lines.append(f"[{ref}] " + "; ".join(parts))
            refs[ref]["label"] = f"{name}: " + "; ".join(parts)
        sections.append("\n".join(lines))

    ids = post_refs(month)
    incomplete = [ids[p["content_item_id"]] for p in posts if p["snapshot"]["data_quality_flag"] != "Full"]
    first_post: dict[str, str] = {}  # source file -> the first post made from it
    lines = ["POSTS (each with its month-end snapshot)"]
    for post in posts:
        ref, snapshot = ids[post["content_item_id"]], post["snapshot"]
        refs[ref] = {
            "source": "post",
            "content_item_id": post["content_item_id"],
            "platform": post["platform"],
            "data_quality_flag": snapshot["data_quality_flag"],
            "label": f"{post_label(post)}; {snapshot_text(post)}",
        }
        label = post_label(post)
        if snapshot["data_quality_flag"] != "Full":
            label += " (some numbers are missing or late: call them incomplete; never rank or compare on them)"
        block = [f"[{ref}] {label}", f"  {snapshot_text(post)}"]
        keep(ref, *(snapshot[key] for key in (*COUNTS, *RATES)))
        if post["source_file"] in first_post:
            block.append(f"  same video as {first_post[post['source_file']]}, posted again on "
                         f"{post['platform']}: one video, not two")  # fmt: skip
        elif post["source_file"]:
            first_post[post["source_file"]] = ref
        if post["title"]:
            block.append(f"  title (may name a person: never repeat a name): {post['title']}")
            keep(ref, post["title"])
        material = materials.get(post["content_item_id"]) or {}
        topics = material.get("topics")
        if topics:
            tags = "; ".join(f"{category} {', '.join(topics[category])}"
                             for category in ("type", "topic", "entity") if topics.get(category))  # fmt: skip
            block.append(f"  topic tags (made by a model from the video; themes, not facts): {tags}")
            keep(ref, tags)
            if topics.get("summary"):
                block.append(f"  what the video is about: {topics['summary']}")
                keep(ref, topics["summary"])
        if hook := material.get("hook"):
            block.append(f"  opening hook used ({hook['style'] or 'unknown style'}): \"{hook['text']}\"")
            keep(ref, hook["text"])
        lines.append("\n".join(block))
    sections.append("\n".join(lines))
    sections.append(leaders_section(month, incomplete))

    lines = ["HIGHLIGHTS (chosen by the report engine; the top post of the month is the "
             "highest-reach one)"]  # fmt: skip
    if incomplete:
        lines[0] += (f"; chosen while the numbers of {', '.join(incomplete)} are incomplete, "
                     "so a highlight line that ranks posts says it leaves them out")  # fmt: skip
    for slot, chosen in month["highlights"].items():
        lines.append(f"- {slot}: {ids[chosen] if chosen else 'none'}")
    sections.append("\n".join(lines))

    if month["next_month_plan"]:
        lines = [f"STRATEGIST'S PLAN FOR {names['next'].upper()} (written by the strategist: "
                 "reword each item for the client; never add, drop or change one)"]  # fmt: skip
        for number, item in enumerate(month["next_month_plan"], 1):
            lines.append(f"[N{number}] {item}")
            refs[f"N{number}"] = {"source": "plan", "text": item, "label": item}
            keep(f"N{number}", item)
    else:
        lines = [f"STRATEGIST'S PLAN FOR {names['next'].upper()}: not written yet. Leave "
                 "next_month empty; the strategist writes it."]  # fmt: skip
    sections.append("\n".join(lines))

    if month["earlier_months"]:
        lines = ["EARLIER MONTHS (for comparisons beyond last month)"]
        for entry in month["earlier_months"]:
            values = [f"{METRICS[key].split(' (')[0].split(',')[0]} {fmt(entry[key])}"
                      for key in METRICS if entry.get(key) is not None]  # fmt: skip
            lines.append(f"- {month_name(entry['month_period'])}: " + "; ".join(values))
            for key in METRICS:
                # An earlier month's number belongs to its total; to none if it is not tracked now.
                keep(f"M:{key}" if f"M:{key}" in refs else None, entry.get(key))
    else:
        lines = ["EARLIER MONTHS: none given. Compare with last month only; never call this "
                 "month the best, strongest or worst, or say ever, yet or so far."]  # fmt: skip
    sections.append("\n".join(lines))

    brand = month["brand"]
    if any(brand.values()) or month["audience"]:
        lines = ["BRAND VOICE (from the organisation's brand guidelines)"]
        if brand["voice_pillars"]:
            lines.append(f"Voice: {', '.join(brand['voice_pillars'])}")
        if brand["tone_rules"]:
            lines.append(f"Tone: {brand['tone_rules']}")
        lines.extend(f"Rule: {item}" for item in brand["do_nots"])
        if month["audience"]:
            lines.append(f"Audience: {'; '.join(month['audience'])}")
        sections.append("\n".join(lines))
        keep(None, *brand["voice_pillars"], brand["tone_rules"], *brand["do_nots"], *month["audience"])
    if section := organisation_section(organisation):
        sections.append(section)
        keep(None, section)

    for item in refs.values():
        item["numbers"] = sorted(set(item.get("numbers", [])))
    general = sorted(set(general))
    allowed = sorted({*general, *(value for item in refs.values() for value in item["numbers"])})
    return "\n\n".join(sections), refs, allowed, general


# --- Running it ----------------------------------------------------------------------


def ready_summary(
    month: dict[str, Any],
    materials: dict[str, dict[str, Any]],
    organisation: dict[str, Any] | None,
    options: dict[str, Any],
    estimated_tokens: int,
    replaces: str | None,
    warnings: list[str],
) -> list[str]:
    """What the user sees before approving the paid step, every line every time."""
    ids = post_refs(month)
    linked = [post for post in month["posts"] if post["source_file"]]
    partial = [f"{ids[p['content_item_id']]} ({p['platform']}, {p['snapshot']['data_quality_flag']})"
               for p in month["posts"] if p["snapshot"]["data_quality_flag"] != "Full"]  # fmt: skip
    chosen = [f"{SLOTS[slot].lower()} {ids[ref]}" for slot, ref in month["highlights"].items() if ref]
    plan = month["next_month_plan"]
    return [
        f"Month: {month_name(month['month_period'])}, compared with "
        f"{month_name(month['previous_month'])}",
        f"Posts: {len(month['posts'])}; made from a video in input/: {len(linked)} (topic "
        f"tags for {sum(1 for m in materials.values() if m['topics'])}, hook used for "
        f"{sum(1 for m in materials.values() if m['hook'])})",
        "Incomplete data: " + (", ".join(partial) if partial else "none (all posts Full)"),
        "Highlights: " + (", ".join(chosen) if chosen else "none"),
        "Next-month plan: "
        + (f"{len(plan)} items from the strategist" if plan else "none (the list stays empty)"),
        f"Earlier months: {len(month['earlier_months']) or 'none'}",
        "Organisation: " + (organisation["name"] if organisation else "none (no organisation.json)"),
        f"Cost: one paid OpenAI request to {options['model']} at "
        f"{options['reasoning_effort']} effort, about {estimated_tokens:,} input tokens "
        "(rough; reasoning adds output tokens)",
        "Replaces: "
        + (f"the result made at {replaces}, which moves to history/" if replaces else "nothing"),
        "Warnings: " + (" | ".join(warnings) if warnings else "none"),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help="the month's report input (JSON)")
    parser.add_argument("--force", action="store_true", help="draft again even if done")
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    if not source.is_file():
        fail(f"file not found: {args.source}")
    month = read_month(source)

    digest = sha256(source)
    output_dir = output_dir_for(PROCESSOR, source, digest)
    organisation = load_organisation()
    materials, records, material_warnings = gather_materials(month)
    inputs = {"posts": records, "organisation": organisation}
    previous = output_dir / "report.json"
    done = read_result(previous)
    if done is not None and not args.force:
        status = "already_done" if done.get("inputs") == inputs else "outdated"
        messages = {
            "already_done": "This month's draft for this input is up to date. Use --force "
            "to pay again.",
            "outdated": "The topic tags or copy of a post's video were made again (or "
            "added), or organisation.json changed, since this draft was. Use --force to "
            "draft it again (charged again).",
        }
        print_json({"status": status, "output_dir": str(output_dir), "message": messages[status]})
        return
    # --force: finalize moves the result it replaces into history/ (see archive_previous).
    replaces = previous_created_at(previous)

    context, refs, allowed, general = build_context(month, materials, organisation)
    warnings = data_warnings(month) + material_warnings + other_reports(source, output_dir)
    if organisation is None:
        warnings.append(
            "No organisation.json: the organisation's name is not given, so the draft "
            "avoids it. Copy organisation.example.json to organisation.json and fill it in."
        )
    if MONTH.fullmatch(source.stem) and source.stem != month["month_period"]:
        warnings.append(f"The file is named {source.name} but holds {month['month_period']}.")
    model = report_model()
    effort = setting("OPENAI_REPORT_REASONING_EFFORT", "low") or "low"
    options = {"model": model, "reasoning_effort": effort}
    period = month["month_period"]
    job_dir = new_job_dir(PROCESSOR, source)
    plan = {
        "version": 1,
        "processor": PROCESSOR,
        "status": "ready",
        "source": {"name": source.name, "path": str(source), "sha256": digest},
        "month": {
            "period": period,
            "previous": month["previous_month"],
            "next": month_of(period, 1),
            "name": month_name(period),
            "previous_name": month_name(month["previous_month"]),
            "next_name": month_name(month_of(period, 1)),
        },
        "inputs": inputs,
        "organisation": organisation,
        "options": options,
        "highlights": {slot: post_refs(month).get(chosen) for slot, chosen in month["highlights"].items()},
        "tiles": {key: month["totals"][key] for key in TILES
                  if (month["totals"].get(key) or {}).get("current") is not None},  # fmt: skip
        "has_earlier_months": bool(month["earlier_months"]),
        # Who leads each measure among posts with complete data, to check rankings.
        "leaders": {key: {k: v for k, v in lead.items() if k != "values"}
                    for key, lead in leaders(month).items()},  # fmt: skip
        "refs": refs,
        "allowed_numbers": allowed,
        "general_numbers": general,
        "context": context,
        "estimated_input_tokens": estimate_text_tokens(INSTRUCTIONS + json.dumps(SCHEMA) + context),
        "warnings": warnings,
        "output_dir": str(output_dir),
        "replaces": replaces,
        "created_at": now_iso(),
    }
    write_json(job_dir / "plan.json", plan)
    summary = ready_summary(
        month, materials, organisation, options, plan["estimated_input_tokens"], replaces, warnings
    )
    print_json(
        {
            "status": "ready",
            "job_dir": str(job_dir),
            "month": period,
            "posts": len(month["posts"]),
            "organisation": organisation["name"] if organisation else None,
            "paid_requests": 1,
            "model": model,
            "reasoning_effort": effort,
            "estimated_input_tokens": plan["estimated_input_tokens"],
            "replaces": replaces,
            "warnings": warnings,
            "summary": summary,
            # The same lines as one block, for the skill to show unchanged.
            "summary_text": "\n".join(f"- {line}" for line in summary),
        }
    )


if __name__ == "__main__":
    main()
