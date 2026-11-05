"""FFmpeg and ffprobe helpers for any processor (audio, video or images)."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from lib.workspace import fail

# Mono AAC is small to upload and enough for speech.
SPEECH_AUDIO = ["-ac", "1", "-ar", "44100", "-c:a", "aac", "-b:a", "128k"]
# Single-pass EBU R128 at spoken-word level. loudnorm alone overshoots after resampling and
# AAC encoding (0 dB peaks seen), so a limiter at -3 dBFS follows; level=false keeps its
# auto-level from undoing the limit.
LOUDNORM = (
    "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=44100,alimiter=limit=0.708:level=false"
)
SILENCE_FLOOR_DB = -120.0
SILENT_CHANNEL_DB = -60.0  # a channel peaking below this carries no sound


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a command as an argument list (never through a shell)."""
    try:
        return subprocess.run(
            args, capture_output=True, text=True, stdin=subprocess.DEVNULL, check=False
        )
    except FileNotFoundError:
        fail(f"{args[0]} is not installed (sudo pacman -S ffmpeg)")


def ffmpeg(*args: str) -> str:
    """Run ffmpeg and return its log (analysis filters such as volumedetect report there).

    File arguments should use the ``file:`` prefix so names are never read as options.
    """
    result = run(["ffmpeg", "-nostdin", "-hide_banner", "-nostats", *args])
    if result.returncode != 0:
        fail("ffmpeg failed: " + " ".join(result.stderr.strip().splitlines()[-3:]))
    return result.stderr


def probe(path: Path) -> dict[str, Any]:
    result = run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
         f"file:{path}"]
    )  # fmt: skip
    if result.returncode != 0:
        fail(f"{path.name} is not a readable media file")
    return json.loads(result.stdout)


def duration_of(info: dict[str, Any]) -> float | None:
    try:
        return float(info["format"]["duration"])
    except (KeyError, TypeError, ValueError):
        return None


def streams_of(info: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    """Streams of one kind: "audio", "video" (images are single-frame video) or "subtitle"."""
    return [s for s in info.get("streams", []) if s.get("codec_type") == kind]


def display_size(info: dict[str, Any]) -> tuple[int, int] | None:
    """Width and height of the first picture as shown, after the rotation flag phones set
    (ffmpeg rotates frames the same way when it decodes them)."""
    videos = streams_of(info, "video")
    if not videos or not videos[0].get("width") or not videos[0].get("height"):
        return None
    stream = videos[0]
    rotation = (stream.get("tags") or {}).get("rotate") or 0
    for side_data in stream.get("side_data_list") or []:
        rotation = side_data.get("rotation", rotation)
    width, height = int(stream["width"]), int(stream["height"])
    return (height, width) if int(float(rotation)) % 180 else (width, height)


# --- audio --------------------------------------------------------------------------------


def audio_tracks(info: dict[str, Any]) -> list[dict[str, Any]]:
    tracks = []
    for stream in streams_of(info, "audio"):
        language = (stream.get("tags") or {}).get("language")
        tracks.append(
            {
                "track": len(tracks),
                "codec": stream.get("codec_name"),
                "language": None if language in (None, "und") else language,
                "default": bool((stream.get("disposition") or {}).get("default")),
            }
        )
    return tracks


def describe_tracks(tracks: list[dict[str, Any]]) -> str:
    """e.g. "track 0 (aac, default), track 1 (aac, eng)"."""
    return ", ".join(
        f"track {t['track']} ("
        + ", ".join(
            filter(None, [t["codec"], t["language"], t["default"] and "default"])
        )
        + ")"
        for t in tracks
    )


def choose_track(tracks: list[dict[str, Any]], requested: int | None) -> int:
    if not tracks:
        fail("this file has no audio track")
    if requested is not None:
        if not 0 <= requested < len(tracks):
            fail(
                f"--track {requested} does not exist: this file has {len(tracks)} audio "
                f"track(s): {describe_tracks(tracks)}. Tracks count from 0."
            )
        return requested
    # With several tracks, follow the file's own "default" flag.
    flagged = [t["track"] for t in tracks if t["default"]]
    return flagged[0] if len(tracks) > 1 and flagged else 0


def channel_peaks(source: Path, track: int) -> list[float]:
    """Peak level in dB of each channel of one audio track."""
    log = ffmpeg(
        "-i", f"file:{source}", "-map", f"0:a:{track}",
        "-af", "astats=measure_overall=none:measure_perchannel=Peak_level",
        "-f", "null", "-",
    )  # fmt: skip
    return [
        SILENCE_FLOOR_DB if value.endswith("inf") else float(value)
        for value in re.findall(r"Peak level dB: (-?inf|-?[\d.]+)", log)
    ]


def live_channel(peaks: list[float]) -> int | None:
    """The one channel with sound when every other is silent (phones often record a
    wireless mic on one side only). None: mix all channels down."""
    live = [index for index, peak in enumerate(peaks) if peak > SILENT_CHANNEL_DB]
    return live[0] if len(peaks) > 1 and len(live) == 1 else None


def extract_audio(
    source: Path,
    destination: Path,
    *,
    track: int,
    normalize: bool,
    channel: int | None = None,
) -> None:
    """Extract one audio track as mono speech audio, without the source's metadata.
    With `channel`, only that channel is kept."""
    chain = [f"pan=mono|c0=c{channel}"] if channel is not None else []
    if normalize:
        chain.append(LOUDNORM)
    filters = ["-af", ",".join(chain)] if chain else []
    ffmpeg(
        "-loglevel", "error", "-y", "-i", f"file:{source}", "-map", f"0:a:{track}",
        "-vn", "-sn", "-dn",
        "-map_metadata", "-1",  # drops camera, device and GPS data
        *filters, *SPEECH_AUDIO, f"file:{destination}",
    )  # fmt: skip


def cut_audio(source: Path, destination: Path, start: float, duration: float) -> None:
    ffmpeg(
        "-loglevel", "error", "-y", "-ss", f"{start:.3f}", "-i", f"file:{source}",
        "-t", f"{duration:.3f}", *SPEECH_AUDIO, f"file:{destination}",
    )  # fmt: skip


def loudness(audio: Path) -> tuple[float, float]:
    """Mean and peak level in dB (volumedetect). Digital silence is about -91 dB."""
    log = ffmpeg("-i", f"file:{audio}", "-af", "volumedetect", "-f", "null", "-")
    values = dict(re.findall(r"(mean|max)_volume: (-?inf|-?[\d.]+) dB", log))
    if len(values) != 2:
        fail("could not measure the audio level")
    as_db = {
        k: SILENCE_FLOOR_DB if v.endswith("inf") else float(v)
        for k, v in values.items()
    }
    return as_db["mean"], as_db["max"]


def find_pauses(
    audio: Path, threshold_db: float, total: float, min_pause: float = 0.4
) -> list[tuple[float, float]]:
    """Quiet stretches (start, end) in seconds, from silencedetect."""
    log = ffmpeg(
        "-i", f"file:{audio}",
        "-af", f"silencedetect=noise={threshold_db:.1f}dB:d={min_pause}",
        "-f", "null", "-",
    )  # fmt: skip
    pauses, start = [], None
    for kind, value in re.findall(r"silence_(start|end): (-?[\d.]+)", log):
        if kind == "start":
            start = max(0.0, float(value))
        elif start is not None:
            pauses.append((start, min(float(value), total)))
            start = None
    if start is not None:
        pauses.append((start, total))
    return pauses
