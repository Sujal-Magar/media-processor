"""Repo folders, file writing and small helpers shared by every processor.

Folder convention (``<processor>`` is e.g. ``transcribe``):

    input/                                   media files the user provides
    work/<processor>/<name>-<time>/          temporary files for one job
    output/<processor>/<name>-<hash8>/       results for one source file
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
    job_dir = WORK / processor / f"{safe_name(source)}-{datetime.now():%Y%m%d-%H%M%S}"
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
