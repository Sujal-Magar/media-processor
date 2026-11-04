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
from collections.abc import Iterator
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `lib`

from lib.workspace import (  # noqa: E402
    fail,
    fmt_time,
    is_job_dir,
    now_iso,
    print_json,
    write_json,
    write_text,
)

CATEGORIES = ("object", "scene", "activity", "attribute")
HEADINGS = {"object": "Objects", "scene": "Scenes", "activity": "Activities",
            "attribute": "Attributes"}  # fmt: skip


def clean_label(label: str) -> str:
    return re.sub(r"\s+", " ", label.strip().lower())


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def cell(value: str) -> str:
    """Make a value safe inside a Markdown table cell."""
    return value.replace("|", "\\|").replace("\n", " ")


def load_results(
    job_dir: Path,
) -> tuple[dict[int, dict[str, Any]], dict[int, dict[str, Any]], dict[str, int]]:
    """Pass-1 answers by frame, pass-2 (high-detail text) answers by frame, and usage."""
    tagged: dict[int, dict[str, Any]] = {}
    reread: dict[int, dict[str, Any]] = {}
    usage = {"requests": 0, "input_tokens": 0, "output_tokens": 0}
    for prefix, target in (("batch", tagged), ("text", reread)):
        for result_file in sorted((job_dir / "results").glob(f"{prefix}_*.json")):
            result = json.loads(result_file.read_text(encoding="utf-8"))
            usage["requests"] += 1
            for key in ("input_tokens", "output_tokens"):
                usage[key] += int((result.get("usage") or {}).get(key) or 0)
            for frame in result["frames"]:
                target[frame["index"]] = frame
    return tagged, reread, usage


def needs_text_pass(
    plan: dict[str, Any], tagged: dict[int, dict[str, Any]]
) -> list[int]:
    """Frames to re-read at high detail: low-detail frames with unreadable text."""
    options = plan["options"]
    if not options.get("text_pass", True) or options["detail"] != "low":
        return []
    return [
        frame["index"]
        for frame in plan["frames"]
        if tagged.get(frame["index"], {}).get("unreadable_text")
    ]


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
    """On-screen text exactly as read; identical text (ignoring case) is merged."""
    texts: dict[str, dict[str, Any]] = {}
    for result, start, end in spans(plan, tagged):
        seen: set[str] = set()
        for raw in result.get("on_screen_text", []):
            text = clean_text(raw)
            key = text.casefold()
            if not text or key in seen:
                continue
            seen.add(key)
            entry = texts.setdefault(key, {"text": text, "frames": [], "ranges": []})
            entry["frames"].append(result["index"])
            extend_ranges(entry["ranges"], start, end)
    for entry in texts.values():
        entry["seconds"] = total_seconds(entry["ranges"])
    return sorted(texts.values(), key=lambda t: (t["frames"][0], t["text"]))


def short_time(seconds: float) -> str:
    text = fmt_time(seconds)
    return text[3:] if text.startswith("00:") else text


def when(ranges: list[list[float]]) -> str:
    return ", ".join(f"{short_time(s)}-{short_time(e)}" for s, e in ranges)


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
        f"- Model: {options['model']} (detail {options['detail']}); confidence is the "
        "model's own estimate",
        f"- New tags (not used in this library before): {document['new_tags']}",
        f"- Small text re-read (cropped, full resolution): {document['text_pass']['frames_covered']} of "
        f"{document['text_pass']['frames_flagged']} flagged frame(s), from "
        f"{document['text_pass']['frames_reread']} re-read frame(s)",
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
                "> Read by the model. Confirm important text (registration numbers, "
                "prices, dates) against the frame before relying on it.",
                "",
                "| Text | When |" if is_video else "| Text |",
                "| --- | --- |" if is_video else "| --- |",
            ]
        )
        for text in document["on_screen_text"]:
            row = f"| {cell(text['text'])} |"
            lines.append(f"{row} {when(text['ranges'])} |" if is_video else row)
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
        texts = "; ".join(clean_text(t) for t in frame["on_screen_text"])
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
    flagged = needs_text_pass(plan, tagged)
    # Each re-read frame stands for its run of flagged frames (see text_runs).
    covered = {
        index: frame_index
        for frame_index, result in reread.items()
        for index in result.get("covers", [frame_index])
    }
    complete = all(frame["index"] in tagged for frame in plan["frames"]) and all(
        index in covered for index in flagged
    )
    # Sharp, cropped readings replace the low-detail ones for every frame they cover.
    for index, source_index in covered.items():
        if index in tagged:
            tagged[index] = {
                **tagged[index],
                "on_screen_text": reread[source_index].get("on_screen_text", []),
                "text_detail": "high",
                "text_from_frame": source_index,
                "text_crop": reread[source_index].get("crop"),
            }

    output_dir = Path(plan["output_dir"])
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
                "tags": result.get("tags", []),
                "on_screen_text": result.get("on_screen_text", []),
                "text_detail": result.get("text_detail", plan["options"]["detail"]),
                "unreadable_text": bool(result.get("unreadable_text")),
                "text_from_frame": result.get("text_from_frame"),
                "text_crop": result.get("text_crop"),
                "tagged": frame["index"] in tagged,
            }
        )
    tags = aggregate(plan, tagged)
    document = {
        "version": 1,
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
        "frames_tagged": len(tagged),
        "text_pass": {
            "frames_flagged": len(flagged),
            "frames_reread": len(reread),
            "frames_covered": len(covered),
        },
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
    write_json(output_dir / "metadata.json", plan)
    # An incomplete job keeps its folder: tag.py can finish it without paying twice.
    if complete and not keep_work:
        shutil.rmtree(job_dir)

    return {
        "status": "complete" if complete else "incomplete",
        "output_dir": str(output_dir),
        "files": ["tags.md", "tags.json", "metadata.json", "frames/"],
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
