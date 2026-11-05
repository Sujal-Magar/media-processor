"""Repo folders, file writing and small helpers shared by every processor.

Folder convention (``<processor>`` is e.g. ``transcribe``):

    input/                                   media files the user provides
    work/<processor>/<name>-<time>/          temporary files for one job
    output/<processor>/<name>-<hash8>/       results for one source file
        history/<time>/                      earlier results that --force replaced
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "input"
WORK = ROOT / "work"  # also the only folder MCP servers may read from
OUTPUT = ROOT / "output"


def fail(message: str) -> NoReturn:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fmt_time(seconds: float) -> str:
    total = round(seconds)
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def safe_name(source: Path) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", source.stem) or "source"


def output_dir_for(processor: str, source: Path, digest: str) -> Path:
    """Stable per source file, so a finished job can be recognised and not paid twice."""
    return OUTPUT / processor / f"{safe_name(source)}-{digest[:8]}"


def new_job_dir(processor: str, source: Path) -> Path:
    job_dir = (
        WORK
        / processor
        / f"{safe_name(source)}-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"
    )
    job_dir.mkdir(parents=True, mode=0o700)
    return job_dir


def is_job_dir(path: Path) -> bool:
    return WORK.resolve() in path.resolve().parents


def write_text(path: Path, text: str) -> None:
    """Write via a temporary file and rename, so a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def write_json(path: Path, data: Any) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def previous_created_at(result_file: Path) -> str | None:
    """`created_at` of an earlier result, which prepare records as `replaces` on --force."""
    try:
        return json.loads(result_file.read_text(encoding="utf-8")).get("created_at")
    except (OSError, ValueError):
        return None


def archive_previous(
    output_dir: Path, result_file: str, names: list[str], replaces: str | None
) -> Path | None:
    """Move the result a --force run replaces into <output_dir>/history/<its time>/.

    Only when `result_file` still has the `created_at` prepare saw, so a resumed or repeated
    finalize never archives twice. History is nested inside the result folder, so globs
    such as output/<processor>/*/tags.json never see it.
    """
    if not replaces or previous_created_at(output_dir / result_file) != replaces:
        return None
    stamp = re.sub(r"[^0-9T]", "", replaces.split("+")[0]).replace("T", "-")
    target = output_dir / "history" / stamp
    target.mkdir(parents=True, exist_ok=True)
    for name in names:
        if (output_dir / name).exists():
            os.replace(output_dir / name, target / name)
    return target


def result_metadata(plan: dict[str, Any], status: str) -> dict[str, Any]:
    """The job plan as saved next to a result: final status, and no paths into work/,
    which is deleted with the job."""
    work = str(WORK) + os.sep

    def clean(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: clean(item)
                for key, item in value.items()
                if not (isinstance(item, str) and item.startswith(work))
            }
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value

    return {**clean(plan), "status": status}


def dotenv_value(name: str) -> str | None:
    """Read one variable from the repo's .env file (simple KEY=value lines)."""
    env_file = ROOT / ".env"
    if not env_file.is_file():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        if key.strip() == name:
            return value.strip().strip("\"'") or None
    return None
