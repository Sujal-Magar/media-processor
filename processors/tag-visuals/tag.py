#!/usr/bin/env python3
"""tag-visuals, step 2: tag the prepared frames with an OpenAI vision model (paid), then
write the outputs (finalize.py).

Pass 1 tags every frame at the planned detail and, where text is visible but too small to
read, reports roughly where it is. When it ran at low detail, pass 2 re-reads that text:
one frame per run of such frames, taken again from the original file at full resolution
and cropped to the reported box, so the text fills the image the model sees. Certificates
or registration numbers are not lost, without paying high detail for every frame.

One request per batch of frames, one at a time, never retried. Finished batches are saved
in the job folder, so running this again on the same job pays only for missing batches.
Prints only counts and paths, never tags, so results stay out of the chat.

    python3 processors/tag-visuals/tag.py work/tag-visuals/<job>
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `lib`

from finalize import (
    finalize,
    load_results,
    needs_text_pass,
    text_runs,
)

from lib.media import ffmpeg
from lib.openai_api import OpenAIError, output_text, request, setting
from lib.workspace import fail, is_job_dir, print_json, write_json

# Pass 2 crops full-resolution frames: the 768 px tagging frames are too small for fine print.
TEXT_FRAME_WIDTH = 2048
TEXT_BATCH_SIZE = 4  # full-size images are larger, so fewer per request
# The re-read crops to the region pass 1 reported, plus this margin on every side (as a
# share of the region), so text near the edge of the box is not cut off.
CROP_MARGIN = 0.15
MIN_REGION = 0.01  # smaller boxes are treated as "no box": the whole frame is re-read

TEXT_RULES = """Copy every clearly readable piece of text exactly as written (signs,
captions, certificates, registration numbers, slides), in its original language and
script, one entry per separate piece of text. Do not translate, correct or guess
unreadable characters; leave the list empty when there is no readable text."""

INSTRUCTIONS = f"""You tag frames from a video or photo library so it can be searched.
For every frame, list what is clearly visible as short lowercase English tags:
- object: physical things (person, laptop, microphone, car, dog)
- scene: the setting (office, classroom, street, kitchen, outdoors, stage)
- activity: what people are doing (presenting, typing, walking, cooking); use
  "speaking to camera" when a person visibly talks to the camera
- attribute: visual qualities (night, close-up, crowded, text on screen)
Use singular nouns or short phrases in plain English. The library may belong to any
kind of organisation, so tag what you see rather than forcing a fixed list. When the
message lists tags already used in this library, reuse that exact wording whenever it
means the same thing, and add a new tag only when none fits.
Use "person" for people: never name or identify anyone, and do not guess age,
ethnicity or emotions. Tag only what you can see.
Give 3 to 15 tags and a summary of at most 15 words per frame.
Confidence: high = unmistakable, medium = likely, low = uncertain.
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
TEXT_LIST = {"type": "array", "items": {"type": "string"}}


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
        "Tags already used in this library (most used first). Reuse the exact wording "
        "when the meaning matches:\n" + "\n".join(lines)
    )


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
    """Send each batch once and save its answer; skip batches saved by an earlier run."""
    for number, batch in enumerate(batches):
        result_file = results_dir / f"{prefix}_{number:03d}.json"
        if result_file.exists():
            continue  # paid for in an earlier run
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
        expected = {frame["index"] for frame in batch}
        write_json(
            result_file,
            {
                "batch": number,
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


def crop_box(region: dict[str, Any] | None) -> list[float] | None:
    """The reported text box plus a margin, kept inside the frame; None if no usable box."""
    if not region:
        return None
    x, y, w, h = (float(region.get(k) or 0) for k in ("x", "y", "width", "height"))
    if w < MIN_REGION or h < MIN_REGION:
        return None
    left, top = max(0.0, x - w * CROP_MARGIN), max(0.0, y - h * CROP_MARGIN)
    right, bottom = (
        min(1.0, x + w * (1 + CROP_MARGIN)),
        min(1.0, y + h * (1 + CROP_MARGIN)),
    )
    if right - left < MIN_REGION or bottom - top < MIN_REGION:
        return None
    return [
        round(left, 4),
        round(top, 4),
        round(right - left, 4),
        round(bottom - top, 4),
    ]


def full_size_frame(
    plan: dict[str, Any], frame: dict[str, Any], target: Path, crop: list[float] | None
) -> dict[str, Any]:
    """The same moment taken again from the original file at full resolution, cropped to
    the text box when there is one, with the longest side at most TEXT_FRAME_WIDTH."""
    when = frame["time_seconds"]
    seek = ["-ss", f"{when:.3f}"] if when is not None else []
    filters = []
    if crop:
        x, y, w, h = crop
        filters.append(f"crop=w=iw*{w}:h=ih*{h}:x=iw*{x}:y=ih*{y}")
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
    options, size = plan["options"], plan["batch_size"]
    results_dir = job_dir / "results"
    results_dir.mkdir(exist_ok=True)

    failure = run_batches(
        results_dir,
        "batch",
        chunks(plan["frames"], size),
        lambda batch: build_payload(
            plan,
            batch,
            intro=[
                existing_tags_text(plan.get("existing_tags", [])),
                "Tag each frame. Answer with the frame index shown.",
            ],
            instructions=INSTRUCTIONS,
            schema=SCHEMA,
            detail=options["detail"],
        ),
    )
    if failure is None:
        tagged = load_results(job_dir)[0]
        runs = text_runs(plan, needs_text_pass(plan, tagged))
        # The middle frame of each run stands for the whole run.
        covers = {run[len(run) // 2]: run for run in runs}
        # Crop to the representative frame's text box, or any box reported in its run.
        crops = {
            rep: next(
                (
                    box
                    for i in [rep, *run]
                    if (box := crop_box(tagged.get(i, {}).get("text_region")))
                ),
                None,
            )
            for rep, run in covers.items()
        }
        if covers and not Path(plan["source"]["path"]).is_file():
            failure = OpenAIError(
                None,
                "source_missing",
                "the original file moved; small text not re-read",
            )
        else:
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
                            plan, f, full_dir / Path(f["file"]).name, crops[f["index"]]
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
