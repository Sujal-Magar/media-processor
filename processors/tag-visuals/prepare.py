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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `lib`

from tag import existing_tags_text, reread_estimate

from lib.media import display_size, duration_of, ffmpeg, probe, streams_of
from lib.openai_api import DEFAULT_VISION_MODEL, estimate_image_tokens, setting
from lib.tags import clean_label, tag_library
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

PROCESSOR = "tag-visuals"
FRAME_WIDTH = 768  # enough for tagging; OpenAI's "low" detail looks at 512x512 anyway
SCENE_THRESHOLD = 0.3  # FFmpeg scene-change score that counts as a new shot
MIN_GAP_SECONDS = (
    1.0  # ignore scene changes closer together than this (flashes, fast cuts)
)
BATCH_SIZE = 8  # most frames per OpenAI request; the frames are split evenly
# Only for the cost estimate, measured in the 2026-11-05 re-tests (R3-R8) against 85
# tokens per low-detail frame: instructions, schema and frame labels per request
# (1,150-1,335 beside a 453-character tag list), plus the tag list itself, counted per
# run at about 4 characters per token (see estimate_tokens), and what each request after
# the first is told about the earlier ones (100-130; more with more earlier batches).
# Rounded up.
REQUEST_OVERHEAD_TOKENS = 1335
CHARS_PER_TOKEN = 4
EARLIER_BATCHES_TOKENS = 150
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
        help="do not re-read small text at full resolution (low detail only; high "
        "detail never does)",
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
) -> tuple[list[tuple[Path, float | None]], int, float]:
    """A frame at every scene change, plus one every `interval` seconds of a still shot.
    The interval is stretched when max_frames could not cover the video at it; the one
    used is returned with the frames and the number of frames that qualified."""
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
    return list(zip(files, times, strict=True)), found, interval


def batch_layout(count: int) -> list[list[int]]:
    """Frame indices per request: as few requests as BATCH_SIZE allows, of near-equal
    size (9 frames -> 5 + 4, not 8 + 1), so no frame is tagged alone. Stored in the plan,
    so a resumed job keeps the batches its saved results belong to."""
    requests = math.ceil(count / BATCH_SIZE)
    size, larger = divmod(count, requests)
    layout, start = [], 0
    for number in range(requests):
        end = start + size + (number < larger)
        layout.append(list(range(start, end)))
        start = end
    return layout


def estimate_tokens(
    frames: list[tuple[Path, float | None]],
    detail: str,
    requests: int,
    offered: list[dict],
) -> int:
    """Rough input tokens for tagging (not the small-text re-reads): every frame has the
    size of the first one, plus the prompt per request, which includes the tag list
    tag.py builds from `offered` (it grows with the library, up to MAX_EXISTING_TAGS).
    """
    size = display_size(probe(frames[0][0])) or (FRAME_WIDTH, FRAME_WIDTH)
    per_frame = estimate_image_tokens(*size, detail)
    tag_list = math.ceil(len(existing_tags_text(offered)) / CHARS_PER_TOKEN)
    return (
        len(frames) * per_frame
        + requests * (REQUEST_OVERHEAD_TOKENS + tag_list)
        + (requests - 1) * EARLIER_BATCHES_TOKENS
    )


def existing_tags(exclude: Path) -> list[dict]:
    """The library's vocabulary, rebuilt from earlier outputs so it never drifts (see
    lib.tags.tag_library; `exclude` is this file's own earlier output)."""
    return tag_library(OUTPUT / PROCESSOR, "tags.json", exclude, MAX_EXISTING_TAGS)


def previous_tags(output_dir: Path, existing: list[dict]) -> list[dict]:
    """This file's own tags from the result --force replaces, offered for reuse but not
    part of the library (they are still marked new; see finalize.py). Labels saved
    before hyphens that now read the same are counted as one."""
    try:
        tags = json.loads((output_dir / "tags.json").read_text(encoding="utf-8"))[
            "tags"
        ]
    except (OSError, ValueError, KeyError):
        return []
    known = {(t["label"], t["category"]) for t in existing}
    own: dict[tuple[str, str], int] = {}
    for tag in tags:
        key = (clean_label(tag["label"]), tag["category"])
        if key[0] and key not in known:
            own[key] = own.get(key, 0) + len(tag.get("frames") or [0])
    return [
        {"label": label, "category": category, "uses": uses}
        for (label, category), uses in own.items()
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
    # --force: finalize moves the result it replaces into history/ (see archive_previous).
    replaces = previous_created_at(previous)

    kind = "image" if is_still_image(info) else "video"
    duration = None if kind == "image" else duration_of(info)
    job_dir = new_job_dir(PROCESSOR, source)
    frames_dir = job_dir / "frames"
    frames_dir.mkdir()
    warnings = []
    interval_used = None
    if kind == "image":
        frames = grab_image(source, frames_dir)
    else:
        assert duration is not None
        frames, found, interval_used = sample_video(
            source, frames_dir, args.interval, args.max_frames, duration
        )
        if interval_used > args.interval:
            needed = math.floor(duration / args.interval) + 1
            warnings.append(
                f"Every {args.interval:g} s needs {needed} frames; --max-frames "
                f"{args.max_frames} spreads them to one every {interval_used:.1f} s. Raise "
                "--max-frames for the asked spacing (more cost)."
            )
        if found > len(frames):
            warnings.append(
                f"{found} frames qualified; kept {len(frames)} spread evenly. "
                "Raise --max-frames for more detail (and more cost)."
            )

    if args.detail == "high" and not args.no_text_pass:
        warnings.append(
            "High detail sends the same 768 px frames and skips the full-resolution "
            "re-read of small text; text too small at 768 px stays unread."
        )

    model = setting("OPENAI_VISION_MODEL", DEFAULT_VISION_MODEL)
    existing = existing_tags(exclude=output_dir)
    own_tags = previous_tags(output_dir, existing)
    batches = batch_layout(len(frames))
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
            "interval_used_seconds": (
                round(interval_used, 3) if interval_used is not None else None
            ),
            "scene_threshold": SCENE_THRESHOLD,
            "max_frames": args.max_frames,
            "detail": args.detail,
            "model": model,
            "text_pass": not args.no_text_pass,
        },
        "batch_size": BATCH_SIZE,
        # Frame indices per tagging request; tag.py uses this layout.
        "batches": batches,
        "existing_tags": existing,
        "previous_tags": own_tags,
        "frames": [
            {
                "index": index,
                "file": str(file),
                "time_seconds": round(time, 3) if time is not None else None,
            }
            for index, (file, time) in enumerate(frames)
        ],
        "estimated_input_tokens": estimate_tokens(
            frames, args.detail, len(batches), existing + own_tags
        ),
        # Only a low-detail run with the text pass re-reads small text (tag.py).
        "text_reread_estimate": (
            reread_estimate(len(frames), display_size(info))
            if args.detail == "low" and not args.no_text_pass
            else None
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
            "kind": kind,
            "frames": len(frames),
            "paid_requests": len(batches),
            "model": model,
            "detail": args.detail,
            "estimated_input_tokens": plan["estimated_input_tokens"],
            "text_reread_estimate": plan["text_reread_estimate"],
            "existing_tags": len(plan["existing_tags"]),
            "previous_tags": len(plan["previous_tags"]),
            "replaces": replaces,
            "warnings": warnings,
        }
    )


if __name__ == "__main__":
    main()
