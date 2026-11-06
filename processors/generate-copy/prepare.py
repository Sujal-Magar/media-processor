#!/usr/bin/env python3
"""generate-copy, step 1: gather what transcribe, tag-visuals and (if run) tag-topics
found for a file into the material generate.py sends, with the organisation's details
(organisation.json) and the platforms, language, translation, tone and brief asked for.
Nothing here costs money. Writes
work/generate-copy/<job>/plan.json and prints a JSON summary, never the material.

    python3 processors/generate-copy/prepare.py input/interview.mov
        [--platforms instagram-reels,tiktok,linkedin] [--language en] [--translate ne]
        [--tone "warm, hopeful"] [--brief "Promote the spring intake"] [--force]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `lib`

from finalize import PLATFORMS
from generate import INSTRUCTIONS, SCHEMA, request_text

from lib.material import (
    build_context,
    input_record,
    partial_section,
    read_result,
    screen_texts,
)
from lib.openai_api import copy_model, estimate_text_tokens, setting
from lib.organisation import load_organisation, organisation_section
from lib.tags import clean_label
from lib.workspace import (
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

PROCESSOR = "generate-copy"
DEFAULT_PLATFORMS = ["instagram-reels", "tiktok", "linkedin"]
LANGUAGES = {"en": "English", "ne": "Nepali", "hi": "Hindi"}
LANGUAGE_NAME = re.compile(r"[A-Za-z][A-Za-z ()-]{1,39}")
MAX_TONE_CHARS = 200
MAX_BRIEF_CHARS = 1000
# What the person asks for; another request for the same file is written anew.
REQUEST_KEYS = ("platforms", "language", "translate", "tone", "brief")


def language_name(value: str | None, default: str | None) -> str | None:
    """A code we know (en, ne, hi) as its English name, or a language name."""
    if not value or not value.strip():
        return default
    value = value.strip()
    if value.lower() in LANGUAGES:
        return LANGUAGES[value.lower()]
    if not LANGUAGE_NAME.fullmatch(value):
        fail(f"not a language: {value!r} (use a name such as Nepali, or en, ne, hi)")
    return value.title()


def free_text(value: str | None, name: str, limit: int) -> str | None:
    value = re.sub(r"\s+", " ", value or "").strip()
    if len(value) > limit:
        fail(f"the {name} has {len(value)} characters; at most {limit} are accepted")
    return value or None


def request_options(
    platforms: str | None,
    language: str | None,
    translate: str | None,
    tone: str | None,
    brief: str | None,
) -> dict[str, Any]:
    chosen = DEFAULT_PLATFORMS
    if platforms:
        chosen = list(
            dict.fromkeys(clean_label(p) for p in platforms.split(",") if p.strip())
        )
        unknown = [p for p in chosen if p not in PLATFORMS]
        if unknown or not chosen:
            fail(
                f"unknown platform {', '.join(unknown) or platforms!r}; "
                f"choose from {', '.join(PLATFORMS)}"
            )
    written = language_name(language, "English")
    translated = language_name(translate, None)
    if translated == written:
        fail(f"the copy is already written in {written}; choose another translation")
    return {
        "platforms": chosen,
        "language": written,
        "translate": translated,
        "tone": free_text(tone, "tone", MAX_TONE_CHARS),
        "brief": free_text(brief, "brief", MAX_BRIEF_CHARS),
    }


def input_records(
    transcript: dict[str, Any] | None,
    tags: dict[str, Any] | None,
    topics: dict[str, Any] | None,
    organisation: dict[str, Any] | None,
) -> dict[str, Any]:
    """When each result was made, and the organisation's details as they were."""
    return {
        "transcript": input_record(transcript),
        "tags": input_record(tags),
        "topics": input_record(topics),
        "organisation": organisation,
    }


def previous_status(
    previous: dict[str, Any], inputs: dict[str, Any], request: dict[str, Any]
) -> str:
    """already_done; outdated when an input was made again (or added) since this copy
    was; different_options when the copy was written for another request."""
    if previous.get("inputs") != inputs:
        return "outdated"
    return "different_options" if changed_options(previous, request) else "already_done"


def changed_options(
    previous: dict[str, Any], request: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Each requested option that differs from the saved copy's, with both values: a
    tone or brief left out of the new request is dropped, not kept."""
    saved = previous.get("options") or {}
    return {
        key: {"saved": saved.get(key), "requested": request[key]}
        for key in REQUEST_KEYS
        if saved.get(key) != request[key]
    }


def input_warnings(
    transcript: dict[str, Any],
    tags: dict[str, Any],
    topics: dict[str, Any] | None,
    organisation: dict[str, Any] | None,
) -> list[str]:
    warnings = []
    spoken = [part for part in transcript.get("parts", []) if part.get("text")]
    if not spoken:
        warnings.append(
            "The transcript holds no speech, so the script has no soundbites; it is "
            "built from the pictures only."
        )
    elif len(spoken) == 1:
        part = spoken[0]
        warnings.append(
            "The transcript is one part, so every soundbite carries its whole time "
            f"({fmt_time(part['start_seconds'])}-{fmt_time(part['end_seconds'])}); the "
            "editor finds each one by ear."
        )
    if spoken and not transcript.get("complete"):
        warnings.append(
            "The transcript is incomplete; the copy covers only what it holds."
        )
    if not tags.get("complete"):
        warnings.append(
            "The visual tags are incomplete; the copy covers only what they hold."
        )
    if topics is None:
        warnings.append(
            "No topic tags: themes and hashtags come from the transcript and visual "
            "tags alone. /tag-topics adds them first (one more paid request)."
        )
    if organisation is None:
        warnings.append(
            "No organisation.json: the organisation's name is taken from the speech and "
            "the screen, and speech-to-text can mishear it. Copy organisation.example.json "
            "to organisation.json and fill it in."
        )
    return warnings


def ready_summary(
    inputs: dict[str, Any],
    options: dict[str, Any],
    estimated_tokens: int,
    replaces: str | None,
    warnings: list[str],
) -> list[str]:
    """What the user sees before approving the paid step, every line every time."""
    yes = {True: "yes", False: "no"}
    organisation = inputs["organisation"]
    return [
        f"Inputs read: transcript {yes[inputs['transcript'] is not None]}, visual tags "
        f"{yes[inputs['tags'] is not None]}, topic tags {yes[inputs['topics'] is not None]}",
        "Organisation: "
        + (organisation["name"] if organisation else "none (no organisation.json)"),
        f"Platforms: {', '.join(PLATFORMS[p][0] for p in options['platforms'])}; written "
        f"in {options['language']}; translation: {options['translate'] or 'none'}",
        f"Tone: {options['tone'] or 'none'}; brief: {options['brief'] or 'none'}",
        f"Cost: one paid OpenAI request to {options['model']} at "
        f"{options['reasoning_effort']} effort, about {estimated_tokens:,} input tokens "
        "(rough; reasoning adds output tokens)",
        "Replaces: "
        + (f"the result made at {replaces}, which moves to history/" if replaces else "nothing"),
        "Warnings: " + (" | ".join(warnings) if warnings else "none"),
    ]


def topics_section(topics: dict[str, Any] | None) -> str:
    if not topics:
        return ""
    lines = ["TOPIC TAGS (made by a model from the same material; themes, not facts)"]
    if topics.get("summary"):
        lines.append(f"Summary: {topics['summary']}")
    for category in ("type", "topic", "entity"):
        if topics.get(category):
            lines.append(f"{category}: {', '.join(topics[category])}")
    return "\n".join(lines) if len(lines) > 1 else ""


def build_material(
    transcript: dict[str, Any],
    tags: dict[str, Any],
    topics: dict[str, Any] | None,
    organisation: dict[str, Any] | None,
) -> tuple[str, dict[str, dict[str, Any]], list[str]]:
    """The shared material (lib.material) with each sentence's text for the soundbites,
    each visual tag's time ranges for the B-roll and each on-screen text's words (to
    notice the copy repeating them), then the partly read text, the topic tags and the
    organisation's details."""
    context, refs, warnings = build_context(transcript, tags, with_text=True)
    for tag in tags.get("tags", []):
        ref = f"V:{clean_label(str(tag.get('label') or ''))}"
        if ref in refs and "ranges" not in refs[ref]:
            refs[ref]["ranges"] = tag.get("ranges") or []
    sent = [
        item
        for item in tags.get("on_screen_text", [])
        if item.get("legibility") == "clear" and item.get("confirmed", True) is not False
    ]
    for number, item in enumerate(sent, 1):  # numbered as lib.material numbers them
        if f"T{number}" in refs:
            refs[f"T{number}"]["text"] = item["text"]
    sections = [partial_section(tags), topics_section(topics), organisation_section(organisation)]
    context = "\n\n".join([context, *(section for section in sections if section)])
    return context, refs, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "source", type=Path, help="the file transcribe and tag-visuals ran on"
    )
    parser.add_argument("--platforms", help=f"comma-separated: {', '.join(PLATFORMS)}")
    parser.add_argument("--language", help="language to write in (default English)")
    parser.add_argument("--translate", help="also translate hooks and captions into it")
    parser.add_argument("--tone", help=f"tone of voice, at most {MAX_TONE_CHARS} chars")
    parser.add_argument("--brief", help=f"what the copy is for, at most {MAX_BRIEF_CHARS}")
    parser.add_argument("--force", action="store_true", help="write again even if done")
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    if not source.is_file():
        fail(f"file not found: {args.source}")
    request = request_options(
        args.platforms, args.language, args.translate, args.tone, args.brief
    )

    digest = sha256(source)
    output_dir = output_dir_for(PROCESSOR, source, digest)
    transcript = read_result(
        output_dir_for("transcribe", source, digest) / "transcript.json"
    )
    tags = read_result(output_dir_for("tag-visuals", source, digest) / "tags.json")
    topics = read_result(output_dir_for("tag-topics", source, digest) / "topics.json")
    organisation = load_organisation()
    if transcript is None or tags is None:
        lacking = [
            command
            for command, result in (("/transcribe", transcript), ("/tag-visuals", tags))
            if result is None
        ]
        print_json(
            {
                "status": "missing_inputs",
                "missing": lacking,
                "message": f"Run {' and '.join(lacking)} on this file first "
                "(/process-video runs both).",
            }
        )
        return
    inputs = input_records(transcript, tags, topics, organisation)
    previous = output_dir / "copy.json"
    done = read_result(previous)
    if done is not None and not args.force:
        status = previous_status(done, inputs, request)
        messages = {
            "already_done": "This file's copy for this request is up to date. Use "
            "--force to pay again.",
            "outdated": "The transcript, visual tags or topic tags were made again (or "
            "added), or organisation.json changed, since this copy was. Use --force to "
            "write it again (charged again).",
            "different_options": "This file's copy was written for another request "
            "(platforms, language, translation, tone or brief). Use --force to write "
            "it for this one (charged again).",
        }
        result = {"status": status, "output_dir": str(output_dir), "message": messages[status]}
        if status == "different_options":
            result["changed"] = changed_options(done, request)
        print_json(result)
        return
    # --force: finalize moves the result it replaces into history/ (see archive_previous).
    replaces = previous_created_at(previous)

    context, refs, warnings = build_material(transcript, tags, topics, organisation)
    warnings = input_warnings(transcript, tags, topics, organisation) + warnings
    model = copy_model()
    effort = setting("OPENAI_COPY_REASONING_EFFORT", "low") or "low"
    options = {"model": model, "reasoning_effort": effort, **request}
    source_info = tags.get("source", {})
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
        "organisation": organisation,
        "options": options,
        "refs": refs,
        "screen_texts": screen_texts(tags),
        "context": context,
        "estimated_input_tokens": estimate_text_tokens(
            INSTRUCTIONS + json.dumps(SCHEMA) + request_text(options) + context
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
            "inputs": {name: record is not None for name, record in inputs.items()},
            "organisation": organisation["name"] if organisation else None,
            "paid_requests": 1,
            "model": model,
            "reasoning_effort": effort,
            "estimated_input_tokens": plan["estimated_input_tokens"],
            "request": request,
            "replaces": replaces,
            "warnings": warnings,
            "summary": ready_summary(
                inputs, options, plan["estimated_input_tokens"], replaces, warnings
            ),
        }
    )


if __name__ == "__main__":
    main()
