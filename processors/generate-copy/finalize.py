#!/usr/bin/env python3
"""generate-copy, step 3: turn the model's answer into output/generate-copy/<name>-<hash>/
copy.md, copy.json and metadata.json. Free; generate.py runs it.

Hooks and script segments keep the footage their references point to (a sentence with
its part's times, a visual tag or on-screen text with its time ranges); a reference to
something that was not sent is dropped, and so is a hook or segment left with none, its
translation with it. A result that lacks a part the request asked for is saved as
incomplete and names it; `checks` lists what a reviewer must look at (a caption too long,
a brand hashtag nothing confirms, a soundbite cut mid-sentence, on-screen text copied
word for word). Prints only counts, paths and these notes, never copy.

    python3 processors/generate-copy/finalize.py work/generate-copy/<job> [--keep-work]
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

from lib.organisation import brand_forms, hashtag_form
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

# Platform: (name, longest caption it accepts in characters).
PLATFORMS = {
    "instagram-reels": ("Instagram Reels", 2200),
    "tiktok": ("TikTok", 4000),
    "linkedin": ("LinkedIn", 3000),
    "youtube-shorts": ("YouTube Shorts", 5000),
}
HOOK_STYLES = ("question", "statement", "curiosity", "story", "benefit")
PURPOSES = ("hook", "context", "story", "proof", "call-to-action")
MIN_HOOKS, MAX_HOOKS = 3, 5
MAX_REFS = 5
MAX_NOTES = 10
ANY_SOURCE = ("speech", "visual", "on_screen_text")
HASHTAG_CLUSTERS = ("niche", "broad", "brand")
MAX_HASHTAGS = {"niche": 10, "broad": 10, "brand": 5}
INPUT_NAMES = {"transcript": "transcript", "tags": "visual tags", "topics": "topic tags"}
# A reference as a model may write it: S6, [S6], a range S6-S8 (S6–8), T2, V:office.
REF_PATTERN = re.compile(
    r"\b(?P<kind>[ST])(?P<first>\d+)\s*[-–—]\s*(?P=kind)?(?P<last>\d+)\b"
    r"|\b(?P<one>[ST]\d+)\b|(?P<visual>V:[\w-]+)"
)
MAX_RANGE = 20


def text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_refs(values: list[Any] | None) -> list[str]:
    """The references in what the model wrote, in order: a range (S6-S8) becomes each
    sentence in it, and brackets, commas or "and" between references do not matter."""
    found = []
    for value in values or []:
        for match in REF_PATTERN.finditer(str(value)):
            if match["kind"]:
                first, last = int(match["first"]), int(match["last"])
                if first <= last <= first + MAX_RANGE:
                    found += [f"{match['kind']}{n}" for n in range(first, last + 1)]
            else:
                found.append(match["one"] or match["visual"])
    return found


def evidence(
    refs: list[Any] | None, known: dict[str, dict[str, Any]], sources: tuple[str, ...]
) -> list[dict[str, Any]]:
    """What the references point to, in order, without repeats, unknown references or
    sources that do not belong here; at most MAX_REFS."""
    kept = [
        {"ref": ref, **known[ref]}
        for ref in dict.fromkeys(parse_refs(refs))
        if ref in known and known[ref]["source"] in sources
    ]
    return kept[:MAX_REFS]


def clean_hooks(
    hooks: list[dict[str, Any]] | None,
    refs: dict[str, dict[str, Any]],
    translate: bool,
    dropped: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Hooks with footage behind them, without repeats (case and spacing ignored), each
    with its own translation when one was asked for. A hook dropped for its references
    is added to `dropped` with them as written."""
    kept, seen = [], set()
    for number, hook in enumerate(hooks or [], 1):
        line = text(hook.get("text"))
        found = evidence(hook.get("refs"), refs, ANY_SOURCE)
        if line and not found and dropped is not None:
            dropped.append({"hook": number, "refs": hook.get("refs") or []})
        if not line or not found or line.lower() in seen:
            continue
        seen.add(line.lower())
        style = hook.get("style")
        entry = {"text": line, "style": style if style in HOOK_STYLES else "statement",
                 "evidence": found}  # fmt: skip
        if translate:
            entry["translation"] = text(hook.get("translation"))
        kept.append(entry)
    return kept[:MAX_HOOKS]


def clean_script(
    script: dict[str, Any] | None, refs: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """The edit: segments in order, soundbites only from speech and B-roll only from the
    pictures or on-screen text; a segment with neither is dropped, and its references
    as written are kept in `segments_dropped`."""
    segments, dropped = [], []
    for number, segment in enumerate((script or {}).get("segments") or [], 1):
        soundbites = evidence(segment.get("soundbites"), refs, ("speech",))
        broll = evidence(segment.get("broll"), refs, ("visual", "on_screen_text"))
        if not soundbites and not broll:
            dropped.append(
                {"segment": number, "soundbites": segment.get("soundbites") or [],
                 "broll": segment.get("broll") or []}
            )  # fmt: skip
            continue
        purpose = segment.get("purpose")
        segments.append(
            {
                "purpose": purpose if purpose in PURPOSES else "story",
                "soundbites": soundbites,
                "subtitle": text(segment.get("subtitle")),
                "broll": broll,
                "overlay_text": text(segment.get("overlay_text")),
                "note": text(segment.get("note")),
            }
        )
    return {
        "title": text((script or {}).get("title")),
        "segments": segments,
        "segments_dropped": dropped,
    }


def clean_captions(
    captions: list[dict[str, Any]] | None,
    refs: dict[str, dict[str, Any]],
    platforms: list[str],
    translate: bool,
) -> list[dict[str, Any]]:
    """The first caption with text for each requested platform, in the requested order,
    with its translation when one was asked for. Captions keep the footage they cite,
    but are kept without it too."""
    first: dict[str, dict[str, Any]] = {}
    for caption in captions or []:
        platform = caption.get("platform")
        body = str(caption.get("text") or "").strip()
        if platform in platforms and body and platform not in first:
            first[platform] = {
                "platform": platform,
                "text": body,
                "call_to_action": text(caption.get("call_to_action")),
                "evidence": evidence(caption.get("refs"), refs, ANY_SOURCE),
            }
            if translate:
                first[platform]["translation"] = str(caption.get("translation") or "").strip()
    return [first[p] for p in platforms if p in first]


def clean_hashtags(hashtags: dict[str, Any] | None) -> dict[str, list[str]]:
    """In hashtag form (lib.organisation), each once over all clusters (the first
    cluster keeps it), capped per cluster."""
    seen: set[str] = set()
    cleaned: dict[str, list[str]] = {}
    for cluster in HASHTAG_CLUSTERS:
        cleaned[cluster] = []
        for value in (hashtags or {}).get(cluster) or []:
            tag = hashtag_form(str(value))
            if tag and tag not in seen and len(cleaned[cluster]) < MAX_HASHTAGS[cluster]:
                seen.add(tag)
                cleaned[cluster].append(tag)
    return cleaned


def names(platforms: list[str]) -> str:
    return ", ".join(PLATFORMS[p][0] for p in platforms)


def missing_parts(
    hooks: list[dict[str, Any]],
    script: dict[str, Any],
    captions: list[dict[str, Any]],
    options: dict[str, Any],
    has_speech: bool = False,
) -> list[str]:
    """What the request asked for and the result lacks; empty when complete. A video
    with speech needs a script that uses some of it."""
    missing = []
    if len(hooks) < MIN_HOOKS:
        missing.append(
            f"only {len(hooks)} usable hooks (at least {MIN_HOOKS} were asked for)"
        )
    if not script["segments"]:
        missing.append("no script segment uses footage that was sent")
    elif has_speech and not any(s["soundbites"] for s in script["segments"]):
        missing.append("the script uses none of the speech (no soundbites)")
    have = {caption["platform"] for caption in captions}
    if lacking := [p for p in options["platforms"] if p not in have]:
        missing.append(f"no caption for {names(lacking)}")
    if language := options.get("translate"):
        if untranslated := sum(not hook["translation"] for hook in hooks):
            missing.append(f"{untranslated} hooks have no {language} translation")
        if lacking := [c["platform"] for c in captions if not c["translation"]]:
            missing.append(f"no {language} translation of the {names(lacking)} caption")
    return missing


def caption_checks(captions: list[dict[str, Any]]) -> list[str]:
    checks = []
    for caption in captions:
        name, limit = PLATFORMS[caption["platform"]]
        if len(caption["text"]) > limit:
            checks.append(
                f"The {name} caption has {len(caption['text']):,} characters; {name} "
                f"accepts {limit:,}. Shorten it before posting."
            )
    return checks


def brand_checks(
    brand: list[str], organisation: dict[str, Any] | None, screen: list[str]
) -> list[str]:
    """Brand hashtags that neither contain one of the organisation's names nor appear in
    any on-screen text: speech-to-text may have misheard the name they come from."""
    forms = brand_forms(organisation)
    shown = [hashtag_form(item) for item in screen]
    return [
        f"The brand hashtag #{tag} matches neither organisation.json nor any on-screen "
        "text; check its spelling before posting."
        for tag in brand
        if not any(form in tag for form in forms) and not any(tag in s for s in shown)
    ]


def cut_checks(segments: list[dict[str, Any]]) -> list[str]:
    """An opening or closing soundbite that a transcript part's edge cuts mid-sentence."""
    if not segments:
        return []
    checks = []
    opening = (segments[0]["soundbites"] or [None])[0]
    if opening and opening.get("cut") in ("start", "both"):
        checks.append(
            f"The video opens on {opening['ref']}, which starts mid-sentence where the "
            "transcript was split; find its start by ear."
        )
    closing = (segments[-1]["soundbites"] or [None])[-1]
    if closing and closing.get("cut") in ("end", "both"):
        checks.append(
            f"The video ends on {closing['ref']}, which stops mid-sentence where the "
            "transcript was split; find its end by ear."
        )
    return checks


def copy_texts(document: dict[str, Any]) -> list[str]:
    """Every piece of text the copy would publish."""
    texts = [hook["text"] for hook in document["hooks"]]
    texts += [hook.get("translation", "") for hook in document["hooks"]]
    for segment in document["script"]["segments"]:
        texts += [segment["subtitle"], segment["overlay_text"]]
    for caption in document["captions"]:
        texts += [caption["text"], caption["call_to_action"], caption.get("translation", "")]
    return [t for t in texts if t]


def screen_copy_checks(
    document: dict[str, Any],
    refs: dict[str, dict[str, Any]],
    organisation: dict[str, Any] | None,
) -> list[str]:
    """Clearly read on-screen text of two words or more that the copy repeats word for
    word, unless it is the organisation's name: a name caption would name a person."""
    published = " ".join(copy_texts(document)).casefold()
    forms = brand_forms(organisation)
    checks = []
    for ref, item in refs.items():
        shown = text(item.get("text"))
        if item["source"] != "on_screen_text" or len(shown.split()) < 2:
            continue
        if any(hashtag_form(shown) in form for form in forms):
            continue
        if shown.casefold() in published:
            checks.append(
                f"The copy repeats on-screen text {ref} word for word; make sure it is "
                "not a person's name."
            )
    return checks


def evidence_text(item: dict[str, Any]) -> str:
    if item["source"] == "speech":
        span = f"speech {fmt_time(item['start_seconds'])}-{fmt_time(item['end_seconds'])}"
        return span + (f", sentence {item['sentence']}" if "sentence" in item else "")
    ranges = item.get("ranges") or []
    when = ", ".join(f"{fmt_time(start)}-{fmt_time(end)}" for start, end in ranges[:3])
    what = item["label"] if item["source"] == "visual" else f"on-screen text {item['ref']}"
    return what + (f" ({when})" if when else "")


def inputs_line(inputs: dict[str, Any]) -> str:
    return ", ".join(
        INPUT_NAMES[name] + ("" if record["complete"] else " (incomplete)")
        for name, record in inputs.items()
        if record and name in INPUT_NAMES
    )


def to_markdown(plan: dict[str, Any], document: dict[str, Any]) -> str:
    options = document["options"]
    language = options["translate"]
    translated = f", translated into {language}" if language else ""
    organisation = document["organisation"]
    lines = [
        f"# Copy: {plan['source']['name']}",
        "",
        f"- Made from: {inputs_line(document['inputs'])}",
        f"- Organisation: {organisation['name'] if organisation else 'not given (organisation.json)'}",
        f"- Model: {document['provider']['model']}",
        f"- Platforms: {names(options['platforms'])}",
        f"- Written in: {options['language']}{translated}",
        f"- Tone: {options['tone'] or 'not given'}",
        f"- Brief: {options['brief'] or 'not given'}",
        f"- Review status: {document['review_status']}",
        f"- Created: {document['created_at']}",
        "",
        "> Drafts made by a model from what was said, the visual tags and the text read "
        "on screen. People are never named. Check every claim and soundbite against the "
        "footage before publishing.",
    ]
    if document["missing"] or document["checks"]:
        lines.extend(["", "## Needs attention", ""])
        lines.extend(f"- {item}" for item in document["missing"] + document["checks"])
    if document["review_notes"]:
        lines.extend(["", "## Notes from the model", ""])
        lines.extend(f"- {note}" for note in document["review_notes"])

    lines.extend(["", "## Hooks", ""])
    for number, hook in enumerate(document["hooks"], 1):
        cited = "; ".join(evidence_text(e) for e in hook["evidence"])
        lines.append(f"{number}. {hook['text']} *({hook['style']}; {cited})*")
        if hook.get("translation"):
            lines.append(f"   - {language}: {hook['translation']}")
    if not document["hooks"]:
        lines.append("_None._")

    script = document["script"]
    lines.extend(["", f"## Script: {script['title'] or 'untitled'}"])
    for number, segment in enumerate(script["segments"], 1):
        lines.extend(["", f"### {number}. {segment['purpose']}", ""])
        for bite in segment["soundbites"]:
            cut = {"start": " (starts mid-sentence)", "end": " (stops mid-sentence)",
                   "both": " (a fragment)"}.get(bite.get("cut", ""), "")  # fmt: skip
            lines.append(
                f'- Soundbite ({evidence_text(bite)}){cut}: "{bite.get("text", "")}"'
            )
        if segment["subtitle"]:
            lines.append(f"- Subtitle: {segment['subtitle']}")
        if segment["broll"]:
            broll = "; ".join(evidence_text(b) for b in segment["broll"])
            lines.append(f"- B-roll: {broll}")
        if segment["overlay_text"]:
            lines.append(f"- On-screen text: {segment['overlay_text']}")
        if segment["note"]:
            lines.append(f"- Note: {segment['note']}")
    if not script["segments"]:
        lines.extend(["", "_None._"])

    lines.extend(["", "## Captions"])
    for caption in document["captions"]:
        lines.extend(["", f"### {PLATFORMS[caption['platform']][0]}", "", caption["text"]])
        if caption["call_to_action"]:
            lines.extend(["", f"Call to action: {caption['call_to_action']}"])
        if caption.get("translation"):
            lines.extend(["", f"**{language}:**", "", caption["translation"]])
    if not document["captions"]:
        lines.extend(["", "_None._"])

    lines.extend(["", "## Hashtags", ""])
    for cluster in HASHTAG_CLUSTERS:
        tags = " ".join(f"#{tag}" for tag in document["hashtags"][cluster])
        lines.append(f"- {cluster.capitalize()}: {tags or '_none_'}")
    return "\n".join(lines) + "\n"


def finalize(job_dir: Path, keep_work: bool = False) -> dict[str, Any]:
    plan = json.loads((job_dir / "plan.json").read_text(encoding="utf-8"))
    answer_file = job_dir / "results" / "answer.json"
    if not answer_file.is_file():
        fail("no answer found; nothing to save (the work folder was kept)")
    result = json.loads(answer_file.read_text(encoding="utf-8"))
    answer, refs, options = result["answer"], plan["refs"], plan["options"]
    organisation = plan.get("organisation")
    translate = bool(options.get("translate"))
    usage = result.get("usage") or {}

    dropped_hooks: list[dict[str, Any]] = []
    hooks = clean_hooks(answer.get("hooks"), refs, translate, dropped_hooks)
    script = clean_script(answer.get("script"), refs)
    dropped_segments = script.pop("segments_dropped")
    captions = clean_captions(answer.get("captions"), refs, options["platforms"], translate)
    hashtags = clean_hashtags(answer.get("hashtags"))
    has_speech = any(ref["source"] == "speech" for ref in refs.values())
    missing = missing_parts(hooks, script, captions, options, has_speech)
    # Answered hooks and segments not kept: no footage that was sent, or a repeat. The
    # references they had, as written, show why.
    dropped = {
        "hooks": len(answer.get("hooks") or []) - len(hooks),
        "segments": len(dropped_segments),
        "for_their_references": dropped_hooks + dropped_segments,
    }
    notes = [note for note in (text(n) for n in answer.get("review_notes") or []) if note]
    status = "incomplete" if missing else "complete"

    output_dir = Path(plan["output_dir"])
    files = ["copy.md", "copy.json", "metadata.json"]
    archived = archive_previous(output_dir, "copy.json", files, plan.get("replaces"))
    document = {
        "version": 1,
        "processor": plan["processor"],
        "complete": not missing,
        # Drafts for a person to approve and edit; never to be published as they are.
        "review_status": "draft",
        "source": plan["source"],
        # When each input was made; prepare compares them to notice a newer one.
        "inputs": plan["inputs"],
        "organisation": organisation,
        "options": options,
        "provider": {"name": "openai", "model": options["model"]},
        "usage": {
            "requests": 1,
            "input_tokens": int(usage.get("input_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or 0),
        },
        "estimated_input_tokens": plan["estimated_input_tokens"],
        "missing": missing,
        "checks": [],
        "review_notes": notes[:MAX_NOTES],
        "dropped": dropped,
        "hooks": hooks,
        "script": script,
        "captions": captions,
        "hashtags": hashtags,
        "created_at": now_iso(),
    }
    document["checks"] = (
        caption_checks(captions)
        + brand_checks(hashtags["brand"], organisation, plan.get("screen_texts") or [])
        + cut_checks(script["segments"])
        + screen_copy_checks(document, refs, organisation)
    )
    write_json(output_dir / "copy.json", document)
    write_text(output_dir / "copy.md", to_markdown(plan, document))
    # The context, refs and screen texts hold the transcript and the frames' text, which
    # already have their own results.
    kept = {k: v for k, v in plan.items() if k not in ("context", "refs", "screen_texts")}
    write_json(output_dir / "metadata.json", result_metadata(kept, status))
    if not keep_work:
        shutil.rmtree(job_dir)

    return {
        "status": status,
        "output_dir": str(output_dir),
        "files": files,
        "previous_result": str(archived) if archived else None,
        "hooks": len(hooks),
        "script_segments": len(script["segments"]),
        "captions": [caption["platform"] for caption in captions],
        "hashtags": {c: len(hashtags[c]) for c in HASHTAG_CLUSTERS},
        "translation": options.get("translate"),
        "dropped": {k: v for k, v in dropped.items() if k != "for_their_references"},
        "missing": missing,
        "checks": document["checks"],
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
