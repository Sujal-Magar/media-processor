"""Tag wording and tag libraries shared by the tagging processors.

Every tag is stored in English, lowercase, with its words joined by hyphens
("speaking-to-camera", "subclass-500"). A processor's library is rebuilt from its
earlier results on every run, so it never drifts from what is on disk.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


def clean_label(label: str) -> str:
    """A tag as stored: lowercase, each run of spaces, underscores and hyphens made one
    hyphen, none at either end. Results saved before hyphens ("speaking to camera")
    read the same as new ones."""
    return "-".join(re.split(r"[\s_-]+", label.strip().lower())).strip("-")


def tag_library(
    folder: Path, result_file: str, exclude: Path | None, limit: int
) -> list[dict]:
    """The vocabulary of one processor's results: each {label, category} in the `tags`
    of folder/*/<result_file>, with how often it was used (its frames, or 1 for a tag
    without frames), most used first.

    `exclude` is the source file's own result folder: when redoing it with --force, its
    old tags must not count as the library, or nothing would ever be marked new.
    """
    uses: Counter[tuple[str, str]] = Counter()
    for path in folder.glob(f"*/{result_file}"):
        if path.parent == exclude:
            continue
        try:
            tags = json.loads(path.read_text(encoding="utf-8")).get("tags", [])
        except (OSError, ValueError):
            continue
        for tag in tags:
            label = clean_label(str(tag.get("label") or ""))
            if label and tag.get("category"):
                uses[(label, tag["category"])] += len(tag.get("frames") or [0])
    return [
        {"label": label, "category": category, "uses": count}
        for (label, category), count in uses.most_common(limit)
    ]
