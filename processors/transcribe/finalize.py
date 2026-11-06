#!/usr/bin/env python3
"""transcribe, step 3: collect the transcript ElevenLabs saved for each part and write
output/transcribe/<name>-<hash>/transcript.md, transcript.json and metadata.json, plus
subtitles (transcript.vtt and transcript.srt, with estimated times; see subtitles.py).

Prints only paths and counts, never the transcript, so the text stays out of the chat.

    python3 processors/transcribe/finalize.py work/transcribe/<job> [--keep-work]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import unicodedata
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
from servers.elevenlabs import PACKAGE, STT_AUDIO_EVENTS, STT_LOGGING, STT_MODEL
from subtitles import FILES as SUBTITLE_FILES
from subtitles import write_subtitles

SPEAKER_LINE = re.compile(r"^(SPEAKER \w+):\s?(.*)$")
# The MCP tool reports no model; the pinned server version fixes it (servers/elevenlabs.py).
PINNED_BY = PACKAGE.replace("==", " ")


def read_part(part: dict[str, Any]) -> str | None:
    """The server names files stt_<name>_<time>.txt; each part has its own folder."""
    files = sorted(
        Path(part["transcript_dir"]).glob("stt_*.txt"), key=lambda f: f.stat().st_mtime
    )
    if not files:
        return None
    # NFC only joins equivalent Unicode forms (matters for Devanagari); words are untouched.
    return unicodedata.normalize("NFC", files[-1].read_text(encoding="utf-8")).strip()


def track_text(source: dict[str, Any]) -> str:
    if source.get("channel") is None:
        return str(source["track"])
    return (
        f"{source['track']}, channel {source['channel']} only (the others are silent)"
    )


def normalized_text(plan: dict[str, Any]) -> str:
    before = plan.get("levels", {}).get("before_normalize")
    if not plan["options"]["normalize"]:
        return "no"
    if not before:
        return "yes"
    return f"yes (average {before['mean_db']:.1f} dB before, {plan['levels']['mean_db']:.1f} dB after)"


def language_text(language: str | None) -> str:
    if not language:
        return "auto-detect"
    return (
        f"{language}, forced: speech in other languages may be translated into "
        f"{language} or left out"
    )


def timestamps_text(options: dict[str, Any], parts: int) -> str:
    if options.get("part_seconds") is None:
        return "per part, split at pauses" if parts > 1 else "none"
    limit = f"up to about {options['part_seconds']:g} s"
    if parts == 1:
        return f"one part (the audio fits in one part of {limit})"
    return f"per part, split at pauses ({parts} parts of {limit})"


def to_markdown(
    plan: dict[str, Any], parts: list[dict[str, Any]], complete: bool
) -> str:
    source, options = plan["source"], plan["options"]
    several = len(parts) > 1
    # Asked for timestamps: every part gets a time heading, even when there is one part.
    timestamps = options.get("part_seconds") is not None
    lines = [
        f"# Transcript: {source['name']}",
        "",
        f"- Length: {fmt_time(source['duration_seconds'])}",
        (
            f"- Language requested: {language_text(options['language'])} "
            "(detected language is not reported by the ElevenLabs MCP tool)"
        ),
        f"- Speaker labels: {'yes' if options['diarize'] else 'no'}",
        f"- Timestamps: {timestamps_text(options, len(parts))}",
        f"- Audio track: {track_text(source)}",
        f"- Normalized: {normalized_text(plan)}",
        f"- Model: {STT_MODEL} (fixed by {PINNED_BY})",
        f"- Created: {plan['finalized_at']}",
        "",
        "> Original-language output from ElevenLabs. Not translated or edited.",
    ]
    if STT_LOGGING:
        lines.append(
            "> ElevenLabs keeps the audio it received (request logging is on)."
        )
    if several and options["diarize"]:
        lines.append("> Speaker numbers restart in every part.")
    if not complete:
        missing = [str(p["index"]) for p in parts if p["missing"]]
        lines.append(
            f"> **Incomplete:** part(s) {', '.join(missing)} were not transcribed."
        )
    for part in parts:
        lines.append("")
        if timestamps or several:
            start, end = fmt_time(part["start_seconds"]), fmt_time(part["end_seconds"])
            lines.extend([f"## {start} - {end}", ""])
        if part["missing"]:
            lines.append("_Not transcribed._")
        elif not part["text"]:
            lines.append("_No speech._")
        for paragraph in filter(None, (p.strip() for p in part["text"].splitlines())):
            match = SPEAKER_LINE.match(paragraph)
            lines.extend([f"**{match[1]}:** {match[2]}" if match else paragraph, ""])
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("job_dir", type=Path)
    parser.add_argument("--keep-work", action="store_true", help="keep extracted audio")
    args = parser.parse_args()

    job_dir = args.job_dir.expanduser().resolve()
    if not is_job_dir(job_dir):
        fail(f"{args.job_dir} is not a job folder inside work/")
    plan_file = job_dir / "plan.json"
    if not plan_file.is_file():
        fail(f"no plan.json in {args.job_dir}; run prepare.py first")
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    plan["finalized_at"] = now_iso()

    parts = []
    for part in plan["parts"]:
        text = read_part(part)
        parts.append(
            {
                "index": part["index"],
                "start_seconds": part["start_seconds"],
                "end_seconds": part["end_seconds"],
                "boundary": part["boundary"],
                "text": text or "",
                "missing": text is None,
            }
        )
    done = sum(not p["missing"] for p in parts)
    if done == 0:
        fail("no transcripts found; nothing to save (the work folder was kept)")
    complete = done == len(parts)

    output_dir = Path(plan["output_dir"])
    files = ["transcript.md", "transcript.json", "metadata.json"]
    archived = archive_previous(
        output_dir, "transcript.json", [*files, *SUBTITLE_FILES], plan.get("replaces")
    )
    document = {
        "version": 1,
        "processor": plan["processor"],
        "complete": complete,
        "source": plan["source"],
        "options": plan["options"],
        # A forced language makes ElevenLabs write other languages in it, or drop them.
        "language_forced": bool(plan["options"]["language"]),
        "provider": {
            "name": "elevenlabs",
            "tool": "elevenlabs-mcp speech_to_text",
            "model": f"{STT_MODEL} (fixed by {PINNED_BY})",
            "request_logging": STT_LOGGING,  # on: ElevenLabs keeps the request
            "audio_events_tagged": STT_AUDIO_EVENTS,
            "detected_language": "not reported",
        },
        "timestamps": (
            "per part"
            if len(parts) > 1 or plan["options"].get("part_seconds") is not None
            else "none"
        ),
        "parts": parts,
        "text": "\n\n".join(p["text"] for p in parts if p["text"]),
        "created_at": plan["finalized_at"],
    }
    write_json(output_dir / "transcript.json", document)
    write_text(output_dir / "transcript.md", to_markdown(plan, parts, complete))
    cues, subtitles = write_subtitles(output_dir, document)
    write_json(
        output_dir / "metadata.json",
        result_metadata(plan, "complete" if complete else "incomplete"),
    )
    if not args.keep_work:
        shutil.rmtree(job_dir)

    print_json(
        {
            "status": "complete" if complete else "incomplete",
            "output_dir": str(output_dir),
            "files": files + subtitles,
            "previous_result": str(archived) if archived else None,
            # Cue times are estimated within each part (no word timings from the tool).
            "subtitle_cues": cues,
            "parts_transcribed": done,
            "parts_total": len(parts),
            "characters": len(document["text"]),
            "warnings": plan["warnings"],
        }
    )


if __name__ == "__main__":
    main()
