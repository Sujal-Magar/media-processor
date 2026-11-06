"""What earlier processors found for one file, as text for a model: the speech from
transcribe, the visual tags and clearly read on-screen text from tag-visuals. Shared by
the processors that write from those results (tag-topics, generate-copy); draft-report
reads earlier results with read_result and input_record.

The text never holds the file name, which can hold a person's name. Each line carries a
reference (S1 for a sentence, V:<label> for a visual tag, T1 for an on-screen text) that
the model cites and finalize maps back to times.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from lib.tags import clean_label
from lib.workspace import fmt_time

# Most transcript characters sent (about 12,000 tokens of English); the rest is cut.
MAX_SPEECH_CHARS = 48_000
MAX_VISUAL_TAGS = 60  # most seen first
MAX_TEXTS = 60
# A sentence ends at . ! ? or the Devanagari danda, followed by a space.
SENTENCE_END = re.compile(r"(?<=[.!?।॥])\s+")
# A part whose text ends without one stops mid-sentence (parts are cut by time).
SENTENCE_FINISHED = re.compile(r"[.!?।॥][\"'”’)\]]*\s*$")
# Diarized transcripts start each turn with "SPEAKER 0:".
SPEAKER_LABEL = re.compile(r"\s*(SPEAKER \d+):\s*")


def read_result(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def input_record(result: dict[str, Any] | None) -> dict[str, Any] | None:
    """What a result remembers of an input, to notice when it is made again."""
    if result is None:
        return None
    return {
        "created_at": result.get("created_at"),
        "complete": bool(result.get("complete")),
    }


def visual_labels(tags: dict[str, Any]) -> list[tuple[str, str, float | None]]:
    """(label, category, seconds on screen) per visual tag, most seen first. Labels are
    cleaned: results saved before hyphens still have spaces."""
    seen: set[str] = set()
    labels = []
    for tag in tags.get("tags", []):
        label = clean_label(str(tag.get("label") or ""))
        if label and label not in seen:
            seen.add(label)
            labels.append((label, tag.get("category", ""), tag.get("seconds")))
    return labels


def sentences(text: str) -> list[str]:
    return [sentence for sentence in SENTENCE_END.split(text.strip()) if sentence]


def sentence_text(
    sentence: str, speaker: str | None
) -> tuple[str, str | None]:
    """A sentence without the speaker label diarized transcripts start a turn with, and
    who says it (the label, else the speaker before it in the part)."""
    match = SPEAKER_LABEL.match(sentence)
    if match:
        return sentence[match.end() :], match.group(1)
    return sentence, speaker


def speech_section(
    transcript: dict[str, Any], with_text: bool = False
) -> tuple[list[str], dict[str, dict[str, Any]], str | None]:
    """The transcript's parts with their times, each split into sentences S1, S2, ...
    (numbered on through the file), cut after MAX_SPEECH_CHARS. A part can span minutes,
    so a reference also names its sentence within the part. With `with_text` it also
    keeps the sentence as sent (without a speaker label), its speaker, and whether a
    part's edge cuts it (`cut`: "end" for a part's unfinished last sentence, "start"
    for the next part's first one, "both" for a part that is one fragment). Returns the
    lines, their references and a warning if cut."""
    parts = [part for part in transcript.get("parts", []) if part.get("text")]
    total = sum(len(part["text"]) for part in parts)
    lines, refs, left, number = [], {}, MAX_SPEECH_CHARS, 0
    previous_unfinished = False
    for part in parts:
        if left <= 0:
            break
        start, end = part["start_seconds"], part["end_seconds"]
        part_lines = [f"[{fmt_time(start)}-{fmt_time(end)}]"]
        speaker, ref = None, None
        for index, sentence in enumerate(sentences(part["text"]), 1):
            if left <= 0:
                break
            number += 1
            ref = f"S{number}"
            part_lines.append(f"[{ref}] {sentence[:left]}")
            refs[ref] = {
                "source": "speech",
                "start_seconds": start,
                "end_seconds": end,
                "sentence": index,
            }
            if with_text:
                text, speaker = sentence_text(sentence[:left], speaker)
                refs[ref]["text"] = text
                if speaker:
                    refs[ref]["speaker"] = speaker
                if index == 1 and previous_unfinished:
                    refs[ref]["cut"] = "start"
            left -= len(sentence)
        unfinished = not SENTENCE_FINISHED.search(part["text"])
        if with_text and ref and unfinished:
            refs[ref]["cut"] = "both" if refs[ref].get("cut") == "start" else "end"
        previous_unfinished = unfinished
        lines.append("\n".join(part_lines))
    warning = (
        f"The transcript has {total:,} characters; only the first "
        f"{MAX_SPEECH_CHARS:,} are sent, so later speech is left out."
        if total > MAX_SPEECH_CHARS
        else None
    )
    return lines, refs, warning


def visual_sections(
    tags: dict[str, Any],
) -> tuple[list[str], list[str], dict[str, dict[str, Any]]]:
    """Visual tags as V:<label>, and clearly read, confirmed on-screen text as T1, T2,
    ... Partial or unconfirmed text is left out: it may be misread or invented."""
    visual, refs = [], {}
    for label, category, seconds in visual_labels(tags)[:MAX_VISUAL_TAGS]:
        ref = f"V:{label}"
        visual.append(f"[{ref}] {category}" + (f", on screen {seconds:g} s" if seconds else ""))
        refs[ref] = {"source": "visual", "label": label}
    readable = [
        item
        for item in tags.get("on_screen_text", [])
        if item.get("legibility") == "clear" and item.get("confirmed", True) is not False
    ]
    texts = []
    for number, item in enumerate(readable[:MAX_TEXTS], 1):
        ref = f"T{number}"
        ranges = item.get("ranges") or []
        when = f" {fmt_time(ranges[0][0])}" if ranges else ""
        texts.append(f'[{ref}{when}] "{item["text"]}"')
        refs[ref] = {"source": "on_screen_text", "ranges": ranges}
    return visual, texts, refs


def partial_texts(tags: dict[str, Any]) -> list[str]:
    """On-screen text read only partly (cut off, blurred), each once. Unconfirmed text is
    left out: it may be invented."""
    texts = [
        item["text"]
        for item in tags.get("on_screen_text", [])
        if item.get("legibility") == "partial" and item.get("confirmed", True) is not False
    ]
    return list(dict.fromkeys(texts))[:MAX_TEXTS]


def partial_section(tags: dict[str, Any]) -> str:
    """Partly read text for checking how names are spelled, never to quote or cite:
    speech-to-text can mishear a name the screen shows ("Tilicho" heard as a place)."""
    texts = partial_texts(tags)
    if not texts:
        return ""
    return (
        "PARTLY READ ON-SCREEN TEXT (cut off or unclear; never quote or cite it, but use "
        "it to check how names in the speech are spelled)\n"
        + "\n".join(f'- "{text}"' for text in texts)
    )


def screen_texts(tags: dict[str, Any]) -> list[str]:
    """Every on-screen text read, clearly or partly (not unconfirmed), to check names."""
    return list(
        dict.fromkeys(
            item["text"]
            for item in tags.get("on_screen_text", [])
            if item.get("legibility") in ("clear", "partial")
            and item.get("confirmed", True) is not False
        )
    )


def build_context(
    transcript: dict[str, Any] | None,
    tags: dict[str, Any] | None,
    with_text: bool = False,
) -> tuple[str, dict[str, dict[str, Any]], list[str]]:
    """The material sent: a header (kind and length, never the file name), speech,
    visual tags and on-screen text. Returns the text, the references finalize maps back
    to times (speech references hold their sentence with `with_text`), and warnings."""
    source = (tags or transcript or {}).get("source", {})
    duration = source.get("duration_seconds")
    header = f"Media: {source.get('kind') or 'audio or video'}" + (
        f", {fmt_time(duration)} long" if duration else ""
    )
    sections, refs, warnings = [header], {}, []
    if transcript:
        lines, speech_refs, warning = speech_section(transcript, with_text)
        if lines:
            sections.append(
                "SPEECH (transcript in the language spoken; SPEAKER 0, SPEAKER 1 are "
                "labels, not names)\n\n" + "\n\n".join(lines)
            )
        refs.update(speech_refs)
        if warning:
            warnings.append(warning)
    if tags:
        visual, texts, visual_refs = visual_sections(tags)
        if visual:
            sections.append(
                "VISUAL TAGS (what the pictures show, most seen first)\n"
                + "\n".join(visual)
            )
        if texts:
            sections.append(
                "ON-SCREEN TEXT (read from the frames by a model; can be wrong)\n"
                + "\n".join(texts)
            )
        refs.update(visual_refs)
        # Results saved before legibility was recorded: their text was never checked.
        if any("legibility" not in item for item in tags.get("on_screen_text", [])):
            warnings.append(
                "The visual tags were saved before on-screen text was checked for "
                "legibility, so their text was not sent. Run /tag-visuals with force to "
                "include it (charged again)."
            )
    return "\n\n".join(sections), refs, warnings
