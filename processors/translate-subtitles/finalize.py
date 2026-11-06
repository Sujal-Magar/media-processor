#!/usr/bin/env python3
"""translate-subtitles, step 3: turn the model's answer into
output/translate-subtitles/<name>-<hash>/transcript.<track>.vtt and .srt for each track,
translation.json and metadata.json. Free; translate.py runs it.

Every cue keeps its number and times from the transcript's own subtitles, so all the
tracks stay in step. The tracks in the language most of the speech is in are put
together here: each cue as said, with only its spans (the words said in another
language, and words that may be the organisation's name misheard) replaced by the
model's rendering, so every word said in that language stays as transcribed. There are
two: the spans translated (transcript.ne), and the spans written in that language's
script by their sound (transcript.ne-spoken). Other tracks are the model's translation
of each whole cue. A cue or span the answer left out keeps the words as said and is
named in `missing` (the result is then incomplete). A cue too long for two lines is shown
as several cues within its time. `checks` lists what a speaker of the language should
look at: a cue in the wrong script, a number lost, a whole-cue track that reworded the
words said in its own language, a cue split to fit.
Prints only counts, paths and these notes, never the text.

    python3 processors/translate-subtitles/finalize.py work/translate-subtitles/<job> [--keep-work]
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

from lib.subtitles import lines, split_cue, to_srt, to_vtt
from lib.workspace import (
    archive_previous,
    fail,
    is_job_dir,
    now_iso,
    print_json,
    result_metadata,
    write_json,
    write_text,
)

# Language code: (name, the script its subtitles are written in).
LANGUAGES = {"en": ("English", "Latin"), "ne": ("Nepali", "Devanagari")}
SPOKEN = "-spoken"  # the track of a language as spoken: other words written by their sound
DEVANAGARI = re.compile(r"[ऀ-ॣ॰-ॿ]")  # letters and signs, not digits
LATIN = re.compile(r"[A-Za-zÀ-ɏ]")
LETTER = re.compile(r"[^\W\d_]")
# A run of one script inside a word: Latin letters, Devanagari letters and signs, or
# anything else (digits, the danda, punctuation). "marketमा" is "market" + "मा".
PIECE = re.compile(
    r"[A-Za-zÀ-ɏ'’]+|[ऀ-ॣ॰-ॿ]+"
    r"|[^A-Za-zÀ-ɏ'’ऀ-ॣ॰-ॿ]+"
)
# Digits in either script; Devanagari ones (०-९) are read as their value.
DIGITS = re.compile(r"[0-9०-९]+")
TO_ASCII = str.maketrans("०१२३४५६७८९", "0123456789")
MAX_LINES = 2
# A whole-cue track keeps the words said in its own language; one that keeps fewer than
# this share of them (in a cue with at least MIN_SAID_WORDS of them) reworded them.
KEEP_SHARE, MIN_SAID_WORDS = 0.9, 3
# What is trimmed from a word's ends: anything but letters, digits and Devanagari signs
# (so the danda । goes too).
WORD_EDGES = re.compile(r"^[^\wऀ-ॣ०-ॿ]+|[^\wऀ-ॣ०-ॿ]+$")
MAX_NOTES = 10


def text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def numbers(value: str) -> set[str]:
    return {found.translate(TO_ASCII).lstrip("0") or "0" for found in DIGITS.findall(value)}


def track_name(code: str) -> str:
    """English, Nepali, Nepali as spoken."""
    base = code.removesuffix(SPOKEN)
    return LANGUAGES[base][0] + (" as spoken" if code.endswith(SPOKEN) else "")


def track_script(code: str) -> str:
    return LANGUAGES[code.removesuffix(SPOKEN)][1]


def answer_key(code: str) -> str:
    """The track's field in the model's answer: ne, ne_spoken."""
    return code.replace("-", "_")


def script_words(text: str, script: str) -> list[str]:
    """The words of the text written in a script (Devanagari or Latin), lowercased and
    trimmed of punctuation; numbers are left out."""
    found = []
    for token in text.lower().split():
        token = WORD_EDGES.sub("", token)
        devanagari = bool(DEVANAGARI.search(token))
        if token and devanagari == (script == "Devanagari") and (devanagari or LETTER.search(token)):
            found.append(token)
    return found


def spoken_first(cues: list[dict[str, Any]], languages: list[str]) -> list[str]:
    """The languages with the one most of the speech is in first (by words in its
    script)."""
    said = {code: sum(len(script_words(cue["text"], LANGUAGES[code][1])) for cue in cues) for code in languages}
    return sorted(languages, key=lambda code: -said[code])


def token_script(token: str) -> str | None:
    """The script a piece is written in; None for numbers and punctuation."""
    if DEVANAGARI.search(token):
        return "Devanagari"
    return "Latin" if LATIN.search(token) else None


def pieces_of(text: str, heard_as: list[str]) -> list[tuple[str, bool, str | None, bool]]:
    """Each word's runs of one script as (piece, space before it, script, is a heard_as
    form). A piece starting with a form of the organisation's name as speech-to-text
    writes it has that form apart, its ending kept as said."""
    forms = sorted({form.lower() for form in heard_as if len(form) >= 3}, key=len, reverse=True)
    found = []
    for number, word in enumerate(text.split()):
        for index, match in enumerate(PIECE.finditer(word)):
            piece, space = match.group(), number > 0 and index == 0
            form = next((f for f in forms if piece.lower().startswith(f)), None)
            if form:
                found.append((piece[: len(form)], space, token_script(piece), True))
                if rest := piece[len(form) :]:
                    found.append((rest, False, token_script(rest), False))
            else:
                found.append((piece, space, token_script(piece), False))
    return found


def joined(items: list[tuple[str, bool, str | None, bool]]) -> str:
    return "".join((" " if space and n else "") + piece for n, (piece, space, _, _) in enumerate(items))


def split_spans(text: str, keep: str, heard_as: list[str] | None = None) -> list[dict[str, Any]]:
    """The cue as parts: runs to keep as said ({"text"}) and spans ({"span"}): words in
    another script, numbers and punctuation between two of them included, and on their
    own the forms of the organisation's name as heard ("name": True). "space" says
    whether a space comes before the part."""
    items = pieces_of(text, heard_as or [])
    other = [name or (script is not None and script != keep) for _, _, script, name in items]
    parts, i = [], 0
    while i < len(items):
        j = i
        if other[i]:
            k = i
            while not items[i][3] and k + 1 < len(items) and not items[k + 1][3] and (
                other[k + 1] or items[k + 1][2] is None
            ):
                k += 1
                if other[k]:
                    j = k
            part: dict[str, Any] = {"span": joined(items[i : j + 1]), "space": items[i][1]}
            if items[i][3]:
                part["name"] = True
        else:
            while j + 1 < len(items) and not other[j + 1]:
                j += 1
            part = {"text": joined(items[i : j + 1]), "space": items[i][1]}
        parts.append(part)
        i = j + 1
    return parts


def assemble(parts: list[dict[str, Any]], rendered: dict[str, str], spans: dict[str, str]) -> str:
    """A cue from its parts, each span replaced by its rendering (or kept as said)."""
    return "".join(
        (" " if part["space"] else "")
        + (part["text"] if "text" in part else rendered.get(part["span"]) or spans[part["span"]])
        for part in parts
    )


def answers(
    answer: dict[str, Any], plan: dict[str, Any]
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]], int]:
    """Each cue's translations (by cue id, per whole-cue track) and each span's
    renderings (by span id, per assembled track), the first answer for one counting, and
    how many answers named nothing that was sent."""
    options = plan["options"]
    assembled = [code for code in (options["assembled"], options.get("spoken")) if code]
    known_cues = {cue["id"] for cue in plan["cues"]}
    known_spans = {span["id"] for span in plan.get("spans", [])}
    cues: dict[str, dict[str, str]] = {}
    spans: dict[str, dict[str, str]] = {}
    unknown = 0
    for item in answer.get("cues") or []:
        cue = str(item.get("cue") or "").strip().strip("[]")
        if cue not in known_cues:
            unknown += 1
        elif cue not in cues:
            cues[cue] = {code: text(item.get(code)) for code in options["full"]}
    for item in answer.get("spans") or []:
        span = str(item.get("span") or "").strip().strip("[]")
        if span not in known_spans:
            unknown += 1
        elif span not in spans:
            spans[span] = {code: text(item.get(answer_key(code))) for code in assembled}
    return cues, spans, unknown


def track_codes(options: dict[str, Any]) -> list[str]:
    """Every track made: the languages asked for, and the spoken one."""
    return [*options["languages"], *([options["spoken"]] if options.get("spoken") else [])]


def build_tracks(
    plan: dict[str, Any], cue_answers: dict[str, dict[str, str]], span_answers: dict[str, dict[str, str]]
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    """One track per code, cue for cue. An assembled track keeps each cue as said and
    puts in its spans; a span without a rendering stays as said. A whole-cue track
    without its translation keeps the original text. Both are named in `missing`."""
    options = plan["options"]
    assembled = [code for code in (options["assembled"], options.get("spoken")) if code]
    said = {span["id"]: span["text"] for span in plan.get("spans", [])}
    tracks: dict[str, list[dict[str, Any]]] = {code: [] for code in track_codes(options)}
    missing = []
    for cue in plan["cues"]:
        shown = {k: v for k, v in cue.items() if k != "parts"}
        for code in assembled:
            rendered = {sid: found.get(code, "") for sid, found in span_answers.items()}
            for part in cue.get("parts") or []:
                if "span" in part and not rendered.get(part["span"]):
                    missing.append(
                        f"{part['span']} (in {cue['id']}) has no {track_name(code)}; the words as said are kept."
                    )
            line = assemble(cue["parts"], rendered, said) if cue.get("parts") else cue["text"]
            tracks[code].append({**shown, "text": line})
        for code in options["full"]:
            translated = cue_answers.get(cue["id"], {}).get(code, "")
            if not translated:
                missing.append(f"{cue['id']} has no {track_name(code)} translation; its original text is kept.")
            tracks[code].append({**shown, "text": translated or cue["text"]})
    return tracks, missing


def track_checks(
    cues: list[dict[str, Any]], tracks: dict[str, list[dict[str, Any]]], full: list[str]
) -> list[str]:
    """What a speaker of each language should look at, cue by cue."""
    checks = []
    for code, track in tracks.items():
        name, script = track_name(code), track_script(code)
        for original, cue in zip(cues, track):
            line = cue["text"]
            if script == "Devanagari" and LETTER.search(line) and not DEVANAGARI.search(line):
                checks.append(f"{cue['id']} in {name} has no Devanagari; check that it was translated.")
            elif script == "Devanagari" and code.endswith(SPOKEN) and LATIN.search(line):
                checks.append(f"{cue['id']} in {name} still has Latin letters; check that every word is in Devanagari.")
            if script == "Latin" and DEVANAGARI.search(line):
                checks.append(f"{cue['id']} in {name} still has Devanagari; check that it was translated.")
            said = script_words(original["text"], script)
            if code in full and len(said) >= MIN_SAID_WORDS:
                kept = set(script_words(line, script))
                share = sum(word in kept for word in said) / len(said)
                if share < KEEP_SHARE:
                    checks.append(
                        f"{cue['id']} in {name} keeps {share:.0%} of the words said in "
                        f"{name}; check that it keeps what was said and translates only the rest."
                    )
            if lacking := sorted(numbers(original["text"]) - numbers(line)):
                checks.append(
                    f"{cue['id']} in {name} lacks the number {', '.join(lacking)} that the "
                    "original has."
                )
    return checks


def shown_tracks(
    tracks: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, list[dict[str, Any]]], list[str], list[dict[str, Any]]]:
    """Each track as it is shown: a cue too long for two lines split within its time.
    Returns the tracks, checks for the splits (and for a piece still too long, a single
    word that does not fit), and which cues were split."""
    shown: dict[str, list[dict[str, Any]]] = {}
    checks, splits = [], []
    for code, track in tracks.items():
        name = track_name(code)
        shown[code] = []
        for cue in track:
            parts = split_cue(cue)
            if len(parts) > 1:
                splits.append({"cue": cue["id"], "track": code, "cues": len(parts)})
                checks.append(
                    f"{cue['id']} in {name} was too long for two lines, so it shows as "
                    f"{len(parts)} cues within its time; check where it breaks."
                )
            for part in parts:
                if (count := len(lines(part["text"]))) > MAX_LINES:
                    checks.append(f"{cue['id']} in {name} still runs to {count} lines; shorten it.")
            shown[code].extend(parts)
    return shown, checks, splits


def note(code: str, model: str) -> str:
    name = LANGUAGES[code.removesuffix(SPOKEN)][0]
    if code.endswith(SPOKEN):
        made = (f"{name} subtitles as spoken: every word as said, the words said in another "
                f"language written in {track_script(code)} by their sound (by a model, {model})")  # fmt: skip
    else:
        made = f"{name} translation of the transcript's subtitles, made by a model ({model})"
    return (
        f"{made}; a draft. Times as in transcript.vtt: estimated within each transcript "
        f"part. Have a {name} speaker check it against the video before publishing."
    )


def finalize(job_dir: Path, keep_work: bool = False) -> dict[str, Any]:
    plan = json.loads((job_dir / "plan.json").read_text(encoding="utf-8"))
    answer_file = job_dir / "results" / "answer.json"
    if not answer_file.is_file():
        fail("no answer found; nothing to save (the work folder was kept)")
    result = json.loads(answer_file.read_text(encoding="utf-8"))
    answer, cues, options = result["answer"], plan["cues"], plan["options"]
    codes = track_codes(options)
    usage = result.get("usage") or {}

    cue_answers, span_answers, unknown = answers(answer, plan)
    tracks, missing = build_tracks(plan, cue_answers, span_answers)
    shown, split_notes, splits = shown_tracks(tracks)
    checks = track_checks(cues, tracks, options["full"]) + split_notes
    notes = [note for note in (text(n) for n in answer.get("review_notes") or []) if note]
    status = "incomplete" if missing else "complete"

    output_dir = Path(plan["output_dir"])
    subtitle_files = [f"transcript.{code}.{kind}" for code in codes for kind in ("vtt", "srt")]
    files = [*subtitle_files, "translation.json", "metadata.json"]
    archived = archive_previous(output_dir, "translation.json", files, plan.get("replaces"))
    for code in codes:
        write_text(output_dir / f"transcript.{code}.vtt", to_vtt(shown[code], note(code, options["model"])))
        write_text(output_dir / f"transcript.{code}.srt", to_srt(shown[code]))
    assembled = [code for code in (options["assembled"], options.get("spoken")) if code]
    document = {
        "version": 1,
        "processor": plan["processor"],
        "complete": not missing,
        # Machine translations for a speaker of each language to check; never published as they are.
        "review_status": "draft",
        "source": plan["source"],
        # When the transcript was made; prepare compares it to notice a newer one.
        "inputs": plan["inputs"],
        "organisation": plan.get("organisation"),
        "options": options,
        "provider": {"name": "openai", "model": options["model"]},
        "usage": {
            "requests": 1,
            "input_tokens": int(usage.get("input_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or 0),
        },
        "estimated_input_tokens": plan["estimated_input_tokens"],
        "missing": missing,
        "checks": checks,
        "review_notes": notes[:MAX_NOTES],
        # Answers for a cue or span that was not sent.
        "dropped": unknown,
        # Cues that show as several cues within their time.
        "split": splits,
        "cues": [
            {**{k: v for k, v in cue.items() if k != "parts"},
             **{code: tracks[code][number]["text"] for code in codes}}
            for number, cue in enumerate(cues)
        ],  # fmt: skip
        # The words said in another language (and name forms) inside the assembled cues.
        "spans": [{**span, **{code: span_answers.get(span["id"], {}).get(code, "") for code in assembled}}
                  for span in plan.get("spans", [])],  # fmt: skip
        "created_at": now_iso(),
    }
    write_json(output_dir / "translation.json", document)
    # The context and cues hold the transcript's text, which has its own result.
    kept = {k: v for k, v in plan.items() if k not in ("context", "cues", "spans")}
    write_json(output_dir / "metadata.json", result_metadata(kept, status))
    if not keep_work:
        shutil.rmtree(job_dir)

    return {
        "status": status,
        "output_dir": str(output_dir),
        "files": files,
        "previous_result": str(archived) if archived else None,
        "tracks": [track_name(code) for code in codes],
        "cues": len(cues),
        "translated": {
            **{track_name(code): sum(bool(cue_answers.get(c["id"], {}).get(code)) for c in cues)
               for code in options["full"]},
            **{f"{track_name(code)} spans": sum(bool(span_answers.get(s["id"], {}).get(code))
               for s in plan.get("spans", [])) for code in assembled},
        },  # fmt: skip
        "spans": len(plan.get("spans", [])),
        "dropped": unknown,
        "split": len(splits),
        "missing": missing,
        "checks": checks,
        "review_notes": document["review_notes"],
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
