"""Subtitles (WebVTT and SRT) from a transcript: cues with estimated times, line
wrapping, and both file formats. Used by transcribe (the transcript's own subtitles) and
translate-subtitles (the same cues in another language).

The ElevenLabs MCP tool gives no word timings, so only each transcript part's start and
end are measured. Inside a part the text is cut into short cues (a sentence, or a piece
of a long one, at most two lines of 42 characters), and the part's time is shared out
among them by their length.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from lib.material import sentence_text, sentences

LINE_CHARS = 42  # a subtitle line most players show without wrapping
CUE_CHARS = 2 * LINE_CHARS
# A cue shorter than this ("Thank you.") would flash by; it joins its neighbour.
MIN_CUE_CHARS = 20
# A cue that cannot join one still gets the time of this many characters (about a
# second of speech), taken from the others in its part.
MIN_TIME_CHARS = 25
# Where a long sentence may be cut: after a comma, semicolon, colon or dash.
CLAUSE_END = re.compile(r"(?<=[,;:–—])\s+")


def width(text: str) -> int:
    """How wide the text shows: characters, not counting marks drawn over or under the
    letter before them (Devanagari ं and ्, accents), which take no room of their own."""
    return sum(unicodedata.category(c) not in ("Mn", "Me") for c in text)


def fits(text: str) -> bool:
    """Whether the text fits a cue: two lines of at most LINE_CHARS once wrapped."""
    return width(text) <= CUE_CHARS and all(width(line) <= LINE_CHARS for line in wrap(text))


def pieces(sentence: str) -> list[str]:
    """A sentence whole if it fits a cue, else cut at clause ends (or, for a clause too
    long itself, between words) into pieces that fit."""
    if fits(sentence):
        return [sentence]
    units = []
    for clause in CLAUSE_END.split(sentence):
        units.extend([clause] if fits(clause) else clause.split())
    found, current = [], ""
    for unit in units:
        joined = f"{current} {unit}" if current else unit
        if fits(joined) or not current:
            current = joined
        else:
            found.append(current)
            current = unit
    return found + [current] if current else found


def wrap(text: str) -> list[str]:
    """One line, or two split at the space nearest the middle that keeps both lines
    within LINE_CHARS (or, when none does, nearest the middle)."""
    if width(text) <= LINE_CHARS or " " not in text:
        return [text]
    middle = len(text) // 2
    spaces = [i for i, c in enumerate(text) if c == " "]
    fitting = [i for i in spaces if width(text[:i]) <= LINE_CHARS and width(text[i + 1 :]) <= LINE_CHARS]
    cut = min(fitting or spaces, key=lambda i: abs(i - middle))
    return [text[:cut], text[cut + 1 :]]


def joined(units: list[tuple[str, str | None]]) -> list[tuple[str, str | None]]:
    """A piece shorter than MIN_CUE_CHARS joined to the one before it (or that one to
    it), when the same speaker says both and together they fit a cue."""
    found: list[tuple[str, str | None]] = []
    for text, speaker in units:
        if found and found[-1][1] == speaker:
            before = found[-1][0]
            both = f"{before} {text}"
            if min(width(before), width(text)) < MIN_CUE_CHARS and fits(both):
                found[-1] = (both, speaker)
                continue
        found.append((text, speaker))
    return found


def cues(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    """The transcript's text as cues with estimated times. A part that failed or holds no
    speech gives none; each speaker turn starts on its own line of the part's text."""
    found = []
    for part in transcript.get("parts", []):
        if part.get("missing") or not str(part.get("text") or "").strip():
            continue
        units: list[tuple[str, str | None]] = []
        speaker = None
        for line in part["text"].splitlines():
            for sentence in sentences(line):
                text, speaker = sentence_text(sentence, speaker)
                units.extend((piece, speaker) for piece in pieces(text.strip()) if piece)
        units = joined(units)
        weights = [max(len(text), MIN_TIME_CHARS) for text, _ in units]
        start, end = float(part["start_seconds"]), float(part["end_seconds"])
        at = start
        for (text, who), weight in zip(units, weights):
            until = at + (end - start) * weight / sum(weights)
            found.append({"start": at, "end": until, "text": text, "speaker": who})
            at = until
    return found


def split_cue(cue: dict[str, Any]) -> list[dict[str, Any]]:
    """A cue whose text does not fit two lines (a translation can run longer than what
    was said) as several cues, cut at sentence and clause ends and joined back while they
    fit, sharing the cue's time by their length; a cue that fits stays as it is."""
    if fits(cue["text"]):
        return [cue]
    parts: list[str] = []
    for sentence in sentences(cue["text"]):
        for piece in pieces(sentence):
            if parts and fits(f"{parts[-1]} {piece}"):
                parts[-1] = f"{parts[-1]} {piece}"
            else:
                parts.append(piece)
    weights = [max(width(text), MIN_TIME_CHARS) for text in parts]
    found, at = [], cue["start"]
    for text, weight in zip(parts, weights):
        until = at + (cue["end"] - cue["start"]) * weight / sum(weights)
        found.append({**cue, "start": at, "end": until, "text": text})
        at = until
    return found


def stamp(seconds: float, separator: str) -> str:
    """00:01:02.345 (WebVTT) or 00:01:02,345 (SRT)."""
    ms = round(seconds * 1000)
    return f"{ms // 3_600_000:02d}:{ms // 60_000 % 60:02d}:{ms // 1000 % 60:02d}{separator}{ms % 1000:03d}"


def vtt_text(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def lines(text: str) -> list[str]:
    """A cue's lines: wrapped in two when it fits; otherwise (a translation can run
    longer than its cue) as many lines of at most LINE_CHARS as it needs."""
    if fits(text) or " " not in text:
        return wrap(text)
    found, current = [], ""
    for word in text.split():
        if current and width(current) + 1 + width(word) > LINE_CHARS:
            found.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    return found + [current]


def to_vtt(found: list[dict[str, Any]], note: str) -> str:
    """WebVTT with a NOTE; a cue's speaker label becomes a voice span."""
    blocks = ["WEBVTT", f"NOTE\n{note}"]
    for number, cue in enumerate(found, 1):
        lines_ = [vtt_text(line) for line in lines(cue["text"])]
        if cue.get("speaker"):  # a voice span: a label, not a name
            lines_[0] = f"<v {cue['speaker']}>{lines_[0]}"
        times = f"{stamp(cue['start'], '.')} --> {stamp(cue['end'], '.')}"
        blocks.append("\n".join([str(number), times, *lines_]))
    return "\n\n".join(blocks) + "\n"


def to_srt(found: list[dict[str, Any]]) -> str:
    """SRT: numbered cues, comma times, no speaker labels."""
    blocks = [
        "\n".join([str(number), f"{stamp(cue['start'], ',')} --> {stamp(cue['end'], ',')}",
                   *lines(cue["text"])])  # fmt: skip
        for number, cue in enumerate(found, 1)
    ]
    return "\n\n".join(blocks) + "\n" if blocks else ""
