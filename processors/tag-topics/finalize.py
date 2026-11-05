#!/usr/bin/env python3
"""tag-topics, step 3: turn the model's answer into output/tag-topics/<name>-<hash>/
topics.md, topics.json and metadata.json. Free; tag.py runs it.

Each tag keeps the evidence its references point to (a speech part with its times, an
on-screen text, a visual tag); a reference to something that was not sent is dropped,
and so is a tag left with none. Tags not in the library's existing tags are marked new.
Prints only counts and paths, never tags.

    python3 processors/tag-topics/finalize.py work/tag-topics/<job> [--keep-work]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `lib`

from lib.tags import clean_label
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

CATEGORIES = ("type", "topic", "entity")
HEADINGS = {"type": "Type", "topic": "Topics", "entity": "Entities"}
CONFIDENCE = ("high", "medium", "low")
INPUT_NAMES = {"transcript": "transcript", "tags": "visual tags"}


def cell(value: str) -> str:
    """Make a value safe inside a Markdown table cell."""
    return value.replace("|", "\\|").replace("\n", " ")


def clean_answer(
    answer: dict[str, Any], refs: dict[str, dict[str, Any]], known: set[str]
) -> list[dict[str, Any]]:
    """The model's tags as stored: labels cleaned (lib.tags), each with the evidence its
    references point to. A tag repeated after cleaning keeps its first confidence and
    gains the other's evidence."""
    kept: dict[tuple[str, str], dict[str, Any]] = {}
    for tag in answer.get("tags", []):
        label = clean_label(str(tag.get("label") or ""))
        category = tag.get("category")
        evidence = [
            {"ref": ref, **refs[ref]}
            for ref in dict.fromkeys(tag.get("refs") or [])
            if ref in refs
        ]
        if not label or category not in CATEGORIES or not evidence:
            continue
        confidence = tag.get("confidence")
        entry = kept.setdefault(
            (label, category),
            {"label": label, "category": category,
             "confidence": confidence if confidence in CONFIDENCE else "low",
             "new": label not in known, "evidence": []},
        )  # fmt: skip
        entry["evidence"] += [e for e in evidence if e not in entry["evidence"]]
    return list(kept.values())


def evidence_text(item: dict[str, Any]) -> str:
    if item["source"] == "speech":
        span = f"speech {fmt_time(item['start_seconds'])}-{fmt_time(item['end_seconds'])}"
        # Results made before speech was split into sentences name only the part.
        return span + (f", sentence {item['sentence']}" if "sentence" in item else "")
    if item["source"] == "on_screen_text":
        ranges = item.get("ranges") or []
        return "on-screen text" + (f" {fmt_time(ranges[0][0])}" if ranges else "")
    return f"visual: {item['label']}"


def inputs_line(inputs: dict[str, Any]) -> str:
    return ", ".join(
        INPUT_NAMES[name] + ("" if record["complete"] else " (incomplete)")
        for name, record in inputs.items()
        if record and name in INPUT_NAMES
    )


def to_markdown(plan: dict[str, Any], document: dict[str, Any]) -> str:
    lines = [
        f"# Topics: {plan['source']['name']}",
        "",
        f"- Made from: {inputs_line(document['inputs'])}",
        (
            f"- Model: {document['provider']['model']}; confidence is the model's own "
            "estimate"
        ),
        f"- New tags (not used in this library before): {document['new_tags']}",
        f"- Review status: {document['review_status']}",
        f"- Created: {document['created_at']}",
        "",
        "> Made by a model from what was said, the visual tags and the text read on "
        "screen. People are never named. Check a tag's evidence before relying on it.",
        "",
        "## Summary",
        "",
        document["summary"] or "_No summary._",
    ]
    for category in CATEGORIES:
        entries = [t for t in document["tags"] if t["category"] == category]
        lines.extend(["", f"## {HEADINGS[category]}", ""])
        if not entries:
            lines.append("_None._")
            continue
        lines.extend(["| Tag | Confidence | Evidence |", "| --- | --- | --- |"])
        for tag in entries:
            label = cell(tag["label"]) + (" *(new)*" if tag["new"] else "")
            evidence = "; ".join(evidence_text(e) for e in tag["evidence"])
            lines.append(f"| {label} | {tag['confidence']} | {cell(evidence)} |")
    lines.extend(["", "## Visual tags", "", ", ".join(document["visual"]) or "_None._"])
    return "\n".join(lines) + "\n"


def finalize(job_dir: Path, keep_work: bool = False) -> dict[str, Any]:
    plan = json.loads((job_dir / "plan.json").read_text(encoding="utf-8"))
    answer_file = job_dir / "results" / "answer.json"
    if not answer_file.is_file():
        fail("no answer found; nothing to save (the work folder was kept)")
    result = json.loads(answer_file.read_text(encoding="utf-8"))
    answer = result["answer"]
    known = {tag["label"] for tag in plan["existing_tags"]}
    tags = clean_answer(answer, plan["refs"], known)
    usage = result.get("usage") or {}

    output_dir = Path(plan["output_dir"])
    files = ["topics.md", "topics.json", "metadata.json"]
    archived = archive_previous(output_dir, "topics.json", files, plan.get("replaces"))
    document = {
        "version": 1,
        "processor": plan["processor"],
        "complete": True,
        # Machine-made tags awaiting human review; shown to clients meanwhile.
        "review_status": "staging_pending",
        "source": plan["source"],
        # When each input was made; prepare compares them to notice a newer one.
        "inputs": plan["inputs"],
        "options": plan["options"],
        "provider": {
            "name": "openai",
            "model": plan["options"]["model"],
            "confidence": "model-reported, not calibrated",
        },
        "usage": {
            "requests": 1,
            "input_tokens": int(usage.get("input_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or 0),
        },
        "estimated_input_tokens": plan["estimated_input_tokens"],
        "existing_tags_offered": len(plan["existing_tags"]),
        "new_tags": sum(tag["new"] for tag in tags),
        "visual": plan["visual"],
        **{c: [t["label"] for t in tags if t["category"] == c] for c in CATEGORIES},
        "summary": re.sub(r"\s+", " ", str(answer.get("summary") or "")).strip(),
        "tags": tags,
        "created_at": now_iso(),
    }
    write_json(output_dir / "topics.json", document)
    write_text(output_dir / "topics.md", to_markdown(plan, document))
    # The context holds the transcript, which already has its own result.
    write_json(
        output_dir / "metadata.json",
        result_metadata({k: v for k, v in plan.items() if k != "context"}, "complete"),
    )
    if not keep_work:
        shutil.rmtree(job_dir)

    return {
        "status": "complete",
        "output_dir": str(output_dir),
        "files": files,
        "previous_result": str(archived) if archived else None,
        "tags": {c: len(document[c]) for c in CATEGORIES},
        # Answered tags not kept: no evidence that was sent, or a repeat.
        "tags_dropped": len(answer.get("tags", [])) - len(tags),
        "new_tags": document["new_tags"],
        "usage": document["usage"],
        "warnings": plan["warnings"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("job_dir", type=Path)
    parser.add_argument("--keep-work", action="store_true", help="keep the job folder")
    args = parser.parse_args()
    job_dir = args.job_dir.expanduser().resolve()
    if not is_job_dir(job_dir) or not (job_dir / "plan.json").is_file():
        fail(f"{args.job_dir} is not a prepared job folder inside work/")
    print_json(finalize(job_dir, args.keep_work))


if __name__ == "__main__":
    main()
