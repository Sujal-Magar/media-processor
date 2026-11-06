"""A month's report input as Pulse's analytics (C15) and report compilation (C17a) would
give it: totals with their change from last month, each platform, each post with its D2
snapshot and the Top 3 highlights. Shape: fixtures/report-input.example.json. Read by
draft-report (C17b) and draft-insights (C18b); each problem stops with where it is.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from lib.workspace import fail

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
PLATFORMS = ("instagram", "tiktok", "linkedin", "youtube")  # D1 content_variants.platform
# C17a's Top 3 highlights; the top post of the month is the highest-reach one.
SLOTS = {
    "highest_reach": "Highest reach",
    "highest_engagement": "Highest engagement",
    "best_retention": "Best retention",
}
QUALITY = ("Full", "Partial", "Stale")  # D2 data_quality_flag
# D2 analytics_snapshots: counts, then percentages.
COUNTS = {
    "reach_count": "people reached",
    "views_count": "plays",
    "likes_count": "likes",
    "comments_count": "comments",
    "shares_count": "shares",
    "saves_count": "saves",
}
RATES = {
    "true_engagement_rate": "engagement rate",
    "retention_3s_pct": "still watching after 3 s",
    "retention_10s_pct": "after 10 s",
    "retention_complete_pct": "to the end",
}
RETENTION = ("retention_3s_pct", "retention_10s_pct", "retention_complete_pct")
LANGUAGES = {"en": "English", "ne": "Nepali", "hi": "Hindi"}
MONTH = re.compile(r"\d{4}-(?:0[1-9]|1[0-2])")
MAX_TEXT_CHARS = 300
MAX_ITEMS = 10
MAX_POSTS = 200


def short_text(value: Any, where: str, required: bool = False) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value.strip()):
        fail(f"{where} must be {'a non-empty' if required else 'a'} string")
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) > MAX_TEXT_CHARS:
        fail(f"{where} has {len(value)} characters; at most {MAX_TEXT_CHARS} are accepted")
    return value


def text_list(value: Any, where: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_ITEMS:
        fail(f"{where} must be a list of at most {MAX_ITEMS} strings")
    items = [short_text(item, f"{where}[{n}]") for n, item in enumerate(value)]
    return [item for item in items if item]


def number(value: Any, where: str, signed: bool = False) -> float | None:
    """A recorded number, or None when it is missing (never 0 in its place)."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or (value < 0 and not signed):
        fail(f"{where} must be a number{'' if signed else ' of 0 or more'} or null")
    return value


def month_of(period: str, shift: int) -> str:
    year, month = divmod(int(period[:4]) * 12 + int(period[5:]) - 1 + shift, 12)
    return f"{year:04d}-{month + 1:02d}"


def month_name(period: str) -> str:
    return date(int(period[:4]), int(period[5:]), 1).strftime("%B %Y")


def change(value: Any, where: str) -> dict[str, Any] | None:
    """A total as C17a gives it: this month, last month and the change in per cent
    (null when it held the change back); null when the metric is not tracked."""
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {"current", "previous", "delta_pct", "footnote"}:
        fail(f"{where} must be null or {{current, previous, delta_pct, footnote}}")
    return {
        "current": number(value.get("current"), f"{where}.current"),
        "previous": number(value.get("previous"), f"{where}.previous"),
        "delta_pct": number(value.get("delta_pct"), f"{where}.delta_pct", signed=True),
        "footnote": short_text(value.get("footnote"), f"{where}.footnote"),
    }


def metric_changes(value: Any, where: str, extra: tuple[str, ...] = ()) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{where} must be an object")
    unknown = set(value) - set(METRICS) - set(extra)
    if unknown:
        fail(f"{where} has unknown metrics {sorted(unknown)}; use {', '.join(METRICS)}")
    return {key: change(value.get(key), f"{where}.{key}") for key in METRICS if key in value}


def read_post(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{where} must be an object")
    platform = value.get("platform")
    if platform not in PLATFORMS:
        fail(f"{where}.platform must be one of {', '.join(PLATFORMS)}")
    try:
        published = date.fromisoformat(str(value.get("published_at"))[:10])
    except ValueError:
        fail(f"{where}.published_at must be a date such as 2026-10-03")
    source_file = short_text(value.get("source_file"), f"{where}.source_file")
    if source_file and Path(source_file).name != source_file:
        fail(f"{where}.source_file must be a file name in input/, without folders")
    hook = value.get("hook_used")
    if hook is not None and (isinstance(hook, bool) or not isinstance(hook, int) or hook < 1):
        fail(f"{where}.hook_used must be a hook number from 1")
    if hook is not None and not source_file:
        fail(f"{where}.hook_used needs the source_file the hook was written for")
    snapshot = value.get("snapshot")
    if not isinstance(snapshot, dict):
        fail(f"{where}.snapshot must be an object (a D2 analytics snapshot)")
    if snapshot.get("platform") not in (None, platform):
        fail(f"{where}.snapshot.platform differs from the post's platform")
    flag = snapshot.get("data_quality_flag")
    if flag not in QUALITY:
        fail(f"{where}.snapshot.data_quality_flag must be one of {', '.join(QUALITY)}")
    return {
        "content_item_id": short_text(value.get("content_item_id"), f"{where}.content_item_id", True),
        "platform": platform,
        "post_url": short_text(value.get("post_url"), f"{where}.post_url"),
        "published_at": published.isoformat(),
        "content_pillar": short_text(value.get("content_pillar"), f"{where}.content_pillar"),
        "language": short_text(value.get("language"), f"{where}.language"),
        "title": short_text(value.get("title"), f"{where}.title"),
        "source_file": source_file,
        "hook_used": hook,
        "snapshot": {
            **{key: number(snapshot.get(key), f"{where}.snapshot.{key}") for key in COUNTS},
            **{key: number(snapshot.get(key), f"{where}.snapshot.{key}") for key in RATES},
            "snapshot_timestamp": short_text(
                snapshot.get("snapshot_timestamp"), f"{where}.snapshot.snapshot_timestamp"
            ),
            "data_quality_flag": flag,
        },
    }


def read_month(path: Path) -> dict[str, Any]:
    """The month's input, checked against the documented shape; stops at the first
    problem with where it is."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        fail(f"{path.name} is not valid JSON: {exc}")
    if not isinstance(data, dict):
        fail(f"{path.name} must hold one JSON object")
    period = data.get("month_period")
    if not isinstance(period, str) or not MONTH.fullmatch(period):
        fail("month_period must be a month such as 2026-10")
    previous = month_of(period, -1)
    if data.get("previous_month") not in (None, previous):
        fail(f"previous_month must be {previous}: a report compares with the month before")

    platforms = data.get("platforms") or {}
    if not isinstance(platforms, dict) or set(platforms) - set(PLATFORMS):
        fail(f"platforms must be an object keyed by {', '.join(PLATFORMS)}")
    by_platform = {}
    for name in PLATFORMS:
        if name not in platforms:
            continue
        entry = platforms[name]
        where = f"platforms.{name}"
        if not isinstance(entry, dict):
            fail(f"{where} must be an object")
        posts = entry.get("posts")
        if posts is not None and (isinstance(posts, bool) or not isinstance(posts, int) or posts < 0):
            fail(f"{where}.posts must be a whole number of 0 or more")
        by_platform[name] = {"posts": posts, **metric_changes(entry, where, ("posts",))}

    raw_posts = data.get("posts")
    if not isinstance(raw_posts, list) or not raw_posts or len(raw_posts) > MAX_POSTS:
        fail(f"posts must be a list of 1 to {MAX_POSTS} posts")
    posts = [read_post(post, f"posts[{n}]") for n, post in enumerate(raw_posts)]
    ids = [post["content_item_id"] for post in posts]
    if repeated := sorted({i for i in ids if ids.count(i) > 1}):
        fail(f"content_item_id repeated: {', '.join(repeated)}")

    highlights = data.get("highlights") or {}
    if not isinstance(highlights, dict) or set(highlights) - set(SLOTS):
        fail(f"highlights must be an object with {', '.join(SLOTS)}")
    for slot, chosen in highlights.items():
        if chosen is not None and chosen not in ids:
            fail(f"highlights.{slot} is {chosen!r}, which is not a content_item_id in posts")

    earlier = data.get("earlier_months") or []
    if not isinstance(earlier, list) or len(earlier) > 24:
        fail("earlier_months must be a list of at most 24 months")
    earlier_months = []
    for n, entry in enumerate(earlier):
        where = f"earlier_months[{n}]"
        if not isinstance(entry, dict) or not MONTH.fullmatch(str(entry.get("month_period"))):
            fail(f"{where} needs a month_period such as 2026-09")
        if entry["month_period"] >= period:
            fail(f"{where}.month_period must be before {period}")
        unknown = set(entry) - set(METRICS) - {"month_period"}
        if unknown:
            fail(f"{where} has unknown metrics {sorted(unknown)}")
        earlier_months.append(
            {"month_period": entry["month_period"],
             **{key: number(entry[key], f"{where}.{key}") for key in METRICS if key in entry}}
        )  # fmt: skip

    brand = data.get("brand") or {}
    if not isinstance(brand, dict) or set(brand) - {"voice_pillars", "tone_rules", "do_nots"}:
        fail("brand must be an object with voice_pillars, tone_rules and do_nots")
    return {
        "month_period": period,
        "previous_month": previous,
        "totals": metric_changes(data.get("totals") or {}, "totals"),
        "platforms": by_platform,
        "posts": posts,
        "highlights": {slot: highlights.get(slot) for slot in SLOTS},
        "next_month_plan": text_list(data.get("next_month_plan"), "next_month_plan"),
        "earlier_months": sorted(earlier_months, key=lambda m: m["month_period"]),
        "brand": {
            "voice_pillars": text_list(brand.get("voice_pillars"), "brand.voice_pillars"),
            "tone_rules": short_text(brand.get("tone_rules"), "brand.tone_rules"),
            "do_nots": text_list(brand.get("do_nots"), "brand.do_nots"),
        },
        "audience": text_list(data.get("audience"), "audience"),
    }


def post_refs(month: dict[str, Any]) -> dict[str, str]:
    """content_item_id -> P1, P2, ... in the input's order."""
    return {post["content_item_id"]: f"P{n}" for n, post in enumerate(month["posts"], 1)}


def fmt(value: float) -> str:
    """A number as the data has it: 48,200, 38.11, 7.6."""
    return f"{int(value):,}" if float(value).is_integer() else f"{value:,}"


def plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def signed(value: float) -> str:
    return ("+" if value > 0 else "") + fmt(value)


def language_name(code: str) -> str:
    return LANGUAGES.get(code.lower(), code) if code else ""


def is_video(post: dict[str, Any]) -> bool:
    return bool(post["source_file"]) or any(post["snapshot"][key] is not None for key in RETENTION)


def post_label(post: dict[str, Any]) -> str:
    published = date.fromisoformat(post["published_at"])
    details = [f"{post['platform']} {'video' if is_video(post) else 'post'}",
               f"published {published.day} {published:%B %Y}"]  # fmt: skip
    if post["content_pillar"]:
        details.append(f"pillar {post['content_pillar']}")
    if post["language"]:
        details.append(f"in {language_name(post['language'])}")
    return ", ".join(details) + f"; data {post['snapshot']['data_quality_flag']}"


def snapshot_text(post: dict[str, Any]) -> str:
    """The snapshot's numbers; views_count counts plays of a video, but the times a
    picture or carousel was shown (D2: "Total impressions / video plays")."""
    snapshot, parts = post["snapshot"], []
    for key, name in COUNTS.items():
        value = snapshot[key]
        if key == "views_count" and not is_video(post):
            name = "times shown"
        parts.append(f"{name} {fmt(value)}" if value is not None else f"{name} not recorded")
    if snapshot["true_engagement_rate"] is not None:
        parts.append(f"engagement rate {fmt(snapshot['true_engagement_rate'])}%")
    retention = [f"{RATES[key]} {fmt(snapshot[key])}%" for key in RETENTION if snapshot[key] is not None]
    return "; ".join(parts + retention)
