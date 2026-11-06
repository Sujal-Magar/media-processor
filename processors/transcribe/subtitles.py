#!/usr/bin/env python3
"""transcribe: subtitles (WebVTT and SRT) from a transcript, written next to it. Free and
local; finalize.py writes them with every new transcript, and this script adds them to
transcripts made before.

The ElevenLabs MCP tool gives no word timings, so only each transcript part's start and
end are measured. Inside a part the text is cut into short cues (a sentence, or a piece
of a long one, at most two lines of 42 characters), and the part's time is shared out
among them by their length. The times are estimates for an editor to adjust, and the
.vtt says so. Prints counts and paths, never the text.

    python3 processors/transcribe/subtitles.py output/transcribe/<name>-<hash> [...]
    python3 processors/transcribe/subtitles.py --all
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `lib`

from lib.material import read_result, sentence_text, sentences
from lib.workspace import OUTPUT, fail, print_json, write_text

LINE_CHARS = 42  # a subtitle line most players show without wrapping
CUE_CHARS = 2 * LINE_CHARS
# A cue shorter than this ("Thank you.") would flash by; it joins its neighbour.
MIN_CUE_CHARS = 20
# A cue that cannot join one still gets the time of this many characters (about a
# second of speech), taken from the others in its part.
MIN_TIME_CHARS = 25
# Where a long sentence may be cut: after a comma, semicolon, colon or dash.
CLAUSE_END = re.compile(r"(?<=[,;:–—])\s+")
FILES = ("transcript.vtt", "transcript.srt")
NOTE = (
    "Made from transcript.json. Times are estimated: each transcript part's start and "
    "end are measured, and the cues inside a part share its time by their length. "
    "Check them against the video before publishing."
)


def fits(text: str) -> bool:
    """Whether the text fits a cue: two lines of at most LINE_CHARS once wrapped."""
    return len(text) <= CUE_CHARS and all(len(line) <= LINE_CHARS for line in wrap(text))


def pieces(sentence: str) -> list[str]:
    """A sentence whole if it fits a cue, else cut at clause ends (or, for a clause too
    long itself, between words) into pieces that fit."""
    if fits(sentence):
        return [sentence]
    units = []
    for clause in CLAUSE_END.split(sentence):
        units.extend([clause] if fits(clause) else clause.split())
    found, current = [], ""
    for unit in units:
        joined = f"{current} {unit}" if current else unit
        if fits(joined) or not current:
            current = joined
        else:
            found.append(current)
            current = unit
    return found + [current] if current else found


def wrap(text: str) -> list[str]:
    """One line, or two split at the space nearest the middle that keeps both lines
    within LINE_CHARS (or, when none does, nearest the middle)."""
    if len(text) <= LINE_CHARS or " " not in text:
        return [text]
    middle = len(text) // 2
    spaces = [i for i, c in enumerate(text) if c == " "]
    fitting = [i for i in spaces if i <= LINE_CHARS and len(text) - i - 1 <= LINE_CHARS]
    cut = min(fitting or spaces, key=lambda i: abs(i - middle))
    return [text[:cut], text[cut + 1 :]]


def joined(units: list[tuple[str, str | None]]) -> list[tuple[str, str | None]]:
    """A piece shorter than MIN_CUE_CHARS joined to the one before it (or that one to
    it), when the same speaker says both and together they fit a cue."""
    found: list[tuple[str, str | None]] = []
    for text, speaker in units:
        if found and found[-1][1] == speaker:
            before = found[-1][0]
            both = f"{before} {text}"
            if min(len(before), len(text)) < MIN_CUE_CHARS and fits(both):
                found[-1] = (both, speaker)
                continue
        found.append((text, speaker))
    return found


def cues(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    """The transcript's text as cues with estimated times. A part that failed or holds no
    speech gives none; each speaker turn starts on its own line of the part's text."""
    found = []
    for part in transcript.get("parts", []):
        if part.get("missing") or not str(part.get("text") or "").strip():
            continue
        units: list[tuple[str, str | None]] = []
        speaker = None
        for line in part["text"].splitlines():
            for sentence in sentences(line):
                text, speaker = sentence_text(sentence, speaker)
                units.extend((piece, speaker) for piece in pieces(text.strip()) if piece)
        units = joined(units)
        weights = [max(len(text), MIN_TIME_CHARS) for text, _ in units]
        start, end = float(part["start_seconds"]), float(part["end_seconds"])
        at = start
        for (text, who), weight in zip(units, weights):
            until = at + (end - start) * weight / sum(weights)
            found.append({"start": at, "end": until, "text": text, "speaker": who})
            at = until
    return found


def stamp(seconds: float, separator: str) -> str:
    """00:01:02.345 (WebVTT) or 00:01:02,345 (SRT)."""
    ms = round(seconds * 1000)
    return f"{ms // 3_600_000:02d}:{ms // 60_000 % 60:02d}:{ms // 1000 % 60:02d}{separator}{ms % 1000:03d}"


def vtt_text(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def to_vtt(found: list[dict[str, Any]], complete: bool) -> str:
    note = NOTE if complete else NOTE + " Parts missing from the transcript have no cues."
    blocks = ["WEBVTT", f"NOTE\n{note}"]
    for number, cue in enumerate(found, 1):
        lines = [vtt_text(line) for line in wrap(cue["text"])]
        if cue["speaker"]:  # a voice span: a label, not a name
            lines[0] = f"<v {cue['speaker']}>{lines[0]}"
        times = f"{stamp(cue['start'], '.')} --> {stamp(cue['end'], '.')}"
        blocks.append("\n".join([str(number), times, *lines]))
    return "\n\n".join(blocks) + "\n"


def to_srt(found: list[dict[str, Any]]) -> str:
    blocks = [
        "\n".join([str(number), f"{stamp(cue['start'], ',')} --> {stamp(cue['end'], ',')}",
                   *wrap(cue["text"])])  # fmt: skip
        for number, cue in enumerate(found, 1)
    ]
    return "\n\n".join(blocks) + "\n" if blocks else ""


def write_subtitles(output_dir: Path, transcript: dict[str, Any]) -> tuple[int, list[str]]:
    """Write transcript.vtt and transcript.srt next to the transcript; none when it holds
    no speech. Returns the number of cues and the file names written."""
    found = cues(transcript)
    if not found:
        return 0, []
    write_text(output_dir / FILES[0], to_vtt(found, bool(transcript.get("complete"))))
    write_text(output_dir / FILES[1], to_srt(found))
    return len(found), list(FILES)


def result_dir(value: str) -> Path:
    """A transcribe result folder (or its transcript.json) inside output/transcribe/."""
    path = Path(value).expanduser().resolve()
    folder = path.parent if path.name == "transcript.json" else path
    if (OUTPUT / "transcribe").resolve() not in folder.parents:
        fail(f"{value} is not a result folder inside output/transcribe/")
    return folder


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folders", nargs="*", type=result_dir, help="output/transcribe/<name>-<hash>")
    parser.add_argument("--all", action="store_true", help="every transcript in output/transcribe/")
    args = parser.parse_args()
    folders = sorted((OUTPUT / "transcribe").glob("*/")) if args.all else args.folders
    if not folders:
        fail("name a result folder in output/transcribe/, or use --all")
    results = []
    for folder in folders:
        transcript = read_result(folder / "transcript.json")
        if transcript is None:
            results.append({"folder": str(folder), "status": "no transcript.json"})
            continue
        count, files = write_subtitles(folder, transcript)
        results.append({"folder": str(folder), "status": "written" if files else "no speech",
                        "cues": count, "files": files})  # fmt: skip
    print_json({"subtitles": results})


if __name__ == "__main__":
    main()
