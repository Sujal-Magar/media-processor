#!/usr/bin/env python3
"""transcribe, step 1: inspect an audio or video file, extract speech audio, plan requests.

Nothing here costs money. Writes work/transcribe/<job>/plan.json and prints a JSON summary.

    python3 processors/transcribe/prepare.py input/interview.mov [--language nep]
        [--diarize] [--part-seconds 120] [--track 1] [--normalize] [--force]
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `lib`

from lib.media import (
    audio_tracks,
    channel_peaks,
    choose_track,
    cut_audio,
    duration_of,
    extract_audio,
    find_pauses,
    live_channel,
    loudness,
    probe,
)
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

PROCESSOR = "transcribe"
SILENT_PEAK_DB = -60.0  # loudest point below this: nothing worth paying for
QUIET_MEAN_DB = -35.0  # average below this: suggest --normalize
MAX_PART_SECONDS = 9.5 * 3600  # ElevenLabs accepts up to 10 hours per request
PAUSE_SECONDS = 0.4  # preferred cut points: clear pauses between phrases
SHORT_PAUSE_SECONDS = (
    0.15  # fallback when a window has no clear pause (breaths, word gaps)
)
# A part may run this share over --part-seconds to end at a pause, instead of costing an
# extra request for a few seconds of tail or cutting through a word.
TOLERANCE = 0.10
# No part is shorter than this, or than a quarter of --part-seconds if that is less.
MIN_PART_SECONDS = 5.0
LANGUAGE_ALIASES = {"en": "eng", "ne": "nep", "hi": "hin"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help="audio or video file")
    parser.add_argument(
        "--language",
        help="ISO 639-3 code such as nep or eng (default: auto); other languages in the "
        "speech may be translated or dropped",
    )
    parser.add_argument("--diarize", action="store_true", help="label speakers")
    parser.add_argument(
        "--part-seconds",
        type=float,
        help="split at pauses into parts of at most N seconds",
    )
    parser.add_argument("--track", type=int, help="audio track to use (0 = first)")
    parser.add_argument("--normalize", action="store_true", help="even out quiet audio")
    parser.add_argument(
        "--force", action="store_true", help="transcribe again even if done"
    )
    return parser.parse_args()


def language_code(value: str | None) -> str | None:
    code = (value or "").strip().lower()
    if code in ("", "auto"):
        return None
    code = LANGUAGE_ALIASES.get(code, code)
    if not re.fullmatch(r"[a-z]{3}", code):
        fail(f"language must be an ISO 639-3 code such as nep or eng, not {value!r}")
    return code


Pause = tuple[float, float]


def stretched(limit: float) -> float:
    """The longest a part may get: the limit plus TOLERANCE, within what ElevenLabs takes."""
    return min(limit * (1 + TOLERANCE), MAX_PART_SECONDS)


def plan_parts(
    total: float,
    pauses: list[Pause],
    limit: float,
    short_pauses: list[Pause] | None = None,
) -> list[tuple[float, float, str]]:
    """Split into as few parts as the limit allows, of about equal length. Each cut goes
    to the pause nearest an even split of what is left, between half the limit and the
    limit plus TOLERANCE. Without a clear pause there, the nearest short pause; only if
    there is none either, cut hard at the even split. Stop once the rest fits. A cut
    never leaves less than the minimum part after it: it is only made when the rest is
    over the stretched limit, so such a tail could not join the part, and the cut moves
    earlier instead."""
    parts, start = [], 0.0
    min_part = min(MIN_PART_SECONDS, limit / 4)
    while total - start > stretched(limit):
        target = start + (total - start) / math.ceil((total - start) / limit)
        lo = start + limit / 2
        hi = min(start + stretched(limit), total - min_part)
        cut, boundary = target, "hard"
        for candidates, kind in (
            (pauses, "pause"),
            (short_pauses or [], "short pause"),
        ):
            inside = [p for p in candidates if lo <= (p[0] + p[1]) / 2 <= hi]
            if inside:
                nearest = min(inside, key=lambda p: abs((p[0] + p[1]) / 2 - target))
                cut, boundary = (nearest[0] + nearest[1]) / 2, kind
                break
        parts.append((start, cut, boundary))
        start = cut
    parts.append((start, total, "end"))
    return parts


def main() -> None:
    args = parse_args()
    source = args.source.expanduser().resolve()
    if not source.is_file():
        fail(f"file not found: {args.source}")
    language = language_code(args.language)
    info = probe(source)
    tracks = audio_tracks(info)
    track = choose_track(tracks, args.track)

    digest = sha256(source)
    output_dir = output_dir_for(PROCESSOR, source, digest)
    previous = output_dir / "transcript.json"
    if previous.exists() and not args.force:
        complete = json.loads(previous.read_text(encoding="utf-8")).get("complete")
        print_json(
            {
                "status": "already_done" if complete else "previous_incomplete",
                "output_dir": str(output_dir),
                "message": (
                    "This file was already transcribed. Use --force to pay again."
                    if complete
                    else "A previous attempt stopped part-way. Use --force to pay again for all parts."
                ),
            }
        )
        return
    # --force: finalize moves the result it replaces into history/ (see archive_previous).
    replaces = previous_created_at(previous)

    job_dir = new_job_dir(PROCESSOR, source)
    audio = job_dir / "audio.m4a"
    peaks = channel_peaks(source, track)
    channel = live_channel(peaks)  # a silent side is left out instead of mixed in
    extract_audio(source, audio, track=track, normalize=args.normalize, channel=channel)
    total = duration_of(probe(audio))
    if not total:
        fail("the extracted audio is empty")

    mean_db, peak_db = loudness(audio)
    if peak_db <= SILENT_PEAK_DB:
        shutil.rmtree(job_dir)
        hint = (
            f" The file has {len(tracks)} audio tracks; try --track N."
            if len(tracks) > 1
            else ""
        )
        print_json(
            {
                "status": "silent",
                "message": f"Track {track} is silent (peak {peak_db:.1f} dB), so nothing was "
                f"sent to ElevenLabs.{hint}",
                "audio_tracks": tracks,
            }
        )
        return

    warnings = []
    if language:
        # ElevenLabs writes the whole clip in the forced language (seen with eng on mixed
        # Nepali/English speech); auto-detect keeps both.
        warnings.append(
            f"Language forced to {language}: speech in other languages may be translated "
            f"into {language} or left out. Leave the language out (auto-detect) for "
            "mixed speech."
        )
    if mean_db < QUIET_MEAN_DB and not args.normalize:
        warnings.append(
            f"The audio is quiet (average {mean_db:.1f} dB); --normalize may help."
        )

    levels: dict = {"mean_db": mean_db, "max_db": peak_db}
    if args.normalize:
        # Measured on the audio as it would be sent without --normalize.
        raw = job_dir / "before_normalize.m4a"
        extract_audio(source, raw, track=track, normalize=False, channel=channel)
        before = loudness(raw)
        raw.unlink()
        levels["before_normalize"] = {"mean_db": before[0], "max_db": before[1]}

    limit = min(args.part_seconds or MAX_PART_SECONDS, MAX_PART_SECONDS)
    if total <= stretched(limit):
        ranges = [(0.0, total, "end")]
    else:
        # Pauses are judged relative to this recording's own level, not a fixed number.
        threshold = min(max(mean_db - 12, -70.0), -20.0)
        pauses = find_pauses(audio, threshold, total, PAUSE_SECONDS)
        ranges = plan_parts(total, pauses, limit)
        if any(boundary == "hard" for *_, boundary in ranges):
            # Second, finer pass only when needed: breaths and gaps between words.
            short = find_pauses(audio, threshold, total, SHORT_PAUSE_SECONDS)
            ranges = plan_parts(total, pauses, limit, short)
    hard_cuts = [f"{end:.1f} s" for _, end, boundary in ranges if boundary == "hard"]
    if hard_cuts:
        warnings.append(
            f"Forced cut with no pause nearby at {', '.join(hard_cuts)}; "
            "a word may be split there."
        )

    parts = []
    for index, (start, end, boundary) in enumerate(ranges):
        part_audio = audio if len(ranges) == 1 else job_dir / f"part_{index:03d}.m4a"
        if len(ranges) > 1:
            cut_audio(audio, part_audio, start, end - start)
        transcript_dir = job_dir / "transcripts" / f"part_{index:03d}"
        transcript_dir.mkdir(parents=True)
        parts.append(
            {
                "index": index,
                "start_seconds": round(start, 3),
                "end_seconds": round(end, 3),
                "boundary": boundary,
                "audio": str(part_audio),
                "transcript_dir": str(transcript_dir),
            }
        )

    plan = {
        "version": 1,
        "processor": PROCESSOR,
        "status": "ready",
        "source": {
            "name": source.name,
            "path": str(source),
            "sha256": digest,
            # The file's own length; the extracted audio can differ by encoder padding.
            "duration_seconds": round(duration_of(info) or total, 3),
            "audio_seconds": round(total, 3),
            "audio_tracks": tracks,
            "track": track,
            "channel_peaks_db": [round(peak, 1) for peak in peaks],
            "channel": channel,  # null: all channels mixed down
        },
        "options": {
            "language": language,
            "diarize": args.diarize,
            "part_seconds": args.part_seconds,
            "normalize": args.normalize,
        },
        "levels": levels,
        "warnings": warnings,
        "parts": parts,
        "output_dir": str(output_dir),
        "replaces": replaces,
        "created_at": now_iso(),
    }
    write_json(job_dir / "plan.json", plan)
    summary_keys = ("index", "start_seconds", "end_seconds", "audio", "transcript_dir")
    print_json(
        {
            "status": "ready",
            "job_dir": str(job_dir),
            "paid_requests": len(parts),
            "audio_seconds": round(total, 1),
            "language_code": language,
            "diarize": args.diarize,
            "part_seconds": args.part_seconds,
            "normalize": args.normalize,
            "parts": [{key: part[key] for key in summary_keys} for part in parts],
            "replaces": replaces,
            "warnings": warnings,
        }
    )


if __name__ == "__main__":
    main()
