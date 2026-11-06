#!/usr/bin/env python3
"""tag-visuals, step 3: merge the per-frame results into output/tag-visuals/<name>-<hash>/
tags.md, tags.json, metadata.json and frames/ (thumbnails). Free; tag.py runs it.

A tag's (or a text's) time range runs from a frame that shows it until the next sampled
frame. Tags that were not in the library's existing tags are marked as new.
Prints only counts and paths, never tags or text.

    python3 processors/tag-visuals/finalize.py work/tag-visuals/<job> [--keep-work]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import unicodedata
from collections import Counter
from collections.abc import Iterator
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `lib`

from lib.workspace import (
    archive_previous,
    fail,
    fmt_time,
    is_job_dir,
    now_iso,
    print_json,
    result_metadata,
    write_json,
    write_text,
)

from lib.tags import clean_label

CATEGORIES = ("object", "scene", "activity", "attribute")
# Readings that differ by a misread letter or two (TELICHO / TILICHO) are one text.
FUZZY_RATIO = 0.85
FUZZY_MAX_DIGITS = 4
HEADINGS = {"object": "Objects", "scene": "Scenes", "activity": "Activities",
            "attribute": "Attributes"}  # fmt: skip


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def has_text(text: str) -> bool:
    """At least one letter or digit: a bare "…" (a line the model could not read at all)
    or other punctuation is not text."""
    return any(unicodedata.category(c)[0] in "LN" for c in text)


def text_items(raw: list[Any], detail: str) -> list[dict[str, Any]]:
    """On-screen text as {text, legibility, detail}. Accepts plain strings (results saved
    before legibility existed) and {text, legibility} objects. Items without a letter or
    digit are dropped."""
    items = []
    for entry in raw:
        item = dict(entry) if isinstance(entry, dict) else {"text": entry}
        text = clean_text(str(item.get("text") or ""))
        legibility = item.get("legibility")
        if legibility not in ("clear", "partial"):
            legibility = "partial" if "…" in text else "clear"
        if has_text(text):
            items.append({"text": text, "legibility": legibility, "detail": detail})
    return items


def text_key(text: str, keep: str = "") -> str:
    """Case-folded letters, digits and combining marks only (keeps Devanagari intact),
    plus any character in `keep`."""
    return "".join(
        c for c in text.casefold() if c in keep or unicodedata.category(c)[0] in "LNM"
    )


def similar_text(a: str, b: str) -> bool:
    """Two readings of one piece of text, merged into one entry by aggregate_text: equal
    keys, or letters at least FUZZY_RATIO alike with the same digits. Text with
    FUZZY_MAX_DIGITS or more digits (phone, registration numbers) must match exactly."""
    key_a, key_b = text_key(a), text_key(b)
    if not key_a or not key_b:
        return False
    if key_a == key_b:
        return True
    digits_a = [c for c in key_a if c.isdigit()]
    if (
        digits_a != [c for c in key_b if c.isdigit()]
        or len(digits_a) >= FUZZY_MAX_DIGITS
    ):
        return False
    letters_a = "".join(c for c in key_a if not c.isdigit())
    letters_b = "".join(c for c in key_b if not c.isdigit())
    return SequenceMatcher(None, letters_a, letters_b).ratio() >= FUZZY_RATIO


def identical_text(a: str, b: str) -> bool:
    """The same reading, "…" included: only such readings join across legibility, so a
    partial reading is never shown as (or hidden behind) a clear one."""
    return has_text(a) and text_key(a, keep="…") == text_key(b, keep="…")


def same_text(a: str, b: str) -> bool:
    """Read again by the re-read: similar, or one (3+ characters) inside the other."""
    short, long = sorted((text_key(a), text_key(b)), key=len)
    return similar_text(a, b) or (len(short) >= 3 and short in long)


def merge_reread(
    low: list[dict[str, Any]], sharp: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """The re-read's text plus every pass-1 text it did not read again: the crop may
    hold only part of the frame, so text outside it is kept, but marked
    `confirmed: false`, since a low-detail reading can also be invented (F-030)."""
    kept = [
        {**t, "confirmed": False}
        for t in low
        if not any(same_text(t["text"], s["text"]) for s in sharp)
    ]
    return sharp + kept


def is_confirmed(item: dict[str, Any]) -> bool:
    """False only for a pass-1 text a re-read of its frame did not read again; results
    saved before the field existed have none."""
    return item.get("confirmed", True) is not False


def cell(value: str) -> str:
    """Make a value safe inside a Markdown table cell."""
    return value.replace("|", "\\|").replace("\n", " ")


def load_results(
    job_dir: Path,
) -> tuple[dict[int, dict[str, Any]], dict[int, dict[str, Any]], dict[str, Any]]:
    """Pass-1 answers by frame, pass-2 (high-detail text) answers by frame, and usage:
    the totals, plus the same counts for `tagging` and `text_reread` apart."""
    tagged: dict[int, dict[str, Any]] = {}
    reread: dict[int, dict[str, Any]] = {}
    usage: dict[str, Any] = {"requests": 0, "input_tokens": 0, "output_tokens": 0}
    for prefix, target, part in (
        ("batch", tagged, "tagging"),
        ("text", reread, "text_reread"),
    ):
        counts = {"requests": 0, "input_tokens": 0, "output_tokens": 0}
        for result_file in sorted((job_dir / "results").glob(f"{prefix}_*.json")):
            result = json.loads(result_file.read_text(encoding="utf-8"))
            counts["requests"] += 1
            for key in ("input_tokens", "output_tokens"):
                counts[key] += int((result.get("usage") or {}).get(key) or 0)
            for frame in result["frames"]:
                target[frame["index"]] = frame
        usage[part] = counts
        for key, value in counts.items():
            usage[key] += value
    return tagged, reread, usage


def load_skipped(job_dir: Path) -> dict[int, dict[str, Any]]:
    """Re-reads tag.py skipped because the text is too small in the source, by frame."""
    skipped_file = job_dir / "results" / "reread_skipped.json"
    if not skipped_file.is_file():
        return {}
    frames = json.loads(skipped_file.read_text(encoding="utf-8"))["frames"]
    return {frame["index"]: frame for frame in frames}


def flagged_frames(
    plan: dict[str, Any], tagged: dict[int, dict[str, Any]]
) -> list[int]:
    """Frames where pass 1 saw text it could not read, whatever the options."""
    return [
        frame["index"]
        for frame in plan["frames"]
        if tagged.get(frame["index"], {}).get("unreadable_text")
    ]


def needs_text_pass(
    plan: dict[str, Any], tagged: dict[int, dict[str, Any]]
) -> list[int]:
    """Frames to re-read at high detail: low-detail frames with unreadable text."""
    options = plan["options"]
    if not options.get("text_pass", True) or options["detail"] != "low":
        return []
    return flagged_frames(plan, tagged)


def text_pass_status(
    plan: dict[str, Any],
    flagged: list[int],
    to_reread: list[int],
    covered: set[int],
    skipped: set[int],
) -> str:
    options = plan["options"]
    if not options.get("text_pass", True):
        return "off (no text pass)"
    if options["detail"] != "low":
        return "skipped (high detail)" if flagged else "not needed"
    if not to_reread:
        return "not needed"
    if not covered >= set(to_reread) - skipped:
        return "incomplete"
    return "done" if covered else "skipped (text too small)"


def apply_text_pass(
    plan: dict[str, Any],
    tagged: dict[int, dict[str, Any]],
    reread: dict[int, dict[str, Any]],
    skipped_runs: dict[int, dict[str, Any]],
) -> tuple[dict[str, Any], bool]:
    """Merge the re-read text into the frames it covers and note per frame what the
    re-read did. Returns the text_pass summary and whether no re-read is missing."""
    detail = plan["options"]["detail"]
    for result in tagged.values():
        result["on_screen_text"] = text_items(result.get("on_screen_text", []), detail)
    flagged = flagged_frames(plan, tagged)
    to_reread = needs_text_pass(plan, tagged)
    # Each re-read frame stands for its run of flagged frames (see text_runs).
    covered = {
        index: frame_index
        for frame_index, result in reread.items()
        for index in result.get("covers", [frame_index])
        if index in tagged
    }
    skipped = {
        index: run["reason"]
        for run in skipped_runs.values()
        for index in run["covers"]
        if index in tagged
    }
    status = text_pass_status(plan, flagged, to_reread, set(covered), set(skipped))
    reason = {
        "off (no text pass)": "skipped: no text pass",
        "skipped (high detail)": "skipped: high detail",
    }.get(status, "skipped: the run stopped before the re-read")
    for index in flagged:
        tagged[index]["text_reread"] = skipped.get(index, reason)
    for index, source in covered.items():
        sharp = text_items(reread[source].get("on_screen_text", []), "high")
        low = tagged[index]["on_screen_text"]
        tagged[index].update(
            on_screen_text=merge_reread(low, sharp),
            text_low_detail=low,
            text_reread="found" if sharp else "nothing readable",
            text_from_frame=source,
            text_crop=reread[source].get("crop"),
        )
    summary = {
        "status": status,
        "frames_flagged": len(flagged),
        "frames_reread": len(reread),
        "frames_covered": len(covered),
        "frames_skipped": len(skipped),  # text too small in the source to re-read
        "frames_with_text": sum(
            tagged[index]["text_reread"] == "found" for index in covered
        ),
        "rereads_empty": sum(
            not text_items(r.get("on_screen_text", []), "high") for r in reread.values()
        ),
    }
    return summary, status != "incomplete"


def text_runs(plan: dict[str, Any], flagged: list[int]) -> list[list[int]]:
    """Group flagged frames that follow each other: in a still shot they show the same
    text, so one sharp re-read per run is enough."""
    wanted = set(flagged)
    runs: list[list[int]] = []
    previous_flagged = False
    for frame in plan["frames"]:
        if frame["index"] in wanted:
            if previous_flagged:
                runs[-1].append(frame["index"])
            else:
                runs.append([frame["index"]])
        previous_flagged = frame["index"] in wanted
    return runs


def spans(
    plan: dict[str, Any], tagged: dict[int, dict[str, Any]]
) -> Iterator[tuple[dict[str, Any], float | None, float | None]]:
    """Each tagged frame's result with the time range it stands for."""
    frames = plan["frames"]
    duration = plan["source"]["duration_seconds"]
    for position, frame in enumerate(frames):
        result = tagged.get(frame["index"])
        if result is None:
            continue
        end = (
            frames[position + 1]["time_seconds"]
            if position + 1 < len(frames)
            else duration
        )
        yield {**result, "index": frame["index"]}, frame["time_seconds"], end


def extend_ranges(
    ranges: list[list[float]], start: float | None, end: float | None
) -> None:
    if start is None or end is None:
        return
    if ranges and ranges[-1][1] == start:
        ranges[-1][1] = end  # seen on consecutive frames: one continuous range
    else:
        ranges.append([start, end])


def total_seconds(ranges: list[list[float]]) -> float | None:
    return round(sum(e - s for s, e in ranges), 1) if ranges else None


def aggregate(
    plan: dict[str, Any], tagged: dict[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    known = {clean_label(t["label"]) for t in plan.get("existing_tags", [])}
    tags: dict[tuple[str, str], dict[str, Any]] = {}
    for result, start, end in spans(plan, tagged):
        seen: set[tuple[str, str]] = set()
        for tag in result["tags"]:
            key = (clean_label(tag["label"]), tag["category"])
            if not key[0] or key in seen:
                continue
            seen.add(key)
            entry = tags.setdefault(
                key,
                {"label": key[0], "category": key[1], "new": key[0] not in known,
                 "frames": [], "ranges": [],
                 "confidence": {"high": 0, "medium": 0, "low": 0}},
            )  # fmt: skip
            entry["frames"].append(result["index"])
            entry["confidence"][tag["confidence"]] += 1
            extend_ranges(entry["ranges"], start, end)
    for entry in tags.values():
        entry["seconds"] = total_seconds(entry["ranges"])
    return sorted(tags.values(), key=lambda t: (-len(t["frames"]), t["label"]))


def aggregate_text(
    plan: dict[str, Any], tagged: dict[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    """On-screen text as read. Readings of the same text (see similar_text) with the same
    legibility become one entry that shows the most frequent spelling and lists the
    others as variants; a clear and a partial reading join only when identical. An
    entry is `confirmed: false` only when every reading of it is (see merge_reread)."""
    entries: list[dict[str, Any]] = []
    for result, start, end in spans(plan, tagged):
        seen: set[int] = set()
        for item in result.get("on_screen_text", []):
            number = next(
                (
                    n
                    for n, e in enumerate(entries)
                    if identical_text(e["first"], item["text"])
                    or (
                        e["legibility"] == item["legibility"]
                        and similar_text(e["first"], item["text"])
                    )
                ),
                None,
            )
            if number is None:
                number = len(entries)
                entries.append({"first": item["text"], "legibility": item["legibility"],
                                "spellings": Counter(), "clear": Counter(),
                                "detail": "low", "confirmed": False,
                                "frames": [], "ranges": []})  # fmt: skip
            entry = entries[number]
            entry["spellings"][item["text"]] += 1
            if item["legibility"] == "clear":
                entry["clear"][item["text"]] += 1
            if item["detail"] == "high":
                entry["detail"] = "high"  # read at high detail at least once
            if is_confirmed(item):
                entry["confirmed"] = True  # unconfirmed only if every reading is
            if number in seen:
                continue
            seen.add(number)
            entry["frames"].append(result["index"])
            extend_ranges(entry["ranges"], start, end)
    texts = []
    for entry in entries:
        # Shown: the most frequent fully readable spelling, else the most frequent one.
        best = (entry["clear"] or entry["spellings"]).most_common(1)[0][0]
        texts.append(
            {"text": best,
             "variants": [t for t, _ in entry["spellings"].most_common() if t != best],
             "legibility": "clear" if entry["clear"] else "partial",
             "detail": entry["detail"],
             **({} if entry["confirmed"] else {"confirmed": False}),
             "frames": entry["frames"],
             "ranges": entry["ranges"], "seconds": total_seconds(entry["ranges"])}
        )  # fmt: skip
    return sorted(texts, key=lambda t: (t["frames"][0], t["text"]))


def short_time(seconds: float) -> str:
    return fmt_time(seconds).removeprefix("00:")


def when(ranges: list[list[float]]) -> str:
    return ", ".join(f"{short_time(s)}-{short_time(e)}" for s, e in ranges)


def text_note(item: dict[str, Any]) -> str:
    notes = [
        *(["partly readable"] if item["legibility"] != "clear" else []),
        *(["unconfirmed"] if not is_confirmed(item) else []),
    ]
    return f" ({', '.join(notes)})" if notes else ""


def text_pass_line(document: dict[str, Any]) -> str:
    tp = document["text_pass"]
    line = f"{tp['status']}; {tp['frames_flagged']} frame(s) had text too small to read"
    if tp.get("frames_skipped"):
        line += f", {tp['frames_skipped']} not re-read (text too small in the source)"
    if tp["frames_reread"]:
        line += (
            f", {tp['frames_covered']} covered by {tp['frames_reread']} re-read frame(s): "
            f"text found for {tp['frames_with_text']}, nothing readable for "
            f"{tp['frames_covered'] - tp['frames_with_text']}"
        )
    return line


def text_table(
    texts: list[dict[str, Any]], is_video: bool, run_detail: str
) -> list[str]:
    """`detail: high` is the full-resolution re-read in a low-detail run, but the 768 px
    tagging frame in a high-detail run."""
    lines = [
        "| Text | When | Read at |" if is_video else "| Text | Read at |",
        "| --- | --- | --- |" if is_video else "| --- | --- |",
    ]
    for text in texts:
        read_at = "low detail"
        if text["detail"] == "high":
            read_at = "high detail" if run_detail == "high" else "full resolution"
        if not is_confirmed(text):
            read_at += ", not in the full-resolution re-read"
        row = f"| {cell(text['text'])} |"
        if is_video:
            row += f" {when(text['ranges'])} |"
        lines.append(f"{row} {read_at} |")
    return lines


def to_markdown(plan: dict[str, Any], document: dict[str, Any]) -> str:
    source, options = plan["source"], plan["options"]
    is_video = source["kind"] == "video"
    total = len(plan["frames"])
    length = f" ({fmt_time(source['duration_seconds'])})" if is_video else ""
    lines = [
        f"# Visual tags: {source['name']}",
        "",
        f"- Type: {source['kind']}{length}",
        f"- Frames tagged: {document['frames_tagged']} of {total}",
        (
            f"- Model: {options['model']} (detail {options['detail']}); confidence is the "
            "model's own estimate"
        ),
        f"- New tags (not used in this library before): {document['new_tags']}",
        f"- Small text re-read (cropped, full resolution): {text_pass_line(document)}",
        f"- Review status: {document['review_status']}",
        f"- Created: {document['created_at']}",
        "",
        '> Tags describe what is visible. People are tagged as "person", never identified.',
    ]
    if not document["complete"]:
        lines.append("> **Incomplete:** some frames were not tagged.")
    lines.extend(["", "## Tags"])
    for category in CATEGORIES:
        entries = [t for t in document["tags"] if t["category"] == category]
        if not entries:
            continue
        lines.extend(["", f"### {HEADINGS[category]}", ""])
        if is_video:
            lines.extend(
                ["| Tag | Frames | On screen | When |", "| --- | --- | --- | --- |"]
            )
        else:
            lines.extend(["| Tag | Confidence |", "| --- | --- |"])
        for tag in entries:
            label = cell(tag["label"]) + (" *(new)*" if tag["new"] else "")
            if is_video:
                lines.append(
                    f"| {label} | {len(tag['frames'])} of {total} | "
                    f"{short_time(tag['seconds'] or 0)} | {when(tag['ranges'])} |"
                )
            else:
                level = max(tag["confidence"], key=lambda k: tag["confidence"][k])
                lines.append(f"| {label} | {level} |")

    lines.extend(["", "## On-screen text", ""])
    if document["on_screen_text"]:
        lines.extend(
            [
                (
                    "> Read by the model. Confirm important text (registration numbers, "
                    "prices, dates) against the frame before relying on it."
                ),
            ]
        )
        read = document["on_screen_text"]
        clear = [t for t in read if t["legibility"] == "clear" and is_confirmed(t)]
        partial = [t for t in read if t["legibility"] != "clear" or not is_confirmed(t)]
        if clear:
            lines.extend(["", *text_table(clear, is_video, options["detail"])])
        if partial:
            lines.extend(
                ["", "### Partly readable or unconfirmed (check against the frame)", "",
                 ("> Some characters could not be read (shown as …), or the text was "
                  "read only at low detail and the full-resolution re-read of its frame "
                  "did not read it again. Not confirmed; check the frame."), "",
                 *text_table(partial, is_video, options["detail"])]
            )  # fmt: skip
    else:
        lines.append("_No readable text._")

    lines.extend(
        ["", "## Frames", "", "| Time | Frame | Summary | Tags | Text |",
         "| --- | --- | --- | --- | --- |"]
    )  # fmt: skip
    for frame in document["frames"]:
        time = (
            short_time(frame["time_seconds"])
            if frame["time_seconds"] is not None
            else "-"
        )
        image = f'<img src="frames/{frame["file"]}" width="160">'
        labels = (
            ", ".join(clean_label(t["label"]) for t in frame["tags"]) or "_not tagged_"
        )
        texts = "; ".join(t["text"] + text_note(t) for t in frame["on_screen_text"])
        lines.append(
            f"| {time} | {image} | {cell(frame['summary'] or '')} | {cell(labels)} "
            f"| {cell(texts)} |"
        )
    return "\n".join(lines) + "\n"


def finalize(job_dir: Path, keep_work: bool = False) -> dict[str, Any]:
    plan = json.loads((job_dir / "plan.json").read_text(encoding="utf-8"))
    tagged, reread, usage = load_results(job_dir)
    if not tagged:
        fail("no tagged frames found; nothing to save (the work folder was kept)")
    text_pass, text_complete = apply_text_pass(
        plan, tagged, reread, load_skipped(job_dir)
    )
    complete = text_complete and all(
        frame["index"] in tagged for frame in plan["frames"]
    )

    output_dir = Path(plan["output_dir"])
    files = ["tags.md", "tags.json", "metadata.json", "frames"]
    archived = archive_previous(output_dir, "tags.json", files, plan.get("replaces"))
    frames_out = output_dir / "frames"
    if frames_out.exists():
        shutil.rmtree(frames_out)
    frames_out.mkdir(parents=True)
    frames = []
    for frame in plan["frames"]:
        shutil.copy2(frame["file"], frames_out / Path(frame["file"]).name)
        result = tagged.get(frame["index"], {})
        frames.append(
            {
                "index": frame["index"],
                "time_seconds": frame["time_seconds"],
                "file": Path(frame["file"]).name,
                "summary": result.get("summary"),
                "tags": [
                    {**tag, "label": clean_label(tag["label"])}
                    for tag in result.get("tags", [])
                ],
                "on_screen_text": result.get("on_screen_text", []),
                # Pass 1 (low detail) saw text it could not read; text_reread says
                # what the full-resolution re-read made of it.
                "unreadable_text": bool(result.get("unreadable_text")),
                "text_reread": result.get("text_reread"),
                "text_low_detail": result.get("text_low_detail"),
                "text_from_frame": result.get("text_from_frame"),
                "text_crop": result.get("text_crop"),
                "tagged": frame["index"] in tagged,
            }
        )
    tags = aggregate(plan, tagged)
    document = {
        # 2: text items are {text, legibility, detail}, plus `confirmed: false` on pass-1
        # text a re-read of the frame did not read again; text_pass.status
        # 3: tag labels joined by hyphens (lib/tags.py)
        "version": 3,
        "processor": plan["processor"],
        "complete": complete,
        # Machine-made tags awaiting human review; shown to clients meanwhile.
        "review_status": "staging_pending",
        "source": plan["source"],
        "options": plan["options"],
        "provider": {
            "name": "openai",
            "model": plan["options"]["model"],
            "confidence": "model-reported, not calibrated",
        },
        "usage": usage,
        # prepare's estimates: the tagging requests (compare usage.tagging), and the most
        # the small-text re-read could add (compare usage.text_reread)
        "estimated_input_tokens": plan.get("estimated_input_tokens"),
        "text_reread_estimate": plan.get("text_reread_estimate"),
        "frames_tagged": len(tagged),
        "text_pass": text_pass,
        "existing_tags_offered": len(plan.get("existing_tags", [])),
        "new_tags": sum(tag["new"] for tag in tags),
        "tags": tags,
        "on_screen_text": aggregate_text(plan, tagged),
        "frames": frames,
        "resume_job_dir": None if complete else str(job_dir),
        "created_at": now_iso(),
    }
    write_json(output_dir / "tags.json", document)
    write_text(output_dir / "tags.md", to_markdown(plan, document))
    write_json(
        output_dir / "metadata.json",
        result_metadata(plan, "complete" if complete else "incomplete"),
    )
    # An incomplete job keeps its folder: tag.py can finish it without paying twice.
    if complete and not keep_work:
        shutil.rmtree(job_dir)

    return {
        "status": "complete" if complete else "incomplete",
        "output_dir": str(output_dir),
        "files": ["tags.md", "tags.json", "metadata.json", "frames/"],
        "previous_result": str(archived) if archived else None,
        "frames_tagged": len(tagged),
        "frames_total": len(plan["frames"]),
        "distinct_tags": len(tags),
        "new_tags": document["new_tags"],
        "text_pass": document["text_pass"],
        "on_screen_texts": len(document["on_screen_text"]),
        "usage": usage,
        "warnings": plan["warnings"],
        "resume_job_dir": document["resume_job_dir"],
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
