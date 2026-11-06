#!/usr/bin/env python3
"""transcribe: subtitles (WebVTT and SRT) from a transcript, written next to it. Free and
local; finalize.py writes them with every new transcript, and this script adds them to
transcripts made before.

The cue times are estimates (lib/subtitles.py) for an editor to adjust, and the .vtt
says so. Prints counts and paths, never the text.

    python3 processors/transcribe/subtitles.py output/transcribe/<name>-<hash> [...]
    python3 processors/transcribe/subtitles.py --all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `lib`

from lib.material import read_result
from lib.subtitles import cues, to_srt
from lib.subtitles import to_vtt as vtt
from lib.workspace import OUTPUT, fail, print_json, write_text

FILES = ("transcript.vtt", "transcript.srt")
NOTE = (
    "Made from transcript.json. Times are estimated: each transcript part's start and "
    "end are measured, and the cues inside a part share its time by their length. "
    "Check them against the video before publishing."
)


def to_vtt(found: list[dict[str, Any]], complete: bool) -> str:
    note = NOTE if complete else NOTE + " Parts missing from the transcript have no cues."
    return vtt(found, note)


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
