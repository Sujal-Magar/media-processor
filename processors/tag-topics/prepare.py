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
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `lib`

from tag import INSTRUCTIONS, SCHEMA, vocabulary_text

from lib.material import (
    build_context,
    input_record,
    partial_section,
    read_result,
    visual_labels,
)
from lib.openai_api import estimate_text_tokens, setting, topic_model
from lib.organisation import load_organisation, organisation_section
from lib.tags import tag_library
from lib.workspace import (
    OUTPUT,
    fail,
    new_job_dir,
    now_iso,
    output_dir_for,
    previous_created_at,
    print_json,
    sha256,
    write_json,
)

PROCESSOR = "tag-topics"
# Topic tags already in the library, offered to the model for reuse (most used first).
MAX_EXISTING_TAGS = 300


def previous_status(previous: dict[str, Any], inputs: dict[str, Any]) -> str:
    """already_done, or outdated when the transcript or tags were made again (or one was
    added), or organisation.json changed, since these topics were."""
    return "already_done" if previous.get("inputs") == inputs else "outdated"


def build_material(
    transcript: dict[str, Any] | None,
    tags: dict[str, Any] | None,
    organisation: dict[str, Any] | None,
) -> tuple[str, dict[str, dict[str, Any]], list[str]]:
    """The shared material (lib.material), then the partly read on-screen text and the
    organisation's details, both only for spelling names."""
    context, refs, warnings = build_context(transcript, tags)
    sections = [partial_section(tags or {}), organisation_section(organisation)]
    context = "\n\n".join([context, *(section for section in sections if section)])
    return context, refs, warnings


def input_warnings(
    transcript: dict[str, Any] | None,
    tags: dict[str, Any] | None,
    organisation: dict[str, Any] | None,
) -> list[str]:
    warnings = []
    if organisation is None:
        warnings.append(
            "No organisation.json: the organisation's name is taken from the speech and "
            "the screen, and speech-to-text can mishear it. Copy organisation.example.json "
            "to organisation.json and fill it in."
        )
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
    organisation = load_organisation()
    inputs = {
        "transcript": input_record(transcript),
        "tags": input_record(tags),
        "organisation": organisation,
    }
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
                    "added), or organisation.json changed, since these topics were. Use "
                    "--force to make them again (charged again)."
                ),
            }
        )
        return
    # --force: finalize moves the result it replaces into history/ (see archive_previous).
    replaces = previous_created_at(previous)

    context, refs, warnings = build_material(transcript, tags, organisation)
    warnings = input_warnings(transcript, tags, organisation) + warnings
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
