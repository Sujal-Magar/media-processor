#!/usr/bin/env python3
"""draft-insights, step 1: read one month's triggers from the anomaly rules and gather the
material draft.py sends: each trigger re-checked against the month's snapshots with its
size worked out (10.23% is 2.2× the 90-day average), the posts with complete data in the
baseline window, comparisons between groups of them (pillar, platform, language, hook
style, what the pictures show) and, for posts made from a video in input/, the topic
tags, hook, call to action and visual tags earlier processors saved. A trigger on a post
whose data is Partial or Stale is held back, and the post is left out of everything.
Nothing here costs money; with no trigger left to send it stops without a job. Writes
work/draft-insights/<job>/plan.json and prints a JSON summary, never the material.

The trigger file stands in for Pulse's anomaly rules (C18a); its shape is
fixtures/insights-input.example.json. The posts come from the report inputs in
input/reports/ (C15/C17a, as for draft-report) whose months the baseline window covers.

    python3 processors/draft-insights/prepare.py input/insights/2026-10.json [--force]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `lib`

from draft import INSTRUCTIONS, schema
from finalize import MAX_INSIGHTS, MAX_QUANTITY, POST_RULES, RULES

from lib.material import input_record, read_result, visual_labels
from lib.numbers import numbers_in
from lib.openai_api import estimate_text_tokens, insight_model, setting
from lib.organisation import load_organisation, organisation_section
from lib.report_input import (
    MONTH,
    fmt,
    is_video,
    language_name,
    month_name,
    month_of,
    plural,
    post_label,
    read_month,
    snapshot_text,
)
from lib.workspace import (
    INPUT,
    fail,
    new_job_dir,
    now_iso,
    output_dir_for,
    previous_created_at,
    print_json,
    sha256,
    write_json,
)

PROCESSOR = "draft-insights"
REPORTS = INPUT / "reports"
# The rules' numbers (DFD_05 §5.5); a drop-off is 100 minus the share still watching
# after 3 seconds.
OUTLIER_TIMES = 2.0
DROPOFF_PCT = 45.0
POSTS_BEHIND = 2
MAX_TRIGGERS = 10
# What a group of posts is compared on, with its unit.
MEASURES = {
    "true_engagement_rate": ("engagement rate", "%"),
    "reach_count": ("people reached", ""),
    "retention_3s_pct": ("still watching after 3 s", "%"),
    "retention_10s_pct": ("still watching after 10 s", "%"),
}
RULE_MEASURES = {
    "engagement_gt_200pct_mean": ("true_engagement_rate", "reach_count"),
    "hook_dropoff_gt_45pct": ("retention_3s_pct", "retention_10s_pct"),
    "pace_behind_quota": ("true_engagement_rate", "reach_count"),
}
# How a group and the posts it is compared with are named, per attribute. Hook style and
# visual tags are known only for posts made from a video, so those groups are compared
# with other videos.
GROUPS = {
    "pillar": ("{} posts", "posts in other pillars"),
    "platform": ("{} posts", "posts on other platforms"),
    "language": ("posts in {}", "posts in other languages"),
    "format": ("{} posts", "posts in the other format"),
    "hook": ("videos opening with a {} hook", "videos with another hook style"),
    "visual": ("videos showing {}", "videos without it"),
}
MIN_GROUP = 2  # different pieces of content with the measure on each side
MIN_DIFFERENCE_PCT = 10  # a smaller gap between groups this small says nothing
MAX_COMPARISONS = 8  # per trigger
MAX_VISUAL_TAGS = 12
PLATFORM_NAMES = {"instagram": "Instagram", "tiktok": "TikTok", "linkedin": "LinkedIn", "youtube": "YouTube"}
# Visual tags on screen equally long are shown in this order of category, so a one-shot
# video's activity (speaking-to-camera) comes before its furniture (F-050).
CATEGORY_ORDER = {"activity": 0, "scene": 1, "attribute": 2, "object": 3}
# generate-copy's caption formats per report platform.
CAPTION_PLATFORMS = {
    "instagram": "instagram-reels",
    "tiktok": "tiktok",
    "linkedin": "linkedin",
    "youtube": "youtube-shorts",
}


# --- Reading the triggers ------------------------------------------------------------


def whole(value: Any, where: str, least: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < least:
        fail(f"{where} must be a whole number of {least} or more")
    return value


def amount(value: Any, where: str, required: bool = True) -> float | None:
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        fail(f"{where} must be a number of 0 or more" + ("" if required else " or null"))
    return value


def day(value: Any, where: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        fail(f"{where} must be a date such as 2026-08-03")


def read_triggers(path: Path) -> dict[str, Any]:
    """The anomaly rules' output for one month, checked against the documented shape;
    stops at the first problem with where it is."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        fail(f"{path.name} is not valid JSON: {exc}")
    if not isinstance(data, dict):
        fail(f"{path.name} must hold one JSON object")
    period = data.get("month_period")
    if not isinstance(period, str) or not MONTH.fullmatch(period):
        fail("month_period must be a month such as 2026-10")

    baseline = data.get("baseline")
    if not isinstance(baseline, dict):
        fail("baseline must be an object (the tenant's 90-day baseline)")
    start = day(baseline.get("window_start"), "baseline.window_start")
    end = day(baseline.get("window_end"), "baseline.window_end")
    days = whole(baseline.get("window_days"), "baseline.window_days", 1)
    if (end - start).days + 1 != days:
        fail(f"baseline.window_days is {days}, but {start} to {end} is {(end - start).days + 1} days")
    if end.isoformat()[:7] != period:
        fail(f"baseline.window_end must fall in {period}")
    mean = amount(baseline.get("engagement_rate_mean"), "baseline.engagement_rate_mean")
    if not mean:
        fail("baseline.engagement_rate_mean must be above 0")

    quota = data.get("quota")
    if not isinstance(quota, dict):
        fail("quota must be an object with monthly_posts and published")

    raw = data.get("triggers")
    if not isinstance(raw, list) or len(raw) > MAX_TRIGGERS:
        fail(f"triggers must be a list of at most {MAX_TRIGGERS}")
    triggers, seen = [], set()
    for n, item in enumerate(raw):
        where = f"triggers[{n}]"
        if not isinstance(item, dict) or item.get("trigger_rule_id") not in RULES:
            fail(f"{where}.trigger_rule_id must be one of {', '.join(RULES)}")
        rule, post = item["trigger_rule_id"], item.get("content_item_id")
        if rule in POST_RULES and (not isinstance(post, str) or not post.strip()):
            fail(f"{where}.content_item_id must name the post {rule} fired on")
        if rule not in POST_RULES and post is not None:
            fail(f"{where}.content_item_id must be null: {rule} is about the month")
        if (rule, post) in seen:
            fail(f"{where} repeats {rule}" + (f" on {post}" if post else ""))
        seen.add((rule, post))
        triggers.append({"rule": rule, "content_item_id": post})
    return {
        "month_period": period,
        "evaluated_at": data.get("evaluated_at"),
        "baseline": {
            "window_days": days,
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "posts": whole(baseline.get("posts"), "baseline.posts"),
            "engagement_rate_mean": mean,
            "engagement_rate_sd": amount(baseline.get("engagement_rate_sd"), "baseline.engagement_rate_sd", False),
            "retention_3s_mean": amount(baseline.get("retention_3s_mean"), "baseline.retention_3s_mean", False),
        },
        "quota": {
            "monthly_posts": whole(quota.get("monthly_posts"), "quota.monthly_posts", 1),
            "published": whole(quota.get("published"), "quota.published"),
        },
        "triggers": triggers,
    }


def read_report(path: Path) -> dict[str, Any]:
    try:
        return read_month(path)
    except SystemExit:
        fail(f"{path.name} does not fit the report input shape (the error above says where)")


def load_window(
    triggers: dict[str, Any], reports_dir: Path = REPORTS
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    """The month's report input, every post published in the baseline window (from the
    report inputs of the months it covers, oldest first) and each file's SHA-256."""
    period, baseline = triggers["month_period"], triggers["baseline"]
    own = reports_dir / f"{period}.json"
    if not own.is_file():
        fail(f"no report input for {period}: {own} is missing (the month's posts come from it)")
    first, last = baseline["window_start"], baseline["window_end"]
    months, current = set(), first[:7]
    while current <= last[:7]:
        months.add(current)
        current = month_of(current, 1)
    month, posts, files = None, {}, {}
    for path in sorted(reports_dir.glob("*.json")):
        if path.stem not in months:
            continue
        report = read_report(path)
        files[path.name] = sha256(path)
        if path.stem == period:
            month = report
        for post in report["posts"]:
            if first <= post["published_at"] <= last:
                posts.setdefault(post["content_item_id"], post)
    assert month is not None  # its file exists and its month is in the window
    return month, sorted(posts.values(), key=lambda p: (p["published_at"], p["content_item_id"])), files


def full(post: dict[str, Any]) -> bool:
    return post["snapshot"]["data_quality_flag"] == "Full"


def check_triggers(
    triggers: dict[str, Any], month: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(sent, held back). Each trigger must hold on the month's snapshots, or prepare
    stops: the rules' output and the numbers disagree. One on a post with incomplete data,
    and any beyond MAX_INSIGHTS, is held back."""
    by_id = {post["content_item_id"]: post for post in month["posts"]}
    mean = triggers["baseline"]["engagement_rate_mean"]
    quota = triggers["quota"]
    sent, held = [], []
    for n, trigger in enumerate(triggers["triggers"]):
        where, rule, item = f"triggers[{n}]", trigger["rule"], trigger["content_item_id"]
        entry: dict[str, Any] = {"rule": rule, "content_item_id": item}
        if rule in POST_RULES:
            post = by_id.get(item)
            if post is None:
                fail(f"{where}.content_item_id {item!r} is not a post in the month's report input")
            snapshot = post["snapshot"]
            label = f"{RULES[rule]}, on the {post['platform']} post of {post['published_at']}"
            if not full(post):
                held.append({**entry, "label": label, "reason": f"its data is {snapshot['data_quality_flag']}, so "
                             "it is not sent and the post is left out of every comparison"})  # fmt: skip
                continue
            kind = " ".join(filter(None, [language_name(post["language"]), PLATFORM_NAMES[post["platform"]],
                                          "video" if is_video(post) else "post"]))  # fmt: skip
            if rule == "engagement_gt_200pct_mean":
                value = snapshot["true_engagement_rate"]
                if value is None or value <= OUTLIER_TIMES * mean:
                    fail(f"{where}: {item}'s engagement rate is {value}, not above 2 × the "
                         f"90-day average of {fmt(mean)}")  # fmt: skip
                times = round(value / mean, 1)
                entry.update(value=value, times=times, threshold=round(OUTLIER_TIMES * mean, 2), bar=mean,
                             card=f"A bigger share of the people who saw your {kind} liked, commented on, "
                                  f"shared or saved it: {fmt(times)}× your usual.")  # fmt: skip
            else:
                value = snapshot["retention_3s_pct"]
                if value is None or 100 - value <= DROPOFF_PCT:
                    fail(f"{where}: {item} kept {value}% watching after 3 s, so no more than "
                         f"{fmt(DROPOFF_PCT)}% stopped watching")  # fmt: skip
                dropoff = round(100 - value, 2)
                average = triggers["baseline"]["retention_3s_mean"]
                entry.update(value=value, dropoff=dropoff, bar=average if average is not None else 100 - DROPOFF_PCT,
                             card=f"{fmt(dropoff)}% of the people who started watching your {kind} "
                                  "stopped in the first 3 seconds.")  # fmt: skip
        else:
            label = RULES[rule]
            behind = quota["monthly_posts"] - quota["published"]
            if behind < POSTS_BEHIND:
                fail(f"{where}: {quota['published']} of {quota['monthly_posts']} posts is not "
                     f"{POSTS_BEHIND} or more behind the quota")  # fmt: skip
            month = month_name(triggers["month_period"]).split()[0]
            # The request toward the gap is sized by code, not the model (F-049).
            entry.update(behind=behind, quantity=min(MAX_QUANTITY, behind),
                         card=f"We posted {quota['published']} of the {quota['monthly_posts']} posts "
                              f"planned for {month}.")  # fmt: skip
        if len(sent) == MAX_INSIGHTS:
            held.append({"rule": rule, "content_item_id": item, "label": label,
                         "reason": f"over the limit of {MAX_INSIGHTS} insights a month"})  # fmt: skip
            continue
        sent.append(entry)
    return sent, held


def rule_warnings(
    triggers: dict[str, Any], month: dict[str, Any], window: list[dict[str, Any]]
) -> list[str]:
    """Where the rules' output and the numbers it stands on do not line up."""
    mean = triggers["baseline"]["engagement_rate_mean"]
    fired = {(t["rule"], t["content_item_id"]) for t in triggers["triggers"]}
    warnings = []
    for post in filter(full, month["posts"]):
        snapshot, item = post["snapshot"], post["content_item_id"]
        rate, kept = snapshot["true_engagement_rate"], snapshot["retention_3s_pct"]
        if rate is not None and rate > OUTLIER_TIMES * mean and ("engagement_gt_200pct_mean", item) not in fired:
            warnings.append(f"{item} has an engagement rate above 2 × the average, but no trigger.")
        if kept is not None and 100 - kept > DROPOFF_PCT and ("hook_dropoff_gt_45pct", item) not in fired:
            warnings.append(f"{item} lost more than {fmt(DROPOFF_PCT)}% of viewers in 3 s, but has no trigger.")
    quota = triggers["quota"]
    if quota["monthly_posts"] - quota["published"] >= POSTS_BEHIND and ("pace_behind_quota", None) not in fired:
        warnings.append("The month is behind the quota, but has no pace trigger.")
    if quota["published"] != len(month["posts"]):
        warnings.append(
            f"quota.published is {quota['published']}, but the month's report input has "
            f"{plural(len(month['posts']), 'post')} (Pulse has not agreed whether the quota "
            "counts content items or platform posts)."
        )
    if triggers["baseline"]["posts"] != len(window):
        warnings.append(
            f"The baseline counts {plural(triggers['baseline']['posts'], 'post')} in the window; "
            f"input/reports/ holds {len(window)} of them, so comparisons use only those."
        )
    return warnings


# --- Earlier results for the posts' videos -------------------------------------------


def gather_materials(
    posts: list[dict[str, Any]],
    refs: dict[str, str],
    input_dir: Path = INPUT,
    organisation: dict[str, Any] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any], list[str]]:
    """Per post made from a video in input/: its topic tags, the hook and call to action
    it used, and its most-seen visual tags. Returns them by content_item_id, what each
    result was (to notice a newer one), and warnings. Each file is hashed once."""
    digests: dict[str, str | None] = {}
    materials, records, warnings = {}, {}, []
    for post in posts:
        name = post["source_file"]
        if not name:
            continue
        ref = refs[post["content_item_id"]]
        path = input_dir / name
        if name not in digests:
            digests[name] = sha256(path) if path.is_file() else None
        if digests[name] is None:
            warnings.append(f"{ref}'s source_file {name} is not in input/; what the video shows is left out.")
            continue
        topics = read_result(output_dir_for("tag-topics", path, digests[name]) / "topics.json")
        copy = read_result(output_dir_for("generate-copy", path, digests[name]) / "copy.json")
        tags = read_result(output_dir_for("tag-visuals", path, digests[name]) / "tags.json")
        hook = action = None
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
            wanted = CAPTION_PLATFORMS[post["platform"]]
            captions = [c for c in (copy or {}).get("captions") or [] if c.get("platform") == wanted]
            action = str(captions[0].get("call_to_action") or "") or None if captions else None
        if topics is None:
            warnings.append(f"No topic tags for {name}; /tag-topics adds them.")
        else:
            # Made from an older transcript, older visual tags or another organisation.json,
            # as tag-topics itself would call it outdated (F-056).
            transcript = read_result(output_dir_for("transcribe", path, digests[name]) / "transcript.json")
            now = {"transcript": input_record(transcript), "tags": input_record(tags), "organisation": organisation}
            if topics.get("inputs") not in (None, now):
                warnings.append(f"The topic tags of {name} are outdated; /tag-topics with force re-makes them (charged).")
        if tags is None:
            warnings.append(f"No visual tags for {name}; /tag-visuals adds them.")
        # Every tag groups the post; the model reads the ones on screen longest. Tags tie on
        # frames in a one-shot video and are then sorted by label, so cutting that list
        # would drop a tag the whole video shows (F-036).
        labels = visual_labels(tags) if tags else []
        shown = [label for label, _, _ in sorted(labels, key=lambda tag: (-(tag[2] or 0), CATEGORY_ORDER.get(tag[1], 4)))]
        materials[post["content_item_id"]] = {
            "topics": topics, "hook": hook, "action": action,
            "visual": [label for label, _, _ in labels], "visual_shown": shown[:MAX_VISUAL_TAGS],
        }  # fmt: skip
        records[post["content_item_id"]] = {
            "source_file": name,
            "topics": input_record(topics),
            "copy": input_record(copy) if post["hook_used"] else None,
            "visual": input_record(tags),
        }
    return materials, records, list(dict.fromkeys(warnings))


# --- Comparisons ---------------------------------------------------------------------


def attributes(post: dict[str, Any], material: dict[str, Any] | None) -> dict[str, set[str]]:
    """What a post can be grouped by; hook style and visual tags only for videos with a
    saved result."""
    found = {"platform": {post["platform"]}, "format": {"video" if is_video(post) else "picture"}}
    if post["content_pillar"]:
        found["pillar"] = {post["content_pillar"]}
    if post["language"]:
        found["language"] = {post["language"]}
    if material and material["hook"] and material["hook"]["style"]:
        found["hook"] = {material["hook"]["style"]}
    if material and material["visual"]:
        found["visual"] = set(material["visual"])
    return found


def content(post: dict[str, Any]) -> str:
    """What a post was made from: a video posted on two platforms is one piece of content
    in two posts."""
    return post["source_file"] or post["content_item_id"]


def average(values: list[float], key: str) -> float:
    mean = sum(values) / len(values)
    return round(mean) if key == "reach_count" else round(mean, 2)


def comparisons(
    posts: list[dict[str, Any]],
    materials: dict[str, dict[str, Any]],
    sent: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Per trigger, groups of posts with complete data against the rest, on the measures
    the trigger is about, when each side has at least MIN_GROUP different pieces of
    content with that measure (a video posted twice is one). For a trigger on a post, the
    groups are those the post belongs to, worked out without the post and the same video
    posted again, so a post never explains itself (F-051); for the pace trigger, groups
    doing better than the rest. The largest differences first, at most MAX_COMPARISONS
    per trigger."""
    attrs = {p["content_item_id"]: attributes(p, materials.get(p["content_item_id"])) for p in posts}
    by_id = {p["content_item_id"]: p for p in posts}
    found = []
    for n, trigger in enumerate(sent):
        flagged = trigger["content_item_id"]
        own = content(by_id[flagged]) if flagged else None
        pool = [p for p in posts if content(p) != own]
        items = merged(sorted(groups_for(pool, attrs, n, trigger, attrs.get(flagged)),
                              key=lambda c: -abs(c["difference_pct"])))[:MAX_COMPARISONS]  # fmt: skip
        for item in items:
            item["without"] = [p["content_item_id"] for p in posts if own and content(p) == own]
        found += items
    return found


def groups_for(
    pool: list[dict[str, Any]],
    attrs: dict[str, dict[str, set[str]]],
    n: int,
    trigger: dict[str, Any],
    flagged: dict[str, set[str]] | None,
) -> list[dict[str, Any]]:
    """The comparisons for one trigger among the posts in `pool`: groups holding what the
    flagged post is (its pillar, platform, ...), or for the pace trigger any group doing
    better than the rest."""
    found = []
    for kind, (group_name, rest_name) in GROUPS.items():
        universe = [p for p in pool if kind in attrs[p["content_item_id"]]]
        for value in sorted({v for p in universe for v in attrs[p["content_item_id"]][kind]}):
            if flagged is not None and value not in flagged.get(kind, set()):
                continue
            group = [p for p in universe if value in attrs[p["content_item_id"]][kind]]
            rest = [p for p in universe if value not in attrs[p["content_item_id"]][kind]]
            for key in RULE_MEASURES[trigger["rule"]]:
                ins = [p for p in group if p["snapshot"][key] is not None]
                outs = [p for p in rest if p["snapshot"][key] is not None]
                pieces, other_pieces = len({content(p) for p in ins}), len({content(p) for p in outs})
                if pieces < MIN_GROUP or other_pieces < MIN_GROUP:
                    continue
                mean_in = average([p["snapshot"][key] for p in ins], key)
                mean_out = average([p["snapshot"][key] for p in outs], key)
                if not mean_out or abs(mean_in - mean_out) / mean_out * 100 < MIN_DIFFERENCE_PCT:
                    continue
                if flagged is None and mean_in <= mean_out:
                    continue
                shown = language_name(value) if kind == "language" else value
                found.append({
                    "kind": kind, "value": value, "measure": key,
                    "group": group_name.format(shown), "rest": rest_name,
                    "posts": [p["content_item_id"] for p in ins],
                    "others": [p["content_item_id"] for p in outs],
                    "pieces": pieces, "other_pieces": other_pieces,
                    "mean": mean_in, "other_mean": mean_out,
                    "times": round(mean_in / mean_out, 1),
                    "difference_pct": round((mean_in - mean_out) / mean_out * 100),
                    "triggers": [n],
                })  # fmt: skip
    return found


def format_lean(posts: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The request category the numbers favour: video when video posts beat picture posts
    on both people reached and engagement (2 or more pieces of content each), photo when
    picture posts beat them on both, else none (F-047)."""
    leads, notes = set(), []
    for key in ("reach_count", "true_engagement_rate"):
        sides = {}
        for name, is_one in (("video", True), ("photo", False)):
            members = [p for p in posts if is_video(p) == is_one and p["snapshot"][key] is not None]
            if len({content(p) for p in members}) >= MIN_GROUP:
                sides[name] = average([p["snapshot"][key] for p in members], key)
        if len(sides) < 2 or not sides["photo"]:
            return None
        leads.add("video" if sides["video"] > sides["photo"] else "photo")
        unit = MEASURES[key][1]
        notes.append(f"{MEASURES[key][0]} {fmt(sides['video'])}{unit} vs {fmt(sides['photo'])}{unit}")
    if len(leads) != 1:
        return None
    return {"category": leads.pop(), "text": "video vs picture posts: " + "; ".join(notes)}


def merged(found: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One comparison per set of posts and measure: groups that hold the same posts
    (several visual tags of the same videos; the TikTok posts that are also the Nepali
    ones) are named together, and a comparison that only swaps the two sides of one
    already kept is left out."""
    kept: dict[tuple, dict[str, Any]] = {}
    for item in found:
        sides = (frozenset(item["posts"]), frozenset(item["others"]))
        key, mirror = (item["measure"], *sides), (item["measure"], *reversed(sides))
        if mirror in kept:
            continue
        if key not in kept:
            kept[key] = {**item, "names": [(item["kind"], item["value"], item["group"])]}
            continue
        first = kept[key]
        first["names"].append((item["kind"], item["value"], item["group"]))
        if all(kind == "visual" for kind, _, _ in first["names"]):
            values = [value for _, value, _ in first["names"]]
            first["group"] = f"videos showing {', '.join(values[:-1])} and {values[-1]}"
        else:
            others = [group for _, _, group in first["names"][1:]]
            first["group"] = f"{first['names'][0][2]} (the same posts as {', '.join(others)})"
            if len({kind for kind, _, _ in first["names"]}) > 1:
                first["rest"] = "the other posts"
        first["triggers"] = sorted(set(first["triggers"]) | set(item["triggers"]))
    return list(kept.values())


# --- The material sent ---------------------------------------------------------------


def side(name: str, count: int, pieces: int) -> str:
    if pieces != count:
        return f"{name} ({plural(count, 'post')} of {plural(pieces, 'piece')} of content)"
    return f"{name} ({plural(count, 'post')})"


def comparison_text(item: dict[str, Any]) -> str:
    label, unit = MEASURES[item["measure"]]
    direction = "higher" if item["difference_pct"] >= 0 else "lower"
    return (
        f"{side(item['group'], len(item['posts']), item['pieces'])} vs "
        f"{side(item['rest'], len(item['others']), item['other_pieces'])}, {label}: average "
        f"{fmt(item['mean'])}{unit} vs {fmt(item['other_mean'])}{unit}; "
        f"{fmt(item['times'])}× ({abs(item['difference_pct'])}% {direction})"
    )


def without_text(item: dict[str, Any], ids: dict[str, str]) -> str:
    """The posts a comparison was worked out without: the trigger's own post and the
    same video posted again."""
    if not item["without"]:
        return ""
    return f"; worked out without the flagged post ({', '.join(ids[i] for i in item['without'])})"


def trigger_text(trigger: dict[str, Any], triggers: dict[str, Any], post_ref: str | None, month: dict[str, Any]) -> tuple[str, list[float]]:
    """What a trigger found, in words, and its numbers."""
    baseline, quota = triggers["baseline"], triggers["quota"]
    if trigger["rule"] == "engagement_gt_200pct_mean":
        mean = baseline["engagement_rate_mean"]
        return (
            f"{post_ref}: engagement rate {fmt(trigger['value'])}%, {fmt(trigger['times'])}× the "
            f"90-day average of {fmt(mean)}% (the rule: above {fmt(trigger['threshold'])}%, "
            f"2 × the average)",
            [trigger["value"], trigger["times"], mean, trigger["threshold"], OUTLIER_TIMES],
        )
    if trigger["rule"] == "hook_dropoff_gt_45pct":
        line = (f"{post_ref}: {fmt(trigger['dropoff'])}% stopped watching in the first 3 seconds "
                f"(still watching after 3 s: {fmt(trigger['value'])}%; the rule: more than "
                f"{fmt(DROPOFF_PCT)}%)")  # fmt: skip
        numbers = [trigger["dropoff"], trigger["value"], DROPOFF_PCT]
        if baseline["retention_3s_mean"] is not None:
            line += f"; the 90-day average still watching after 3 s: {fmt(baseline['retention_3s_mean'])}%"
            numbers.append(baseline["retention_3s_mean"])
        return line, numbers
    return (
        f"{quota['published']} of the {quota['monthly_posts']} posts in "
        f"{month_name(month['month_period'])}'s quota were published; {trigger['behind']} "
        f"behind (the rule: {POSTS_BEHIND} or more behind)",
        [quota["published"], quota["monthly_posts"], trigger["behind"], POSTS_BEHIND],
    )


def build_context(
    triggers: dict[str, Any],
    month: dict[str, Any],
    posts: list[dict[str, Any]],
    sent: list[dict[str, Any]],
    found: list[dict[str, Any]],
    materials: dict[str, dict[str, Any]],
    organisation: dict[str, Any] | None,
    quantities: list[int],
) -> tuple[str, dict[str, dict[str, Any]], list[float], list[float]]:
    """The material sent; the references finalize maps sentences to, each with its own
    numbers; every number the draft may show; and the numbers any sentence may use
    (years, the seconds and days the measures are named by)."""
    period = month["month_period"]
    following = month_of(period, 1)
    ids = {post["content_item_id"]: f"P{n}" for n, post in enumerate(posts, 1)}
    refs: dict[str, dict[str, Any]] = {}
    baseline = triggers["baseline"]
    general: list[float] = [int(period[:4]), int(following[:4]), 3, 10, baseline["window_days"]]

    def keep(ref: str, *values: Any) -> None:
        numbers = refs[ref].setdefault("numbers", [])
        for value in values:
            if isinstance(value, str):
                numbers.extend(number for _, number, _ in numbers_in(value))
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                numbers.append(float(value))

    sections = ["\n".join([
        "INSIGHTS",
        f"Month: {month_name(period)} ({period}); requests are for {month_name(following)}",
        f"A request may ask for {', '.join(map(str, quantities[:-1]))} or {quantities[-1]} items"
        if len(quantities) > 1 else f"A request may ask for {quantities[0]} item",
    ])]  # fmt: skip

    start, end = date.fromisoformat(baseline["window_start"]), date.fromisoformat(baseline["window_end"])
    line = (f"{baseline['window_days']}-day baseline ({start.day} {start:%B %Y} to {end.day} {end:%B %Y}, "
            f"{plural(baseline['posts'], 'post')} in Pulse's analytics): average engagement rate "
            f"{fmt(baseline['engagement_rate_mean'])}%")  # fmt: skip
    if baseline["engagement_rate_sd"] is not None:
        line += f" (standard deviation {fmt(baseline['engagement_rate_sd'])})"
    if baseline["retention_3s_mean"] is not None:
        line += f"; average still watching after 3 s {fmt(baseline['retention_3s_mean'])}%"
    refs["BL"] = {"source": "baseline", "label": line}
    keep("BL", baseline["posts"], baseline["engagement_rate_mean"], baseline["engagement_rate_sd"],
         baseline["retention_3s_mean"])  # fmt: skip
    sections.append(f"BASELINE\n[BL] {line}")

    lines = ["TRIGGERS (raised by fixed rules on this month's numbers; one insight each)"]
    for n, trigger in enumerate(sent, 1):
        ref = f"T{n}"
        post_ref = ids.get(trigger["content_item_id"])
        words, numbers = trigger_text(trigger, triggers, post_ref, month)
        label = f"{RULES[trigger['rule']]}: {words}"
        refs[ref] = {"source": "trigger", "rule": trigger["rule"],
                     "content_item_id": trigger["content_item_id"], "post": post_ref, "label": label}  # fmt: skip
        keep(ref, *numbers, trigger.get("bar"), trigger.get("quantity"))
        block = [f"[{ref}] {label}",
                 f"  the client card's finding, written from the numbers (do not write your own): \"{trigger['card']}\""]  # fmt: skip
        if trigger.get("bar") is not None:
            measure = "liked, commented on, shared or saved" if trigger["rule"] == "engagement_gt_200pct_mean" \
                else "still watching after 3 s"  # fmt: skip
            block.append(f"  a test must beat {fmt(trigger['bar'])}% {measure} (the 90-day average), or the "
                         "average of the group a hypothesis cites where that is higher; "
                         "a lower bar would confirm nothing")  # fmt: skip
        if trigger.get("quantity"):
            block.append(f"  request size, set from the gap: {trigger['quantity']}")
        if trigger["content_item_id"] and not any(n - 1 in item["triggers"] for item in found):
            block.append("  no comparison bears on this trigger: answer enough_evidence false (a post "
                         "cannot explain its own result)")  # fmt: skip
        lines.append("\n".join(block))
    sections.append("\n".join(lines))

    lines = [f"COMPARISONS (posts with complete data in the baseline window; each side needs "
             f"{MIN_GROUP} or more different pieces of content, and a video posted on two "
             "platforms is two posts but one piece of content; a trigger's comparisons leave its "
             "own post out; cite these, never work out your own)"]  # fmt: skip
    for n, item in enumerate(found, 1):
        ref = f"G{n}"
        words = comparison_text(item) + without_text(item, ids)
        bears = ", ".join(f"T{i + 1}" for i in item["triggers"])
        refs[ref] = {"source": "comparison", "measure": item["measure"], "kind": item["kind"], "mean": item["mean"],
                     "triggers": [f"T{i + 1}" for i in item["triggers"]], "label": words,
                     "posts": [ids[i] for i in item["posts"]], "others": [ids[i] for i in item["others"]]}  # fmt: skip
        keep(ref, len(item["posts"]), len(item["others"]), item["pieces"], item["other_pieces"],
             item["mean"], item["other_mean"], item["times"], abs(item["difference_pct"]))  # fmt: skip
        lines.append(f"[{ref}] {words}; bears on {bears}; posts: {', '.join(refs[ref]['posts'])}")
    if not found:
        lines.append("- none: no group has enough posts with complete data on each side")
    sections.append("\n".join(lines))

    lines = ["POSTS IN THE BASELINE WINDOW WITH COMPLETE DATA (each with its latest numbers)"]
    first_post: dict[str, str] = {}  # source file -> the first post made from it
    for post in posts:
        ref = ids[post["content_item_id"]]
        refs[ref] = {"source": "post", "content_item_id": post["content_item_id"],
                     "platform": post["platform"], "label": f"{post_label(post)}; {snapshot_text(post)}"}  # fmt: skip
        snapshot = post["snapshot"]
        keep(ref, *(value for key, value in snapshot.items() if key not in ("snapshot_timestamp", "data_quality_flag")))
        block = [f"[{ref}] {post_label(post)}", f"  {snapshot_text(post)}"]
        if post["source_file"] in first_post:
            block.append(f"  same video as {first_post[post['source_file']]}, posted again on "
                         f"{post['platform']}: one video, not two")  # fmt: skip
        elif post["source_file"]:
            first_post[post["source_file"]] = ref
        material = materials.get(post["content_item_id"]) or {}
        if topics := material.get("topics"):
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
        if action := material.get("action"):
            block.append(f"  call to action in its caption: \"{action}\"")
            keep(ref, action)
        if visual := material.get("visual_shown"):
            block.append(f"  what its pictures show (longest on screen first; tagged by a model): {', '.join(visual)}")
        lines.append("\n".join(block))
    sections.append("\n".join(lines))

    brand = month["brand"]
    extra: list[str] = []
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
        extra += [*brand["voice_pillars"], brand["tone_rules"], *brand["do_nots"], *month["audience"]]
    if section := organisation_section(organisation):
        sections.append(section)
        extra.append(section)
    general += [number for value in extra for _, number, _ in numbers_in(value)]

    for item in refs.values():
        item["numbers"] = sorted(set(item.get("numbers", [])))
    general = sorted(set(general))
    allowed = sorted({*general, *(value for item in refs.values() for value in item["numbers"])})
    return "\n\n".join(sections), refs, allowed, general


# --- Running it ----------------------------------------------------------------------


def ready_summary(
    triggers: dict[str, Any],
    sent: list[dict[str, Any]],
    held: list[dict[str, Any]],
    posts: list[dict[str, Any]],
    found: list[dict[str, Any]],
    materials: dict[str, dict[str, Any]],
    organisation: dict[str, Any] | None,
    options: dict[str, Any],
    quantities: list[int],
    estimated_tokens: int,
    replaces: str | None,
    warnings: list[str],
) -> list[str]:
    """What the user sees before approving the paid step, every line every time."""
    period, baseline = triggers["month_period"], triggers["baseline"]
    names = {
        "engagement_gt_200pct_mean": lambda t: f"engagement {fmt(t['times'])}× the average on {t['content_item_id']}",
        "hook_dropoff_gt_45pct": lambda t: f"{fmt(t['dropoff'])}% gone in 3 s on {t['content_item_id']}",
        "pace_behind_quota": lambda t: f"{t['behind']} posts behind the quota",
    }
    return [
        f"Month: {month_name(period)}; requests are for {month_name(month_of(period, 1))}",
        "Triggers sent: " + "; ".join(f"T{n} {names[t['rule']](t)}" for n, t in enumerate(sent, 1)),
        "Held back: " + ("; ".join(f"{item['label']} ({item['reason']})" for item in held) if held else "none"),
        f"Baseline: {baseline['window_days']} days, {baseline['window_start']} to "
        f"{baseline['window_end']}; posts with complete data in input/reports/: {len(posts)}",
        f"Comparisons: {len(found)} (at least {MIN_GROUP} posts on each side)",
        f"Posts made from a video in input/: {len(materials)} (topic tags for "
        f"{sum(1 for m in materials.values() if m['topics'])}, hook for "
        f"{sum(1 for m in materials.values() if m['hook'])}, visual tags for "
        f"{sum(1 for m in materials.values() if m['visual'])})",
        f"Request quantities allowed: {', '.join(map(str, quantities))}",
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
    parser.add_argument("source", type=Path, help="the month's triggers (JSON)")
    parser.add_argument("--force", action="store_true", help="draft again even if done")
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    if not source.is_file():
        fail(f"file not found: {args.source}")
    triggers = read_triggers(source)
    month, window, files = load_window(triggers)
    sent, held = check_triggers(triggers, month)
    warnings = rule_warnings(triggers, month, window)
    if MONTH.fullmatch(source.stem) and source.stem != triggers["month_period"]:
        warnings.append(f"The file is named {source.name} but holds {triggers['month_period']}.")
    if not sent:
        print_json({
            "status": "nothing_to_send",
            "month": triggers["month_period"],
            "held_back": held,
            "warnings": warnings,
            "message": "No trigger is left to send, so nothing is drafted and nothing is charged.",
        })  # fmt: skip
        return

    digest = sha256(source)
    output_dir = output_dir_for(PROCESSOR, source, digest)
    organisation = load_organisation()
    posts = [post for post in window if full(post)]
    ids = {post["content_item_id"]: f"P{n}" for n, post in enumerate(posts, 1)}
    materials, records, material_warnings = gather_materials(posts, ids, organisation=organisation)
    period = triggers["month_period"]
    inputs = {"report": {"name": f"{period}.json", "sha256": files[f"{period}.json"]},
              "window_reports": files, "posts": records, "organisation": organisation}  # fmt: skip
    previous = output_dir / "insights.json"
    done = read_result(previous)
    if done is not None and not args.force:
        status = "already_done" if done.get("inputs") == inputs else "outdated"
        messages = {
            "already_done": "This month's insights for these triggers are up to date. Use "
            "--force to pay again.",
            "outdated": "A report input in the baseline window, a post's topic tags, copy or "
            "visual tags, or organisation.json changed since these insights were drafted. Use "
            "--force to draft them again (charged again).",
        }
        print_json({"status": status, "output_dir": str(output_dir), "message": messages[status]})
        return
    # --force: finalize moves the result it replaces into history/ (see archive_previous).
    replaces = previous_created_at(previous)

    found = comparisons(posts, materials, sent)
    quantities = list(range(1, min(MAX_QUANTITY, triggers["quota"]["monthly_posts"]) + 1))
    context, refs, allowed, general = build_context(
        triggers, month, posts, sent, found, materials, organisation, quantities
    )
    warnings += material_warnings
    if organisation is None:
        warnings.append(
            "No organisation.json: the organisation's name is not given, so the draft "
            "avoids it. Copy organisation.example.json to organisation.json and fill it in."
        )
    model = insight_model()
    effort = setting("OPENAI_INSIGHT_REASONING_EFFORT", "low") or "low"
    options = {"model": model, "reasoning_effort": effort}
    job_dir = new_job_dir(PROCESSOR, source)
    plan = {
        "version": 1,
        "processor": PROCESSOR,
        "status": "ready",
        "source": {"name": source.name, "path": str(source), "sha256": digest},
        "month": {
            "period": period,
            "next": month_of(period, 1),
            "name": month_name(period),
            "next_name": month_name(month_of(period, 1)),
        },
        "inputs": inputs,
        "organisation": organisation,
        "options": options,
        "baseline": triggers["baseline"],
        "quota": triggers["quota"],
        "triggers": {f"T{n}": {"rule": t["rule"], "content_item_id": t["content_item_id"], "card": t["card"],
                               "bar": t.get("bar"), "quantity": t.get("quantity")}
                     for n, t in enumerate(sent, 1)},  # fmt: skip
        "format_lean": format_lean(posts),
        # The kinds of post a request can name, to tell two requests for the same kind apart.
        "pillars": sorted({post["content_pillar"].lower() for post in posts if post["content_pillar"]}),
        "held_back": held,
        "quantities": quantities,
        "comparisons": len(found),
        "refs": refs,
        "allowed_numbers": allowed,
        "general_numbers": general,
        "context": context,
        "estimated_input_tokens": estimate_text_tokens(
            INSTRUCTIONS + json.dumps(schema(quantities)) + context
        ),
        "warnings": warnings,
        "output_dir": str(output_dir),
        "replaces": replaces,
        "created_at": now_iso(),
    }
    write_json(job_dir / "plan.json", plan)
    summary = ready_summary(
        triggers, sent, held, posts, found, materials, organisation, options, quantities,
        plan["estimated_input_tokens"], replaces, warnings,
    )  # fmt: skip
    print_json(
        {
            "status": "ready",
            "job_dir": str(job_dir),
            "month": period,
            "triggers": len(sent),
            "held_back": len(held),
            "comparisons": len(found),
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
