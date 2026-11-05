#!/usr/bin/env python3
"""tag-topics, step 1: gather what transcribe and tag-visuals found for a file into the
material tag.py sends, plus the topic tags already used in output/tag-topics/ (the
folder's topic library). Nothing here costs money. Writes work/tag-topics/<job>/plan.json
and prints a JSON summary, never the transcript or the tags.

    python3 processors/tag-topics/prepare.py input/interview.mov [--force]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `lib`

from tag import INSTRUCTIONS, SCHEMA, vocabulary_text

from lib.openai_api import estimate_text_tokens, setting, topic_model
from lib.tags import clean_label, tag_library
from lib.workspace import (
    OUTPUT,
    fail,
    fmt_time,
    new_job_dir,
    now_iso,
    output_dir_for,
    previous_created_at,
    print_json,
    sha256,
    write_json,
)

PROCESSOR = "tag-topics"
# Most transcript characters sent (about 12,000 tokens of English); the rest is cut.
MAX_SPEECH_CHARS = 48_000
MAX_VISUAL_TAGS = 60  # most seen first
MAX_TEXTS = 60
# Topic tags already in the library, offered to the model for reuse (most used first).
MAX_EXISTING_TAGS = 300
# A sentence ends at . ! ? or the Devanagari danda, followed by a space.
SENTENCE_END = re.compile(r"(?<=[.!?।॥])\s+")


def read_result(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def input_record(result: dict[str, Any] | None) -> dict[str, Any] | None:
    """What topics.json remembers of an input, to notice when it is made again."""
    if result is None:
        return None
    return {
        "created_at": result.get("created_at"),
        "complete": bool(result.get("complete")),
    }


def previous_status(previous: dict[str, Any], inputs: dict[str, Any]) -> str:
    """already_done, or outdated when the transcript or tags were made again (or one was
    added) since these topics were."""
    return "already_done" if previous.get("inputs") == inputs else "outdated"


def input_warnings(
    transcript: dict[str, Any] | None, tags: dict[str, Any] | None
) -> list[str]:
    warnings = []
    if transcript is None and tags and tags.get("source", {}).get("kind") == "video":
        warnings.append(
            "No transcript: topics come from the pictures and on-screen text only. Run "
            "/transcribe first if the video has speech."
        )
    if tags is None:
        warnings.append(
            "No visual tags: topics come from the speech only. Run /tag-visuals first "
            "to include the pictures and on-screen text."
        )
    if transcript is not None and not transcript.get("complete"):
        warnings.append("The transcript is incomplete; topics cover only what it holds.")
    if tags is not None and not tags.get("complete"):
        warnings.append("The visual tags are incomplete; topics cover only what they hold.")
    return warnings


def visual_labels(tags: dict[str, Any]) -> list[tuple[str, str, float | None]]:
    """(label, category, seconds on screen) per visual tag, most seen first. Labels are
    cleaned: results saved before hyphens still have spaces."""
    seen: set[str] = set()
    labels = []
    for tag in tags.get("tags", []):
        label = clean_label(str(tag.get("label") or ""))
        if label and label not in seen:
            seen.add(label)
            labels.append((label, tag.get("category", ""), tag.get("seconds")))
    return labels


def sentences(text: str) -> list[str]:
    return [sentence for sentence in SENTENCE_END.split(text.strip()) if sentence]


def speech_section(
    transcript: dict[str, Any],
) -> tuple[list[str], dict[str, dict[str, Any]], str | None]:
    """The transcript's parts with their times, each split into sentences S1, S2, ...
    (numbered on through the file), cut after MAX_SPEECH_CHARS. A part can span minutes,
    so a reference also names its sentence within the part. Returns the lines, their
    references and a warning if cut."""
    parts = [part for part in transcript.get("parts", []) if part.get("text")]
    total = sum(len(part["text"]) for part in parts)
    lines, refs, left, number = [], {}, MAX_SPEECH_CHARS, 0
    for part in parts:
        if left <= 0:
            break
        start, end = part["start_seconds"], part["end_seconds"]
        part_lines = [f"[{fmt_time(start)}-{fmt_time(end)}]"]
        for index, sentence in enumerate(sentences(part["text"]), 1):
            if left <= 0:
                break
            number += 1
            ref = f"S{number}"
            part_lines.append(f"[{ref}] {sentence[:left]}")
            refs[ref] = {
                "source": "speech",
                "start_seconds": start,
                "end_seconds": end,
                "sentence": index,
            }
            left -= len(sentence)
        lines.append("\n".join(part_lines))
    warning = (
        f"The transcript has {total:,} characters; only the first "
        f"{MAX_SPEECH_CHARS:,} are sent, so topics from later speech can be missed."
        if total > MAX_SPEECH_CHARS
        else None
    )
    return lines, refs, warning


def visual_sections(
    tags: dict[str, Any],
) -> tuple[list[str], list[str], dict[str, dict[str, Any]]]:
    """Visual tags as V:<label>, and clearly read, confirmed on-screen text as T1, T2,
    ... Partial or unconfirmed text is left out: it may be misread or invented."""
    visual, refs = [], {}
    for label, category, seconds in visual_labels(tags)[:MAX_VISUAL_TAGS]:
        ref = f"V:{label}"
        visual.append(f"[{ref}] {category}" + (f", on screen {seconds:g} s" if seconds else ""))
        refs[ref] = {"source": "visual", "label": label}
    readable = [
        item
        for item in tags.get("on_screen_text", [])
        if item.get("legibility") == "clear" and item.get("confirmed", True) is not False
    ]
    texts = []
    for number, item in enumerate(readable[:MAX_TEXTS], 1):
        ref = f"T{number}"
        ranges = item.get("ranges") or []
        when = f" {fmt_time(ranges[0][0])}" if ranges else ""
        texts.append(f'[{ref}{when}] "{item["text"]}"')
        refs[ref] = {"source": "on_screen_text", "ranges": ranges}
    return visual, texts, refs


def build_context(
    transcript: dict[str, Any] | None, tags: dict[str, Any] | None
) -> tuple[str, dict[str, dict[str, Any]], list[str]]:
    """The material tag.py sends: a header (kind and length, never the file name, which
    can hold a person's name), speech, visual tags and on-screen text. Returns the text,
    the references finalize maps back to times, and warnings."""
    source = (tags or transcript or {}).get("source", {})
    duration = source.get("duration_seconds")
    header = f"Media: {source.get('kind') or 'audio or video'}" + (
        f", {fmt_time(duration)} long" if duration else ""
    )
    sections, refs, warnings = [header], {}, []
    if transcript:
        lines, speech_refs, warning = speech_section(transcript)
        if lines:
            sections.append(
                "SPEECH (transcript in the language spoken; SPEAKER 0, SPEAKER 1 are "
                "labels, not names)\n\n" + "\n\n".join(lines)
            )
        refs.update(speech_refs)
        if warning:
            warnings.append(warning)
    if tags:
        visual, texts, visual_refs = visual_sections(tags)
        if visual:
            sections.append(
                "VISUAL TAGS (what the pictures show, most seen first)\n"
                + "\n".join(visual)
            )
        if texts:
            sections.append(
                "ON-SCREEN TEXT (read from the frames by a model; can be wrong)\n"
                + "\n".join(texts)
            )
        refs.update(visual_refs)
        # Results saved before legibility was recorded: their text was never checked.
        if any("legibility" not in item for item in tags.get("on_screen_text", [])):
            warnings.append(
                "The visual tags were saved before on-screen text was checked for "
                "legibility, so their text was not sent. Run /tag-visuals with force to "
                "include it (charged again)."
            )
    return "\n\n".join(sections), refs, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "source", type=Path, help="the file transcribe or tag-visuals ran on"
    )
    parser.add_argument("--force", action="store_true", help="tag again even if done")
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    if not source.is_file():
        fail(f"file not found: {args.source}")

    digest = sha256(source)
    output_dir = output_dir_for(PROCESSOR, source, digest)
    transcript = read_result(
        output_dir_for("transcribe", source, digest) / "transcript.json"
    )
    tags = read_result(output_dir_for("tag-visuals", source, digest) / "tags.json")
    if transcript is None and tags is None:
        print_json(
            {
                "status": "missing_inputs",
                "message": "Nothing to read yet: run /transcribe or /tag-visuals on this "
                "file first (/process-video runs both).",
            }
        )
        return
    inputs = {"transcript": input_record(transcript), "tags": input_record(tags)}
    previous = output_dir / "topics.json"
    done = read_result(previous)
    if done is not None and not args.force:
        status = previous_status(done, inputs)
        print_json(
            {
                "status": status,
                "output_dir": str(output_dir),
                "message": (
                    "This file's topics are up to date. Use --force to pay again."
                    if status == "already_done"
                    else "The transcript or visual tags were made again (or one was "
                    "added) since these topics were. Use --force to make them again "
                    "(charged again)."
                ),
            }
        )
        return
    # --force: finalize moves the result it replaces into history/ (see archive_previous).
    replaces = previous_created_at(previous)

    context, refs, warnings = build_context(transcript, tags)
    warnings = input_warnings(transcript, tags) + warnings
    existing = tag_library(
        OUTPUT / PROCESSOR, "topics.json", output_dir, MAX_EXISTING_TAGS
    )
    model = topic_model()
    effort = setting("OPENAI_TOPIC_REASONING_EFFORT", "low") or "low"
    source_info = (tags or transcript or {}).get("source", {})
    job_dir = new_job_dir(PROCESSOR, source)
    plan = {
        "version": 1,
        "processor": PROCESSOR,
        "status": "ready",
        "source": {
            "name": source.name,
            "path": str(source),
            "sha256": digest,
            "kind": source_info.get("kind"),
            "duration_seconds": source_info.get("duration_seconds"),
        },
        "inputs": inputs,
        "options": {"model": model, "reasoning_effort": effort},
        "existing_tags": existing,
        "visual": [label for label, _, _ in visual_labels(tags or {})],
        "refs": refs,
        "context": context,
        "estimated_input_tokens": estimate_text_tokens(
            INSTRUCTIONS + json.dumps(SCHEMA) + vocabulary_text(existing) + context
        ),
        "warnings": warnings,
        "output_dir": str(output_dir),
        "replaces": replaces,
        "created_at": now_iso(),
    }
    write_json(job_dir / "plan.json", plan)
    print_json(
        {
            "status": "ready",
            "job_dir": str(job_dir),
            "inputs": {
                "transcript": transcript is not None,
                "visual_tags": tags is not None,
            },
            "paid_requests": 1,
            "model": model,
            "reasoning_effort": effort,
            "estimated_input_tokens": plan["estimated_input_tokens"],
            "existing_tags": len(existing),
            "replaces": replaces,
            "warnings": warnings,
        }
    )


if __name__ == "__main__":
    main()
