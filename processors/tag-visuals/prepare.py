#!/usr/bin/env python3
"""tag-visuals, step 1: pick the frames of a video (or take a photo) to be tagged.

Also collects the tags already used in output/tag-visuals/ (the folder's tag library),
which tag.py offers to the model for reuse. Nothing here costs money. Writes
work/tag-visuals/<job>/plan.json and frames/, and prints a JSON summary.

    python3 processors/tag-visuals/prepare.py input/interview.mov [--interval 5]
        [--max-frames 60] [--detail low|high] [--force]
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `lib`

from lib.media import duration_of, ffmpeg, probe, streams_of  # noqa: E402
from lib.openai_api import DEFAULT_VISION_MODEL, setting  # noqa: E402
from lib.workspace import (  # noqa: E402
    OUTPUT,
    fail,
    new_job_dir,
    now_iso,
    output_dir_for,
    print_json,
    sha256,
    write_json,
)

PROCESSOR = "tag-visuals"
FRAME_WIDTH = 768  # enough for tagging; OpenAI's "low" detail looks at 512x512 anyway
SCENE_THRESHOLD = 0.3  # FFmpeg scene-change score that counts as a new shot
MIN_GAP_SECONDS = (
    1.0  # ignore scene changes closer together than this (flashes, fast cuts)
)
BATCH_SIZE = 8  # frames per OpenAI request
# Tags already in the library, offered to the model for reuse (most used first).
MAX_EXISTING_TAGS = 300
IMAGE_FORMATS = {
    "image2",
    "png_pipe",
    "jpeg_pipe",
    "webp_pipe",
    "bmp_pipe",
    "tiff_pipe",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help="video or image file")
    parser.add_argument(
        "--interval", type=float, default=5.0, help="seconds between frames"
    )
    parser.add_argument(
        "--max-frames", type=int, default=60, help="upper limit on frames"
    )
    parser.add_argument(
        "--detail", choices=["low", "high"], default="low", help="image detail"
    )
    parser.add_argument(
        "--no-text-pass",
        action="store_true",
        help="do not re-read small text at high detail (low detail only)",
    )
    parser.add_argument("--force", action="store_true", help="tag again even if done")
    return parser.parse_args()


def is_still_image(info: dict) -> bool:
    formats = set(str(info.get("format", {}).get("format_name", "")).split(","))
    return bool(formats & IMAGE_FORMATS) or not duration_of(info)


def grab_image(source: Path, frames_dir: Path) -> list[tuple[Path, float | None]]:
    target = frames_dir / "frame_0001.jpg"
    ffmpeg(
        "-loglevel", "error", "-i", f"file:{source}", "-frames:v", "1",
        "-vf", f"scale=w='min({FRAME_WIDTH},iw)':h=-2", "-q:v", "3", f"file:{target}",
    )  # fmt: skip
    return [(target, None)]


def sample_video(
    source: Path, frames_dir: Path, interval: float, max_frames: int, duration: float
) -> tuple[list[tuple[Path, float | None]], int]:
    """A frame at every scene change, plus one every `interval` seconds of a still shot."""
    interval = max(interval, duration / max_frames)
    select = (
        f"isnan(prev_selected_t)"
        f"+gt(scene,{SCENE_THRESHOLD})*gte(t-prev_selected_t,{MIN_GAP_SECONDS})"
        f"+gte(t-prev_selected_t,{interval:.3f})"
    )
    log = ffmpeg(
        "-i", f"file:{source}", "-map", "0:v:0",
        "-vf", f"select='{select}',scale=w='min({FRAME_WIDTH},iw)':h=-2,showinfo",
        "-fps_mode", "vfr", "-q:v", "3", f"file:{frames_dir}/frame_%04d.jpg",
    )  # fmt: skip
    times = [float(t) for t in re.findall(r"pts_time:\s*(-?[\d.]+)", log)]
    files = sorted(frames_dir.glob("frame_*.jpg"))
    if not files or len(files) != len(times):
        fail(
            f"frame sampling went wrong ({len(files)} frames, {len(times)} timestamps)"
        )
    found = len(files)
    if found > max_frames:
        # Many scene changes: keep an even spread instead of the first N.
        keep = {round(i * (found - 1) / (max_frames - 1)) for i in range(max_frames)}
        for index, file in enumerate(files):
            if index not in keep:
                file.unlink()
        files, times = (
            [files[i] for i in sorted(keep)],
            [times[i] for i in sorted(keep)],
        )
    return list(zip(files, times, strict=True)), found


def existing_tags(exclude: Path) -> list[dict]:
    """The library's vocabulary, rebuilt from earlier outputs so it never drifts.

    `exclude` is this file's own earlier output: when re-tagging with --force, its old
    tags must not count as the library, or nothing would ever be marked new.
    """
    uses: Counter[tuple[str, str]] = Counter()
    for tags_file in (OUTPUT / PROCESSOR).glob("*/tags.json"):
        if tags_file.parent == exclude:
            continue
        try:
            tags = json.loads(tags_file.read_text(encoding="utf-8")).get("tags", [])
        except (OSError, ValueError):
            continue
        for tag in tags:
            uses[(tag["label"], tag["category"])] += len(tag.get("frames") or [0])
    return [
        {"label": label, "category": category, "uses": count}
        for (label, category), count in uses.most_common(MAX_EXISTING_TAGS)
    ]


def main() -> None:
    args = parse_args()
    if args.max_frames < 1 or args.interval <= 0:
        fail("--max-frames and --interval must be positive")
    source = args.source.expanduser().resolve()
    if not source.is_file():
        fail(f"file not found: {args.source}")
    info = probe(source)
    if not streams_of(info, "video"):
        fail("no picture to tag: this file has no video or image stream (audio only?)")

    digest = sha256(source)
    output_dir = output_dir_for(PROCESSOR, source, digest)
    previous = output_dir / "tags.json"
    if previous.exists() and not args.force:
        done = json.loads(previous.read_text(encoding="utf-8"))
        print_json(
            {
                "status": (
                    "already_done" if done.get("complete") else "previous_incomplete"
                ),
                "output_dir": str(output_dir),
                "resume_job_dir": done.get("resume_job_dir"),
                "message": (
                    "This file was already tagged. Use --force to pay again."
                    if done.get("complete")
                    else "A previous run stopped part-way. Run tag.py on resume_job_dir to pay "
                    "only for the missing frames, or use --force to start over."
                ),
            }
        )
        return

    kind = "image" if is_still_image(info) else "video"
    duration = None if kind == "image" else duration_of(info)
    job_dir = new_job_dir(PROCESSOR, source)
    frames_dir = job_dir / "frames"
    frames_dir.mkdir()
    warnings = []
    if kind == "image":
        frames = grab_image(source, frames_dir)
    else:
        assert duration is not None
        frames, found = sample_video(
            source, frames_dir, args.interval, args.max_frames, duration
        )
        if found > len(frames):
            warnings.append(
                f"{found} frames qualified; kept {len(frames)} spread evenly. "
                "Raise --max-frames for more detail (and more cost)."
            )

    model = setting("OPENAI_VISION_MODEL", DEFAULT_VISION_MODEL)
    plan = {
        "version": 1,
        "processor": PROCESSOR,
        "status": "ready",
        "source": {
            "name": source.name,
            "path": str(source),
            "sha256": digest,
            "kind": kind,
            "duration_seconds": round(duration, 3) if duration else None,
        },
        "options": {
            "interval_seconds": args.interval,
            "scene_threshold": SCENE_THRESHOLD,
            "max_frames": args.max_frames,
            "detail": args.detail,
            "model": model,
            "text_pass": not args.no_text_pass,
        },
        "batch_size": BATCH_SIZE,
        "existing_tags": existing_tags(exclude=output_dir),
        "frames": [
            {
                "index": index,
                "file": str(file),
                "time_seconds": round(time, 3) if time is not None else None,
            }
            for index, (file, time) in enumerate(frames)
        ],
        "warnings": warnings,
        "output_dir": str(output_dir),
        "created_at": now_iso(),
    }
    write_json(job_dir / "plan.json", plan)
    print_json(
        {
            "status": "ready",
            "job_dir": str(job_dir),
            "kind": kind,
            "frames": len(frames),
            "paid_requests": math.ceil(len(frames) / BATCH_SIZE),
            "model": model,
            "detail": args.detail,
            "existing_tags": len(plan["existing_tags"]),
            "warnings": warnings,
        }
    )


if __name__ == "__main__":
    main()
