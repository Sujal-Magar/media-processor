"""The organisation this folder belongs to (one folder is one organisation's library),
from organisation.json at the repo root: its name as written, other names it goes by,
its website, approved brand hashtags, a short note and the forms speech-to-text writes
for its name (`heard_as`). Speech-to-text and frame reading can get a name wrong
("Tilicho" heard as a better-known place); this file is the spelling the processors
trust. Optional; the file is client data and stays out of git.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from lib.workspace import ROOT, fail

ORGANISATION_FILE = ROOT / "organisation.json"
MAX_NOTE_CHARS = 300


def hashtag_form(value: str) -> str:
    """How a name or text reads as a hashtag: "Tilicho Consulting" -> tilichoconsulting.
    Spaces, punctuation and symbols go (a hashtag breaks at them), except _; letters,
    digits and the vowel signs of any script stay."""
    return "".join(
        c for c in value if c == "_" or unicodedata.category(c)[0] not in "PSZC"
    ).lower()


def strings(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key) or []
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        fail(f"{ORGANISATION_FILE.name}: {key} must be a list of strings")
    return [v.strip() for v in value if v.strip()]


def load_organisation(path: Path = ORGANISATION_FILE) -> dict[str, Any] | None:
    """The organisation's details, or None when the file does not exist."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        fail(f"{path.name} is not valid JSON: {exc}")
    if not isinstance(data, dict) or not str(data.get("name") or "").strip():
        fail(f"{path.name} needs at least a name")
    note = re.sub(r"\s+", " ", str(data.get("note") or "")).strip()
    if len(note) > MAX_NOTE_CHARS:
        fail(f"{path.name}: note has {len(note)} characters; at most {MAX_NOTE_CHARS}")
    organisation = {
        "name": data["name"].strip(),
        "other_names": strings(data, "other_names"),
        "website": str(data.get("website") or "").strip(),
        "hashtags": [hashtag_form(tag) for tag in strings(data, "hashtags")],
        "note": note,
    }
    # Only when set, so results saved before the field existed are not taken as outdated.
    if heard_as := strings(data, "heard_as"):
        organisation["heard_as"] = heard_as
    return organisation


def brand_forms(organisation: dict[str, Any] | None) -> list[str]:
    """The organisation's names, website and hashtags in hashtag form."""
    if not organisation:
        return []
    website = re.sub(r"^(https?://)?(www\.)?", "", organisation["website"]).split(".")[0]
    names = [organisation["name"], *organisation["other_names"], website]
    forms = [hashtag_form(name) for name in names] + organisation["hashtags"]
    return [form for form in dict.fromkeys(forms) if form]


def organisation_section(organisation: dict[str, Any] | None) -> str:
    """The organisation's details as text for a model; empty without them."""
    if not organisation:
        return ""
    lines = [
        "ORGANISATION (from the organisation itself: spell its name exactly like this, "
        "even where the speech or on-screen text has it differently)",
        f"Name: {organisation['name']}",
    ]
    if organisation["other_names"]:
        lines.append(f"Also called: {', '.join(organisation['other_names'])}")
    if organisation["website"]:
        lines.append(f"Website: {organisation['website']}")
    if organisation["hashtags"]:
        lines.append(f"Its hashtags: {', '.join(organisation['hashtags'])}")
    if organisation["note"]:
        lines.append(f"Note: {organisation['note']}")
    if organisation.get("heard_as"):
        lines.append(
            "Speech-to-text may write the name as: "
            f"{', '.join(organisation['heard_as'])} (which can also be a real word or place)"
        )
    return "\n".join(lines)
