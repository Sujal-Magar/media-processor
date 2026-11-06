#!/usr/bin/env python3
"""translate-subtitles, step 1: the cues of a transcribed file's subtitles (the same cues
and times as its transcript.vtt, from lib/subtitles.py), numbered C1, C2, ..., with the
languages asked for and the organisation's details, into the material translate.py
sends. The tracks in the language most of the speech is in keep each cue as said: only
the words said in another language, and the forms of the organisation's name speech-to-
text writes (organisation.json heard_as), go to the model as spans S1, S2, ..., to be
translated (transcript.ne) and written by their sound (transcript.ne-spoken), so no word
said in that language can be reworded. Nothing here costs money. Writes work/translate-subtitles/<job>/plan.json and
prints a JSON summary, never the text.

    python3 processors/translate-subtitles/prepare.py input/interview.mov
        [--languages en,ne] [--force]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `lib`

from finalize import LANGUAGES, SPOKEN, split_spans, spoken_first, track_name
from translate import INSTRUCTIONS, request_text, schema

from lib.material import input_record, read_result
from lib.openai_api import estimate_text_tokens, setting, translate_model
from lib.organisation import load_organisation, organisation_section
from lib.subtitles import cues as subtitle_cues
from lib.workspace import (
    fail,
    new_job_dir,
    now_iso,
    output_dir_for,
    previous_created_at,
    print_json,
    sha256,
    write_json,
)

PROCESSOR = "translate-subtitles"
NAMES = {name.lower(): code for code, (name, _) in LANGUAGES.items()}


def request_languages(value: str | None) -> list[str]:
    """Language codes or names, comma-separated, each once; both languages by default."""
    if not value or not value.strip():
        return list(LANGUAGES)
    chosen = []
    for item in value.split(","):
        item = item.strip().lower()
        code = item if item in LANGUAGES else NAMES.get(item)
        if not code:
            fail(f"unknown language {item!r}; choose from {', '.join(f'{c} ({n})' for c, (n, _) in LANGUAGES.items())}")
        if code not in chosen:
            chosen.append(code)
    return chosen


def numbered(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    """The transcript's subtitle cues as C1, C2, ... with their times and speaker."""
    return [
        {"id": f"C{number}", "start": round(cue["start"], 3), "end": round(cue["end"], 3),
         "text": cue["text"], "speaker": cue["speaker"]}
        for number, cue in enumerate(subtitle_cues(transcript), 1)
    ]  # fmt: skip


def tracks(cues: list[dict[str, Any]], languages: list[str]) -> tuple[str | None, list[str]]:
    """The assembled track (the language most of the speech is in, when asked for) and
    the languages written as whole cues."""
    spoken = spoken_first(cues, list(LANGUAGES))[0]
    assembled = spoken if spoken in languages else None
    return assembled, [code for code in languages if code != assembled]


def with_spans(
    cues: list[dict[str, Any]], assembled: str, heard_as: list[str] | None = None
) -> list[dict[str, Any]]:
    """Mark the spans in each cue (its "parts", the spans by id) and return them."""
    spans: list[dict[str, Any]] = []
    for cue in cues:
        parts = split_spans(cue["text"], LANGUAGES[assembled][1], heard_as)
        if not any("span" in part for part in parts):
            continue
        for part in parts:
            if "span" in part:
                span = {"id": f"S{len(spans) + 1}", "cue": cue["id"], "text": part["span"]}
                if part.pop("name", False):
                    span["name"] = True
                spans.append(span)
                part["span"] = span["id"]
        cue["parts"] = parts
    return spans


def build_context(
    cues: list[dict[str, Any]],
    spans: list[dict[str, Any]],
    assembled: str | None,
    organisation: dict[str, Any] | None,
) -> str:
    lines = ["CUES (what was said, in the language spoken, in order; SPEAKER labels are not names)"]
    lines += [f"[{cue['id']}] {cue['text']}" for cue in cues]
    sections = ["\n".join(lines)]
    if spans:
        name = LANGUAGES[assembled][0]
        lines = [f"SPANS FOR THE {name.upper()} TRACK (words said in another language inside "
                 f"a cue; give only each one's {name}, to fit the words around it)"]  # fmt: skip
        lines += [f"[{span['id']} in {span['cue']}"
                  + (", the organisation's name as heard" if span.get("name") else "")
                  + f"] {span['text']}" for span in spans]  # fmt: skip
        sections.append("\n".join(lines))
    if section := organisation_section(organisation):
        sections.append(section)
    return "\n\n".join(sections)


def input_warnings(transcript: dict[str, Any], organisation: dict[str, Any] | None) -> list[str]:
    warnings = []
    if not transcript.get("complete"):
        warnings.append("The transcript is incomplete; parts that failed have no subtitles to translate.")
    spoken = [part for part in transcript.get("parts", []) if part.get("text")]
    if len(spoken) == 1:
        warnings.append(
            "The transcript is one part, so the cue times are estimated across the whole "
            "speech; /transcribe with timestamps 15 gives closer times (charged again)."
        )
    if organisation is None:
        warnings.append(
            "No organisation.json: the organisation's name is translated as the speech has "
            "it, and speech-to-text can mishear it."
        )
    return warnings


def ready_summary(
    cues: list[dict[str, Any]],
    spans: list[dict[str, Any]],
    options: dict[str, Any],
    organisation: dict[str, Any] | None,
    estimated_tokens: int,
    replaces: str | None,
    warnings: list[str],
) -> list[str]:
    """What the user sees before approving the paid step, every line every time."""
    return [
        f"Cues: {len(cues)}, from the transcript's subtitles (times as in transcript.vtt)",
        "Tracks: " + "; ".join(
            ([f"{track_name(options['assembled'])} and {track_name(options['spoken'])} kept as "
              f"said, with {len(spans)} spans of other words translated or written by their "
              "sound"] if options["assembled"] else [])
            + [f"{track_name(code)} translated cue by cue" for code in options["full"]]
        ),  # fmt: skip
        "Organisation: " + (organisation["name"] if organisation else "none (no organisation.json)"),
        f"Cost: one paid OpenAI request to {options['model']} at "
        f"{options['reasoning_effort']} effort, about {estimated_tokens:,} input tokens "
        "(rough; the answer holds every cue in each language)",
        "Replaces: "
        + (f"the result made at {replaces}, which moves to history/" if replaces else "nothing"),
        "Warnings: " + (" | ".join(warnings) if warnings else "none"),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help="the file transcribe ran on")
    parser.add_argument("--languages", help="comma-separated: en, ne (default both)")
    parser.add_argument("--force", action="store_true", help="translate again even if done")
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    if not source.is_file():
        fail(f"file not found: {args.source}")
    languages = request_languages(args.languages)

    digest = sha256(source)
    output_dir = output_dir_for(PROCESSOR, source, digest)
    transcript = read_result(output_dir_for("transcribe", source, digest) / "transcript.json")
    if transcript is None:
        print_json({"status": "missing_inputs", "missing": ["/transcribe"],
                    "message": "Run /transcribe on this file first."})  # fmt: skip
        return
    cues = numbered(transcript)
    if not cues:
        print_json({"status": "no_speech", "message": "The transcript holds no speech, so "
                    "there are no subtitles to translate."})  # fmt: skip
        return
    organisation = load_organisation()
    inputs = {"transcript": input_record(transcript), "organisation": organisation}
    previous = output_dir / "translation.json"
    done = read_result(previous)
    if done is not None and not args.force:
        saved = (done.get("options") or {}).get("languages")
        status = ("outdated" if done.get("inputs") != inputs
                  else "different_options" if saved != languages else "already_done")  # fmt: skip
        messages = {
            "already_done": "This file's subtitles are already translated into these "
            "languages. Use --force to pay again.",
            "outdated": "The transcript was made again, or organisation.json changed, since "
            "this translation was. Use --force to translate again (charged again).",
            "different_options": "This file's subtitles were translated into other "
            "languages. Use --force to translate into these (charged again).",
        }
        result = {"status": status, "output_dir": str(output_dir), "message": messages[status]}
        if status == "different_options":
            result["changed"] = {"languages": {"saved": saved, "requested": languages}}
        print_json(result)
        return
    # --force: finalize moves the result it replaces into history/ (see archive_previous).
    replaces = previous_created_at(previous)

    model = translate_model()
    effort = setting("OPENAI_TRANSLATE_REASONING_EFFORT", "low") or "low"
    assembled, full = tracks(cues, languages)
    heard_as = (organisation or {}).get("heard_as") or []
    spans = with_spans(cues, assembled, heard_as) if assembled else []
    # With an assembled track comes the same track as spoken: other words by their sound.
    spoken = f"{assembled}{SPOKEN}" if assembled else None
    options = {"model": model, "reasoning_effort": effort, "languages": languages,
               "assembled": assembled, "spoken": spoken, "full": full}  # fmt: skip
    context = build_context(cues, spans, assembled, organisation)
    warnings = input_warnings(transcript, organisation)
    estimated = estimate_text_tokens(
        INSTRUCTIONS + json.dumps(schema(full, assembled, spoken)) + request_text(full, assembled, spoken) + context
    )
    job_dir = new_job_dir(PROCESSOR, source)
    plan = {
        "version": 1,
        "processor": PROCESSOR,
        "status": "ready",
        "source": {"name": source.name, "path": str(source), "sha256": digest},
        "inputs": inputs,
        "organisation": organisation,
        "options": options,
        "cues": cues,
        "spans": spans,
        "context": context,
        "estimated_input_tokens": estimated,
        "warnings": warnings,
        "output_dir": str(output_dir),
        "replaces": replaces,
        "created_at": now_iso(),
    }
    write_json(job_dir / "plan.json", plan)
    summary = ready_summary(cues, spans, options, organisation, estimated, replaces, warnings)
    print_json(
        {
            "status": "ready",
            "job_dir": str(job_dir),
            "cues": len(cues),
            "spans": len(spans),
            "languages": languages,
            "organisation": organisation["name"] if organisation else None,
            "paid_requests": 1,
            "model": model,
            "reasoning_effort": effort,
            "estimated_input_tokens": estimated,
            "replaces": replaces,
            "warnings": warnings,
            "summary": summary,
            "summary_text": "\n".join(f"- {line}" for line in summary),
        }
    )


if __name__ == "__main__":
    main()
