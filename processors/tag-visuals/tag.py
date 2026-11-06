#!/usr/bin/env python3
"""tag-visuals, step 2: tag the prepared frames with an OpenAI vision model (paid), then
write the outputs (finalize.py).

Pass 1 tags every frame at the planned detail and, where text is visible but too small to
read, reports roughly where it is. When it ran at low detail, pass 2 re-reads that text:
one frame per run of such frames, taken again from the original file at full resolution
and cropped generously around the run's reported boxes, so the text fills more of the
image the model sees. Certificates or registration numbers are not lost, without paying
high detail for every frame. Text too small in the source to read is not sent at all.

One request per batch of frames, one at a time, never retried. Finished batches are saved
in the job folder, so running this again on the same job pays only for missing batches.
Prints only counts and paths, never tags, so results stay out of the chat.

    python3 processors/tag-visuals/tag.py work/tag-visuals/<job>
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `lib`

from finalize import (
    finalize,
    has_text,
    load_results,
    needs_text_pass,
    text_runs,
)

from lib.media import display_size, ffmpeg, probe
from lib.openai_api import (
    OpenAIError,
    estimate_image_tokens,
    output_text,
    request,
    setting,
)
from lib.tags import clean_label
from lib.workspace import fail, is_job_dir, print_json, write_json

# Pass 2 crops full-resolution frames: the 768 px tagging frames are too small for fine print.
TEXT_FRAME_WIDTH = 2048
TEXT_BATCH_SIZE = 4  # full-size images are larger, so fewer per request
# Re-read instructions and schema per request, measured in the 2026-11-05 re-tests
# beside one crop: R5 ~146 (1,251 for 6 tiles), R8 ~265 (1,030 for 4 tiles). The larger
# one, so neither is underestimated. Only for the cost estimate.
TEXT_REQUEST_OVERHEAD_TOKENS = 265
# Carried from earlier batches of the same video into the next request (~100-300 tokens).
MAX_EARLIER_TAGS = 40
MAX_EARLIER_TEXTS = 20
# The re-read crops to the boxes pass 1 reported for the run, plus a margin on every side.
# Low-detail boxes are often off by about 0.04 of the frame (F-001), so the margin is at
# least MIN_PAD of the frame, and the crop at least MIN_CROP of each side.
CROP_MARGIN = 0.15  # share of the box
MIN_PAD = 0.06  # share of the frame
MIN_CROP = 0.30  # share of the frame, centred on the box
# Smaller boxes are left out of a run's box when it has a larger one. A run with only
# such boxes keeps them, so the MIN_TEXT_PIXELS check skips it; only a run with no box
# at all (all four values 0) re-reads the whole frame.
MIN_REGION = 0.01
# Text whose box is shorter than this in the source can't be read even at full size,
# so that re-read is skipped (and recorded) instead of paid for.
MIN_TEXT_PIXELS = 80
UPSCALE_BELOW = 512  # crops with a shorter side (source px) are enlarged 2x (lanczos)

TEXT_RULES = """Copy every readable piece of text exactly as written (signs, captions,
certificates, registration numbers, slides), in its original language and script, one
entry per separate piece of text. Do not translate or correct it. legibility: "clear" when
you can read every character; "partial" when you cannot, and then write each unreadable
character or word as "…". Leave out lines you cannot read at all. Never complete names,
numbers, phone numbers, addresses or web addresses from context or from what they
usually look like: write "…" instead. Leave the list empty when there is no readable
text."""

INSTRUCTIONS = f"""You tag frames from a video or photo library so it can be searched.
For every frame, list what is clearly visible as short English tags, lowercase, with
words joined by hyphens:
- object: physical things (person, laptop, microphone, car, dog)
- scene: the setting (office, classroom, street, kitchen, outdoors, stage)
- activity: what people are doing (presenting, typing, walking, cooking); use
  "speaking-to-camera" when a person visibly talks to the camera
- attribute: visual qualities (night, close-up, crowded, text-on-screen)
Use singular nouns or short phrases in plain English. The library may belong to any
kind of organisation, so tag what you see rather than forcing a fixed list. When the
message lists tags already used in this library, treat them as a vocabulary, not a
checklist: use a listed tag only for something visible in this frame that it describes
exactly, and then with its exact wording. A tag that names a colour, garment, posture or
kind of object (white-shirt, sitting, certificate) fits only when exactly that is
visible; otherwise add a new tag that says what you see.
Use "person" for people: never name or identify anyone, and do not guess age,
ethnicity or emotions. Tag only what you can see.
Give 3 to 15 tags and a summary of at most 15 words per frame.
Confidence: high = plainly visible, no doubt; medium = visible but small, partly hidden
or open to another reading; low = a guess. Rate a reused library tag the same way.
on_screen_text: {TEXT_RULES}
unreadable_text: true when the frame shows text you cannot read at this resolution
(too small, blurry or far away), otherwise false.
text_region: when unreadable_text is true, a box around that text as fractions of the
frame (x and y of the top-left corner, width and height, each from 0 to 1); if there are
several, one box around all of them. Otherwise all four values are 0."""

TEXT_INSTRUCTIONS = f"""You read the text shown in frames from a video or photo library.
For every frame: {TEXT_RULES}"""

TAG = {
    "type": "object",
    "additionalProperties": False,
    "required": ["label", "category", "confidence"],
    "properties": {
        "label": {"type": "string"},
        "category": {
            "type": "string",
            "enum": ["object", "scene", "activity", "attribute"],
        },
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
}
TEXT_LIST = {
    "type": "array",
    "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["text", "legibility"],
        "properties": {
            "text": {"type": "string"},
            "legibility": {"type": "string", "enum": ["clear", "partial"]},
        },
    },
}


def frames_schema(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["frames"],
        "properties": {
            "frames": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["index", *properties],
                    "properties": {"index": {"type": "integer"}, **properties},
                },
            }
        },
    }


SCHEMA = frames_schema(
    {
        "summary": {"type": "string"},
        "tags": {"type": "array", "items": TAG},
        "on_screen_text": TEXT_LIST,
        "unreadable_text": {"type": "boolean"},
        "text_region": {
            "type": "object",
            "additionalProperties": False,
            "required": ["x", "y", "width", "height"],
            "properties": {
                key: {"type": "number"} for key in ("x", "y", "width", "height")
            },
        },
    }
)
TEXT_SCHEMA = frames_schema({"on_screen_text": TEXT_LIST})


def existing_tags_text(existing: list[dict[str, Any]]) -> str:
    if not existing:
        return (
            "No tags have been used in this library yet. Choose clear, general "
            "wording that later frames can reuse."
        )
    by_category: dict[str, list[str]] = {}
    for tag in existing:
        by_category.setdefault(tag["category"], []).append(tag["label"])
    lines = [
        f"{category}: {', '.join(labels)}" for category, labels in by_category.items()
    ]
    return (
        "Tags already used in this library (most used first). A vocabulary, not a "
        "checklist: use one only when it describes what this frame shows exactly, "
        "with the same wording:\n" + "\n".join(lines)
    )


def earlier_batches_text(results_dir: Path, batch: list[dict[str, Any]]) -> str | None:
    """What earlier batches of this video answered, so the same unchanged thing keeps
    the same tag and spelling across requests (and a new tag isn't named twice)."""
    first = min(frame["index"] for frame in batch)
    tags: Counter[tuple[str, str]] = Counter()
    texts: Counter[str] = Counter()
    for result_file in sorted(results_dir.glob("batch_*.json")):
        result = json.loads(result_file.read_text(encoding="utf-8"))
        for frame in result["frames"]:
            if frame["index"] >= first:
                continue
            for tag in frame.get("tags", []):
                tags[(clean_label(tag["label"]), tag["category"])] += 1
            for item in frame.get("on_screen_text", []):
                text = item.get("text") if isinstance(item, dict) else item
                if has_text(text or "") and (
                    not isinstance(item, dict) or item.get("legibility") != "partial"
                ):
                    texts[text.strip()] += 1
    if not tags:
        return None
    by_category: dict[str, list[str]] = {}
    for (label, category), _ in tags.most_common(MAX_EARLIER_TAGS):
        by_category.setdefault(category, []).append(label)
    lines = [
        f"{category}: {', '.join(labels)}" for category, labels in by_category.items()
    ]
    if texts:
        quoted = "; ".join(f'"{t}"' for t, _ in texts.most_common(MAX_EARLIER_TEXTS))
        lines.append(f"text read: {quoted}")
    return (
        "Earlier frames of this same video were answered with these tags and text. When "
        "the same thing is still visible, use the same tag and spelling; leave out what "
        "this frame doesn't show, and don't copy text you can't read in it:\n"
        + "\n".join(lines)
    )


def batch_intro(
    plan: dict[str, Any], results_dir: Path, batch: list[dict[str, Any]]
) -> list[str]:
    # A --force re-run also offers this file's own earlier tags (previous_tags); they
    # still count as new against the rest of the library (finalize.py).
    offered = plan.get("existing_tags", []) + plan.get("previous_tags", [])
    earlier = earlier_batches_text(results_dir, batch)
    return [
        existing_tags_text(offered),
        *([earlier] if earlier else []),
        "Tag each frame. Answer with the frame index shown.",
    ]


def build_payload(
    plan: dict[str, Any],
    frames: list[dict[str, Any]],
    *,
    intro: list[str],
    instructions: str,
    schema: dict[str, Any],
    detail: str,
) -> dict[str, Any]:
    content: list[dict[str, Any]] = [
        {"type": "input_text", "text": text} for text in intro
    ]
    for frame in frames:
        when = frame["time_seconds"]
        label = f"Frame {frame['index']}" + (
            f" at {when:.1f} s" if when is not None else ""
        )
        image = base64.b64encode(Path(frame["file"]).read_bytes()).decode("ascii")
        content.append({"type": "input_text", "text": label})
        content.append(
            {
                "type": "input_image",
                "image_url": f"data:image/jpeg;base64,{image}",
                "detail": detail,
            }
        )
    payload: dict[str, Any] = {
        "model": plan["options"]["model"],
        "instructions": instructions,
        "input": [{"role": "user", "content": content}],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "frames",
                "strict": True,
                "schema": schema,
            }
        },
        "max_output_tokens": 6000,
    }
    # Tagging is perception, not reasoning. "unset" leaves the model's default.
    effort = setting("OPENAI_REASONING_EFFORT", "none")
    if effort != "unset":
        payload["reasoning"] = {"effort": effort}
    return payload


def run_batches(
    results_dir: Path,
    prefix: str,
    batches: list[list[dict[str, Any]]],
    make_payload: Callable[[list[dict[str, Any]]], dict[str, Any]],
    annotate: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> OpenAIError | None:
    """Send each batch once and save its answer; skip batches saved by an earlier run.
    A saved batch must hold the same frames, or the job stops instead of paying twice.
    """
    for number, batch in enumerate(batches):
        result_file = results_dir / f"{prefix}_{number:03d}.json"
        expected = {frame["index"] for frame in batch}
        if result_file.exists():  # paid for in an earlier run
            saved = json.loads(result_file.read_text(encoding="utf-8"))
            # `sent` is missing from files saved before it was added; their answers
            # can only hold frames of the batch.
            sent = set(saved.get("sent") or [])
            answered = {frame.get("index") for frame in saved.get("frames", [])}
            if (sent and sent != expected) or not answered <= expected:
                return OpenAIError(
                    None,
                    "batch_mismatch",
                    f"{result_file.name} holds other frames than this plan's {prefix} "
                    f"{number + 1}; nothing was sent. Start over with force.",
                )
            continue
        print(
            f"{prefix} {number + 1}/{len(batches)}: {len(batch)} frame(s)",
            file=sys.stderr,
        )
        try:
            response = request("POST", "/responses", make_payload(batch))
            answer = json.loads(output_text(response))["frames"]
        except OpenAIError as exc:
            return exc
        except (ValueError, KeyError, TypeError) as exc:
            return OpenAIError(None, "bad_output", f"unexpected answer: {exc}"[:200])
        write_json(
            result_file,
            {
                "batch": number,
                "sent": sorted(expected),
                "frames": [
                    {**f, **(annotate(f) if annotate else {})}
                    for f in answer
                    if f.get("index") in expected
                ],
                "usage": response.get("usage") or {},
            },
        )
    return None


def chunks(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def tagging_batches(plan: dict[str, Any]) -> list[list[dict[str, Any]]]:
    """The frames of each tagging request, by the layout prepare stored (`batches`). A
    plan made before the layout was stored gets the fixed chunks of `batch_size` it was
    made with, so a job resumed after the change matches its saved batches."""
    if "batches" not in plan:
        return chunks(plan["frames"], plan["batch_size"])
    by_index = {frame["index"]: frame for frame in plan["frames"]}
    return [[by_index[index] for index in batch] for batch in plan["batches"]]


def text_box(regions: list[dict[str, Any] | None]) -> list[float] | None:
    """One box [x, y, width, height] around the boxes reported for a run (see
    MIN_REGION); None when no frame of the run reported one."""
    reported = []
    for region in regions:
        x, y, w, h = (
            float((region or {}).get(k) or 0) for k in ("x", "y", "width", "height")
        )
        if w > 0 or h > 0:
            w, h = max(w, 0.0), max(h, 0.0)
            reported.append(
                (max(0.0, x), max(0.0, y), min(1.0, x + w), min(1.0, y + h), w, h)
            )
    if not reported:
        return None
    boxes = [
        b for b in reported if b[4] >= MIN_REGION and b[5] >= MIN_REGION
    ] or reported
    left, top = min(b[0] for b in boxes), min(b[1] for b in boxes)
    right, bottom = max(b[2] for b in boxes), max(b[3] for b in boxes)
    return [left, top, right - left, bottom - top]


def padded(start: float, size: float) -> tuple[float, float]:
    """One side of the crop: margin added, grown to MIN_CROP, shifted inside the frame."""
    pad = max(size * CROP_MARGIN, MIN_PAD)
    start, size = start - pad, size + 2 * pad
    if size < MIN_CROP:
        start, size = start - (MIN_CROP - size) / 2, MIN_CROP
    start = min(max(start, 0.0), max(1.0 - size, 0.0))
    return round(start, 4), round(min(size, 1.0 - start), 4)


def crop_box(box: list[float] | None) -> list[float] | None:
    """The run's text box with its margin, kept inside the frame; None for no box."""
    if not box:
        return None
    left, width = padded(box[0], box[2])
    top, height = padded(box[1], box[3])
    return [left, top, width, height]


def short_side_pixels(box: list[float], size: tuple[int, int] | None) -> float | None:
    return min(box[2] * size[0], box[3] * size[1]) if size else None


def plan_rereads(
    runs: list[list[int]],
    tagged: dict[int, dict[str, Any]],
    size: tuple[int, int] | None,
) -> tuple[dict[int, list[int]], dict[int, list[float] | None], list[dict[str, Any]]]:
    """For each run of frames with small text: the frame to re-read (the middle one
    stands for the run) and its crop, or why the re-read is skipped."""
    covers, crops, skipped = {}, {}, []
    for run in runs:
        rep = run[len(run) // 2]
        box = text_box([tagged.get(i, {}).get("text_region") for i in run])
        crops[rep] = crop_box(box)
        pixels = short_side_pixels(box, size) if box else None
        if pixels is not None and pixels < MIN_TEXT_PIXELS:
            skipped.append(
                {"index": rep, "covers": run, "crop": crops[rep],
                 "reason": f"skipped: text box {pixels:.0f} px on its short side in "
                 f"the source (under {MIN_TEXT_PIXELS} px)"}
            )  # fmt: skip
        else:
            covers[rep] = run
    return covers, crops, skipped


def sent_size(crop: list[float] | None, size: tuple[int, int]) -> tuple[int, int]:
    """Width and height of the image full_size_frame sends for a crop of a source of
    `size` (the whole frame for None)."""
    width, height = float(size[0]), float(size[1])
    if crop:
        width, height = width * crop[2], height * crop[3]
        if min(width, height) < UPSCALE_BELOW:
            width, height = width * 2, height * 2
    scale = min(1.0, TEXT_FRAME_WIDTH / max(width, height))
    return round(width * scale), round(height * scale)


def reread_estimate(frames: int, size: tuple[int, int] | None) -> dict[str, Any]:
    """The most the small-text re-read can add (nothing when no frame has small text):
    one re-read frame per run of flagged frames, so at most every other frame, sent
    TEXT_BATCH_SIZE per request, each a crop of at least MIN_CROP of the source at high
    detail. An estimate, like estimate_image_tokens."""
    width, height = sent_size([0.0, 0.0, MIN_CROP, MIN_CROP], size or (2048, 2048))
    per_frame = estimate_image_tokens(width, height, "high")
    max_frames = math.ceil(frames / 2)
    max_requests = math.ceil(max_frames / TEXT_BATCH_SIZE)
    return {
        "max_requests": max_requests,
        "max_frames": max_frames,
        "crop_pixels": [width, height],
        "input_tokens_per_frame": per_frame,
        "max_input_tokens": max_frames * per_frame
        + max_requests * TEXT_REQUEST_OVERHEAD_TOKENS,
    }


def full_size_frame(
    plan: dict[str, Any],
    frame: dict[str, Any],
    target: Path,
    crop: list[float] | None,
    size: tuple[int, int] | None,
) -> dict[str, Any]:
    """The same moment taken again from the original file at full resolution, cropped to
    the text box when there is one (a small crop enlarged 2x), with the longest side at
    most TEXT_FRAME_WIDTH."""
    when = frame["time_seconds"]
    seek = ["-ss", f"{when:.3f}"] if when is not None else []
    filters = []
    if crop:
        x, y, w, h = crop
        filters.append(f"crop=w=iw*{w}:h=ih*{h}:x=iw*{x}:y=ih*{y}")
        if (short_side_pixels(crop, size) or UPSCALE_BELOW) < UPSCALE_BELOW:
            filters.append("scale=w=iw*2:h=ih*2:flags=lanczos")
    longest = TEXT_FRAME_WIDTH
    filters.append(
        f"scale=w='if(gte(iw,ih),min({longest},iw),-2)':h='if(gte(iw,ih),-2,min({longest},ih))'"
    )
    ffmpeg(
        "-loglevel", "error", "-y", *seek, "-i", f"file:{plan['source']['path']}",
        "-frames:v", "1", "-vf", ",".join(filters), "-q:v", "2", f"file:{target}",
    )  # fmt: skip
    return {**frame, "file": str(target)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("job_dir", type=Path)
    args = parser.parse_args()
    job_dir = args.job_dir.expanduser().resolve()
    if not is_job_dir(job_dir) or not (job_dir / "plan.json").is_file():
        fail(f"{args.job_dir} is not a prepared job folder inside work/")
    plan = json.loads((job_dir / "plan.json").read_text(encoding="utf-8"))
    options = plan["options"]
    results_dir = job_dir / "results"
    results_dir.mkdir(exist_ok=True)

    failure = run_batches(
        results_dir,
        "batch",
        tagging_batches(plan),
        lambda batch: build_payload(
            plan,
            batch,
            intro=batch_intro(plan, results_dir, batch),
            instructions=INSTRUCTIONS,
            schema=SCHEMA,
            detail=options["detail"],
        ),
    )
    if failure is None:
        tagged = load_results(job_dir)[0]
        runs = text_runs(plan, needs_text_pass(plan, tagged))
        source = Path(plan["source"]["path"])
        if runs and not source.is_file():
            failure = OpenAIError(
                None,
                "source_missing",
                "the original file moved; small text not re-read",
            )
        else:
            source_size = display_size(probe(source)) if runs else None
            covers, crops, skipped = plan_rereads(runs, tagged, source_size)
            if skipped:
                write_json(results_dir / "reread_skipped.json", {"frames": skipped})
            full_dir = job_dir / "full_frames"
            full_dir.mkdir(exist_ok=True)
            failure = run_batches(
                results_dir,
                "text",
                chunks(
                    [f for f in plan["frames"] if f["index"] in covers], TEXT_BATCH_SIZE
                ),
                lambda batch: build_payload(
                    plan,
                    [
                        full_size_frame(
                            plan,
                            f,
                            full_dir / Path(f["file"]).name,
                            crops[f["index"]],
                            source_size,
                        )
                        for f in batch
                    ],
                    intro=[
                        "Read the text in each frame. Answer with the frame index shown."
                    ],
                    instructions=TEXT_INSTRUCTIONS,
                    schema=TEXT_SCHEMA,
                    detail="high",
                ),
                annotate=lambda f: {
                    "covers": covers[f["index"]],
                    "crop": crops[f["index"]],
                },
            )

    error = (
        {"code": failure.code, "status": failure.status, "message": failure.message}
        if failure
        else None
    )
    if not any(results_dir.glob("batch_*.json")):
        print_json({"status": "failed", "job_dir": str(job_dir), "error": error})
        sys.exit(1)
    summary = finalize(job_dir)
    if error:
        summary["error"] = error
    print_json(summary)
    sys.exit(1 if failure else 0)


if __name__ == "__main__":
    main()
