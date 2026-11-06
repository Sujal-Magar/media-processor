#!/usr/bin/env python3
"""tag-topics, step 2: one OpenAI request (paid, text only, never retried) that tags
what the file is about from the material prepare gathered, then writes the outputs
(finalize.py).

The answer is saved in the job folder before finalize runs, so running this again on
the same job sends nothing. Prints only counts and paths, never tags.

    python3 processors/tag-topics/tag.py work/tag-topics/<job>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `lib`

from finalize import CATEGORIES, finalize

from lib.openai_api import OpenAIError, output_text, request
from lib.workspace import fail, is_job_dir, print_json, write_json

# Reasoning tokens count as output, so leave room beyond the answer itself (tag-visuals
# uses the same for 8 frames).
MAX_OUTPUT_TOKENS = 6000

INSTRUCTIONS = """You tag the files of an organisation's media library by what they are
about, so they can be searched. You get one file as text: what was said (a transcript
in the language spoken, in sentences S1, S2, ... under the times of their part), tags
of what its pictures show (V:<tag>), and text read on screen (T1, T2, ...). A file may
have only some of these. It may also come with partly read on-screen text and the
organisation's own details.
Give tags in three categories:
- type: what kind of media this is (student-testimonial, event-recap, advertisement,
  tutorial, interview, certificate)
- topic: what it is about (australia-student-visa, visa-success-story, scholarship)
- entity: specific named things that are not people: countries, cities, schools and
  universities, organisations, programmes, visa subclasses, products (australia,
  subclass-500)
Spell the organisation's name as the ORGANISATION section gives it, even where the
speech has it differently: speech-to-text can hear a name as a better-known place.
Without that section, prefer the spelling on screen (partly read text included) to the
speech's. Partly read on-screen text is only for checking spellings: never cite it.
Write every tag in English, lowercase, with words joined by hyphens, whatever language
was spoken. Use the common English name of a place or institution.
Never include a person's name, in a tag or in the summary, even when it is said or
shown on screen; refer to people by their role (the student, the counsellor). SPEAKER 0
and SPEAKER 1 are labels, not names. Do not guess age, ethnicity or emotions.
Tag only what the material supports, and give each tag the references it rests on (for
example S4, T2, V:office), at most 5 references per tag (the strongest), using only
references that appear in the material. Cite the sentences that say it, wherever they
are; do not default to the first sentence. Visual tags alone rarely show
what a file is about: rely on speech and on-screen text where there is any. When visual
tags or on-screen text also support a tag (a type tag often rests on what the pictures
show), cite those too.
On-screen text was read by a model and can be wrong.
When the message lists tags already used in this library, treat them as a vocabulary,
not a checklist: reuse one, with its exact wording, only when it describes this file
exactly; otherwise add a new tag.
Give 1 to 3 type tags, up to 10 topic tags and up to 15 entity tags, and a summary of
at most 40 words.
Confidence: high = said or shown plainly; medium = implied or only partly supported;
low = a guess."""

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "tags"],
    "properties": {
        "summary": {"type": "string"},
        "tags": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["label", "category", "confidence", "refs"],
                "properties": {
                    "label": {"type": "string"},
                    "category": {"type": "string", "enum": list(CATEGORIES)},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "refs": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}


def vocabulary_text(existing: list[dict[str, Any]]) -> str:
    if not existing:
        return (
            "No topic tags have been used in this library yet. Choose clear, general "
            "wording that later files can reuse."
        )
    by_category: dict[str, list[str]] = {}
    for tag in existing:
        by_category.setdefault(tag["category"], []).append(tag["label"])
    lines = [
        f"{category}: {', '.join(labels)}" for category, labels in by_category.items()
    ]
    return (
        "Tags already used in this library (most used first). A vocabulary, not a "
        "checklist: use one only when it describes this file exactly, with the same "
        "wording:\n" + "\n".join(lines)
    )


def build_payload(plan: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": plan["options"]["model"],
        "instructions": INSTRUCTIONS,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": vocabulary_text(plan["existing_tags"])},
                    {"type": "input_text", "text": plan["context"]},
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "topics",
                "strict": True,
                "schema": SCHEMA,
            }
        },
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }
    # Working out what a file is about takes some reasoning, unlike frame tagging.
    effort = plan["options"]["reasoning_effort"]
    if effort != "unset":
        payload["reasoning"] = {"effort": effort}
    return payload


def ask(job_dir: Path, plan: dict[str, Any]) -> OpenAIError | None:
    """Send the request once and save the answer; send nothing when it is saved."""
    answer_file = job_dir / "results" / "answer.json"
    if answer_file.exists():  # paid for in an earlier run
        return None
    try:
        response = request("POST", "/responses", build_payload(plan))
        reason = (response.get("incomplete_details") or {}).get("reason")
        if response.get("status") == "incomplete" and reason == "max_output_tokens":
            # Charged, but the answer stops mid-way: say so rather than "bad output".
            raise OpenAIError(
                None, "max_output_tokens", "the answer was cut off at the token limit"
            )
        answer = json.loads(output_text(response))
    except OpenAIError as exc:
        return exc
    except (ValueError, KeyError, TypeError) as exc:
        return OpenAIError(None, "bad_output", f"unexpected answer: {exc}"[:200])
    answer_file.parent.mkdir(exist_ok=True)
    write_json(answer_file, {"answer": answer, "usage": response.get("usage") or {}})
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("job_dir", type=Path)
    args = parser.parse_args()
    job_dir = args.job_dir.expanduser().resolve()
    if not is_job_dir(job_dir) or not (job_dir / "plan.json").is_file():
        fail(f"{args.job_dir} is not a prepared job folder inside work/")
    plan = json.loads((job_dir / "plan.json").read_text(encoding="utf-8"))

    failure = ask(job_dir, plan)
    if failure:
        print_json(
            {
                "status": "failed",
                "job_dir": str(job_dir),
                "error": {
                    "code": failure.code,
                    "status": failure.status,
                    "message": failure.message,
                },
            }
        )
        sys.exit(1)
    print_json(finalize(job_dir))


if __name__ == "__main__":
    main()
